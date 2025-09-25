import os
import re
import time
import random
import difflib
import traceback
import aiohttp
import json
from pathlib import Path
from core.handle.sendAudioHandle import send_stt_message
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from core.utils.dialogue import Message
from core.providers.tts.dto.dto import TTSMessageDTO, SentenceType, ContentType

TAG = __name__

MUSIC_CACHE = {}

play_music_function_desc = {
    "type": "function",
    "function": {
        "name": "play_music",
        "description": "播放音乐、歌曲、白噪音、环境音的功能。支持播放音乐歌曲和各种白噪音（如雨声、海浪声、森林声等自然环境音）。当用户要求播放任何音频内容时使用此功能。",
        "parameters": {
            "type": "object",
            "properties": {
                "song_name": {
                    "type": "string",
                    "description": "音频内容名称。可以是歌曲名、白噪音类型或'random'。示例: ```用户:播放两只老虎\n参数：两只老虎``` ```用户:播放音乐\n参数：random``` ```用户:播放白噪音\n参数：白噪音``` ```用户:播放雨声\n参数：雨声``` ```用户:来点环境音\n参数：环境音```",
                }
            },
            "required": ["song_name"],
        },
    },
}


@register_function("play_music", play_music_function_desc, ToolType.SYSTEM_CTL)
def play_music(conn, song_name: str):
    try:
        music_intent = (
            f"播放音乐 {song_name}" if song_name != "random" else "随机播放音乐"
        )

        # 检查事件循环状态
        if not conn.loop.is_running():
            conn.logger.bind(tag=TAG).error("事件循环未运行，无法提交任务")
            return ActionResponse(
                action=Action.RESPONSE, result="系统繁忙", response="请稍后再试"
            )

        # 提交异步任务
        task = conn.loop.create_task(
            handle_music_command(conn, music_intent)  # 封装异步逻辑
        )

        # 非阻塞回调处理
        def handle_done(f):
            try:
                f.result()  # 可在此处理成功逻辑
                conn.logger.bind(tag=TAG).info("播放完成")
            except Exception as e:
                conn.logger.bind(tag=TAG).error(f"播放失败: {e}")

        task.add_done_callback(handle_done)

        return ActionResponse(
            action=Action.NONE, result="指令已接收", response="正在为您播放音乐"
        )
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"处理音乐意图错误: {e}")
        return ActionResponse(
            action=Action.RESPONSE, result=str(e), response="播放音乐时出错了"
        )


def _extract_song_name(text):
    """从用户输入中提取歌名"""
    for keyword in ["播放音乐"]:
        if keyword in text:
            parts = text.split(keyword)
            if len(parts) > 1:
                return parts[1].strip()
    return None


def _is_white_noise(song_name):
    """判断歌曲名称是否为白噪音"""
    if not song_name or song_name == "random":
        return False

    white_noise_keywords = [
        "白噪音", "白噪声", "white noise",
        "雨声", "海浪声", "森林声", "风声", "鸟鸣",
        "环境音", "自然音", "放松音乐", "助眠音乐",
        "大自然", "流水声", "虫鸣", "雷声", "火焰声"
    ]

    song_name_lower = song_name.lower()
    for keyword in white_noise_keywords:
        if keyword in song_name_lower:
            return True
    return False


def _find_best_match(potential_song, music_files):
    """查找最匹配的歌曲"""
    best_match = None
    highest_ratio = 0

    for music_file in music_files:
        song_name = os.path.splitext(music_file)[0]
        ratio = difflib.SequenceMatcher(None, potential_song, song_name).ratio()
        if ratio > highest_ratio and ratio > 0.4:
            highest_ratio = ratio
            best_match = music_file
    return best_match


def get_music_files(music_dir, music_ext):
    music_dir = Path(music_dir)
    music_files = []
    music_file_names = []
    for file in music_dir.rglob("*"):
        # 判断是否是文件
        if file.is_file():
            # 获取文件扩展名
            ext = file.suffix.lower()
            # 判断扩展名是否在列表中
            if ext in music_ext:
                # 添加相对路径
                music_files.append(str(file.relative_to(music_dir)))
                music_file_names.append(
                    os.path.splitext(str(file.relative_to(music_dir)))[0]
                )
    return music_files, music_file_names


