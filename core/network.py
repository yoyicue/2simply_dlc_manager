"""
HTTP/2 网络客户端管理器
支持连接复用、自动重试、性能监控
"""
import asyncio
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, AsyncIterator
from pathlib import Path

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


@dataclass
class NetworkConfig:
    """网络配置"""
    use_http2: bool = True  # HTTP/2特性开关
    max_connections: int = 100  # 最大连接数
    max_keepalive: int = 50  # 最大保持连接数
    timeout_seconds: int = 180  # 总超时时间
    connect_timeout: int = 30  # 连接超时
    read_timeout: int = 60  # 读取超时
    
    # 性能监控
    enable_performance_tracking: bool = True
    connection_pool_stats: bool = True


class AsyncHttpClient:
    """统一的HTTP/2异步客户端封装"""
    
    def __init__(self, config: NetworkConfig):
        self.config = config
        self._client: Optional[Any] = None
        self._session_start_time: Optional[float] = None
        self._total_requests = 0
        self._total_bytes = 0
        self._connection_reused = 0
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self._session_start_time = time.time()
        
        if HTTPX_AVAILABLE and self.config.use_http2:
            # 使用 httpx 的 HTTP/2 支持
            await self._init_httpx_client()
        elif AIOHTTP_AVAILABLE:
            # 降级到 aiohttp HTTP/1.1
            await self._init_aiohttp_client()
        else:
            raise ImportError("Neither httpx nor aiohttp is available")
            
        return self
        
    async def _init_httpx_client(self):
        """初始化 httpx HTTP/2 客户端"""
        limits = httpx.Limits(
            max_connections=self.config.max_connections,
            max_keepalive_connections=self.config.max_keepalive,
            keepalive_expiry=30.0
        )
        
        timeout = httpx.Timeout(
            connect=self.config.connect_timeout,
            read=self.config.read_timeout,
            write=30.0,
            pool=60.0
        )
        
        self._client = httpx.AsyncClient(
            http2=True,  # 启用 HTTP/2
            limits=limits,
            timeout=timeout,
            follow_redirects=True,
            headers={
                'User-Agent': 'DLC-Manager/2.0 (HTTP/2 Enabled)',
                'Accept': '*/*',
                'Accept-Encoding': 'gzip, br, deflate',
                'Connection': 'keep-alive'
            }
        )
        
    async def _init_aiohttp_client(self):
        """降级到 aiohttp HTTP/1.1 客户端"""
        if not AIOHTTP_AVAILABLE:
            raise ImportError("aiohttp is not available")
            
        timeout = aiohttp.ClientTimeout(
            total=self.config.timeout_seconds,
            connect=self.config.connect_timeout,
            sock_read=self.config.read_timeout
        )
        
        connector = aiohttp.TCPConnector(
            limit=self.config.max_connections,
            limit_per_host=self.config.max_keepalive,
            keepalive_timeout=30,
            enable_cleanup_closed=True,
            ttl_dns_cache=300,
            use_dns_cache=True
        )
        
        self._client = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'User-Agent': 'DLC-Manager/2.0 (HTTP/1.1 Fallback)',
                'Accept': '*/*',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            }
        )
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        if self._client:
            if HTTPX_AVAILABLE and isinstance(self._client, httpx.AsyncClient):
                await self._client.aclose()
            else:
                await self._client.close()
            
        # 打印性能统计
        if self.config.enable_performance_tracking and self._session_start_time:
            session_duration = time.time() - self._session_start_time
            print(f"🔗 网络会话统计: {self._total_requests}个请求, "
                  f"{self._total_bytes/1024/1024:.1f}MB传输, "
                  f"连接复用{self._connection_reused}次, "
                  f"会话时长{session_duration:.1f}秒")
    
    def stream_download(self, url: str, headers: Optional[Dict[str, str]] = None) -> 'DownloadResponse':
        """流式下载，支持Range请求和进度跟踪"""
        merged_headers = {}
        if headers:
            merged_headers.update(headers)
            
        self._total_requests += 1
        
        if HTTPX_AVAILABLE and isinstance(self._client, httpx.AsyncClient):
            # 返回httpx的流式响应context manager
            response_cm = self._client.stream('GET', url, headers=merged_headers)
            return HttpxDownloadResponse(response_cm, self)
        else:
            # aiohttp 返回 context manager，需要特殊处理
            response_cm = self._client.get(url, headers=merged_headers)
            return AiohttpDownloadResponse(response_cm, self)
    
    async def head_request(self, url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """HEAD请求获取文件元信息"""
        merged_headers = {}
        if headers:
            merged_headers.update(headers)
            
        self._total_requests += 1
        
        if HTTPX_AVAILABLE and isinstance(self._client, httpx.AsyncClient):
            response = await self._client.head(url, headers=merged_headers)
            return {
                'status_code': response.status_code,
                'headers': dict(response.headers),
                'content_length': response.headers.get('content-length'),
                'accept_ranges': response.headers.get('accept-ranges', '').lower() == 'bytes',
                'etag': response.headers.get('etag')
            }
        else:
            async with self._client.head(url, headers=merged_headers) as response:
                return {
                    'status_code': response.status,
                    'headers': dict(response.headers),
                    'content_length': response.headers.get('content-length'),
                    'accept_ranges': response.headers.get('accept-ranges', '').lower() == 'bytes',
                    'etag': response.headers.get('etag')
                }
    
    def track_bytes_downloaded(self, byte_count: int):
        """跟踪下载字节数"""
        self._total_bytes += byte_count
        
    def track_connection_reuse(self):
        """跟踪连接复用"""
        self._connection_reused += 1


class DownloadResponse:
    """下载响应基类"""
    
    def __init__(self, response, client: AsyncHttpClient):
        self.response = response
        self.client = client
        self._downloaded_bytes = 0
    
    @property
    def status_code(self) -> int:
        """HTTP状态码"""
        raise NotImplementedError
        
    @property
    def headers(self) -> Dict[str, str]:
        """响应头"""
        raise NotImplementedError
        
    @property
    def content_length(self) -> Optional[int]:
        """内容长度"""
        length = self.headers.get('content-length')
        return int(length) if length else None
    
    async def iter_chunks(self, chunk_size: int = 32768) -> AsyncIterator[bytes]:
        """迭代读取响应数据块"""
        raise NotImplementedError


class HttpxDownloadResponse(DownloadResponse):
    """httpx 响应封装"""
    
    def __init__(self, response_cm, client: AsyncHttpClient):
        self.response_cm = response_cm  # httpx stream context manager
        self.response = None  # 实际的 response 对象
        self.client = client
        self._downloaded_bytes = 0
    
    @property
    def status_code(self) -> int:
        if self.response is None:
            raise RuntimeError("Response not initialized. Use 'async with' to access.")
        return self.response.status_code
        
    @property
    def headers(self) -> Dict[str, str]:
        if self.response is None:
            raise RuntimeError("Response not initialized. Use 'async with' to access.")
        return dict(self.response.headers)
    
    async def iter_chunks(self, chunk_size: int = 32768) -> AsyncIterator[bytes]:
        if self.response is None:
            raise RuntimeError("Response not initialized. Use 'async with' to access.")
        async for chunk in self.response.aiter_bytes(chunk_size):
            self._downloaded_bytes += len(chunk)
            self.client.track_bytes_downloaded(len(chunk))
            yield chunk
    
    async def __aenter__(self):
        self.response = await self.response_cm.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.response_cm:
            await self.response_cm.__aexit__(exc_type, exc_val, exc_tb)


class AiohttpDownloadResponse(DownloadResponse):
    """aiohttp 响应封装"""
    
    def __init__(self, response_cm, client: AsyncHttpClient):
        self.response_cm = response_cm  # aiohttp context manager
        self.response = None  # 实际的 response 对象
        self.client = client
        self._downloaded_bytes = 0
    
    @property
    def status_code(self) -> int:
        if self.response is None:
            raise RuntimeError("Response not initialized. Use 'async with' to access.")
        return self.response.status
        
    @property
    def headers(self) -> Dict[str, str]:
        if self.response is None:
            raise RuntimeError("Response not initialized. Use 'async with' to access.")
        return dict(self.response.headers)
    
    async def iter_chunks(self, chunk_size: int = 32768) -> AsyncIterator[bytes]:
        if self.response is None:
            raise RuntimeError("Response not initialized. Use 'async with' to access.")
        async for chunk in self.response.content.iter_chunked(chunk_size):
            self._downloaded_bytes += len(chunk)
            self.client.track_bytes_downloaded(len(chunk))
            yield chunk
    
    async def __aenter__(self):
        self.response = await self.response_cm.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.response_cm:
            await self.response_cm.__aexit__(exc_type, exc_val, exc_tb)


class NetworkManager:
    """网络管理器，提供高层网络操作接口"""
    
    def __init__(self, config: Optional[NetworkConfig] = None):
        self.config = config or NetworkConfig()
        self._client_instance: Optional[AsyncHttpClient] = None
    
    def create_client(self) -> AsyncHttpClient:
        """创建客户端实例"""
        return AsyncHttpClient(self.config)
    
    async def probe_http2_support(self, base_url: str) -> bool:
        """探测服务器HTTP/2支持情况"""
        if not HTTPX_AVAILABLE:
            return False
            
        try:
            test_config = NetworkConfig(use_http2=True, timeout_seconds=10)
            async with AsyncHttpClient(test_config) as client:
                response_info = await client.head_request(f"{base_url}/favicon.ico")
                # 检查响应中是否有HTTP/2标识
                return response_info['status_code'] < 400
        except Exception:
            return False
    
    def get_recommended_config(self, file_count: int, avg_file_size: int) -> NetworkConfig:
        """根据下载任务特征推荐网络配置"""
        config = NetworkConfig()
        
        # 根据文件数量调整连接池
        if file_count > 10000:
            config.max_connections = 150
            config.max_keepalive = 80
        elif file_count > 1000:
            config.max_connections = 100
            config.max_keepalive = 50
        else:
            config.max_connections = 50
            config.max_keepalive = 25
            
        # 根据文件大小调整超时
        if avg_file_size > 5 * 1024 * 1024:  # >5MB
            config.timeout_seconds = 300
            config.read_timeout = 120
        elif avg_file_size < 100 * 1024:  # <100KB
            config.timeout_seconds = 60
            config.read_timeout = 30
            
        return config 