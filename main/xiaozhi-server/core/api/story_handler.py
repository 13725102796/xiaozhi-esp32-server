import json
import asyncio
import os
import time
import tempfile
import requests
from aiohttp import web
from core.api.base_handler import BaseHandler
from core.api.music_handler import MusicHandler
from plugins_func.functions.play_story import handle_story_command
from core.handle.sendAudioHandle import send_stt_message
from core.utils.dialogue import Message
from core.providers.tts.dto.dto import TTSMessageDTO, SentenceType, ContentType
from config.logger import setup_logging

TAG = __name__


class StoryHandler(BaseHandler):
    def __init__(self, config: dict, websocket_server=None):
        super().__init__(config)
        self.websocket_server = websocket_server
        self.logger = setup_logging()
        self.music_handler = MusicHandler(config, websocket_server)

    def _create_error_response(self, message: str) -> dict:
        """创建统一的错误响应格式"""
        return {"success": False, "message": message}

    def _create_success_response(self, message: str) -> dict:
        """创建统一的成功响应格式"""
        return {"success": True, "message": message}

    def _find_connection_by_device_id(self, device_id: str):
        """根据设备ID查找对应的WebSocket连接"""
        if not self.websocket_server or not hasattr(self.websocket_server, 'active_connections'):
            self.logger.bind(tag=TAG).warning("WebSocket服务器或active_connections不存在")
            return None
        
        # 记录当前所有活跃连接的device_id（用于调试）
        active_device_ids = []
        for conn in self.websocket_server.active_connections:
            conn_device_id = getattr(conn, 'device_id', None)
            active_device_ids.append(conn_device_id)
        
        self.logger.bind(tag=TAG).info(f"查找设备ID: {device_id}, 活跃连接数: {len(self.websocket_server.active_connections)}")
        self.logger.bind(tag=TAG).debug(f"当前活跃的device_id列表: {active_device_ids}")
        
        for conn in self.websocket_server.active_connections:
            if hasattr(conn, 'device_id') and conn.device_id:
                # 尝试不同的匹配方式
                conn_id = str(conn.device_id).strip()
                target_id = str(device_id).strip()
                
                # 精确匹配
                if conn_id == target_id:
                    self.logger.bind(tag=TAG).info(f"找到匹配的连接(精确): device_id={conn.device_id}")
                    return conn
                # 忽略大小写匹配
                elif conn_id.lower() == target_id.lower():
                    self.logger.bind(tag=TAG).info(f"找到匹配的连接(忽略大小写): device_id={conn.device_id}")
                    return conn
        
        self.logger.bind(tag=TAG).warning(f"未找到设备ID为 {device_id} 的连接")
        return None

    async def _trigger_music_play(self, device_id: str):
        """触发音乐播放API"""
        try:
            conn = self._find_connection_by_device_id(device_id)
            if not conn:
                self.logger.bind(tag=TAG).warning(f"触发音乐播放失败: 未找到设备 {device_id} 的连接")
                return False

            # 直接调用music_handler的发送播放命令方法
            result = await self.music_handler._send_play_command(conn)
            
            if result:
                self.logger.bind(tag=TAG).info(f"成功触发设备 {device_id} 的音乐播放")
                return True
            else:
                self.logger.bind(tag=TAG).warning(f"触发设备 {device_id} 的音乐播放失败")
                return False
                
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"触发音乐播放异常: {e}")
            return False

    def _is_device_playing(self, conn):
        """检查设备是否正在播放"""
        try:
            # 如果没有TTS对象，肯定不在播放
            if not hasattr(conn, 'tts'):
                return False
                
            # 检查基本的播放控制标志
            client_abort = getattr(conn, 'client_abort', False)
            llm_finish_task = getattr(conn, 'llm_finish_task', True)  # 默认为完成状态
            
            # 如果被中止或已完成，不在播放
            if client_abort or llm_finish_task:
                return False
            
            # 检查是否有待处理的内容
            text_queue_has_content = hasattr(conn.tts, 'tts_text_queue') and not conn.tts.tts_text_queue.empty()
            audio_queue_has_content = hasattr(conn.tts, 'tts_audio_queue') and not conn.tts.tts_audio_queue.empty()
            text_buff_has_content = hasattr(conn.tts, 'tts_text_buff') and bool(conn.tts.tts_text_buff)
            
            # 有任何待处理内容就认为在播放
            return text_queue_has_content or audio_queue_has_content or text_buff_has_content
            
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"检查播放状态失败: {str(e)}")
            return False

    def _stop_current_playback(self, conn):
        """停止当前播放"""
        try:
            # 设置中止标志
            conn.client_abort = True
            conn.llm_finish_task = True
            
            # 清空TTS队列
            if hasattr(conn, 'tts'):
                # 清空文本队列中的所有任务
                if hasattr(conn.tts, 'tts_text_queue'):
                    while not conn.tts.tts_text_queue.empty():
                        try:
                            conn.tts.tts_text_queue.get_nowait()
                        except:
                            break
                
                # 清空音频队列中的所有任务  
                if hasattr(conn.tts, 'tts_audio_queue'):
                    while not conn.tts.tts_audio_queue.empty():
                        try:
                            conn.tts.tts_audio_queue.get_nowait()
                        except:
                            break
                
                # 设置TTS停止请求标志
                if hasattr(conn.tts, 'tts_stop_request'):
                    conn.tts.tts_stop_request = True
            
            # 清空播放状态
            if hasattr(conn, 'playback_paused'):
                conn.playback_paused = False
            if hasattr(conn, 'paused_content'):
                conn.paused_content = None
            
            self.logger.bind(tag=TAG).info(f"已停止设备 {conn.device_id} 的当前播放")
            return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"停止播放失败: {str(e)}")
            return False

    def _pause_current_playback(self, conn):
        """暂停当前播放 - 暂停音频数据包的发送，但保持播放进度"""
        try:
            # 设置暂停标志，音频发送循环会在检测到此标志时暂停
            conn.playback_paused = True
            
            self.logger.bind(tag=TAG).info(f"已暂停设备 {conn.device_id} 的播放 - 音频发送已暂停")
            return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"暂停播放失败: {str(e)}")
            return False

    def _resume_current_playback(self, conn):
        """继续播放 - 恢复音频数据包的发送"""
        try:
            if not hasattr(conn, 'playback_paused') or not conn.playback_paused:
                self.logger.bind(tag=TAG).warning(f"设备 {conn.device_id} 当前没有暂停的播放")
                return False
            
            # 清除暂停标志，音频发送循环会继续发送剩余的音频包
            conn.playback_paused = False
            
            self.logger.bind(tag=TAG).info(f"已恢复设备 {conn.device_id} 的播放 - 音频发送已恢复")
            return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"恢复播放失败: {str(e)}")
            return False

    async def _play_audio_from_url(self, conn, audio_url: str, story_title: str = "精彩故事"):
        """直接从URL播放音频"""
        temp_file_path = None
        try:
            # 下载音频文件到临时目录 (使用同步方法)
            temp_file_path = self._download_audio_from_url(audio_url)
            if not temp_file_path:
                raise ValueError("下载音频文件失败")

            self.logger.bind(tag=TAG).info(f"成功下载音频文件: {temp_file_path}")

            # 生成播放提示语
            text = f"正在为您播放，{story_title}"
            await send_stt_message(conn, text)
            conn.dialogue.put(Message(role="assistant", content=text))

            # 生成新的sentence_id并重置TTS状态
            import uuid
            conn.sentence_id = str(uuid.uuid4())
            conn.tts.tts_audio_first_sentence = True  # 重置首句标志
            
            # 将音频文件加入TTS队列播放
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
                    content_detail=story_title,  # 添加内容描述，避免 None
                )
            )
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.LAST,
                    content_type=ContentType.ACTION,
                )
            )

            self.logger.bind(tag=TAG).info(f"音频播放任务已加入队列: {story_title}")

        except Exception as e:
            self.logger.bind(tag=TAG).error(f"播放URL音频失败: {str(e)}")
            raise e
        finally:
            # 临时文件会被TTS处理完后自动清理
            pass

    def _download_audio_from_url(self, audio_url: str):
        """从URL下载音频文件到临时目录 (同步版本)"""
        try:
            # 创建临时文件
            temp_dir = tempfile.gettempdir()
            temp_filename = f"api_story_{int(time.time())}.mp3"
            temp_path = os.path.join(temp_dir, temp_filename)

            self.logger.bind(tag=TAG).info(f"开始下载音频: {audio_url} -> {temp_path}")

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
                self.logger.bind(tag=TAG).error("下载的音频文件大小为0")
                os.remove(temp_path)
                return None

            self.logger.bind(tag=TAG).info(f"音频下载完成: {temp_path}, 大小: {file_size} 字节")
            return temp_path

        except requests.exceptions.RequestException as e:
            self.logger.bind(tag=TAG).error(f"下载音频失败: {str(e)}")
            return None
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"下载音频时发生未知错误: {str(e)}")
            return None

    async def handle_post(self, request):
        """处理播放故事的POST请求"""
        response = None
        try:
            # 解析请求体
            try:
                data = await request.json()
            except Exception as e:
                raise ValueError(f"无效的JSON格式: {str(e)}")

            # 验证必要参数
            device_id = data.get('device_id')
            if not device_id:
                raise ValueError("缺少必要参数: device_id")

            story_name = data.get('story_name', 'random')
            audio_url = data.get('audio_url')  # 新增：直接音频URL
            story_title = data.get('story_title', story_name)  # 新增：故事标题

            self.logger.bind(tag=TAG).info(f"接收到播放故事请求: device_id={device_id}, story_name={story_name}, audio_url={audio_url}")

            # 查找对应的WebSocket连接
            conn = self._find_connection_by_device_id(device_id)
            if not conn:
                raise ValueError(f"设备 {device_id} 未连接或不在线")

            # 检查连接状态
            if not hasattr(conn, 'loop') or not conn.loop.is_running():
                raise ValueError("设备连接状态异常，无法处理请求")

            # 检查是否正在播放，如果是则先停止
            is_currently_playing = self._is_device_playing(conn)
            if is_currently_playing:
                self.logger.bind(tag=TAG).info(f"设备 {device_id} 正在播放内容，先停止当前播放")
                self._stop_current_playback(conn)
                
                # 给一点时间让停止操作生效
                import asyncio
                await asyncio.sleep(0.1)
            else:
                self.logger.bind(tag=TAG).info(f"设备 {device_id} 当前没有播放内容")
            
            # 重置连接状态，确保可以播放（无论之前是否在播放）
            conn.client_abort = False
            conn.llm_finish_task = False
            # 清除任何暂停状态
            if hasattr(conn, 'playback_paused'):
                conn.playback_paused = False

            # 根据是否提供audio_url决定播放方式
            if audio_url:
                self.logger.bind(tag=TAG).info(f"使用直接URL模式播放: {audio_url}")
                # 直接在conn的事件循环中创建任务
                task = conn.loop.create_task(
                    self._play_audio_from_url(conn, audio_url, story_title)
                )
                
                # 添加任务完成回调
                def handle_url_done(t):
                    try:
                        result = t.result()
                        self.logger.bind(tag=TAG).info(f"设备 {device_id} URL音频播放完成: {result}")
                    except Exception as e:
                        self.logger.bind(tag=TAG).error(f"设备 {device_id} URL音频播放失败: {e}")
                
                task.add_done_callback(handle_url_done)
                
            else:
                self.logger.bind(tag=TAG).info(f"使用远程故事API模式播放: {story_name}")
                # 使用原有的远程故事API方式
                story_intent = f"讲故事 {story_name}" if story_name != "random" else "随机播放故事"
                task = conn.loop.create_task(
                    handle_story_command(conn, story_intent)
                )
                
                # 添加任务完成回调
                def handle_remote_done(t):
                    try:
                        result = t.result()
                        self.logger.bind(tag=TAG).info(f"设备 {device_id} 远程故事播放完成: {result}")
                    except Exception as e:
                        self.logger.bind(tag=TAG).error(f"设备 {device_id} 远程故事播放失败: {e}")
                
                task.add_done_callback(handle_remote_done)

            # 调用音乐播放API
            await self._trigger_music_play(device_id)

            # 立即返回成功响应
            success_msg = f"故事播放指令已发送到设备 {device_id}"
            if is_currently_playing:
                success_msg += "（已停止当前播放）"
            if audio_url:
                success_msg += f"，将播放: {story_title}"
            else:
                success_msg += f"，将播放: {story_name}"
            
            return_json = self._create_success_response(success_msg)
            self.logger.bind(tag=TAG).info(f"API响应: {success_msg}")
            
            response = web.Response(
                text=json.dumps(return_json, ensure_ascii=False),
                content_type="application/json",
                status=200
            )

        except ValueError as e:
            self.logger.bind(tag=TAG).warning(f"播放故事请求参数错误: {e}")
            return_json = self._create_error_response(str(e))
            response = web.Response(
                text=json.dumps(return_json, ensure_ascii=False),
                content_type="application/json",
                status=400
            )
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"播放故事请求处理异常: {e}")
            import traceback
            self.logger.bind(tag=TAG).error(f"详细错误栈: {traceback.format_exc()}")
            return_json = self._create_error_response(f"服务器内部错误: {str(e)}")
            response = web.Response(
                text=json.dumps(return_json, ensure_ascii=False),
                content_type="application/json",
                status=500
            )
        finally:
            # 确保总是有响应
            if response is None:
                self.logger.bind(tag=TAG).error("响应为空，创建默认错误响应")
                return_json = self._create_error_response("未知错误")
                response = web.Response(
                    text=json.dumps(return_json, ensure_ascii=False),
                    content_type="application/json",
                    status=500
                )
            
            # 添加CORS头
            self._add_cors_headers(response)
            self.logger.bind(tag=TAG).info(f"返回响应: 状态码={response.status}, 内容长度={len(response.text) if hasattr(response, 'text') else 'unknown'}")
            return response

    async def handle_get(self, request):
        """处理播放故事的GET请求 - 返回API使用说明"""
        try:
            active_devices = []
            if self.websocket_server and hasattr(self.websocket_server, 'active_connections'):
                for conn in self.websocket_server.active_connections:
                    if hasattr(conn, 'device_id') and conn.device_id:
                        active_devices.append(conn.device_id)

            message = {
                "api": "故事播放控制API",
                "endpoints": {
                    "play": "POST /xiaozhi/story/play - 播放故事",
                    "stop": "POST /xiaozhi/story/stop - 停止播放",
                    "pause": "POST /xiaozhi/story/pause - 暂停播放",
                    "resume": "POST /xiaozhi/story/resume - 继续播放",
                    "status": "GET /xiaozhi/story/status?device_id=xxx - 查询播放状态"
                },
                "play_parameters": {
                    "device_id": "设备ID（必填）",
                    "audio_url": "音频URL（可选，直接播放指定音频）",
                    "story_title": "故事标题（可选，配合audio_url使用）",
                    "story_name": "故事名称（可选，用于远程API查询，默认为random）"
                },
                "control_parameters": {
                    "device_id": "设备ID（必填）"
                },
                "usage_modes": {
                    "mode1": "直接播放指定音频URL",
                    "mode2": "使用远程故事API获取音频",
                    "mode3": "播放控制（停止、暂停、继续）"
                },
                "active_devices": active_devices,
                "examples": {
                    "play_direct_url": {
                        "device_id": "xx:xx:xx:xx:xx:xx",
                        "audio_url": "https://example.com/story.mp3",
                        "story_title": "小红帽的故事"
                    },
                    "play_remote_api": {
                        "device_id": "xx:xx:xx:xx:xx:xx",
                        "story_name": "random"
                    },
                    "stop_playback": {
                        "device_id": "xx:xx:xx:xx:xx:xx"
                    },
                    "pause_playback": {
                        "device_id": "xx:xx:xx:xx:xx:xx"
                    },
                    "resume_playback": {
                        "device_id": "xx:xx:xx:xx:xx:xx"
                    },
                    "get_status": {
                        "url": "/xiaozhi/story/status?device_id=xx:xx:xx:xx:xx:xx",
                        "method": "GET"
                    }
                }
            }

            response = web.Response(
                text=json.dumps(message, ensure_ascii=False, indent=2),
                content_type="application/json"
            )
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"播放故事GET请求异常: {e}")
            return_json = self._create_error_response("服务器内部错误")
            response = web.Response(
                text=json.dumps(return_json, ensure_ascii=False),
                content_type="application/json",
                status=500
            )
        finally:
            self._add_cors_headers(response)
            return response

    async def handle_stop_playback(self, request):
        """处理停止播放的请求"""
        response = None
        try:
            # 解析请求体
            try:
                data = await request.json()
            except Exception as e:
                raise ValueError(f"无效的JSON格式: {str(e)}")

            # 验证必要参数
            device_id = data.get('device_id')
            if not device_id:
                raise ValueError("缺少必要参数: device_id")

            self.logger.bind(tag=TAG).info(f"接收到停止播放请求: device_id={device_id}")

            # 查找对应的WebSocket连接
            conn = self._find_connection_by_device_id(device_id)
            if not conn:
                raise ValueError(f"设备 {device_id} 未连接或不在线")

            # 停止当前播放
            success = self._stop_current_playback(conn)
            
            if success:
                success_msg = f"设备 {device_id} 播放已停止"
                return_json = self._create_success_response(success_msg)
                self.logger.bind(tag=TAG).info(success_msg)
                
                response = web.Response(
                    text=json.dumps(return_json, ensure_ascii=False),
                    content_type="application/json",
                    status=200
                )
            else:
                error_msg = f"停止设备 {device_id} 播放失败"
                return_json = self._create_error_response(error_msg)
                response = web.Response(
                    text=json.dumps(return_json, ensure_ascii=False),
                    content_type="application/json",
                    status=500
                )

        except ValueError as e:
            self.logger.bind(tag=TAG).warning(f"停止播放请求参数错误: {e}")
            return_json = self._create_error_response(str(e))
            response = web.Response(
                text=json.dumps(return_json, ensure_ascii=False),
                content_type="application/json",
                status=400
            )
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"停止播放请求处理异常: {e}")
            import traceback
            self.logger.bind(tag=TAG).error(f"详细错误栈: {traceback.format_exc()}")
            return_json = self._create_error_response(f"服务器内部错误: {str(e)}")
            response = web.Response(
                text=json.dumps(return_json, ensure_ascii=False),
                content_type="application/json",
                status=500
            )
        finally:
            # 确保总是有响应
            if response is None:
                self.logger.bind(tag=TAG).error("停止播放响应为空，创建默认错误响应")
                return_json = self._create_error_response("未知错误")
                response = web.Response(
                    text=json.dumps(return_json, ensure_ascii=False),
                    content_type="application/json",
                    status=500
                )
            
            # 添加CORS头
            self._add_cors_headers(response)
            self.logger.bind(tag=TAG).info(f"停止播放响应: 状态码={response.status}")
            return response

    async def handle_pause_playback(self, request):
        """处理暂停播放的请求"""
        response = None
        try:
            # 解析请求体
            try:
                data = await request.json()
            except Exception as e:
                raise ValueError(f"无效的JSON格式: {str(e)}")

            # 验证必要参数
            device_id = data.get('device_id')
            if not device_id:
                raise ValueError("缺少必要参数: device_id")

            self.logger.bind(tag=TAG).info(f"接收到暂停播放请求: device_id={device_id}")

            # 查找对应的WebSocket连接
            conn = self._find_connection_by_device_id(device_id)
            if not conn:
                raise ValueError(f"设备 {device_id} 未连接或不在线")

            # 暂停当前播放
            success = self._pause_current_playback(conn)
            
            if success:
                success_msg = f"设备 {device_id} 播放已暂停"
                return_json = self._create_success_response(success_msg)
                self.logger.bind(tag=TAG).info(success_msg)
                
                response = web.Response(
                    text=json.dumps(return_json, ensure_ascii=False),
                    content_type="application/json",
                    status=200
                )
            else:
                error_msg = f"暂停设备 {device_id} 播放失败"
                return_json = self._create_error_response(error_msg)
                response = web.Response(
                    text=json.dumps(return_json, ensure_ascii=False),
                    content_type="application/json",
                    status=500
                )

        except ValueError as e:
            self.logger.bind(tag=TAG).warning(f"暂停播放请求参数错误: {e}")
            return_json = self._create_error_response(str(e))
            response = web.Response(
                text=json.dumps(return_json, ensure_ascii=False),
                content_type="application/json",
                status=400
            )
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"暂停播放请求处理异常: {e}")
            import traceback
            self.logger.bind(tag=TAG).error(f"详细错误栈: {traceback.format_exc()}")
            return_json = self._create_error_response(f"服务器内部错误: {str(e)}")
            response = web.Response(
                text=json.dumps(return_json, ensure_ascii=False),
                content_type="application/json",
                status=500
            )
        finally:
            # 确保总是有响应
            if response is None:
                self.logger.bind(tag=TAG).error("暂停播放响应为空，创建默认错误响应")
                return_json = self._create_error_response("未知错误")
                response = web.Response(
                    text=json.dumps(return_json, ensure_ascii=False),
                    content_type="application/json",
                    status=500
                )
            
            # 添加CORS头
            self._add_cors_headers(response)
            self.logger.bind(tag=TAG).info(f"暂停播放响应: 状态码={response.status}")
            return response

    async def handle_resume_playback(self, request):
        """处理恢复播放的请求"""
        response = None
        try:
            # 解析请求体
            try:
                data = await request.json()
            except Exception as e:
                raise ValueError(f"无效的JSON格式: {str(e)}")

            # 验证必要参数
            device_id = data.get('device_id')
            if not device_id:
                raise ValueError("缺少必要参数: device_id")

            self.logger.bind(tag=TAG).info(f"接收到恢复播放请求: device_id={device_id}")

            # 查找对应的WebSocket连接
            conn = self._find_connection_by_device_id(device_id)
            if not conn:
                raise ValueError(f"设备 {device_id} 未连接或不在线")

            # 恢复播放
            success = self._resume_current_playback(conn)
            
            if success:
                success_msg = f"设备 {device_id} 播放已恢复"
                return_json = self._create_success_response(success_msg)
                self.logger.bind(tag=TAG).info(success_msg)
                
                response = web.Response(
                    text=json.dumps(return_json, ensure_ascii=False),
                    content_type="application/json",
                    status=200
                )
            else:
                error_msg = f"恢复设备 {device_id} 播放失败"
                return_json = self._create_error_response(error_msg)
                response = web.Response(
                    text=json.dumps(return_json, ensure_ascii=False),
                    content_type="application/json",
                    status=500
                )

        except ValueError as e:
            self.logger.bind(tag=TAG).warning(f"恢复播放请求参数错误: {e}")
            return_json = self._create_error_response(str(e))
            response = web.Response(
                text=json.dumps(return_json, ensure_ascii=False),
                content_type="application/json",
                status=400
            )
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"恢复播放请求处理异常: {e}")
            import traceback
            self.logger.bind(tag=TAG).error(f"详细错误栈: {traceback.format_exc()}")
            return_json = self._create_error_response(f"服务器内部错误: {str(e)}")
            response = web.Response(
                text=json.dumps(return_json, ensure_ascii=False),
                content_type="application/json",
                status=500
            )
        finally:
            # 确保总是有响应
            if response is None:
                self.logger.bind(tag=TAG).error("恢复播放响应为空，创建默认错误响应")
                return_json = self._create_error_response("未知错误")
                response = web.Response(
                    text=json.dumps(return_json, ensure_ascii=False),
                    content_type="application/json",
                    status=500
                )
            
            # 添加CORS头
            self._add_cors_headers(response)
            self.logger.bind(tag=TAG).info(f"恢复播放响应: 状态码={response.status}")
            return response

    async def handle_get_status(self, request):
        """获取设备播放状态"""
        response = None
        try:
            # 获取设备ID参数
            device_id = request.query.get('device_id')
            if not device_id:
                raise ValueError("缺少必要参数: device_id")

            self.logger.bind(tag=TAG).info(f"获取设备播放状态: device_id={device_id}")

            # 查找对应的WebSocket连接
            conn = self._find_connection_by_device_id(device_id)
            if not conn:
                raise ValueError(f"设备 {device_id} 未连接或不在线")

            # 获取播放状态
            is_playing = self._is_device_playing(conn)
            is_paused = getattr(conn, 'playback_paused', False)
            
            # 获取队列状态
            status_info = {
                "device_id": device_id,
                "is_playing": is_playing,
                "is_paused": is_paused,
                "client_abort": getattr(conn, 'client_abort', True),
                "llm_finish_task": getattr(conn, 'llm_finish_task', True)
            }
            
            if hasattr(conn, 'tts'):
                status_info.update({
                    "text_queue_size": conn.tts.tts_text_queue.qsize() if hasattr(conn.tts, 'tts_text_queue') else 0,
                    "audio_queue_size": conn.tts.tts_audio_queue.qsize() if hasattr(conn.tts, 'tts_audio_queue') else 0,
                    "text_buffer_length": len(conn.tts.tts_text_buff) if hasattr(conn.tts, 'tts_text_buff') else 0
                })

            return_json = {
                "success": True,
                "message": "播放状态获取成功",
                "data": status_info
            }
            
            response = web.Response(
                text=json.dumps(return_json, ensure_ascii=False),
                content_type="application/json",
                status=200
            )

        except ValueError as e:
            self.logger.bind(tag=TAG).warning(f"获取播放状态请求参数错误: {e}")
            return_json = self._create_error_response(str(e))
            response = web.Response(
                text=json.dumps(return_json, ensure_ascii=False),
                content_type="application/json",
                status=400
            )
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"获取播放状态请求处理异常: {e}")
            import traceback
            self.logger.bind(tag=TAG).error(f"详细错误栈: {traceback.format_exc()}")
            return_json = self._create_error_response(f"服务器内部错误: {str(e)}")
            response = web.Response(
                text=json.dumps(return_json, ensure_ascii=False),
                content_type="application/json",
                status=500
            )
        finally:
            # 确保总是有响应
            if response is None:
                self.logger.bind(tag=TAG).error("获取播放状态响应为空，创建默认错误响应")
                return_json = self._create_error_response("未知错误")
                response = web.Response(
                    text=json.dumps(return_json, ensure_ascii=False),
                    content_type="application/json",
                    status=500
                )
            
            # 添加CORS头
            self._add_cors_headers(response)
            self.logger.bind(tag=TAG).info(f"播放状态响应: 状态码={response.status}")
            return response