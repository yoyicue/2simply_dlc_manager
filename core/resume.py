"""
智能断点续传模块 - Day 2用户体验优化版本
支持大文件断点续传、网络中断恢复、完整性校验、性能监控
"""
import asyncio
import aiofiles
import hashlib
import time
import json
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, Callable, Union, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
from enum import Enum

from .models import FileItem, DownloadStatus
from .network import AsyncHttpClient


class HashAlgorithm(Enum):
    """支持的哈希算法"""
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    SHA512 = "sha512"
    CRC32 = "crc32"


@dataclass
class IntegrityResult:
    """完整性校验结果"""
    is_valid: bool
    algorithm: HashAlgorithm
    expected_hash: str
    calculated_hash: str
    file_size: int
    verification_time: float
    error_message: Optional[str] = None
    
    @property
    def hash_match(self) -> bool:
        """哈希值是否匹配"""
        return self.expected_hash.lower() == self.calculated_hash.lower()
    
    @property
    def summary(self) -> str:
        """获取校验结果摘要"""
        if self.is_valid:
            return f"✅ {self.algorithm.value.upper()}校验通过 (耗时{self.verification_time:.1f}s)"
        else:
            return f"❌ {self.algorithm.value.upper()}不匹配: 期望{self.expected_hash[:8]}...，实际{self.calculated_hash[:8]}..."


@dataclass
class IntegrityCache:
    """完整性校验缓存"""
    file_path: str
    file_size: int
    mtime: float
    algorithm: HashAlgorithm
    hash_value: str
    verification_time: float
    cache_timestamp: str
    
    def is_valid(self, current_path: Path) -> bool:
        """检查缓存是否仍然有效"""
        try:
            if not current_path.exists():
                return False
            
            stat_info = current_path.stat()
            return (stat_info.st_size == self.file_size and 
                   stat_info.st_mtime == self.mtime)
        except:
            return False


@dataclass
class ProgressInfo:
    """详细进度信息 - Day 2 新增"""
    current_bytes: int = 0
    total_bytes: Optional[int] = None
    speed_bps: float = 0.0  # 字节/秒
    eta_seconds: Optional[float] = None
    start_time: float = field(default_factory=time.time)
    last_update_time: float = field(default_factory=time.time)
    
    @property
    def progress_percent(self) -> float:
        if not self.total_bytes or self.total_bytes == 0:
            return 0.0
        return min((self.current_bytes / self.total_bytes) * 100, 100.0)
    
    @property
    def elapsed_time(self) -> float:
        return time.time() - self.start_time
    
    def update_speed(self, new_bytes: int):
        """更新下载速度计算"""
        current_time = time.time()
        time_diff = current_time - self.last_update_time
        
        if time_diff > 0:
            byte_diff = new_bytes - self.current_bytes
            self.speed_bps = byte_diff / time_diff
            
            # 计算预计剩余时间
            if self.total_bytes and self.speed_bps > 0:
                remaining_bytes = self.total_bytes - new_bytes
                self.eta_seconds = remaining_bytes / self.speed_bps
        
        self.current_bytes = new_bytes
        self.last_update_time = current_time


@dataclass
class ResumeConfig:
    """断点续传配置"""
    min_resume_size: int = 2 * 1024 * 1024  # 2MB
    chunk_size: int = 64 * 1024  # 64KB
    max_retries: int = 5
    retry_delay: float = 1.0
    enable_integrity_cache: bool = True
    integrity_cache_max_age: int = 24  # 小时
    supported_algorithms: List[HashAlgorithm] = field(default_factory=lambda: [
        HashAlgorithm.MD5, HashAlgorithm.SHA1, HashAlgorithm.SHA256
    ])


