from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__

WHITE_NOISE_CONFIG = {}

play_white_noise_function_desc = {
    "type": "function",
    "function": {
        "name": "play_white_noise",
        "description": "专门播放白噪音的功能。当用户说'播放白噪音'、'来点白噪音'、'播放环境音'、'播放雨声'、'播放海浪声'等时使用此功能。包括各种自然声音和环境音效，如雨声、海浪声、森林声等，用于放松和助眠。绝对不播放音乐歌曲。",
        "parameters": {
            "type": "object",
            "properties": {
                "noise_type": {
                    "type": "string",
                    "description": "白噪音类型，如果用户没有指定具体类型则为'random', 明确指定的时返回白噪音的名字 示例: ```用户:播放雨声\n参数：雨声``` ```用户:播放白噪音 \n参数：random ```",
                }
            },
            "required": ["noise_type"],
        },
    },
}



@register_function("play_white_noise", play_white_noise_function_desc, ToolType.SYSTEM_CTL)
def play_white_noise(conn, noise_type: str):
    try:

        # 暂时直接返回成功响应，不执行复杂逻辑
        return ActionResponse(
            action=Action.RESPONSE, result="测试成功", response="白噪音功能测试成功！函数已被正确调用。"
        )
    except Exception as e:
        print(f"白噪音函数执行错误: {e}")
        return ActionResponse(
            action=Action.RESPONSE, result=str(e), response="播放白噪音时出错了"
        )



def initialize_white_noise_config(conn):
    global WHITE_NOISE_CONFIG
    if not WHITE_NOISE_CONFIG:
        # 获取基础API URL
        base_url = conn.config.get("api", {}).get("base_url", "https://qy-toy.airlabs.art")
        default_white_noise_url = f"{base_url}/api/v1/public/white-noise/random/"

        if "play_white_noise" in conn.config["plugins"]:
            WHITE_NOISE_CONFIG["remote_api_url"] = conn.config["plugins"]["play_white_noise"].get(
                "remote_api_url", default_white_noise_url
            )
            WHITE_NOISE_CONFIG["enable_remote_white_noise"] = conn.config["plugins"]["play_white_noise"].get(
                "enable_remote_white_noise", True
            )
        else:
            # 默认远程白噪音API配置
            WHITE_NOISE_CONFIG["remote_api_url"] = default_white_noise_url
            WHITE_NOISE_CONFIG["enable_remote_white_noise"] = True

        # 输出日志，便于调试
        conn.logger.bind(tag=TAG).info(f"远程白噪音API设置为: {WHITE_NOISE_CONFIG['remote_api_url']}")
        conn.logger.bind(tag=TAG).info(f"远程白噪音功能: {'启用' if WHITE_NOISE_CONFIG['enable_remote_white_noise'] else '禁用'}")

    return WHITE_NOISE_CONFIG


async def get_remote_white_noise(conn):
    """从远程API获取随机白噪音"""
    global WHITE_NOISE_CONFIG

    conn.logger.bind(tag=TAG).info("get_remote_white_noise 开始执行")

    if not WHITE_NOISE_CONFIG.get("enable_remote_white_noise", True):
        conn.logger.bind(tag=TAG).info("远程白噪音功能已禁用")
        return None

    if not conn.device_id:
        conn.logger.bind(tag=TAG).warning("设备ID为空，无法获取远程白噪音")
        return None

    try:
        # 构建API请求URL
        api_url = WHITE_NOISE_CONFIG["remote_api_url"]
        params = {"mac_address": conn.device_id}

        conn.logger.bind(tag=TAG).info(f"请求远程白噪音API: {api_url}")
        conn.logger.bind(tag=TAG).info(f"请求参数: {params}")

        # 暂时模拟成功的响应，测试函数调用
        conn.logger.bind(tag=TAG).info("模拟API调用成功")

        # 模拟返回数据
        white_noise_data = {
            "title": "测试白噪音",
            "audio_url": "http://example.com/test.mp3"
        }

        conn.logger.bind(tag=TAG).info(f"模拟获取白噪音: {white_noise_data.get('title', '未知标题')}")
        return white_noise_data

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"模拟API调用失败: {str(e)}")
        return None
    except json.JSONDecodeError as e:
        conn.logger.bind(tag=TAG).error(f"解析远程API响应失败: {str(e)}")
        return None
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"获取远程白噪音时发生未知错误: {str(e)}")
        conn.logger.bind(tag=TAG).debug(f"详细错误: {traceback.format_exc()}")
        return None