def initialize_music_handler(conn):
    global MUSIC_CACHE
    # 强制重新初始化配置，确保读取最新的配置
    if True:  # 强制重新初始化配置
        if "play_music" in conn.config["plugins"]:
            MUSIC_CACHE["music_config"] = conn.config["plugins"]["play_music"]
            MUSIC_CACHE["music_dir"] = os.path.abspath(
                MUSIC_CACHE["music_config"].get("music_dir", "./music")  # 默认路径修改
            )
            MUSIC_CACHE["music_ext"] = MUSIC_CACHE["music_config"].get(
                "music_ext", (".mp3", ".wav", ".p3")
            )
            MUSIC_CACHE["refresh_time"] = MUSIC_CACHE["music_config"].get(
                "refresh_time", 60
            )
        else:
            MUSIC_CACHE["music_dir"] = os.path.abspath("./music")
            MUSIC_CACHE["music_ext"] = (".mp3", ".wav", ".p3")
            MUSIC_CACHE["refresh_time"] = 60

        # 设置白噪音API配置
        # 尝试多种配置源
        base_url = None

        # 调试日志：打印配置内容
        conn.logger.bind(tag=TAG).info(f"调试: conn.config keys: {list(conn.config.keys())}")
        if "api" in conn.config:
            conn.logger.bind(tag=TAG).info(f"调试: api配置存在，内容: {conn.config['api']}")
        else:
            conn.logger.bind(tag=TAG).info("调试: api配置不存在")

        if "stories-api" in conn.config:
            conn.logger.bind(tag=TAG).info(f"调试: stories-api配置存在，内容: {conn.config['stories-api']}")
        else:
            conn.logger.bind(tag=TAG).info("调试: stories-api配置不存在")

        # 方法1: 从api配置读取
        if "api" in conn.config and "base_url" in conn.config["api"]:
            base_url = conn.config["api"]["base_url"]
            conn.logger.bind(tag=TAG).info(f"从api.base_url读取到: {base_url}")

        # 方法2: 从stories-api配置读取（作为备选）
        elif "stories-api" in conn.config and "url" in conn.config["stories-api"]:
            base_url = conn.config["stories-api"]["url"]
            conn.logger.bind(tag=TAG).info(f"从stories-api.url读取到: {base_url}")

        # 方法3: 使用默认URL
        else:
            base_url = "http://192.168.124.24:9001"
            conn.logger.bind(tag=TAG).info(f"使用默认base_url: {base_url}")

        if base_url:
            MUSIC_CACHE["white_noise_api_url"] = f"{base_url}/api/v1/public/white-noise/random/"
            conn.logger.bind(tag=TAG).info(f"白噪音API URL设置为: {MUSIC_CACHE['white_noise_api_url']}")
        else:
            conn.logger.bind(tag=TAG).error("无法确定API base_url，白噪音功能将无法使用")
            MUSIC_CACHE["white_noise_api_url"] = None

        # 获取音乐文件列表
        MUSIC_CACHE["music_files"], MUSIC_CACHE["music_file_names"] = get_music_files(
            MUSIC_CACHE["music_dir"], MUSIC_CACHE["music_ext"]
        )
        MUSIC_CACHE["scan_time"] = time.time()
    return MUSIC_CACHE


async def _get_white_noise_from_api(conn):
    """从API获取白噪音数据"""
    global MUSIC_CACHE

    if not conn.device_id:
        conn.logger.bind(tag=TAG).warning("设备ID为空，无法获取白噪音")
        return None

    api_url = MUSIC_CACHE.get("white_noise_api_url")
    if not api_url:
        conn.logger.bind(tag=TAG).error("白噪音API URL未配置")
        return None

    try:
        params = {"mac_address": conn.device_id}

        conn.logger.bind(tag=TAG).info(f"请求白噪音API: {api_url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, params=params) as response:
                if response.status == 200:
                    response_data = await response.json()
                    conn.logger.bind(tag=TAG).info(f"API原始响应: {response_data}")

                    # 检查API响应格式并提取数据
                    if response_data.get("success") and "data" in response_data:
                        white_noise_data = response_data["data"]
                        conn.logger.bind(tag=TAG).info(f"成功获取白噪音数据: {white_noise_data.get('title', '未知')}")
                        return white_noise_data
                    else:
                        conn.logger.bind(tag=TAG).error(f"API响应格式错误: {response_data}")
                        return None
                else:
                    conn.logger.bind(tag=TAG).error(f"API请求失败，状态码: {response.status}")
                    return None

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"获取白噪音API数据失败: {str(e)}")
        return None


