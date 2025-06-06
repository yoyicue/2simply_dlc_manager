"""
数据模型定义
"""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class DownloadStatus(Enum):
    """下载状态枚举"""
    PENDING = "待下载"
    DOWNLOADING = "下载中"
    COMPLETED = "已完成"
    FAILED = "失败"
    CANCELLED = "已取消"
    SKIPPED = "已跳过"


@dataclass
class FileItem:
    """文件项数据模型"""
    filename: str
    md5: str
    status: DownloadStatus = DownloadStatus.PENDING
    progress: float = 0.0  # 0-100的进度百分比
    size: Optional[int] = None  # 文件大小（字节）
    downloaded_size: int = 0  # 已下载大小（字节）
    local_path: Optional[Path] = None  # 本地保存路径
    error_message: Optional[str] = None  # 错误信息
    download_url: Optional[str] = None  # 下载URL
    
    @property
    def file_extension(self) -> str:
        """获取文件扩展名"""
        return Path(self.filename).suffix.lower()
    
    @property
    def base_filename(self) -> str:
        """获取不含扩展名的文件名"""
        return Path(self.filename).stem
    
    @property
    def full_filename(self) -> str:
        """获取完整的本地文件名（包含MD5）"""
        return f"{self.base_filename}-{self.md5}{self.file_extension}"
    
    @property
    def is_binary_file(self) -> bool:
        """判断是否为二进制文件"""
        binary_extensions = {
            # 图像文件
            '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.ico', '.tiff', '.svg',
            # 音频文件  
            '.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg', '.wma', '.opus',
            # 视频文件
            '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv', '.m4v',
            # 其他二进制文件
            '.zip', '.rar', '.7z', '.tar', '.gz', '.pdf', '.exe', '.dll'
        }
        return self.file_extension in binary_extensions
    
    def reset_progress(self):
        """重置下载进度"""
        self.progress = 0.0
        self.downloaded_size = 0
        self.status = DownloadStatus.PENDING
        self.error_message = None
    
    def mark_completed(self, local_path: Path):
        """标记为下载完成"""
        self.status = DownloadStatus.COMPLETED
        self.progress = 100.0
        self.local_path = local_path
        if local_path.exists():
            self.size = local_path.stat().st_size
            self.downloaded_size = self.size
    
    def mark_failed(self, error_message: str):
        """标记为下载失败"""
        self.status = DownloadStatus.FAILED
        self.error_message = error_message
    
    def mark_skipped(self, reason: str):
        """标记为跳过"""
        self.status = DownloadStatus.SKIPPED
        self.error_message = reason


@dataclass
class DownloadConfig:
    """下载配置"""
    concurrent_requests: int = 50  # 提高并发数到50
    timeout: int = 120  # 增加超时时间到120秒
    batch_size: int = 20  # 增加批次大小到20
    retry_delay: float = 0.5  # 减少重试延迟到0.5秒
    asset_base_url: str = "https://assets.joytunes.com/play_assets"
    max_retries: int = 5  # 增加重试次数到5
    chunk_size: int = 16384  # 添加块大小配置(16KB)
    connection_limit: int = 100  # 添加连接池限制
    connection_limit_per_host: int = 50  # 添加每主机连接限制
    
    def __post_init__(self):
        """验证配置参数"""
        if self.concurrent_requests <= 0:
            self.concurrent_requests = 1
        if self.timeout <= 0:
            self.timeout = 60
        if self.batch_size <= 0:
            self.batch_size = 1
        if self.chunk_size <= 0:
            self.chunk_size = 8192
        if self.connection_limit <= 0:
            self.connection_limit = 100
        if self.connection_limit_per_host <= 0:
            self.connection_limit_per_host = 50
    
    def get_optimal_batch_size(self, total_files: int, files_to_download: int) -> int:
        """根据实际需要下载的文件数量计算最优批次大小"""
        if files_to_download == 0:
            return 1
        
        # 如果需要下载的文件很少，减小批次大小
        if files_to_download <= 10:
            return min(5, files_to_download)
        elif files_to_download <= 50:
            return min(10, self.batch_size)
        else:
            # 根据跳过比例调整批次大小
            skip_ratio = (total_files - files_to_download) / total_files
            if skip_ratio > 0.8:  # 超过80%的文件被跳过
                return max(5, self.batch_size // 2)  # 减小批次大小
            elif skip_ratio > 0.5:  # 超过50%的文件被跳过
                return max(10, self.batch_size * 2 // 3)  # 适当减小批次大小
            else:
                return self.batch_size  # 使用默认批次大小
    
    def get_optimal_concurrent_requests(self, total_files: int, files_to_download: int) -> int:
        """根据实际需要下载的文件数量计算最优并发数"""
        optimal_batch_size = self.get_optimal_batch_size(total_files, files_to_download)
        
        # 并发数不应该超过批次大小太多，避免资源浪费
        # 但也要保持一定的并发度以提高效率
        if files_to_download <= 5:
            return min(files_to_download, 5)  # 极小文件数时，并发数等于文件数
        elif files_to_download <= 20:
            return min(optimal_batch_size * 2, self.concurrent_requests)  # 中等文件数时，并发数为批次大小的2倍
        else:
            return min(optimal_batch_size * 3, self.concurrent_requests)  # 大量文件时，并发数为批次大小的3倍 