class IntegrityManager:
    """完整性校验管理器 - Day 2 增强版本"""
    
    def __init__(self, config: ResumeConfig, cache_dir: Optional[Path] = None):
        self.config = config
        self.cache_dir = cache_dir or Path.home() / ".dlc_manager" / "integrity_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "integrity_cache.json"
        self._cache: Dict[str, IntegrityCache] = {}
        self._load_cache()
    
    def _load_cache(self):
        """加载完整性校验缓存"""
        if not self.config.enable_integrity_cache or not self.cache_file.exists():
            return
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            for key, data in cache_data.items():
                self._cache[key] = IntegrityCache(
                    file_path=data['file_path'],
                    file_size=data['file_size'],
                    mtime=data['mtime'],
                    algorithm=HashAlgorithm(data['algorithm']),
                    hash_value=data['hash_value'],
                    verification_time=data['verification_time'],
                    cache_timestamp=data['cache_timestamp']
                )
        except Exception as e:
            print(f"⚠️ 加载完整性缓存失败: {e}")
            self._cache = {}
    
    def _save_cache(self):
        """保存完整性校验缓存"""
        if not self.config.enable_integrity_cache:
            return
        
        try:
            cache_data = {}
            for key, cache_item in self._cache.items():
                cache_data[key] = {
                    'file_path': cache_item.file_path,
                    'file_size': cache_item.file_size,
                    'mtime': cache_item.mtime,
                    'algorithm': cache_item.algorithm.value,
                    'hash_value': cache_item.hash_value,
                    'verification_time': cache_item.verification_time,
                    'cache_timestamp': cache_item.cache_timestamp
                }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ 保存完整性缓存失败: {e}")
    
    def _get_cache_key(self, file_path: Path, algorithm: HashAlgorithm) -> str:
        """生成缓存键"""
        return f"{file_path.absolute()}:{algorithm.value}"
    
    def _detect_algorithm(self, hash_value: str) -> HashAlgorithm:
        """根据哈希值长度检测算法"""
        hash_length = len(hash_value)
        if hash_length == 32:
            return HashAlgorithm.MD5
        elif hash_length == 40:
            return HashAlgorithm.SHA1
        elif hash_length == 64:
            return HashAlgorithm.SHA256
        elif hash_length == 128:
            return HashAlgorithm.SHA512
        elif hash_length == 8:
            return HashAlgorithm.CRC32
        else:
            # 默认使用MD5
            return HashAlgorithm.MD5
    
    def calculate_hash_with_progress(self, file_path: Path, algorithm: HashAlgorithm,
                                   progress_callback: Optional[Callable] = None) -> str:
        """带进度的哈希计算 - 支持多种算法"""
        # 创建哈希对象
        if algorithm == HashAlgorithm.MD5:
            hasher = hashlib.md5()
        elif algorithm == HashAlgorithm.SHA1:
            hasher = hashlib.sha1()
        elif algorithm == HashAlgorithm.SHA256:
            hasher = hashlib.sha256()
        elif algorithm == HashAlgorithm.SHA512:
            hasher = hashlib.sha512()
        elif algorithm == HashAlgorithm.CRC32:
            import zlib
            crc_value = 0
        else:
            raise ValueError(f"不支持的哈希算法: {algorithm}")
        
        file_size = file_path.stat().st_size
        processed = 0
        start_time = time.time()
        last_update = start_time
        
        with open(file_path, 'rb') as f:
            while chunk := f.read(self.config.chunk_size):
                if algorithm == HashAlgorithm.CRC32:
                    crc_value = zlib.crc32(chunk, crc_value)
                else:
                    hasher.update(chunk)
                
                processed += len(chunk)
                current_time = time.time()
                
                # 每500ms或每1MB更新一次进度
                if (current_time - last_update >= 0.5 or 
                    processed % (1024*1024) < self.config.chunk_size) and progress_callback and file_size > 0:
                    
                    progress = (processed / file_size) * 100
                    elapsed = current_time - start_time
                    if elapsed > 0:
                        speed_mb = (processed / elapsed) / (1024 * 1024)
                        eta = (file_size - processed) / (processed / elapsed) if processed > 0 else 0
                        progress_callback(
                            f"🔍 {algorithm.value.upper()}校验进度: {progress:.1f}% "
                            f"({processed/1024/1024:.1f}MB/{file_size/1024/1024:.1f}MB) "
                            f"速度:{speed_mb:.1f}MB/s 剩余:{eta:.0f}s"
                        )
                    last_update = current_time
        
        if algorithm == HashAlgorithm.CRC32:
            return f"{crc_value & 0xffffffff:08x}"
        else:
            return hasher.hexdigest()
    
    def verify_integrity_enhanced(self, file_item: FileItem, local_path: Path,
                                progress_callback: Optional[Callable] = None) -> IntegrityResult:
        """增强的完整性校验 - 支持多算法、缓存、增量校验"""
        if not local_path.exists():
            return IntegrityResult(
                is_valid=False,
                algorithm=HashAlgorithm.MD5,
                expected_hash="",
                calculated_hash="",
                file_size=0,
                verification_time=0.0,
                error_message="文件不存在"
            )
        
        file_size = local_path.stat().st_size
        
        # 检查文件大小
        if file_item.size and file_size != file_item.size:
            return IntegrityResult(
                is_valid=False,
                algorithm=HashAlgorithm.MD5,
                expected_hash=file_item.md5 or "",
                calculated_hash="",
                file_size=file_size,
                verification_time=0.0,
                error_message=f"文件大小不匹配: 期望{file_item.size}字节，实际{file_size}字节"
            )
        
        # 检查哈希值
        if not file_item.md5:
            return IntegrityResult(
                is_valid=True,
                algorithm=HashAlgorithm.MD5,
                expected_hash="",
                calculated_hash="",
                file_size=file_size,
                verification_time=0.0,
                error_message="无哈希信息，仅验证文件大小"
            )
        
        # 检测哈希算法
        algorithm = self._detect_algorithm(file_item.md5)
        cache_key = self._get_cache_key(local_path, algorithm)
        
        # 检查缓存
        if self.config.enable_integrity_cache and cache_key in self._cache:
            cached_result = self._cache[cache_key]
            if cached_result.is_valid(local_path):
                if progress_callback:
                    progress_callback(f"🚀 使用缓存的{algorithm.value.upper()}校验结果")
                
                return IntegrityResult(
                    is_valid=cached_result.hash_value.lower() == file_item.md5.lower(),
                    algorithm=algorithm,
                    expected_hash=file_item.md5,
                    calculated_hash=cached_result.hash_value,
                    file_size=file_size,
                    verification_time=0.0  # 缓存命中，时间为0
                )
        
        # 执行实际校验
        if progress_callback:
            progress_callback(f"🔍 开始{algorithm.value.upper()}完整性校验 ({file_size/1024/1024:.1f}MB)...")
        
        try:
            start_time = time.time()
            calculated_hash = self.calculate_hash_with_progress(local_path, algorithm, progress_callback)
            verification_time = time.time() - start_time
            
            is_valid = calculated_hash.lower() == file_item.md5.lower()
            
            # 保存到缓存
            if self.config.enable_integrity_cache:
                stat_info = local_path.stat()
                self._cache[cache_key] = IntegrityCache(
                    file_path=str(local_path.absolute()),
                    file_size=file_size,
                    mtime=stat_info.st_mtime,
                    algorithm=algorithm,
                    hash_value=calculated_hash,
                    verification_time=verification_time,
                    cache_timestamp=datetime.now().isoformat()
                )
                self._save_cache()
            
            result = IntegrityResult(
                is_valid=is_valid,
                algorithm=algorithm,
                expected_hash=file_item.md5,
                calculated_hash=calculated_hash,
                file_size=file_size,
                verification_time=verification_time
            )
            
            if progress_callback:
                progress_callback(result.summary)
            
            return result
            
        except Exception as e:
            error_msg = f"{algorithm.value.upper()}计算失败: {str(e)}"
            if progress_callback:
                progress_callback(f"❌ {error_msg}")
            
            return IntegrityResult(
                is_valid=False,
                algorithm=algorithm,
                expected_hash=file_item.md5,
                calculated_hash="",
                file_size=file_size,
                verification_time=0.0,
                error_message=error_msg
            )
    
    def batch_verify_integrity(self, file_items: List[Tuple[FileItem, Path]],
                             progress_callback: Optional[Callable] = None) -> List[IntegrityResult]:
        """批量完整性校验 - 优化性能"""
        results = []
        total_files = len(file_items)
        
        for idx, (file_item, local_path) in enumerate(file_items):
            if progress_callback:
                progress_callback(f"📋 批量校验进度: {idx+1}/{total_files}")
            
            result = self.verify_integrity_enhanced(file_item, local_path, progress_callback)
            results.append(result)
        
        return results
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        if not self.config.enable_integrity_cache:
            return {"enabled": False}
        
        total_entries = len(self._cache)
        algorithms_count = defaultdict(int)
        total_verification_time = 0.0
        
        for cache_item in self._cache.values():
            algorithms_count[cache_item.algorithm.value] += 1
            total_verification_time += cache_item.verification_time
        
        return {
            "enabled": True,
            "total_entries": total_entries,
            "algorithms_distribution": dict(algorithms_count),
            "total_saved_time": total_verification_time,
            "cache_file_size": self.cache_file.stat().st_size if self.cache_file.exists() else 0
        }
    
    def cleanup_cache(self, max_age_hours: int = None):
        """清理过期缓存"""
        if not self.config.enable_integrity_cache:
            return
        
        max_age = max_age_hours or self.config.integrity_cache_max_age
        cutoff_time = datetime.now() - timedelta(hours=max_age)
        
        cleaned_count = 0
        for key in list(self._cache.keys()):
            cache_item = self._cache[key]
            try:
                cache_time = datetime.fromisoformat(cache_item.cache_timestamp)
                if cache_time < cutoff_time:
                    del self._cache[key]
                    cleaned_count += 1
            except:
                # 无效的时间戳，删除
                del self._cache[key]
                cleaned_count += 1
        
        if cleaned_count > 0:
            self._save_cache()
            print(f"🧹 清理了 {cleaned_count} 个过期缓存条目")


