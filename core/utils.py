import os

ICON_PATH = os.path.join(os.path.dirname(__file__), '..', 'resources', 'icons')

def get_icon_path(icon_name):
    """获取图标完整路径"""
    return os.path.join(ICON_PATH, icon_name) 