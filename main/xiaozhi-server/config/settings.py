import os
from config.config_loader import read_config, get_project_dir, load_config

# 全局变量存储本地配置路径
_local_config_path = None


default_config_file = "config.yaml"
config_file_valid = False


def set_local_config_path(path):
    """设置本地配置文件路径"""
    global _local_config_path
    _local_config_path = path

def check_config_file():
    global config_file_valid
    if config_file_valid:
        return
    """
    简化的配置检查，仅提示用户配置文件的使用情况
    """
    # 如果使用了本地配置文件，跳过原有检查
    if _local_config_path:
        local_config_full_path = get_project_dir() + _local_config_path
        if not os.path.exists(local_config_full_path):
            raise FileNotFoundError(f"找不到指定的本地配置文件：{_local_config_path}")
        config_file_valid = True
        print(f"使用本地配置文件：{_local_config_path}")
        return

    custom_config_file = get_project_dir() + "data/." + default_config_file
    if not os.path.exists(custom_config_file):
        raise FileNotFoundError(
            "找不到data/.config.yaml文件，请按教程确认该配置文件是否存在"
        )

    # 检查是否从API读取配置
    config = load_config(_local_config_path)
    if config.get("read_config_from_api", False):
        print("从API读取配置")
        old_config_origin = read_config(custom_config_file)
        if old_config_origin.get("selected_module") is not None:
            error_msg = "您的配置文件好像既包含智控台的配置又包含本地配置：\n"
            error_msg += "\n建议您：\n"
            error_msg += "1、将根目录的config_from_api.yaml文件复制到data下，重命名为.config.yaml\n"
            error_msg += "2、按教程配置好接口地址和密钥\n"
            raise ValueError(error_msg)
    config_file_valid = True