class ResumeManager:
    """断点续传管理器 - Day 2 增强版本"""
    
    def __init__(self, config: ResumeConfig = None):
        self.config = config or ResumeConfig()
        self.integrity_manager = IntegrityManager(self.config)
        self.session_stats = {
            'resume_attempts': 0,
            'resume_successes': 0,
            'bytes_resumed': 0,
            'time_saved': 0.0
        }
    
    async def probe_resume_support(self, client: AsyncHttpClient, url: str) -> Dict[str, Any]:
        """探测服务器断点续传支持 - Day 2 智能缓存版本"""
        
        # 1. 检查缓存
        domain = url.split('/')[2] if url.startswith('http') else url.split('/')[0]
        if domain in self.server_capabilities:
            cached = self.server_capabilities[domain]
            if time.time() - cached['cached_at'] < 3600:  # 1小时缓存
                return cached['info']
        
        try:
            # 2. 先尝试HEAD请求
            response_info = await client.head_request(url)
            
            basic_info = {
                'supports_range': response_info.get('accept_ranges', False),
                'content_length': response_info.get('content_length'),
                'etag': response_info.get('etag'),
                'last_modified': response_info.headers.get('last-modified'),
                'status_code': response_info['status_code'],
                'server_type': response_info.headers.get('server', 'unknown')
            }
            
            # 3. 如果声称支持Range，进行实际测试
            if basic_info['supports_range'] and basic_info['content_length']:
                content_length = int(basic_info['content_length'])
                if content_length > 1024:  # 只对大于1KB的文件测试
                    # 请求前512字节进行Range测试
                    range_test = await self._test_range_request(client, url, 0, 511)
                    basic_info['range_test_passed'] = range_test
                    basic_info['actually_supports_range'] = range_test
                else:
                    basic_info['range_test_passed'] = True
                    basic_info['actually_supports_range'] = True
            else:
                basic_info['range_test_passed'] = False
                basic_info['actually_supports_range'] = False
            
            # 4. 缓存结果
            self.server_capabilities[domain] = {
                'info': basic_info,
                'cached_at': time.time()
            }
            
            return basic_info
            
        except Exception as e:
            return {
                'supports_range': False,
                'actually_supports_range': False,
                'range_test_passed': False,
                'error': str(e),
                'status_code': 0
            }
    
    async def _test_range_request(self, client: AsyncHttpClient, url: str, 
                                start: int, end: int) -> bool:
        """实际测试Range请求 - Day 2 新增"""
        try:
            headers = {'Range': f'bytes={start}-{end}'}
            async with client.stream_download(url, headers) as response:
                if response.status_code == 206:  # Partial Content
                    # 读取一些数据确认Range工作正常
                    chunk_count = 0
                    async for chunk in response.iter_chunks():
                        chunk_count += 1
                        if chunk_count >= 3:  # 读取几个chunk就够了
                            break
                    return True
                return False
        except Exception:
            return False
    
    def should_resume(self, file_item: FileItem, local_path: Path) -> Tuple[bool, str]:
        """判断是否应该断点续传 - O(1)判断，返回原因"""
        # 基本条件检查
        if not local_path.exists():
            return False, "文件不存在"
        
        local_size = local_path.stat().st_size
        
        # 文件太小不值得续传
        if local_size < self.config.min_resume_size:
            return False, f"文件过小({local_size/1024:.1f}KB < {self.config.min_resume_size/1024:.1f}KB)"
        
        # 如果知道总大小，检查是否完整
        if file_item.size and local_size >= file_item.size:
            return False, "文件已完整"
        
        return True, f"可续传({local_size/1024/1024:.1f}MB已下载)"
    
    async def resume_download(self, client: AsyncHttpClient, file_item: FileItem, 
                            url: str, local_path: Path, 
                            progress_callback: Optional[Callable] = None) -> bool:
        """执行断点续传下载 - Day 2 增强进度版本"""
        
        # 1. 检查本地文件状态
        should_resume, reason = self.should_resume(file_item, local_path)
        if not should_resume:
            if progress_callback:
                progress_callback(f"⚠️ 无法续传: {reason}")
            return False
        
        local_size = local_path.stat().st_size
        self.session_stats['resume_attempts'] += 1
        
        # 2. 构建Range请求头
        headers = {
            'Range': f'bytes={local_size}-'
        }
        
        # 3. 发起Range请求
        try:
            start_time = time.time()
            progress_info = ProgressInfo(current_bytes=local_size, total_bytes=file_item.size)
            
            if progress_callback:
                progress_callback(f"🔄 续传开始: 从{local_size/1024/1024:.1f}MB处继续...")
            
            async with client.stream_download(url, headers) as response:
                # 检查服务器是否支持Range
                if response.status_code not in (206, 416):  # 206=Partial Content, 416=Range Not Satisfiable
                    if progress_callback:
                        progress_callback(f"⚠️ 服务器返回状态码{response.status_code}，不支持续传")
                    return False
                
                if response.status_code == 416:
                    # 文件已完整，无需续传
                    if progress_callback:
                        progress_callback("✅ 文件已完整，无需续传")
                    self.session_stats['resume_successes'] += 1
                    return True
                
                # 4. 续写文件
                async with aiofiles.open(local_path, 'ab') as f:  # append binary
                    resumed_bytes = 0  # 本次续传的字节数
                    chunk_count = 0
                    last_progress_update = time.time()
                    
                    async for chunk in response.iter_chunks():
                        await f.write(chunk)
                        resumed_bytes += len(chunk)
                        chunk_count += 1
                        
                        # 优化的进度更新 - 避免频繁更新
                        current_time = time.time()
                        if current_time - last_progress_update >= 0.5:  # 500ms更新一次
                            current_size = local_size + resumed_bytes
                            progress_info.update_speed(current_size)
                            
                            if progress_callback:
                                speed_mb = progress_info.speed_bps / (1024 * 1024)
                                if progress_info.eta_seconds:
                                    eta_str = f"，预计{progress_info.eta_seconds:.0f}秒完成"
                                else:
                                    eta_str = ""
                                    
                                progress_callback(
                                    f"📥 续传中: {progress_info.progress_percent:.1f}% "
                                    f"({speed_mb:.1f}MB/s{eta_str})"
                                )
                            
                            # 更新FileItem进度
                            if file_item.size:
                                file_item.progress = progress_info.progress_percent
                                file_item.downloaded_size = current_size
                            
                            last_progress_update = current_time
                
                # 5. 统计续传效果
                elapsed_time = time.time() - start_time
                self.session_stats['resume_successes'] += 1
                self.session_stats['bytes_resumed'] += local_size  # 节省的字节数
                
                # 估算节省的时间（假设平均速度）
                if resumed_bytes > 0 and elapsed_time > 0:
                    avg_speed = resumed_bytes / elapsed_time
                    estimated_saved_time = local_size / avg_speed if avg_speed > 0 else 0
                    self.session_stats['time_saved'] += estimated_saved_time
                
                if progress_callback:
                    progress_callback(f"✅ 续传完成！节省了{local_size/1024/1024:.1f}MB的重复下载")
                
                return True
                
        except Exception as e:
            # 续传失败，回退到完整下载
            self.session_stats['resume_successes'] -= 1
            if progress_callback:
                progress_callback(f"⚠️ 续传失败: {str(e)}，将使用完整下载")
            return False
    
    def calculate_md5_with_progress(self, file_path: Path, 
                                  progress_callback: Optional[Callable] = None, 
                                  chunk_size: int = 64*1024) -> str:
        """带进度的MD5计算 - Day 2 优化版本（保持向后兼容）"""
        return self.integrity_manager.calculate_hash_with_progress(
            file_path, HashAlgorithm.MD5, progress_callback
        )
    
    def verify_integrity(self, file_item: FileItem, local_path: Path, 
                        progress_callback: Optional[Callable] = None) -> Tuple[bool, str]:
        """验证文件完整性 - Day 2 增强版本，返回详细结果（保持向后兼容）"""
        result = self.integrity_manager.verify_integrity_enhanced(file_item, local_path, progress_callback)
        return result.is_valid, result.summary if result.is_valid else result.error_message or result.summary
    
    def get_stats_summary(self) -> str:
        """获取统计摘要 - Day 2 新增"""
        return (
            f"断点续传统计: 成功率{(self.session_stats['resume_successes'] / self.session_stats['resume_attempts']) * 100:.1f}% "
            f"({self.session_stats['resume_successes']}/{self.session_stats['resume_attempts']}) "
            f"节省流量{self.session_stats['bytes_resumed']/1024/1024:.1f}MB "
            f"节省时间{self.session_stats['time_saved']/60:.1f}分钟"
        )


