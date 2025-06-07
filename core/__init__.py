"""
核心模块 - HTTP/2 优化版本
"""
from .models import FileItem, DownloadStatus, DownloadConfig
from .downloader import Downloader
from .persistence import DataManager
from .network import NetworkManager, AsyncHttpClient, NetworkConfig
from .utils import (
    get_user_data_dir, get_user_cache_dir, get_user_config_dir,
    get_app_data_file, get_app_cache_file, is_running_from_bundle,
    ensure_writable_path
)

__all__ = [
    'FileItem',
    'DownloadStatus', 
    'DownloadConfig',
    'Downloader',
    'DataManager',
    'NetworkManager',
    'AsyncHttpClient', 
    'NetworkConfig',
    'get_user_data_dir',
    'get_user_cache_dir', 
    'get_user_config_dir',
    'get_app_data_file',
    'get_app_cache_file',
    'is_running_from_bundle',
    'ensure_writable_path'
] 