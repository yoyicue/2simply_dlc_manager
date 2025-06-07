"""
核心模块 - HTTP/2 优化版本
"""
from .models import FileItem, DownloadStatus, DownloadConfig
from .downloader import Downloader
from .persistence import DataManager
from .network import NetworkManager, AsyncHttpClient, NetworkConfig
from .resume import SmartResume, ResumeManager, NetworkRecovery
from .compression import CompressionManager, CompressionConfig, FileTypeAnalyzer
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
    'SmartResume',
    'ResumeManager',
    'NetworkRecovery',
    # 第三阶段：压缩传输优化
    'CompressionManager',
    'CompressionConfig',
    'FileTypeAnalyzer',
    'get_user_data_dir',
    'get_user_cache_dir', 
    'get_user_config_dir',
    'get_app_data_file',
    'get_app_cache_file',
    'is_running_from_bundle',
    'ensure_writable_path'
] 