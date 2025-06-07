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
    
    # 阶段一新增：元数据缓存字段
    mtime: Optional[float] = None  # 文件修改时间戳
    disk_verified: bool = False  # 磁盘验证标记
    last_checked: Optional[str] = None  # 最后检查时间 ISO格式
    cache_version: str = "1.0"  # 缓存版本号
    
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
    
    def update_disk_metadata(self, file_path: Path):
        """更新文件的磁盘元数据"""
        if file_path.exists():
            try:
                stat_info = file_path.stat()
                self.mtime = stat_info.st_mtime
                self.size = stat_info.st_size
                self.disk_verified = True
                from datetime import datetime
                self.last_checked = datetime.now().isoformat()
            except (OSError, IOError):
                self.disk_verified = False
    
    def is_cache_valid(self, file_path: Path, max_age_hours: int = 24) -> bool:
        """检查缓存是否仍然有效"""
        if not self.disk_verified or not self.last_checked:
            return False
        
        try:
            from datetime import datetime, timedelta
            last_check = datetime.fromisoformat(self.last_checked)
            
            # 检查缓存时间是否过期
            if datetime.now() - last_check > timedelta(hours=max_age_hours):
                return False
            
            # 快速检查文件是否存在且大小匹配
            if not file_path.exists():
                return False
            
            stat_info = file_path.stat()
            # 比较mtime和size，如果变化则缓存失效
            return (self.mtime == stat_info.st_mtime and 
                   self.size == stat_info.st_size)
        except:
            return False


