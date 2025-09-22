import json
import random
from typing import Dict, Any

from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from core.api.story_handler import StoryHandler
from config.manage_api_client import get_device_stories

TAG = __name__

class StoryTextMessageHandler(TextMessageHandler):
    """Story消息处理器"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.STORY

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        """处理story消息"""
        try:
            # 记录接收到的story消息
            conn.logger.bind(tag=TAG).info(f"处理story消息: {msg_json}")
            
            # 获取设备ID
            device_id = conn.device_id
            if not device_id:
                conn.logger.bind(tag=TAG).error("设备ID不存在，无法播放故事")
                await conn.websocket.send(
                    json.dumps(
                        {
                            "type": "story",
                            "status": "error",
                            "message": "设备ID不存在",
                        }
                    )
                )
                return

            # 获取故事相关参数
            # 默认故事信息（作为兜底）
            default_story_name = "侦探与龙：宝石的秘密"
            default_audio_url = "https://toy-storage.airlabs.art/audio/volcano_tts/permanent/20250904/story_7369183431743246336_cfd71314.mp3"
            default_story_title = "侦探与龙：宝石的秘密"

            # 调用API获取设备故事信息
            conn.logger.bind(tag=TAG).info(f"开始调用API获取设备故事，device_id: {device_id}")
            stories_data = get_device_stories(device_id)
            conn.logger.bind(tag=TAG).info(f"API返回的stories_data: {stories_data}")

            story_name = default_story_name
            audio_url = default_audio_url
            story_title = default_story_title

            if stories_data:
                # 从API响应中提取故事信息
                story_info = None

                # 检查API返回格式：{"success": true, "data": {"stories": [...]}}
                if isinstance(stories_data, dict) and stories_data.get("success") and "data" in stories_data:
                    story_list = stories_data["data"].get("stories", [])
                    if len(story_list) > 0:
                        # 随机选择一个故事
                        story_info = random.choice(story_list)
                        conn.logger.bind(tag=TAG).info(f"从API获取到{len(story_list)}个故事，随机选择其中一个")
                # 兼容其他格式
                elif isinstance(stories_data, list) and len(stories_data) > 0:
                    story_info = random.choice(stories_data)
                elif isinstance(stories_data, dict) and 'stories' in stories_data:
                    story_list = stories_data['stories']
                    if len(story_list) > 0:
                        story_info = random.choice(story_list)

                if story_info:
                    story_name = story_info.get("title", default_story_name)
                    audio_url = story_info.get("audio_url", default_audio_url)
                    story_title = story_info.get("title", default_story_title)
                    conn.logger.bind(tag=TAG).info(f"使用API随机选择的故事: {story_title}")
                else:
                    conn.logger.bind(tag=TAG).warning("API返回数据格式不正确，使用默认故事信息")
            else:
                conn.logger.bind(tag=TAG).warning("无法获取设备故事信息，使用默认故事信息")
            
            # 获取WebSocket服务器实例
            websocket_server = getattr(conn, 'server', None)
            if not websocket_server:
                conn.logger.bind(tag=TAG).error("无法获取WebSocket服务器实例")
                await conn.websocket.send(
                    json.dumps(
                        {
                            "type": "story",
                            "status": "error", 
                            "message": "服务器实例不可用",
                        }
                    )
                )
                return

            # 创建StoryHandler实例
            story_handler = StoryHandler(conn.config, websocket_server)
            
            # 构造请求数据
            story_data = {
                "device_id": device_id,
                "story_name": story_name
            }
            
            # 如果提供了audio_url，添加到请求数据中
            if audio_url:
                story_data["audio_url"] = audio_url
                story_data["story_title"] = story_title
            
            # 创建一个模拟的请求对象
            class MockRequest:
                def __init__(self, data):
                    self.data = data
                    
                async def json(self):
                    return self.data
                    
            mock_request = MockRequest(story_data)
            
            # 调用story_handler的handle_post方法
            conn.logger.bind(tag=TAG).info(f"调用故事播放API: device_id={device_id}, story_name={story_name}, audio_url={audio_url}")
            
            # 在conn的事件循环中执行
            result = await story_handler.handle_post(mock_request)
            
            # 检查结果状态
            if result.status == 200:
                conn.logger.bind(tag=TAG).info("故事播放成功启动")
                await conn.websocket.send(
                    json.dumps(
                        {
                            "type": "story",
                            "status": "success",
                            "message": "故事播放已启动",
                        }
                    )
                )
            else:
                conn.logger.bind(tag=TAG).error(f"故事播放启动失败: {result.status}")
                await conn.websocket.send(
                    json.dumps(
                        {
                            "type": "story",
                            "status": "error",
                            "message": f"播放启动失败: {result.status}",
                        }
                    )
                )
                
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"处理story消息失败: {str(e)}")
            await conn.websocket.send(
                json.dumps(
                    {
                        "type": "story",
                        "status": "error",
                        "message": f"处理失败: {str(e)}",
                    }
                )
            )