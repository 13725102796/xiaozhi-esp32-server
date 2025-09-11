import requests
import json
import base64
import time
from bs4 import BeautifulSoup
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from core.utils.util import get_ip_info
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

TAG = __name__
logger = setup_logging()

GET_WEATHER_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": (
            "获取某个地点的天气，用户应提供一个位置，比如用户说杭州天气，参数为：杭州。"
            "如果用户说的是省份，默认用省会城市。如果用户说的不是省份或城市而是一个地名，默认用该地所在省份的省会城市。"
            "如果用户没有指明地点，说“天气怎么样”，”今天天气如何“，location参数为空"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "地点名，例如杭州。可选参数，如果不提供则不传",
                },
                "lang": {
                    "type": "string",
                    "description": "返回用户使用的语言code，例如zh_CN/zh_HK/en_US/ja_JP等，默认zh_CN",
                },
            },
            "required": ["lang"],
        },
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
    )
}

# 天气代码 https://dev.qweather.com/docs/resource/icons/#weather-icons
WEATHER_CODE_MAP = {
    "100": "晴",
    "101": "多云",
    "102": "少云",
    "103": "晴间多云",
    "104": "阴",
    "150": "晴",
    "151": "多云",
    "152": "少云",
    "153": "晴间多云",
    "300": "阵雨",
    "301": "强阵雨",
    "302": "雷阵雨",
    "303": "强雷阵雨",
    "304": "雷阵雨伴有冰雹",
    "305": "小雨",
    "306": "中雨",
    "307": "大雨",
    "308": "极端降雨",
    "309": "毛毛雨/细雨",
    "310": "暴雨",
    "311": "大暴雨",
    "312": "特大暴雨",
    "313": "冻雨",
    "314": "小到中雨",
    "315": "中到大雨",
    "316": "大到暴雨",
    "317": "暴雨到大暴雨",
    "318": "大暴雨到特大暴雨",
    "350": "阵雨",
    "351": "强阵雨",
    "399": "雨",
    "400": "小雪",
    "401": "中雪",
    "402": "大雪",
    "403": "暴雪",
    "404": "雨夹雪",
    "405": "雨雪天气",
    "406": "阵雨夹雪",
    "407": "阵雪",
    "408": "小到中雪",
    "409": "中到大雪",
    "410": "大到暴雪",
    "456": "阵雨夹雪",
    "457": "阵雪",
    "499": "雪",
    "500": "薄雾",
    "501": "雾",
    "502": "霾",
    "503": "扬沙",
    "504": "浮尘",
    "507": "沙尘暴",
    "508": "强沙尘暴",
    "509": "浓雾",
    "510": "强浓雾",
    "511": "中度霾",
    "512": "重度霾",
    "513": "严重霾",
    "514": "大雾",
    "515": "特强浓雾",
    "900": "热",
    "901": "冷",
    "999": "未知",
}


def base64url_encode(data):
    """Base64URL encode without padding"""
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')


def generate_jwt_token(kid, project_id, private_key_pem):
    """
    Generate JWT token for QWeather API authentication
    
    Args:
        kid: Credential ID from QWeather console
        project_id: Project ID from QWeather console  
        private_key_pem: Private key in PEM format
    
    Returns:
        JWT token string
    """
    # Header
    header = {
        "alg": "EdDSA",
        "kid": kid
    }
    
    # Payload
    current_time = int(time.time())
    payload = {
        "sub": project_id,
        "iat": current_time - 30,  # Set to 30 seconds before current time to prevent time errors
        "exp": current_time + 3600  # Expire in 1 hour
    }
    
    # Encode header and payload
    header_encoded = base64url_encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))
    payload_encoded = base64url_encode(json.dumps(payload, separators=(',', ':')).encode('utf-8'))
    
    # Create signing input
    signing_input = f"{header_encoded}.{payload_encoded}"
    
    # Load private key and sign
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode('utf-8'),
        password=None
    )
    
    signature = private_key.sign(signing_input.encode('utf-8'))
    signature_encoded = base64url_encode(signature)
    
    # Return complete JWT
    return f"{signing_input}.{signature_encoded}"