async def _download_white_noise_audio(conn, audio_url):
    """下载白噪音音频文件到临时位置"""
    try:
        import tempfile

        # 创建临时文件
        temp_dir = tempfile.mkdtemp()
        temp_file_path = os.path.join(temp_dir, "white_noise.mp3")

        conn.logger.bind(tag=TAG).info(f"下载白噪音音频: {audio_url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(audio_url) as response:
                if response.status == 200:
                    with open(temp_file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)

                    conn.logger.bind(tag=TAG).info(f"白噪音下载完成: {temp_file_path}")
                    return temp_file_path
                else:
                    conn.logger.bind(tag=TAG).error(f"下载白噪音失败，状态码: {response.status}")
                    return None

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"下载白噪音音频失败: {str(e)}")
        return None


async def handle_music_command(conn, text):
    initialize_music_handler(conn)
    global MUSIC_CACHE

    """处理音乐播放指令"""
    clean_text = re.sub(r"[^\w\s]", "", text).strip()
    conn.logger.bind(tag=TAG).debug(f"检查是否是音乐命令: {clean_text}")

    # 提取歌曲名称
    potential_song = _extract_song_name(clean_text)

    # 检查是否是白噪音请求
    if potential_song and _is_white_noise(potential_song):
        conn.logger.bind(tag=TAG).info(f"检测到白噪音请求: {potential_song}")
        await play_white_noise_from_api(conn, potential_song)
        return True

    # 尝试匹配具体歌名
    if os.path.exists(MUSIC_CACHE["music_dir"]):
        if time.time() - MUSIC_CACHE["scan_time"] > MUSIC_CACHE["refresh_time"]:
            # 刷新音乐文件列表
            MUSIC_CACHE["music_files"], MUSIC_CACHE["music_file_names"] = (
                get_music_files(MUSIC_CACHE["music_dir"], MUSIC_CACHE["music_ext"])
            )
            MUSIC_CACHE["scan_time"] = time.time()

        if potential_song:
            best_match = _find_best_match(potential_song, MUSIC_CACHE["music_files"])
            if best_match:
                conn.logger.bind(tag=TAG).info(f"找到最匹配的歌曲: {best_match}")
                await play_local_music(conn, specific_file=best_match)
                return True
    # 检查是否是通用播放音乐命令
    await play_local_music(conn)
    return True


