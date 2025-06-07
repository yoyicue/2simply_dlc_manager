"""
核心工具函数模块
"""
import os
import sys
from pathlib import Path
from typing import Optional


def get_user_data_dir(app_name: str = "DLC Manager") -> Path:
    """
    获取用户数据目录路径
    
    Args:
        app_name: 应用名称，用于创建子目录
        
    Returns:
        用户数据目录路径
    """
    if sys.platform == "win32":
        # Windows: %APPDATA%/app_name
        appdata = os.environ.get('APPDATA')
        if appdata:
            user_dir = Path(appdata) / app_name
        else:
            user_dir = Path.home() / "AppData" / "Roaming" / app_name
    elif sys.platform == "darwin":
        # macOS: ~/Library/Application Support/app_name
        user_dir = Path.home() / "Library" / "Application Support" / app_name
    else:
        # Linux: ~/.local/share/app_name
        xdg_data_home = os.environ.get('XDG_DATA_HOME')
        if xdg_data_home:
            user_dir = Path(xdg_data_home) / app_name
        else:
            user_dir = Path.home() / ".local" / "share" / app_name
    
    # 确保目录存在
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def get_user_cache_dir(app_name: str = "DLC Manager") -> Path:
    """
    获取用户缓存目录路径
    
    Args:
        app_name: 应用名称，用于创建子目录
        
    Returns:
        用户缓存目录路径
    """
    if sys.platform == "win32":
        # Windows: %LOCALAPPDATA%/app_name/Cache
        localappdata = os.environ.get('LOCALAPPDATA')
        if localappdata:
            cache_dir = Path(localappdata) / app_name / "Cache"
        else:
            cache_dir = Path.home() / "AppData" / "Local" / app_name / "Cache"
    elif sys.platform == "darwin":
        # macOS: ~/Library/Caches/app_name
        cache_dir = Path.home() / "Library" / "Caches" / app_name
    else:
        # Linux: ~/.cache/app_name
        xdg_cache_home = os.environ.get('XDG_CACHE_HOME')
        if xdg_cache_home:
            cache_dir = Path(xdg_cache_home) / app_name
        else:
            cache_dir = Path.home() / ".cache" / app_name
    
    # 确保目录存在
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_user_config_dir(app_name: str = "DLC Manager") -> Path:
    """
    获取用户配置目录路径
    
    Args:
        app_name: 应用名称，用于创建子目录
        
    Returns:
        用户配置目录路径
    """
    if sys.platform == "win32":
        # Windows: 配置文件通常和数据文件在同一目录
        return get_user_data_dir(app_name)
    elif sys.platform == "darwin":
        # macOS: 配置文件通常和数据文件在同一目录
        return get_user_data_dir(app_name)
    else:
        # Linux: ~/.config/app_name
        xdg_config_home = os.environ.get('XDG_CONFIG_HOME')
        if xdg_config_home:
            config_dir = Path(xdg_config_home) / app_name
        else:
            config_dir = Path.home() / ".config" / app_name
    
    # 确保目录存在
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def is_running_from_bundle() -> bool:
    """
    检查是否从打包的应用程序运行
    
    Returns:
        如果从打包应用运行返回True，否则返回False
    """
    return (
        getattr(sys, 'frozen', False) or  # PyInstaller
        getattr(sys, '_MEIPASS', False) or  # PyInstaller临时目录
        'python' not in sys.executable.lower()  # 其他打包方式
    )


def get_app_data_file(filename: str, app_name: str = "DLC Manager") -> Path:
    """
    获取应用数据文件的完整路径
    
    Args:
        filename: 文件名
        app_name: 应用名称
        
    Returns:
        数据文件的完整路径
    """
    user_data_dir = get_user_data_dir(app_name)
    return user_data_dir / filename


def get_app_cache_file(filename: str, app_name: str = "DLC Manager") -> Path:
    """
    获取应用缓存文件的完整路径
    
    Args:
        filename: 文件名
        app_name: 应用名称
        
    Returns:
        缓存文件的完整路径
    """
    user_cache_dir = get_user_cache_dir(app_name)
    return user_cache_dir / filename


def ensure_writable_path(file_path: Path) -> Path:
    """
    确保路径是可写的，如果不可写则返回用户数据目录中的路径
    
    Args:
        file_path: 原始文件路径
        
    Returns:
        可写的文件路径
    """
    try:
        # 尝试在原路径创建测试文件
        test_file = file_path.parent / f".write_test_{os.getpid()}"
        test_file.touch()
        test_file.unlink()
        return file_path
    except (OSError, PermissionError):
        # 如果无法写入，使用用户数据目录
        return get_app_data_file(file_path.name) 