def fetch_city_info(location, api_key, api_host, kid=None, project_id=None, private_key=None):
    # Use JWT authentication if JWT parameters are provided
    if kid and project_id and private_key:
        try:
            logger.bind(tag=TAG).info(f"使用JWT认证，kid: {kid[:10]}..., project_id: {project_id[:10]}...")
            jwt_token = generate_jwt_token(kid, project_id, private_key)
            headers = HEADERS.copy()
            headers['Authorization'] = f'Bearer {jwt_token}'
            url = f"https://{api_host}/geo/v2/city/lookup?location={location}&lang=zh"
            logger.bind(tag=TAG).info(f"JWT请求URL: {url}")
            
            response = requests.get(url, headers=headers)
            logger.bind(tag=TAG).info(f"HTTP状态码: {response.status_code}")
            
            if response.status_code != 200:
                logger.bind(tag=TAG).error(f"HTTP请求失败: {response.status_code} - {response.text}")
                return None
                
            response_json = response.json()
            logger.bind(tag=TAG).info(f"API响应: {response_json}")
            
        except Exception as e:
            logger.bind(tag=TAG).error(f"JWT认证失败: {str(e)}")
            # Fallback to API key authentication
            logger.bind(tag=TAG).info("回退到API KEY认证")
            url = f"https://{api_host}/geo/v2/city/lookup?key={api_key}&location={location}&lang=zh"
            response = requests.get(url, headers=HEADERS)
            if response.status_code != 200:
                logger.bind(tag=TAG).error(f"API KEY认证也失败: {response.status_code} - {response.text}")
                return None
            response_json = response.json()
    else:
        # Fallback to API key authentication
        logger.bind(tag=TAG).info(f"使用API KEY认证: {api_key}")
        url = f"https://{api_host}/geo/v2/city/lookup?key={api_key}&location={location}&lang=zh"
        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200:
            logger.bind(tag=TAG).error(f"API KEY认证失败: {response.status_code} - {response.text}")
            return None
        response_json = response.json()
    
    if response_json.get("error") is not None:
        error_detail = response_json.get('error', {})
        logger.bind(tag=TAG).error(f"API错误 - 状态: {error_detail.get('status')}, 详情: {error_detail.get('detail')}")
        return None
    
    locations = response_json.get("location", [])
    if not locations:
        logger.bind(tag=TAG).warning(f"未找到位置信息: {location}")
        return None
        
    return locations[0]


def fetch_weather_page(url):
    logger.bind(tag=TAG).info(f"正在获取天气页面: {url}")
    response = requests.get(url, headers=HEADERS)
    logger.bind(tag=TAG).info(f"页面请求状态码: {response.status_code}")
    
    if response.ok:
        soup = BeautifulSoup(response.text, "html.parser")
        logger.bind(tag=TAG).info(f"页面内容长度: {len(response.text)}")
        logger.bind(tag=TAG).info(f"页面标题: {soup.title.string if soup.title else '无标题'}")
        return soup
    else:
        logger.bind(tag=TAG).error(f"获取天气页面失败: {response.status_code}")
        return None


def parse_weather_info(soup):
    try:
        # 尝试解析城市名称
        city_element = soup.select_one("h1.c-submenu__location")
        if city_element:
            city_name = city_element.get_text(strip=True)
            logger.bind(tag=TAG).info(f"成功解析城市名称: {city_name}")
        else:
            logger.bind(tag=TAG).warning("未找到城市名称元素，尝试其他选择器")
            # 尝试其他可能的选择器
            alt_selectors = ["h1", ".location", ".city-name", "title"]
            city_name = "未知城市"
            for selector in alt_selectors:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(strip=True)
                    logger.bind(tag=TAG).info(f"使用选择器 {selector} 找到: {text}")
                    city_name = text
                    break

        # 尝试解析当前天气摘要
        current_abstract = soup.select_one(".c-city-weather-current .current-abstract")
        if current_abstract:
            current_abstract = current_abstract.get_text(strip=True)
            logger.bind(tag=TAG).info(f"成功解析天气摘要: {current_abstract}")
        else:
            current_abstract = "未知"
            logger.bind(tag=TAG).warning("未找到天气摘要元素")

        # 尝试解析详细参数
        current_basic = {}
        basic_items = soup.select(".c-city-weather-current .current-basic .current-basic___item")
        logger.bind(tag=TAG).info(f"找到 {len(basic_items)} 个基本信息元素")
        
        for item in basic_items:
            parts = item.get_text(strip=True, separator=" ").split(" ")
            if len(parts) == 2:
                key, value = parts[1], parts[0]
                current_basic[key] = value
                logger.bind(tag=TAG).debug(f"解析基本信息: {key} = {value}")

        # 尝试解析7天预报
        temps_list = []
        forecast_rows = soup.select(".city-forecast-tabs__row")
        logger.bind(tag=TAG).info(f"找到 {len(forecast_rows)} 个预报行")
        
        for i, row in enumerate(forecast_rows[:7]):
            try:
                date_element = row.select_one(".date-bg .date")
                icon_element = row.select_one(".date-bg .icon")
                temp_elements = row.select(".tmp-cont .temp")
                
                if date_element and icon_element and temp_elements:
                    date = date_element.get_text(strip=True)
                    weather_code = icon_element["src"].split("/")[-1].split(".")[0]
                    weather = WEATHER_CODE_MAP.get(weather_code, "未知")
                    temps = [span.get_text(strip=True) for span in temp_elements]
                    high_temp, low_temp = (temps[0], temps[-1]) if len(temps) >= 2 else (None, None)
                    temps_list.append((date, weather, high_temp, low_temp))
                    logger.bind(tag=TAG).debug(f"解析第{i+1}天: {date} {weather} {high_temp}~{low_temp}")
                else:
                    logger.bind(tag=TAG).warning(f"第{i+1}天预报元素不完整")
            except Exception as e:
                logger.bind(tag=TAG).warning(f"解析第{i+1}天预报失败: {e}")

        if not temps_list:
            logger.bind(tag=TAG).error("未能解析任何预报数据，页面结构可能已更改")
            # 打印页面结构用于调试
            logger.bind(tag=TAG).debug(f"页面主要结构: {[tag.name for tag in soup.find_all()[:20]]}")

        return city_name, current_abstract, current_basic, temps_list
        
    except Exception as e:
        logger.bind(tag=TAG).error(f"解析天气信息时发生错误: {e}")
        return "解析失败", "无法获取", {}, []