async def play_white_noise_from_api(conn, noise_type):
    """从API播放白噪音"""
    try:
        # 获取白噪音数据
        white_noise_data = await _get_white_noise_from_api(conn)
        if not white_noise_data:
            conn.logger.bind(tag=TAG).error("无法获取白噪音数据")
            return

        # 下载音频文件
        audio_url = white_noise_data.get("audio_url")
        if not audio_url:
            conn.logger.bind(tag=TAG).error("白噪音数据中缺少音频URL")
            return

        temp_file_path = await _download_white_noise_audio(conn, audio_url)
        if not temp_file_path:
            conn.logger.bind(tag=TAG).error("下载白噪音音频失败")
            return

        # 获取白噪音标题
        noise_title = white_noise_data.get("title", "舒缓白噪音")
        text = _get_random_white_noise_prompt(noise_title)

        conn.logger.bind(tag=TAG).info(f"准备播放白噪音，sentence_id: {conn.sentence_id}, intent_type: {conn.intent_type}")
        conn.logger.bind(tag=TAG).info(f"播放提示语: {text}")

        await send_stt_message(conn, text)
        conn.dialogue.put(Message(role="assistant", content=text))

        # 适配不同的 intent_type，确保TTS队列正确处理
        # function_call 模式也需要 ACTION 消息来正确启动和结束TTS处理
        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=conn.sentence_id,
                sentence_type=SentenceType.FIRST,
                content_type=ContentType.ACTION,
            )
        )
        conn.logger.bind(tag=TAG).info("已添加TTS FIRST ACTION到队列")

        tts_text_msg = TTSMessageDTO(
            sentence_id=conn.sentence_id,
            sentence_type=SentenceType.MIDDLE,
            content_type=ContentType.TEXT,
            content_detail=text,
        )
        conn.tts.tts_text_queue.put(tts_text_msg)
        conn.logger.bind(tag=TAG).info(f"已添加TTS文本到队列: {text}")

        tts_file_msg = TTSMessageDTO(
            sentence_id=conn.sentence_id,
            sentence_type=SentenceType.MIDDLE,
            content_type=ContentType.FILE,
            content_file=temp_file_path,
        )
        conn.tts.tts_text_queue.put(tts_file_msg)
        conn.logger.bind(tag=TAG).info(f"已添加TTS音频文件到队列: {temp_file_path}")

        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=conn.sentence_id,
                sentence_type=SentenceType.LAST,
                content_type=ContentType.ACTION,
            )
        )
        conn.logger.bind(tag=TAG).info("已添加TTS LAST ACTION到队列")

        conn.logger.bind(tag=TAG).info(f"白噪音播放完成: {noise_title}")

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"播放白噪音失败: {str(e)}")
        conn.logger.bind(tag=TAG).error(f"详细错误: {traceback.format_exc()}")


def _get_random_white_noise_prompt(noise_title):
    """生成白噪音播放引导语"""
    prompts = [
        f"正在为您播放白噪音，{noise_title}",
        f"请享受放松的环境音，{noise_title}",
        f"即将为您播放，{noise_title}",
        f"为您带来舒缓的，{noise_title}",
        f"让我们聆听，{noise_title}",
        f"接下来请欣赏，{noise_title}",
        f"为您献上，{noise_title}",
    ]
    return random.choice(prompts)


def _get_random_play_prompt(song_name):
    """生成随机播放引导语"""
    # 移除文件扩展名
    clean_name = os.path.splitext(song_name)[0]
    prompts = [
        f"正在为您播放，《{clean_name}》",
        f"请欣赏歌曲，《{clean_name}》",
        f"即将为您播放，《{clean_name}》",
        f"现在为您带来，《{clean_name}》",
        f"让我们一起聆听，《{clean_name}》",
        f"接下来请欣赏，《{clean_name}》",
        f"此刻为您献上，《{clean_name}》",
    ]
    # 直接使用random.choice，不设置seed
    return random.choice(prompts)


async def play_local_music(conn, specific_file=None):
    global MUSIC_CACHE
    """播放本地音乐文件"""
    try:
        if not os.path.exists(MUSIC_CACHE["music_dir"]):
            conn.logger.bind(tag=TAG).error(
                f"音乐目录不存在: " + MUSIC_CACHE["music_dir"]
            )
            return

        # 确保路径正确性
        if specific_file:
            selected_music = specific_file
            music_path = os.path.join(MUSIC_CACHE["music_dir"], specific_file)
        else:
            if not MUSIC_CACHE["music_files"]:
                conn.logger.bind(tag=TAG).error("未找到MP3音乐文件")
                return
            selected_music = random.choice(MUSIC_CACHE["music_files"])
            music_path = os.path.join(MUSIC_CACHE["music_dir"], selected_music)

        if not os.path.exists(music_path):
            conn.logger.bind(tag=TAG).error(f"选定的音乐文件不存在: {music_path}")
            return
        text = _get_random_play_prompt(selected_music)
        await send_stt_message(conn, text)
        conn.dialogue.put(Message(role="assistant", content=text))

        if conn.intent_type == "intent_llm":
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
                content_file=music_path,
            )
        )
        if conn.intent_type == "intent_llm":
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.LAST,
                    content_type=ContentType.ACTION,
                )
            )

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"播放音乐失败: {str(e)}")
        conn.logger.bind(tag=TAG).error(f"详细错误: {traceback.format_exc()}")