async def download_remote_white_noise(conn, white_noise_data):
    """模拟下载远程白噪音到临时文件"""
    try:
        conn.logger.bind(tag=TAG).info("模拟下载白噪音文件")

        # 模拟返回一个存在的音频文件路径（使用现有的音乐文件作为测试）
        test_audio_path = "/Users/maidong/Desktop/zyc/github/xiaozhi-esp32-server/main/xiaozhi-server/music/慢悠悠之歌2.mp3"

        if os.path.exists(test_audio_path):
            conn.logger.bind(tag=TAG).info(f"使用测试音频文件: {test_audio_path}")
            return test_audio_path
        else:
            conn.logger.bind(tag=TAG).error(f"测试音频文件不存在: {test_audio_path}")
            return None

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"模拟下载白噪音时发生错误: {str(e)}")
        conn.logger.bind(tag=TAG).debug(f"详细错误: {traceback.format_exc()}")
        return None


async def handle_white_noise_command(conn, text="播放随机白噪音"):
    conn.logger.bind(tag=TAG).info(f"handle_white_noise_command 开始执行: text={text}")
    conn.logger.bind(tag=TAG).info(f"play white noise on device {conn.device_id}")

    try:
        conn.logger.bind(tag=TAG).info("开始初始化白噪音配置")
        initialize_white_noise_config(conn)
        conn.logger.bind(tag=TAG).info("白噪音配置初始化完成")

        conn.logger.bind(tag=TAG).info("开始播放远程白噪音")
        await play_remote_white_noise(conn)
        conn.logger.bind(tag=TAG).info("远程白噪音播放流程完成")
        return True
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"handle_white_noise_command 执行失败: {e}")
        import traceback
        conn.logger.bind(tag=TAG).error(f"详细错误: {traceback.format_exc()}")
        return False


def _get_random_white_noise_prompt(noise_title):
    """生成随机播放引导语"""
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


async def play_remote_white_noise(conn):
    """播放远程白噪音"""
    temp_file_path = None

    try:
        # 获取远程白噪音
        remote_white_noise_data = await get_remote_white_noise(conn)

        if not remote_white_noise_data:
            conn.logger.bind(tag=TAG).error("无法获取远程白噪音")
            return

        # 下载远程白噪音到临时文件
        temp_file_path = await download_remote_white_noise(conn, remote_white_noise_data)
        if not temp_file_path:
            conn.logger.bind(tag=TAG).error("下载远程白噪音失败")
            return

        noise_title = remote_white_noise_data.get("title", "舒缓白噪音")
        conn.logger.bind(tag=TAG).info(f"成功获取远程白噪音: {noise_title}")

        # 使用白噪音标题生成播放提示语
        text = _get_random_white_noise_prompt(noise_title)
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
                content_file=temp_file_path,
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

        # 输出临时文件路径，方便调试
        conn.logger.bind(tag=TAG).info(f"远程白噪音临时文件路径: {temp_file_path}")

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"播放白噪音失败: {str(e)}")
        conn.logger.bind(tag=TAG).error(f"详细错误: {traceback.format_exc()}")
    finally:
        # 临时文件保留，方便调试
        if temp_file_path and os.path.exists(temp_file_path):
            conn.logger.bind(tag=TAG).info(f"临时文件保留: {temp_file_path}")