@register_function("get_weather", GET_WEATHER_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def get_weather(conn, location: str = None, lang: str = "zh_CN"):
    from core.utils.cache.manager import cache_manager, CacheType

    # 硬编码配置参数
    api_host = "kq3aapg9h5.re.qweatherapi.com"
    api_key = "aa5ec0859c144ac7b33966e25eef5580"
    default_location = "北京"
    kid = "T45F5GTR8Y"
    project_id = "4N855TEVNN"
    private_key = """-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIA26lz31HoaZV17EjIGcyo9YNGGQ77/gOZU8Chw8wlWq
-----END PRIVATE KEY-----"""
    
    # Debug JWT configuration
    logger.bind(tag=TAG).info(f"使用硬编码JWT配置 - kid: {kid}, project_id: {project_id}")
    logger.bind(tag=TAG).info(f"✅ JWT认证已配置，将使用JWT认证访问: {api_host}")
    client_ip = conn.client_ip

    # 优先使用用户提供的location参数
    if not location:
        # 通过客户端IP解析城市
        if client_ip:
            # 先从缓存获取IP对应的城市信息
            cached_ip_info = cache_manager.get(CacheType.IP_INFO, client_ip)
            if cached_ip_info:
                location = cached_ip_info.get("city")
            else:
                # 缓存未命中，调用API获取
                ip_info = get_ip_info(client_ip, logger)
                if ip_info:
                    cache_manager.set(CacheType.IP_INFO, client_ip, ip_info)
                    location = ip_info.get("city")

            if not location:
                location = default_location
        else:
            # 若无IP，使用默认位置
            location = default_location
    # 尝试从缓存获取完整天气报告
    weather_cache_key = f"full_weather_{location}_{lang}"
    cached_weather_report = cache_manager.get(CacheType.WEATHER, weather_cache_key)
    if cached_weather_report:
        return ActionResponse(Action.REQLLM, cached_weather_report, None)

    # 缓存未命中，获取实时天气数据
    city_info = fetch_city_info(location, api_key, api_host, kid, project_id, private_key)
    if not city_info:
        return ActionResponse(
            Action.REQLLM, f"未找到相关的城市: {location}，请确认地点是否正确", None
        )
    soup = fetch_weather_page(city_info["fxLink"])
    if not soup:
        return ActionResponse(Action.REQLLM, None, "请求失败")
    city_name, current_abstract, current_basic, temps_list = parse_weather_info(soup)

    weather_report = f"您查询的位置是：{city_name}\n\n当前天气: {current_abstract}\n"

    # 添加有效的当前天气参数
    if current_basic:
        weather_report += "详细参数：\n"
        for key, value in current_basic.items():
            if value != "0":  # 过滤无效值
                weather_report += f"  · {key}: {value}\n"

    # 添加7天预报
    weather_report += "\n未来7天预报：\n"
    for date, weather, high, low in temps_list:
        weather_report += f"{date}: {weather}，气温 {low}~{high}\n"

    # 提示语
    weather_report += "\n（如需某一天的具体天气，请告诉我日期）"

    # 缓存完整的天气报告
    cache_manager.set(CacheType.WEATHER, weather_cache_key, weather_report)

    return ActionResponse(Action.REQLLM, weather_report, None)
