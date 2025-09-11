import asyncio
from aiohttp import web
from config.logger import setup_logging
from core.api.ota_handler import OTAHandler
from core.api.vision_handler import VisionHandler
from core.api.story_handler import StoryHandler
from core.api.music_handler import MusicHandler
TAG = __name__


class SimpleHttpServer:
    def __init__(self, config: dict,websocket_server=None):
        self.config = config
        self.logger = setup_logging()
        self.ota_handler = OTAHandler(config)
        self.vision_handler = VisionHandler(config)
        self.story_handler = StoryHandler(config, websocket_server)
        self.music_handler = MusicHandler(config, websocket_server)
    def _get_websocket_url(self, local_ip: str, port: int) -> str:
        """获取websocket地址

        Args:
            local_ip: 本地IP地址
            port: 端口号

        Returns:
            str: websocket地址
        """
        server_config = self.config["server"]
        websocket_config = server_config.get("websocket")

        if websocket_config and "你" not in websocket_config:
            return websocket_config
        else:
            return f"ws://{local_ip}:{port}/xiaozhi/v1/"

    async def start(self):
        server_config = self.config["server"]
        read_config_from_api = self.config.get("read_config_from_api", False)
        host = server_config.get("ip", "0.0.0.0")
        port = int(server_config.get("http_port", 8003))

        if port:
            app = web.Application()

            if not read_config_from_api:
                # 如果没有开启智控台，只是单模块运行，就需要再添加简单OTA接口，用于下发websocket接口
                app.add_routes(
                    [
                        web.get("/xiaozhi/ota/", self.ota_handler.handle_get),
                        web.post("/xiaozhi/ota/", self.ota_handler.handle_post),
                        web.options("/xiaozhi/ota/", self.ota_handler.handle_post),
                    ]
                )
            # 添加路由
            app.add_routes(
                [
                    web.get("/mcp/vision/explain", self.vision_handler.handle_get),
                    web.post("/mcp/vision/explain", self.vision_handler.handle_post),
                    web.options("/mcp/vision/explain", self.vision_handler.handle_post),

                    # 添加故事播放API路由
                    web.get("/xiaozhi/story/play", self.story_handler.handle_get),
                    web.post("/xiaozhi/story/play", self.story_handler.handle_post),
                    web.options("/xiaozhi/story/play", self.story_handler.handle_post),
                    # 添加播放控制API路由
                    web.post("/xiaozhi/story/stop", self.story_handler.handle_stop_playback),
                    web.options("/xiaozhi/story/stop", self.story_handler.handle_stop_playback),
                    web.post("/xiaozhi/story/pause", self.story_handler.handle_pause_playback),
                    web.options("/xiaozhi/story/pause", self.story_handler.handle_pause_playback),
                    web.post("/xiaozhi/story/resume", self.story_handler.handle_resume_playback),
                    web.options("/xiaozhi/story/resume", self.story_handler.handle_resume_playback),
                    # 添加播放状态查询API路由
                    web.get("/xiaozhi/story/status", self.story_handler.handle_get_status),
                    web.options("/xiaozhi/story/status", self.story_handler.handle_get_status),
                    # 添加音乐控制API路由
                    web.post("/xiaozhi/music/pause", self.music_handler.handle_pause_music),
                    web.options("/xiaozhi/music/pause", self.music_handler.handle_pause_music),
                    web.post("/xiaozhi/music/resume", self.music_handler.handle_resume_music),
                    web.options("/xiaozhi/music/resume", self.music_handler.handle_resume_music),
                    web.post("/xiaozhi/music/play", self.music_handler.handle_play_music),
                    web.options("/xiaozhi/music/play", self.music_handler.handle_play_music),
                    web.get("/xiaozhi/music/status", self.music_handler.handle_music_status),
                    web.options("/xiaozhi/music/status", self.music_handler.handle_music_status),
                    web.get("/xiaozhi/music/info", self.music_handler.handle_music_info),
                    web.options("/xiaozhi/music/info", self.music_handler.handle_music_info),
                ]
            )

            # 运行服务
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, host, port)
            await site.start()

            # 保持服务运行
            while True:
                await asyncio.sleep(3600)  # 每隔 1 小时检查一次
