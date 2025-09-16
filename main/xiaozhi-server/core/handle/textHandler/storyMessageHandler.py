import json
from typing import Dict, Any

from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from core.api.story_handler import StoryHandler

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
            story_name = "侦探与龙：宝石的秘密"
            audio_url = "https://toy-storage.airlabs.art/audio/volcano_tts/permanent/20250904/story_7369183431743246336_cfd71314.mp3"
            story_title = "侦探与龙：宝石的秘密"
            
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