class NetworkRecovery:
    """网络恢复机制 - Day 2 增强版本"""
    
    def __init__(self, max_retries: int = 5, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.error_stats = defaultdict(int)
    
    async def download_with_recovery(self, download_func, progress_callback=None, *args, **kwargs):
        """带网络恢复的下载包装器 - Day 2 增强版本"""
        
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return await download_func(*args, **kwargs)
            
            except (asyncio.TimeoutError, ConnectionError, OSError) as e:
                last_error = e
                error_type = self.classify_error(e)
                self.error_stats[error_type] += 1
                
                if attempt == self.max_retries - 1:
                    if progress_callback:
                        progress_callback(f"❌ 重试{self.max_retries}次后仍然失败: {str(e)}")
                    raise e
                
                # 指数退避策略
                delay = min(self.base_delay * (2 ** attempt), 16.0)
                
                if progress_callback:
                    progress_callback(
                        f"⚠️ 网络错误 ({error_type})，{delay:.1f}秒后重试 "
                        f"(第{attempt + 1}次/共{self.max_retries}次): {str(e)[:50]}..."
                    )
                
                await asyncio.sleep(delay)
            
            except Exception as e:
                # 非网络错误，记录并直接抛出
                error_type = self.classify_error(e)
                self.error_stats[error_type] += 1
                
                if progress_callback:
                    progress_callback(f"❌ 致命错误 ({error_type}): {str(e)}")
                raise e
        
        # 如果到这里，说明重试次数用尽
        if progress_callback:
            progress_callback(f"❌ 超过最大重试次数({self.max_retries})，放弃下载")
        raise last_error
    
    def classify_error(self, error: Exception) -> str:
        """错误分类 - Day 2 精准分析"""
        error_str = str(error).lower()
        
        if isinstance(error, asyncio.TimeoutError) or 'timeout' in error_str:
            return "timeout"
        elif isinstance(error, ConnectionError) or 'connection' in error_str:
            return "connection"
        elif 'http 5' in error_str or '50' in error_str:
            return "server_error"
        elif 'http 4' in error_str or ('40' in error_str and 'http' in error_str):
            return "client_error"
        elif 'ssl' in error_str or 'certificate' in error_str:
            return "ssl_error"
        elif 'dns' in error_str or 'resolve' in error_str:
            return "dns_error"
        else:
            return "unknown"
    
    def get_error_summary(self) -> str:
        """获取错误统计摘要 - Day 2 新增"""
        if not self.error_stats:
            return "无网络错误记录"
        
        total_errors = sum(self.error_stats.values())
        summary_parts = [f"网络错误统计(共{total_errors}次)"]
        
        for error_type, count in self.error_stats.items():
            percentage = (count / total_errors) * 100
            summary_parts.append(f"{error_type}:{count}次({percentage:.1f}%)")
        
        return " ".join(summary_parts)


# 集成到现有下载器的简化接口
class SmartResume:
    """智能断点续传门面类 - Day 2 完整优化版本"""
    
    def __init__(self, progress_callback: Optional[Callable] = None):
        self.resume_manager = ResumeManager()
        self.network_recovery = NetworkRecovery()
        self.progress_callback = progress_callback  # 进度回调函数
        self.session_stats = {
            'total_downloads': 0,
            'successful_downloads': 0,
            'resumed_downloads': 0,
            'bytes_downloaded': 0,
            'start_time': time.time()
        }
    
    async def smart_download(self, client: AsyncHttpClient, file_item: FileItem, 
                           url: str, local_path: Path) -> bool:
        """智能下载 - Day 2 完整优化版本"""
        
        self.session_stats['total_downloads'] += 1
        download_start = time.time()
        
        try:
            # 1. 预检查服务器支持 - 带缓存
            if self.progress_callback:
                self.progress_callback("🔍 检查服务器断点续传支持...")
                
            server_info = await self.resume_manager.probe_resume_support(client, url)
            server_type = server_info.get('server_type', 'unknown')
            
            # 2. 分析续传可行性
            should_resume, resume_reason = self.resume_manager.should_resume(file_item, local_path)
            server_supports = server_info.get('actually_supports_range', False)
            
            if self.progress_callback:
                self.progress_callback(f"📊 服务器:{server_type} Range支持:{server_supports} 续传条件:{resume_reason}")
            
            # 3. 尝试断点续传
            if should_resume and server_supports:
                local_size = local_path.stat().st_size
                
                resume_success = await self.network_recovery.download_with_recovery(
                    self.resume_manager.resume_download,
                    self.progress_callback,
                    client, file_item, url, local_path, self.progress_callback
                )
                
                if resume_success:
                    # 验证完整性
                    is_valid, integrity_msg = self.resume_manager.verify_integrity(
                        file_item, local_path, self.progress_callback
                    )
                    
                    if is_valid:
                        self.session_stats['successful_downloads'] += 1
                        self.session_stats['resumed_downloads'] += 1
                        
                        elapsed = time.time() - download_start
                        if self.progress_callback:
                            self.progress_callback(
                                f"✅ 断点续传成功完成 (耗时{elapsed:.1f}s) "
                                f"- {integrity_msg}"
                            )
                        return True
                    else:
                        # 完整性验证失败，删除重下
                        if self.progress_callback:
                            self.progress_callback(f"⚠️ {integrity_msg}，删除文件重新下载...")
                        local_path.unlink(missing_ok=True)
            else:
                # 给出具体的不能续传的原因
                if should_resume and not server_supports:
                    reason = ("服务器Range测试失败" if server_info.get('supports_range') 
                             else f"服务器({server_type})不支持断点续传")
                else:
                    reason = resume_reason
                
                if self.progress_callback:
                    self.progress_callback(f"📥 使用完整下载: {reason}")
            
            # 4. 回退到完整下载
            download_success = await self.network_recovery.download_with_recovery(
                self._full_download,
                self.progress_callback,
                client, file_item, url, local_path
            )
            
            if download_success:
                self.session_stats['successful_downloads'] += 1
                elapsed = time.time() - download_start
                
                if self.progress_callback:
                    file_size_mb = local_path.stat().st_size / (1024 * 1024)
                    speed_mb = file_size_mb / elapsed if elapsed > 0 else 0
                    self.progress_callback(
                        f"✅ 完整下载成功 (耗时{elapsed:.1f}s，平均{speed_mb:.1f}MB/s)"
                    )
                
                self.session_stats['bytes_downloaded'] += local_path.stat().st_size
                return True
            
            return False
            
        except Exception as e:
            if self.progress_callback:
                self.progress_callback(f"❌ 下载失败: {str(e)}")
            return False
    
    async def _full_download(self, client: AsyncHttpClient, file_item: FileItem, 
                           url: str, local_path: Path) -> bool:
        """完整文件下载的内部实现 - Day 2 优化版本"""
        try:
            # 准备请求头
            headers = {}
            if file_item.filename.endswith('.json'):
                headers['Accept-Encoding'] = 'gzip, br, deflate'
            
            # 流式下载完整文件
            async with client.stream_download(url, headers) as response:
                if response.status_code != 200:
                    raise Exception(f"HTTP {response.status_code}")
                
                # 获取文件大小
                if response.content_length:
                    file_item.size = response.content_length
                
                # 初始化进度跟踪
                progress_info = ProgressInfo(total_bytes=file_item.size)
                last_progress_update = time.time()
                
                # 下载文件
                if file_item.is_binary_file:
                    # 二进制文件
                    async with aiofiles.open(local_path, 'wb') as f:
                        downloaded = 0
                        chunk_count = 0
                        
                        async for chunk in response.iter_chunks():
                            await f.write(chunk)
                            downloaded += len(chunk)
                            chunk_count += 1
                            
                            # 优化的进度更新
                            current_time = time.time()
                            if (current_time - last_progress_update >= 0.5 or  # 500ms
                                chunk_count % 100 == 0):  # 每100个chunk
                                
                                progress_info.update_speed(downloaded)
                                
                                if self.progress_callback and file_item.size:
                                    speed_mb = progress_info.speed_bps / (1024 * 1024)
                                    eta_str = f"，预计{progress_info.eta_seconds:.0f}秒完成" if progress_info.eta_seconds else ""
                                    
                                    self.progress_callback(
                                        f"📥 下载中: {progress_info.progress_percent:.1f}% "
                                        f"({speed_mb:.1f}MB/s{eta_str})"
                                    )
                                
                                # 更新FileItem进度
                                file_item.progress = progress_info.progress_percent
                                file_item.downloaded_size = downloaded
                                
                                last_progress_update = current_time
                    
                    file_item.progress = 100.0
                
                else:
                    # 文本文件
                    content_bytes = b''
                    async for chunk in response.iter_chunks():
                        content_bytes += chunk
                    
                    try:
                        content = content_bytes.decode('utf-8')
                    except UnicodeDecodeError:
                        content = content_bytes.decode('utf-8', errors='replace')
                    
                    async with aiofiles.open(local_path, 'w', encoding='utf-8') as f:
                        await f.write(content)
                    
                    file_item.progress = 100.0
                
                # 验证完整性
                is_valid, integrity_msg = self.resume_manager.verify_integrity(
                    file_item, local_path, self.progress_callback
                )
                
                if is_valid:
                    return True
                else:
                    local_path.unlink(missing_ok=True)
                    raise Exception(f"文件完整性验证失败: {integrity_msg}")
                    
        except Exception as e:
            raise Exception(f"完整下载失败: {str(e)}")
    
    def get_session_summary(self) -> str:
        """获取会话统计摘要 - Day 2 新增"""
        elapsed_time = time.time() - self.session_stats['start_time']
        success_rate = (self.session_stats['successful_downloads'] / 
                       self.session_stats['total_downloads'] * 100) if self.session_stats['total_downloads'] > 0 else 0
        
        resume_rate = (self.session_stats['resumed_downloads'] / 
                      self.session_stats['successful_downloads'] * 100) if self.session_stats['successful_downloads'] > 0 else 0
        
        avg_speed = (self.session_stats['bytes_downloaded'] / elapsed_time / (1024 * 1024)) if elapsed_time > 0 else 0
        
        return (
            f"会话统计: 成功率{success_rate:.1f}% ({self.session_stats['successful_downloads']}/{self.session_stats['total_downloads']}) "
            f"续传率{resume_rate:.1f}% 平均速度{avg_speed:.1f}MB/s "
            f"总流量{self.session_stats['bytes_downloaded']/1024/1024:.1f}MB 耗时{elapsed_time/60:.1f}分钟"
        ) 