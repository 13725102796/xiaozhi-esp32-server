from config.logger import setup_logging
import os
import re
import time
import random
import asyncio
import traceback
import json
import tempfile
import requests
from pathlib import Path
from core.utils import p3
from core.handle.sendAudioHandle import send_stt_message
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from core.utils.dialogue import Message
from core.providers.tts.dto.dto import TTSMessageDTO, SentenceType, ContentType

TAG = __name__

STORY_CONFIG = {}

play_story_function_desc = {
    "type": "function",
    "function": {
        "name": "play_story",
        "description": "讲故事、播放故事的方法。",
        "parameters": {
            "type": "object",
            "properties": {
                "story_name": {
                    "type": "string",
                    "description": "故事名称，如果用户没有指定具体故事名则为'random', 明确指定的时返回故事名字 示例: ```用户:讲下王子与公主的故事\n参数：王子与公主``` ```用户:讲个故事 \n参数：random ```",
                }
            },
            "required": ["story_name"],
        },
    },
}


@register_function("play_story", play_story_function_desc, ToolType.SYSTEM_CTL)
def play_story(conn, story_name: str):
    try:
        story_intent = (
            f"讲故事 {story_name}" if story_name != "random" else "随机播放故事"
        )

        # 检查事件循环状态
        if not conn.loop.is_running():
            conn.logger.bind(tag=TAG).error("事件循环未运行，无法提交任务")
            return ActionResponse(
                action=Action.RESPONSE, result="系统繁忙", response="请稍后再试"
            )

        # 提交异步任务
        future = asyncio.run_coroutine_threadsafe(
            handle_story_command(conn, story_intent), conn.loop
        )

        # 非阻塞回调处理
        def handle_done(f):
            try:
                f.result()  # 可在此处理成功逻辑
                conn.logger.bind(tag=TAG).info("播放完成")
            except Exception as e:
                conn.logger.bind(tag=TAG).error(f"播放失败: {e}")

        future.add_done_callback(handle_done)

        return ActionResponse(
            action=Action.NONE, result="指令已接收", response="正在为您播放故事"
        )
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"处理故事意图错误: {e}")
        return ActionResponse(
            action=Action.RESPONSE, result=str(e), response="播放故事时出错了"
        )


def initialize_story_config(conn):
    global STORY_CONFIG
    if not STORY_CONFIG:
        # 获取基础API URL
        base_url = conn.config.get("api", {}).get("base_url", "https://qy-toy.airlabs.art")
        default_story_url = f"{base_url}/api/v1/public/random-story-audio/"

        if "play_story" in conn.config["plugins"]:
            STORY_CONFIG["remote_api_url"] = conn.config["plugins"]["play_story"].get(
                "remote_api_url", default_story_url
            )
            STORY_CONFIG["enable_remote_story"] = conn.config["plugins"]["play_story"].get(
                "enable_remote_story", True
            )
        else:
            # 默认远程故事API配置
            STORY_CONFIG["remote_api_url"] = default_story_url
            STORY_CONFIG["enable_remote_story"] = True

        # 输出日志，便于调试
        conn.logger.bind(tag=TAG).info(f"远程故事API设置为: {STORY_CONFIG['remote_api_url']}")
        conn.logger.bind(tag=TAG).info(f"远程故事功能: {'启用' if STORY_CONFIG['enable_remote_story'] else '禁用'}")

    return STORY_CONFIG


async def get_remote_story(conn):
    """从远程API获取随机故事"""
    global STORY_CONFIG
    
    if not STORY_CONFIG.get("enable_remote_story", True):
        conn.logger.bind(tag=TAG).info("远程故事功能已禁用")
        return None
    
    if not conn.device_id:
        conn.logger.bind(tag=TAG).warning("设备ID为空，无法获取远程故事")
        return None
    
    try:
        # 构建API请求URL
        api_url = STORY_CONFIG["remote_api_url"]
        params = {"mac_address": conn.device_id}
        
        conn.logger.bind(tag=TAG).info(f"请求远程故事API: {api_url}?mac_address={conn.device_id}")
        
        # 发送HTTP请求
        response = requests.get(api_url, params=params, timeout=30)
        response.raise_for_status()
        
        # 解析响应
        data = response.json()
        if not data.get("success", False):
            conn.logger.bind(tag=TAG).error(f"远程API返回错误: {data.get('message', '未知错误')}")
            return None
        
        story_data = data.get("data", {})
        if not story_data:
            conn.logger.bind(tag=TAG).error("远程API返回的故事数据为空")
            return None
        
        conn.logger.bind(tag=TAG).info(f"成功获取远程故事: {story_data.get('title', '未知标题')}")
        return story_data
        
    except requests.exceptions.RequestException as e:
        conn.logger.bind(tag=TAG).error(f"请求远程故事API失败: {str(e)}")
        return None
    except json.JSONDecodeError as e:
        conn.logger.bind(tag=TAG).error(f"解析远程API响应失败: {str(e)}")
        return None
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"获取远程故事时发生未知错误: {str(e)}")
        conn.logger.bind(tag=TAG).debug(f"详细错误: {traceback.format_exc()}")
        return None


