import json
import asyncio
from aiohttp import web
from core.api.base_handler import BaseHandler
from config.logger import setup_logging

TAG = __name__


class MusicHandler(BaseHandler):
    def __init__(self, config: dict, websocket_server=None):
        super().__init__(config)
        self.websocket_server = websocket_server
        self.logger = setup_logging()

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
            if hasattr(conn, 'device_id') and conn.device_id == device_id:
                self.logger.bind(tag=TAG).info(f"找到匹配的连接: device_id={conn.device_id}")
                return conn
        
        self.logger.bind(tag=TAG).warning(f"未找到设备ID为 {device_id} 的连接")
        return None

    async def handle_pause_music(self, request):
        """处理暂停音乐播放的请求"""
        try:
            # 解析请求参数
            try:
                data = await request.json()
                device_id = data.get("device_id")
            except Exception as e:
                self.logger.bind(tag=TAG).warning(f"暂停音乐请求参数错误: {e}")
                response = web.json_response(
                    self._create_error_response("请求参数格式错误"),
                    status=400
                )
                self._add_cors_headers(response)
                return response

            if not device_id:
                response = web.json_response(
                    self._create_error_response("缺少必需参数: device_id"),
                    status=400
                )
                self._add_cors_headers(response)
                return response

            self.logger.bind(tag=TAG).info(f"接收到暂停音乐请求: device_id={device_id}")

            # 查找对应的连接
            conn = self._find_connection_by_device_id(device_id)
            if not conn:
                error_msg = f"未找到设备 {device_id} 的连接"
                self.logger.bind(tag=TAG).error(error_msg)
                response = web.json_response(
                    self._create_error_response(error_msg),
                    status=404
                )
                self._add_cors_headers(response)
                return response

            # 通过websocket发送暂停命令
            result = await self._send_pause_command(conn)
            
            if result:
                success_msg = f"设备 {device_id} 音乐暂停命令已发送"
                self.logger.bind(tag=TAG).info(success_msg)
                response_data = self._create_success_response(success_msg)
                response_data["device_id"] = device_id
                response_data["action"] = "pause"
                
                response = web.json_response(response_data)
            else:
                error_msg = f"向设备 {device_id} 发送暂停命令失败"
                self.logger.bind(tag=TAG).error(error_msg)
                response = web.json_response(
                    self._create_error_response(error_msg),
                    status=500
                )

        except ValueError as e:
            self.logger.bind(tag=TAG).warning(f"暂停音乐请求参数错误: {e}")
            response = web.json_response(
                self._create_error_response(f"参数错误: {str(e)}"),
                status=400
            )

        except Exception as e:
            self.logger.bind(tag=TAG).error(f"暂停音乐请求处理异常: {e}")
            response = web.json_response(
                self._create_error_response("服务器内部错误"),
                status=500
            )

        # 确保响应对象存在
        if 'response' not in locals():
            self.logger.bind(tag=TAG).error("暂停音乐响应为空，创建默认错误响应")
            response = web.json_response(
                self._create_error_response("未知错误"),
                status=500
            )

        try:
            # 添加CORS头并记录响应状态
            self._add_cors_headers(response)
            self.logger.bind(tag=TAG).info(f"暂停音乐响应: 状态码={response.status}")
            return response
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"暂停音乐响应处理异常: {e}")
            response = web.json_response(
                self._create_error_response("响应处理异常"),
                status=500
            )
            self._add_cors_headers(response)
            return response

    async def handle_resume_music(self, request):
        """处理继续音乐播放的请求"""
        try:
            # 解析请求参数
            try:
                data = await request.json()
                device_id = data.get("device_id")
            except Exception as e:
                self.logger.bind(tag=TAG).warning(f"继续音乐请求参数错误: {e}")
                response = web.json_response(
                    self._create_error_response("请求参数格式错误"),
                    status=400
                )
                self._add_cors_headers(response)
                return response

            if not device_id:
                response = web.json_response(
                    self._create_error_response("缺少必需参数: device_id"),
                    status=400
                )
                self._add_cors_headers(response)
                return response

            self.logger.bind(tag=TAG).info(f"接收到继续音乐请求: device_id={device_id}")

            # 查找对应的连接
            conn = self._find_connection_by_device_id(device_id)
            if not conn:
                error_msg = f"未找到设备 {device_id} 的连接"
                self.logger.bind(tag=TAG).error(error_msg)
                response = web.json_response(
                    self._create_error_response(error_msg),
                    status=404
                )
                self._add_cors_headers(response)
                return response

            # 通过websocket发送继续播放命令
            result = await self._send_resume_command(conn)
            
            if result:
                success_msg = f"设备 {device_id} 音乐继续命令已发送"
                self.logger.bind(tag=TAG).info(success_msg)
                response_data = self._create_success_response(success_msg)
                response_data["device_id"] = device_id
                response_data["action"] = "resume"
                
                response = web.json_response(response_data)
            else:
                error_msg = f"向设备 {device_id} 发送继续命令失败"
                self.logger.bind(tag=TAG).error(error_msg)
                response = web.json_response(
                    self._create_error_response(error_msg),
                    status=500
                )

        except ValueError as e:
            self.logger.bind(tag=TAG).warning(f"继续音乐请求参数错误: {e}")
            response = web.json_response(
                self._create_error_response(f"参数错误: {str(e)}"),
                status=400
            )

        except Exception as e:
            self.logger.bind(tag=TAG).error(f"继续音乐请求处理异常: {e}")
            response = web.json_response(
                self._create_error_response("服务器内部错误"),
                status=500
            )

        # 确保响应对象存在
        if 'response' not in locals():
            self.logger.bind(tag=TAG).error("继续音乐响应为空，创建默认错误响应")
            response = web.json_response(
                self._create_error_response("未知错误"),
                status=500
            )

        try:
            # 添加CORS头并记录响应状态
            self._add_cors_headers(response)
            self.logger.bind(tag=TAG).info(f"继续音乐响应: 状态码={response.status}")
            return response
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"继续音乐响应处理异常: {e}")
            response = web.json_response(
                self._create_error_response("响应处理异常"),
                status=500
            )
            self._add_cors_headers(response)
            return response

    async def handle_play_music(self, request):
        """处理播放音乐的请求"""
        try:
            # 解析请求参数
            try:
                data = await request.json()
                device_id = data.get("device_id")
            except Exception as e:
                self.logger.bind(tag=TAG).warning(f"播放音乐请求参数错误: {e}")
                response = web.json_response(
                    self._create_error_response("请求参数格式错误"),
                    status=400
                )
                self._add_cors_headers(response)
                return response

            if not device_id:
                response = web.json_response(
                    self._create_error_response("缺少必需参数: device_id"),
                    status=400
                )
                self._add_cors_headers(response)
                return response

            self.logger.bind(tag=TAG).info(f"接收到播放音乐请求: device_id={device_id}")

            # 查找对应的连接
            conn = self._find_connection_by_device_id(device_id)
            if not conn:
                error_msg = f"未找到设备 {device_id} 的连接"
                self.logger.bind(tag=TAG).error(error_msg)
                response = web.json_response(
                    self._create_error_response(error_msg),
                    status=404
                )
                self._add_cors_headers(response)
                return response

            # 通过websocket发送播放音乐命令
            result = await self._send_play_command(conn)
            
            if result:
                success_msg = f"设备 {device_id} 音乐播放命令已发送"
                self.logger.bind(tag=TAG).info(success_msg)
                response_data = self._create_success_response(success_msg)
                response_data["device_id"] = device_id
                response_data["action"] = "play"
                
                response = web.json_response(response_data)
            else:
                error_msg = f"向设备 {device_id} 发送播放命令失败"
                self.logger.bind(tag=TAG).error(error_msg)
                response = web.json_response(
                    self._create_error_response(error_msg),
                    status=500
                )

        except ValueError as e:
            self.logger.bind(tag=TAG).warning(f"播放音乐请求参数错误: {e}")
            response = web.json_response(
                self._create_error_response(f"参数错误: {str(e)}"),
                status=400
            )

        except Exception as e:
            self.logger.bind(tag=TAG).error(f"播放音乐请求处理异常: {e}")
            response = web.json_response(
                self._create_error_response("服务器内部错误"),
                status=500
            )

        # 确保响应对象存在
        if 'response' not in locals():
            self.logger.bind(tag=TAG).error("播放音乐响应为空，创建默认错误响应")
            response = web.json_response(
                self._create_error_response("未知错误"),
                status=500
            )

        try:
            # 添加CORS头并记录响应状态
            self._add_cors_headers(response)
            self.logger.bind(tag=TAG).info(f"播放音乐响应: 状态码={response.status}")
            return response
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"播放音乐响应处理异常: {e}")
            response = web.json_response(
                self._create_error_response("播放音乐响应处理异常"),
                status=500
            )
            self._add_cors_headers(response)
            return response

    async def _send_pause_command(self, conn):
        """通过websocket发送暂停命令给设备"""
        try:
            pause_message = {
                "type": "music_control",
                "action": "pause",
                "timestamp": asyncio.get_event_loop().time()
            }
            await conn.websocket.send(json.dumps(pause_message))
            self.logger.bind(tag=TAG).info(f"向设备 {conn.device_id} 发送暂停命令")
            return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"发送暂停命令失败: {e}")
            return False

    async def _send_resume_command(self, conn):
        """通过websocket发送继续播放命令给设备"""
        try:
            resume_message = {
                "type": "music_control",
                "action": "resume",
                "timestamp": asyncio.get_event_loop().time()
            }
            await conn.websocket.send(json.dumps(resume_message))
            self.logger.bind(tag=TAG).info(f"向设备 {conn.device_id} 发送继续播放命令")
            return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"发送继续播放命令失败: {e}")
            return False

    async def _send_play_command(self, conn):
        """通过websocket发送播放音乐命令给设备"""
        try:
            play_message = {
                "type": "music_control",
                "action": "play",
                "timestamp": asyncio.get_event_loop().time()
            }
            await conn.websocket.send(json.dumps(play_message))
            self.logger.bind(tag=TAG).info(f"向设备 {conn.device_id} 发送播放音乐命令")
            return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"发送播放音乐命令失败: {e}")
            return False

    async def handle_music_status(self, request):
        """获取音乐播放状态"""
        try:
            device_id = request.query.get("device_id")
            
            if not device_id:
                response = web.json_response(
                    self._create_error_response("缺少必需参数: device_id"),
                    status=400
                )
                self._add_cors_headers(response)
                return response

            conn = self._find_connection_by_device_id(device_id)
            if not conn:
                response = web.json_response(
                    self._create_error_response(f"未找到设备 {device_id} 的连接"),
                    status=404
                )
                self._add_cors_headers(response)
                return response

            # 获取设备状态
            status = {
                "device_id": device_id,
                "connected": True,
                "websocket_active": hasattr(conn, 'websocket') and conn.websocket is not None
            }
            
            response_data = self._create_success_response("获取状态成功")
            response_data.update({"status": status})
            
            response = web.json_response(response_data)
            self._add_cors_headers(response)
            return response

        except Exception as e:
            self.logger.bind(tag=TAG).error(f"获取音乐状态异常: {e}")
            response = web.json_response(
                self._create_error_response("获取状态失败"),
                status=500
            )
            self._add_cors_headers(response)
            return response

    async def handle_music_info(self, request):
        """获取音乐控制API信息"""
        info = {
            "api_name": "Music Control API",
            "version": "1.0",
            "description": "通过WebSocket向设备发送音乐控制命令",
            "endpoints": {
                "pause": "POST /xiaozhi/music/pause - 暂停播放",
                "resume": "POST /xiaozhi/music/resume - 继续播放", 
                "play": "POST /xiaozhi/music/play - 播放音乐",
                "status": "GET /xiaozhi/music/status - 获取设备连接状态",
                "info": "GET /xiaozhi/music/info - 获取API信息"
            },
            "request_format": {
                "pause/resume/play": {
                    "device_id": "设备ID（MAC地址）"
                },
                "status": {
                    "device_id": "设备ID（查询参数）"
                }
            },
            "websocket_commands": {
                "pause": {
                    "type": "music_control",
                    "action": "pause"
                },
                "resume": {
                    "type": "music_control", 
                    "action": "resume"
                },
                "play": {
                    "type": "music_control", 
                    "action": "play"
                }
            },
            "supported_operations": {
                "mode1": "通过WebSocket发送音乐控制命令",
                "mode2": "设备连接状态查询",
                "mode3": "API信息查询"
            }
        }
        response = web.json_response(info)
        self._add_cors_headers(response)
        return response