@dataclass
class DownloadConfig:
    """下载配置 - 基于真实数据优化版本"""
    concurrent_requests: int = 80  # 基于15GB下载经验，提高到80
    timeout: int = 180  # 考虑到最大15MB文件，增加到180秒
    batch_size: int = 50  # 基于44K文件总量，增加到50
    retry_delay: float = 0.3  # 减少重试延迟到0.3秒
    asset_base_url: str = "https://assets.joytunes.com/play_assets"
    max_retries: int = 5
    chunk_size: int = 32768  # 增加到32KB，适应大文件
    connection_limit: int = 150  # 增加连接池到150
    connection_limit_per_host: int = 80  # 增加每主机连接到80
    
    # 新增：基于文件类型的差异化配置
    small_file_threshold: int = 100000  # 100KB以下为小文件
    large_file_threshold: int = 2000000  # 2MB以上为大文件
    
    # HTTP/2 网络优化配置
    use_http2: bool = True  # 启用HTTP/2
    enable_network_optimization: bool = True  # 启用网络优化
    auto_detect_http2: bool = True  # 自动检测HTTP/2支持
    fallback_to_http1: bool = True  # HTTP/2失败时降级到HTTP/1.1
    
    # 断点续传配置 - 第二阶段新增
    enable_resume: bool = True  # 启用断点续传
    min_resume_size: int = 2 * 1024 * 1024  # 2MB最小续传文件大小
    resume_timeout: int = 60  # 续传检测超时
    verify_integrity: bool = True  # 启用完整性校验
    
    # 网络恢复配置 - 高ROI自动化功能
    max_recovery_attempts: int = 5  # 最大网络恢复尝试次数
    recovery_base_delay: float = 1.0  # 基础重试延迟
    network_error_threshold: int = 3  # 网络错误阈值
    
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
    
    def get_optimal_batch_size(self, total_files: int, files_to_download: int, file_items=None) -> int:
        """根据实际需要下载的文件数量和文件类型计算最优批次大小"""
        if files_to_download == 0:
            return 1
        
        # 基础批次大小计算
        base_batch_size = self.batch_size
        
        # 根据文件数量调整
        if files_to_download <= 10:
            base_batch_size = min(5, files_to_download)
        elif files_to_download <= 50:
            base_batch_size = min(15, base_batch_size)
        elif files_to_download <= 200:
            base_batch_size = min(30, base_batch_size)
        
        # 根据跳过比例调整
        skip_ratio = (total_files - files_to_download) / total_files if total_files > 0 else 0
        
        if skip_ratio > 0.95:  # 超过95%的文件被跳过，说明增量下载
            base_batch_size = max(10, base_batch_size // 3)  # 大幅减小批次
        elif skip_ratio > 0.8:  # 超过80%的文件被跳过
            base_batch_size = max(15, base_batch_size // 2)  # 减小批次大小
        elif skip_ratio > 0.5:  # 超过50%的文件被跳过
            base_batch_size = max(20, base_batch_size * 2 // 3)  # 适当减小批次大小
        
        # 根据文件类型和大小进一步优化
        if file_items:
            large_files = sum(1 for item in file_items if getattr(item, 'size', 0) and item.size > self.large_file_threshold)
            small_files = sum(1 for item in file_items if getattr(item, 'size', 0) and item.size < self.small_file_threshold)
            
            large_ratio = large_files / len(file_items) if file_items else 0
            small_ratio = small_files / len(file_items) if file_items else 0
            
            if large_ratio > 0.3:  # 大文件占比超过30%
                base_batch_size = max(10, base_batch_size // 2)  # 减小批次，避免内存压力
            elif small_ratio > 0.8:  # 小文件占比超过80%
                base_batch_size = min(100, base_batch_size * 2)  # 增大批次，提高效率
        
        return max(1, base_batch_size)
    
    def get_optimal_concurrent_requests(self, total_files: int, files_to_download: int, file_items=None) -> int:
        """根据实际需要下载的文件数量和类型计算最优并发数"""
        optimal_batch_size = self.get_optimal_batch_size(total_files, files_to_download, file_items)
        
        # 基础并发数计算
        base_concurrent = self.concurrent_requests
        
        # 根据文件数量调整
        if files_to_download <= 5:
            return min(files_to_download, 5)  # 极小文件数时，并发数等于文件数
        elif files_to_download <= 20:
            base_concurrent = min(optimal_batch_size * 2, base_concurrent)  # 中等文件数时
        elif files_to_download <= 100:
            base_concurrent = min(optimal_batch_size * 3, base_concurrent)  # 较多文件时
        else:
            base_concurrent = min(optimal_batch_size * 4, base_concurrent)  # 大量文件时，提高并发倍数
        
        # 根据文件类型和大小调整并发数
        if file_items:
            large_files = sum(1 for item in file_items if getattr(item, 'size', 0) and item.size > self.large_file_threshold)
            small_files = sum(1 for item in file_items if getattr(item, 'size', 0) and item.size < self.small_file_threshold)
            
            large_ratio = large_files / len(file_items) if file_items else 0
            small_ratio = small_files / len(file_items) if file_items else 0
            
            if large_ratio > 0.5:  # 大文件占比超过50%
                base_concurrent = max(20, base_concurrent // 2)  # 减少并发，避免带宽竞争
            elif small_ratio > 0.8:  # 小文件占比超过80%
                base_concurrent = min(120, base_concurrent * 3 // 2)  # 增加并发，充分利用网络
            
            # 特殊处理：JSON文件通常较小，PNG文件较大
            json_files = sum(1 for item in file_items if item.filename.endswith('.json'))
            png_files = sum(1 for item in file_items if item.filename.endswith('.png'))
            
            json_ratio = json_files / len(file_items) if file_items else 0
            png_ratio = png_files / len(file_items) if file_items else 0
            
            if json_ratio > 0.7:  # JSON文件占主导
                base_concurrent = min(100, base_concurrent * 4 // 3)  # 适当增加并发
            elif png_ratio > 0.7:  # PNG文件占主导
                base_concurrent = max(30, base_concurrent * 3 // 4)  # 适当减少并发
        
        return max(5, min(base_concurrent, self.concurrent_requests))
    
    def get_adaptive_timeout(self, file_item=None) -> int:
        """根据文件大小自适应调整超时时间"""
        base_timeout = self.timeout
        
        if file_item and hasattr(file_item, 'size') and file_item.size:
            if file_item.size > self.large_file_threshold:
                # 大文件：按1MB/10秒计算，最少3分钟
                estimated_timeout = max(180, (file_item.size / 1024 / 1024) * 10)
                return min(int(estimated_timeout), base_timeout * 2)
            elif file_item.size < self.small_file_threshold:
                # 小文件：减少超时时间
                return max(60, base_timeout // 2)
        
        return base_timeout
    
    def get_adaptive_chunk_size(self, file_item=None) -> int:
        """根据文件大小自适应调整块大小"""
        base_chunk = self.chunk_size
        
        if file_item and hasattr(file_item, 'size') and file_item.size:
            if file_item.size > self.large_file_threshold:
                # 大文件使用更大的块
                return min(65536, base_chunk * 2)  # 最大64KB
            elif file_item.size < self.small_file_threshold:
                # 小文件使用较小的块
                return max(8192, base_chunk // 2)  # 最小8KB
        
        return base_chunk
    
    def create_network_config(self, file_items=None) -> 'NetworkConfig':
        """根据下载配置创建网络配置"""
        # 延迟导入避免循环依赖
        from .network import NetworkConfig
        
        # 根据文件数量和类型调整网络配置
        max_connections = self.connection_limit
        max_keepalive = self.connection_limit_per_host
        
        if file_items:
            file_count = len(file_items)
            if file_count > 10000:
                max_connections = min(150, max_connections)
                max_keepalive = min(80, max_keepalive)
            elif file_count < 100:
                max_connections = max(20, max_connections // 3)
                max_keepalive = max(10, max_keepalive // 3)
        
        return NetworkConfig(
            use_http2=self.use_http2 and self.enable_network_optimization,
            max_connections=max_connections,
            max_keepalive=max_keepalive,
            timeout_seconds=self.timeout,
            connect_timeout=min(30, self.timeout // 6),
            read_timeout=min(60, self.timeout // 3),
            enable_performance_tracking=True,
            connection_pool_stats=True
        ) 