async def download_remote_story(conn, story_data):
    """下载远程故事到临时文件"""
    try:
        audio_url = story_data.get("audio_url")
        if not audio_url:
            conn.logger.bind(tag=TAG).error("故事数据中没有音频URL")
            return None
        
        # 创建临时文件
        temp_dir = tempfile.gettempdir()
        story_id = story_data.get("id", "unknown")
        temp_filename = f"remote_story_{story_id}_{int(time.time())}.mp3"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        conn.logger.bind(tag=TAG).info(f"开始下载远程故事到: {temp_path}")
        
        # 下载音频文件
        response = requests.get(audio_url, stream=True, timeout=60)
        response.raise_for_status()
        
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # 验证文件大小
        file_size = os.path.getsize(temp_path)
        if file_size == 0:
            conn.logger.bind(tag=TAG).error("下载的故事文件大小为0")
            os.remove(temp_path)
            return None
        
        conn.logger.bind(tag=TAG).info(f"远程故事下载完成: {temp_path}, 大小: {file_size} 字节")
        return temp_path
        
    except requests.exceptions.RequestException as e:
        conn.logger.bind(tag=TAG).error(f"下载远程故事失败: {str(e)}")
        return None
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"下载远程故事时发生未知错误: {str(e)}")
        conn.logger.bind(tag=TAG).debug(f"详细错误: {traceback.format_exc()}")
        return None


async def cleanup_temp_story_file(file_path):
    """清理临时故事文件"""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            # 使用全局logger记录清理信息
            import logging
            logger = logging.getLogger(TAG)
            logger.info(f"已清理临时故事文件: {file_path}")
    except Exception as e:
        import logging
        logger = logging.getLogger(TAG)
        logger.warning(f"清理临时故事文件失败: {str(e)}")


async def handle_story_command(conn, text="播放随机故事"):
    conn.logger.bind(tag=TAG).info(f"play story on device {conn.device_id}")
    initialize_story_config(conn)
    
    """处理故事播放指令"""
    await play_remote_story(conn)
    return True


def _get_random_play_prompt(story_title):
    """生成随机播放引导语"""
    prompts = [
        f"正在为您播放，{story_title}",
        f"请欣赏故事，{story_title}",
        f"即将为您播放，{story_title}",
        f"为您带来，{story_title}",
        f"让我们聆听，{story_title}",
        f"接下来请欣赏，{story_title}",
        f"为您献上，{story_title}",
    ]
    return random.choice(prompts)


async def play_remote_story(conn):
    """播放远程故事"""
    temp_file_path = None
    
    try:
        # 获取远程故事
        remote_story_data = await get_remote_story(conn)
        
        if not remote_story_data:
            conn.logger.bind(tag=TAG).error("无法获取远程故事")
            return
        
        # 下载远程故事到临时文件
        temp_file_path = await download_remote_story(conn, remote_story_data)
        if not temp_file_path:
            conn.logger.bind(tag=TAG).error("下载远程故事失败")
            return
        
        story_title = remote_story_data.get("title", "精彩故事")
        conn.logger.bind(tag=TAG).info(f"成功获取远程故事: {story_title}")
        
        # 使用故事标题生成播放提示语
        text = _get_random_play_prompt(story_title)
        await send_stt_message(conn, text)
        conn.dialogue.put(Message(role="assistant", content=text))

        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=conn.sentence_id,
                sentence_type=SentenceType.FIRST,
                content_type=ContentType.ACTION,
            )
        )
        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=conn.sentence_id,
                sentence_type=SentenceType.MIDDLE,
                content_type=ContentType.TEXT,
                content_detail=text,
            )
        )
        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=conn.sentence_id,
                sentence_type=SentenceType.MIDDLE,
                content_type=ContentType.FILE,
                content_file=temp_file_path,
            )
        )
        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=conn.sentence_id,
                sentence_type=SentenceType.LAST,
                content_type=ContentType.ACTION,
            )
        )
        
        # 输出临时文件路径，方便调试
        conn.logger.bind(tag=TAG).info(f"远程故事临时文件路径: {temp_file_path}")
        conn.logger.bind(tag=TAG).info(f"注意：临时文件不会自动清理，请手动删除")

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"播放故事失败: {str(e)}")
        conn.logger.bind(tag=TAG).error(f"详细错误: {traceback.format_exc()}")
    finally:
        # 如果存在临时文件且播放失败，暂时不清理（方便调试）
        if temp_file_path and os.path.exists(temp_file_path):
            conn.logger.bind(tag=TAG).info(f"临时文件保留: {temp_file_path}")
            conn.logger.bind(tag=TAG).info(f"注意：临时文件不会自动清理，请手动删除")
