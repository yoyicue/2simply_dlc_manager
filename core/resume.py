"""
智能断点续传模块
支持大文件断点续传、网络中断恢复、完整性校验
"""
import asyncio
import aiofiles
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import FileItem, DownloadStatus
from .network import AsyncHttpClient


@dataclass
class ResumeInfo:
    """断点续传信息"""
    file_path: Path
    downloaded_bytes: int
    total_bytes: Optional[int]
    etag: Optional[str]
    last_modified: Optional[str]
    supports_range: bool
    created_at: datetime
    
    def is_valid(self, max_age_hours: int = 24) -> bool:
        """检查续传信息是否有效"""
        if datetime.now() - self.created_at > timedelta(hours=max_age_hours):
            return False
        return self.file_path.exists() and self.file_path.stat().st_size == self.downloaded_bytes


class ResumeManager:
    """断点续传管理器 - 高ROI核心实现"""
    
    def __init__(self, min_resume_size: int = 2 * 1024 * 1024):  # 2MB
        self.min_resume_size = min_resume_size
        self.resume_cache: Dict[str, ResumeInfo] = {}
    
    async def probe_resume_support(self, client: AsyncHttpClient, url: str) -> Dict[str, Any]:
        """探测服务器断点续传支持 - 30秒内完成"""
        try:
            response_info = await client.head_request(url)
            
            return {
                'supports_range': response_info.get('accept_ranges', False),
                'content_length': response_info.get('content_length'),
                'etag': response_info.get('etag'),
                'last_modified': response_info.headers.get('last-modified'),
                'status_code': response_info['status_code']
            }
        except Exception as e:
            return {
                'supports_range': False,
                'error': str(e),
                'status_code': 0
            }
    
    def should_resume(self, file_item: FileItem, local_path: Path) -> bool:
        """判断是否应该断点续传 - O(1)判断"""
        # 基本条件检查
        if not local_path.exists():
            return False
        
        local_size = local_path.stat().st_size
        
        # 文件太小不值得续传
        if local_size < self.min_resume_size:
            return False
        
        # 如果知道总大小，检查是否完整
        if file_item.size and local_size >= file_item.size:
            return False
        
        return True
    
    async def resume_download(self, client: AsyncHttpClient, file_item: FileItem, 
                            url: str, local_path: Path) -> bool:
        """执行断点续传下载 - 核心高价值功能"""
        
        # 1. 检查本地文件状态
        if not self.should_resume(file_item, local_path):
            return False
        
        local_size = local_path.stat().st_size
        
        # 2. 构建Range请求头
        headers = {
            'Range': f'bytes={local_size}-'
        }
        
        # 3. 发起Range请求
        try:
            async with client.stream_download(url, headers) as response:
                # 检查服务器是否支持Range
                if response.status_code not in (206, 416):  # 206=Partial Content, 416=Range Not Satisfiable
                    return False
                
                if response.status_code == 416:
                    # 文件已完整，无需续传
                    return True
                
                # 4. 续写文件
                async with aiofiles.open(local_path, 'ab') as f:  # append binary
                    async for chunk in response.iter_chunks():
                        await f.write(chunk)
                        
                        # 更新进度
                        current_size = local_path.stat().st_size
                        if file_item.size:
                            progress = (current_size / file_item.size) * 100
                            file_item.progress = progress
                            file_item.downloaded_size = current_size
                
                return True
                
        except Exception as e:
            # 续传失败，回退到完整下载
            return False
    
    def calculate_md5(self, file_path: Path, chunk_size: int = 8192) -> str:
        """流式计算文件MD5 - 内存友好"""
        md5_hash = hashlib.md5()
        
        with open(file_path, 'rb') as f:
            while chunk := f.read(chunk_size):
                md5_hash.update(chunk)
        
        return md5_hash.hexdigest()
    
    def verify_integrity(self, file_item: FileItem, local_path: Path) -> bool:
        """验证文件完整性 - 高价值保障功能"""
        if not local_path.exists():
            return False
        
        # 检查文件大小
        if file_item.size and local_path.stat().st_size != file_item.size:
            return False
        
        # 检查MD5
        if file_item.md5:
            calculated_md5 = self.calculate_md5(local_path)
            return calculated_md5.lower() == file_item.md5.lower()
        
        return True


class NetworkRecovery:
    """网络恢复机制 - 高ROI自动化功能"""
    
    def __init__(self, max_retries: int = 5, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
    
    async def download_with_recovery(self, download_func, *args, **kwargs):
        """带网络恢复的下载包装器"""
        
        for attempt in range(self.max_retries):
            try:
                return await download_func(*args, **kwargs)
            
            except (asyncio.TimeoutError, ConnectionError, OSError) as e:
                if attempt == self.max_retries - 1:
                    raise e
                
                # 指数退避策略
                delay = min(self.base_delay * (2 ** attempt), 16.0)
                print(f"网络错误，{delay:.1f}秒后重试 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                await asyncio.sleep(delay)
            
            except Exception as e:
                # 非网络错误直接抛出
                raise e
    
    def classify_error(self, error: Exception) -> str:
        """错误分类 - 精准处理策略"""
        if isinstance(error, asyncio.TimeoutError):
            return "timeout"
        elif isinstance(error, ConnectionError):
            return "connection"
        elif "HTTP 5" in str(error):
            return "server_error"
        elif "HTTP 4" in str(error):
            return "client_error"
        else:
            return "unknown"


# 集成到现有下载器的简化接口
class SmartResume:
    """智能断点续传门面类 - 最小侵入集成"""
    
    def __init__(self):
        self.resume_manager = ResumeManager()
        self.network_recovery = NetworkRecovery()
    
    async def smart_download(self, client: AsyncHttpClient, file_item: FileItem, 
                           url: str, local_path: Path) -> bool:
        """智能下载 - 自动选择续传或完整下载"""
        
        # 1. 尝试断点续传
        if self.resume_manager.should_resume(file_item, local_path):
            resume_success = await self.network_recovery.download_with_recovery(
                self.resume_manager.resume_download,
                client, file_item, url, local_path
            )
            
            if resume_success:
                # 2. 验证完整性
                if self.resume_manager.verify_integrity(file_item, local_path):
                    return True
                else:
                    # 完整性验证失败，删除重下
                    local_path.unlink(missing_ok=True)
        
        # 3. 回退到完整下载
        return await self.network_recovery.download_with_recovery(
            self._full_download,
            client, file_item, url, local_path
        )
    
    async def _full_download(self, client: AsyncHttpClient, file_item: FileItem, 
                           url: str, local_path: Path) -> bool:
        """完整文件下载的内部实现"""
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
                
                # 下载文件
                if file_item.is_binary_file:
                    # 二进制文件
                    async with aiofiles.open(local_path, 'wb') as f:
                        downloaded = 0
                        async for chunk in response.iter_chunks():
                            await f.write(chunk)
                            downloaded += len(chunk)
                            
                            # 更新进度
                            if file_item.size:
                                progress = (downloaded / file_item.size) * 100
                                file_item.progress = progress
                                file_item.downloaded_size = downloaded
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
                if self.resume_manager.verify_integrity(file_item, local_path):
                    return True
                else:
                    local_path.unlink(missing_ok=True)
                    raise Exception("文件完整性验证失败")
                    
        except Exception as e:
            raise Exception(f"完整下载失败: {str(e)}") 