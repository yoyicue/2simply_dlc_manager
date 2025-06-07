"""
智能压缩传输优化模块 - 第三阶段
支持基于文件类型的智能压缩策略、gzip传输优化、流式处理和性能监控
"""
import asyncio
import gzip
import zlib
import aiofiles
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import defaultdict

from .models import FileItem


class CompressionType(Enum):
    """支持的压缩类型"""
    NONE = "none"
    GZIP = "gzip"
    DEFLATE = "deflate"
    BROTLI = "br"
    AUTO = "auto"


class FileCategory(Enum):
    """文件分类"""
    JSON_SMALL = "json_small"      # <100KB JSON
    JSON_LARGE = "json_large"      # >=100KB JSON
    PNG_SMALL = "png_small"        # <500KB PNG
    PNG_MEDIUM = "png_medium"      # 500KB-2MB PNG
    PNG_LARGE = "png_large"        # >2MB PNG
    OTHER = "other"


@dataclass
class CompressionConfig:
    """压缩配置"""
    # JSON文件压缩配置
    force_json_compression: bool = True       # 强制JSON文件压缩
    json_compression_threshold: int = 1024    # JSON文件压缩阈值(字节)
    json_preferred_encoding: str = "gzip, br, deflate"
    
    # PNG文件优化配置
    png_stream_threshold: int = 500 * 1024   # 500KB以上PNG使用流式处理
    png_large_file_threshold: int = 2 * 1024 * 1024  # 2MB以上为大PNG文件
    enable_png_optimization: bool = True      # 启用PNG流式优化
    
    # 通用压缩配置
    compression_level: int = 6                # gzip压缩级别(1-9)
    stream_chunk_size: int = 64 * 1024      # 流式处理块大小
    enable_compression_cache: bool = True     # 启用压缩缓存
    cache_max_age: int = 3600                # 缓存有效期(秒)
    
    # 性能监控配置
    enable_performance_tracking: bool = True  # 启用性能跟踪
    track_compression_ratios: bool = True     # 跟踪压缩比
    track_transfer_savings: bool = True       # 跟踪传输节省


@dataclass
class CompressionStats:
    """压缩统计信息"""
    files_processed: int = 0
    total_original_size: int = 0
    total_compressed_size: int = 0
    total_transfer_time: float = 0.0
    compression_ratios: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    transfer_savings: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    method_usage: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    @property
    def overall_compression_ratio(self) -> float:
        """总体压缩比"""
        if self.total_original_size == 0:
            return 1.0
        return self.total_compressed_size / self.total_original_size
    
    @property
    def overall_savings_mb(self) -> float:
        """总体节省的MB数"""
        return (self.total_original_size - self.total_compressed_size) / (1024 * 1024)
    
    @property
    def overall_savings_percent(self) -> float:
        """总体节省百分比"""
        if self.total_original_size == 0:
            return 0.0
        return (1 - self.overall_compression_ratio) * 100


class FileTypeAnalyzer:
    """文件类型分析器"""
    
    @staticmethod
    def categorize_file(file_item: FileItem) -> FileCategory:
        """文件分类"""
        filename = file_item.filename.lower()
        size = getattr(file_item, 'size', 0) or 0
        
        if filename.endswith('.json'):
            if size < 100 * 1024:  # 100KB
                return FileCategory.JSON_SMALL
            else:
                return FileCategory.JSON_LARGE
        elif filename.endswith('.png'):
            if size < 500 * 1024:  # 500KB
                return FileCategory.PNG_SMALL
            elif size < 2 * 1024 * 1024:  # 2MB
                return FileCategory.PNG_MEDIUM
            else:
                return FileCategory.PNG_LARGE
        else:
            return FileCategory.OTHER
    
    @staticmethod
    def should_compress(file_item: FileItem, config: CompressionConfig) -> bool:
        """判断是否应该压缩"""
        category = FileTypeAnalyzer.categorize_file(file_item)
        
        # JSON文件：始终尝试压缩
        if category in [FileCategory.JSON_SMALL, FileCategory.JSON_LARGE]:
            return config.force_json_compression
        
        # PNG文件：通常不压缩，但可以优化传输
        if category in [FileCategory.PNG_SMALL, FileCategory.PNG_MEDIUM, FileCategory.PNG_LARGE]:
            return False  # PNG已经是压缩格式
        
        return False
    
    @staticmethod
    def get_optimal_headers(file_item: FileItem, config: CompressionConfig) -> Dict[str, str]:
        """获取最优请求头"""
        headers = {}
        category = FileTypeAnalyzer.categorize_file(file_item)
        
        if category in [FileCategory.JSON_SMALL, FileCategory.JSON_LARGE]:
            # JSON文件：强制请求压缩
            headers['Accept-Encoding'] = config.json_preferred_encoding
            # 明确告知服务器我们接受压缩内容
            headers['Accept'] = 'application/json'
        elif category in [FileCategory.PNG_SMALL, FileCategory.PNG_MEDIUM, FileCategory.PNG_LARGE]:
            # PNG文件：优化传输但不强制压缩
            headers['Accept'] = 'image/png'
            # 对于大PNG文件，尝试请求Range支持
            if category == FileCategory.PNG_LARGE:
                headers['Range'] = 'bytes=0-'  # 探测Range支持
        
        return headers


class CompressionOptimizer:
    """压缩优化器"""
    
    def __init__(self, config: CompressionConfig = None):
        self.config = config or CompressionConfig()
        self.stats = CompressionStats()
        self.cache = {}  # 压缩能力缓存
        
    def optimize_request_headers(self, file_item: FileItem) -> Dict[str, str]:
        """优化请求头以获得最佳压缩效果"""
        return FileTypeAnalyzer.get_optimal_headers(file_item, self.config)
    
    async def process_compressed_response(self, response_data: bytes, 
                                        content_encoding: Optional[str],
                                        file_item: FileItem,
                                        progress_callback: Optional[Callable] = None) -> bytes:
        """处理压缩响应数据"""
        
        if not content_encoding:
            # 无压缩，直接返回
            return response_data
        
        original_size = len(response_data)
        start_time = time.time()
        
        try:
            # 解压缩数据
            if content_encoding.lower() in ['gzip', 'x-gzip']:
                decompressed_data = gzip.decompress(response_data)
                method = "gzip"
            elif content_encoding.lower() == 'deflate':
                decompressed_data = zlib.decompress(response_data)
                method = "deflate"
            elif content_encoding.lower() == 'br':
                try:
                    import brotli
                    decompressed_data = brotli.decompress(response_data)
                    method = "brotli"
                except ImportError:
                    if progress_callback:
                        progress_callback("⚠️  Brotli解压缩不支持，使用原始数据")
                    return response_data
            else:
                if progress_callback:
                    progress_callback(f"⚠️  不支持的压缩编码: {content_encoding}")
                return response_data
            
            # 统计压缩效果
            decompressed_size = len(decompressed_data)
            compression_ratio = original_size / decompressed_size if decompressed_size > 0 else 1.0
            process_time = time.time() - start_time
            
            # 更新统计信息
            self._update_compression_stats(file_item, original_size, decompressed_size, 
                                         compression_ratio, method, process_time)
            
            if progress_callback:
                savings_percent = (1 - compression_ratio) * 100
                progress_callback(
                    f"📦 {method.upper()}解压完成: "
                    f"{original_size/1024:.1f}KB → {decompressed_size/1024:.1f}KB "
                    f"(节省{savings_percent:.1f}%, 耗时{process_time*1000:.1f}ms)"
                )
            
            return decompressed_data
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"❌ 解压缩失败({content_encoding}): {str(e)}")
            # 解压缩失败，返回原始数据
            return response_data
    
    def _update_compression_stats(self, file_item: FileItem, compressed_size: int, 
                                decompressed_size: int, compression_ratio: float,
                                method: str, process_time: float):
        """更新压缩统计信息"""
        if not self.config.enable_performance_tracking:
            return
        
        category = FileTypeAnalyzer.categorize_file(file_item)
        category_name = category.value
        
        self.stats.files_processed += 1
        self.stats.total_original_size += decompressed_size
        self.stats.total_compressed_size += compressed_size
        self.stats.total_transfer_time += process_time
        
        if self.config.track_compression_ratios:
            self.stats.compression_ratios[category_name].append(compression_ratio)
        
        if self.config.track_transfer_savings:
            savings = decompressed_size - compressed_size
            self.stats.transfer_savings[category_name] += savings
        
        self.stats.method_usage[method] += 1
    
    def get_compression_summary(self) -> Dict[str, Any]:
        """获取压缩效果摘要"""
        summary = {
            'files_processed': self.stats.files_processed,
            'overall_compression_ratio': self.stats.overall_compression_ratio,
            'overall_savings_mb': self.stats.overall_savings_mb,
            'overall_savings_percent': self.stats.overall_savings_percent,
            'transfer_time_total': self.stats.total_transfer_time,
            'methods_used': dict(self.stats.method_usage)
        }
        
        # 按文件类型的压缩效果
        category_summary = {}
        for category, ratios in self.stats.compression_ratios.items():
            if ratios:
                avg_ratio = sum(ratios) / len(ratios)
                avg_savings = (1 - avg_ratio) * 100
                total_savings = self.stats.transfer_savings.get(category, 0)
                
                category_summary[category] = {
                    'files': len(ratios),
                    'avg_compression_ratio': avg_ratio,
                    'avg_savings_percent': avg_savings,
                    'total_savings_mb': total_savings / (1024 * 1024)
                }
        
        summary['category_breakdown'] = category_summary
        return summary


class StreamingOptimizer:
    """流式传输优化器"""
    
    def __init__(self, config: CompressionConfig = None):
        self.config = config or CompressionConfig()
    
    async def optimize_png_streaming(self, response, file_item: FileItem, 
                                   local_path: Path,
                                   progress_callback: Optional[Callable] = None) -> bool:
        """PNG文件流式传输优化"""
        category = FileTypeAnalyzer.categorize_file(file_item)
        
        if category not in [FileCategory.PNG_MEDIUM, FileCategory.PNG_LARGE]:
            # 小PNG文件使用常规处理
            return False
        
        try:
            file_size = getattr(file_item, 'size', 0) or response.content_length or 0
            
            if progress_callback:
                progress_callback(f"🖼️  启用PNG流式优化: {file_item.filename} ({file_size/1024/1024:.1f}MB)")
            
            # 使用优化的块大小
            if category == FileCategory.PNG_LARGE:
                chunk_size = min(128 * 1024, self.config.stream_chunk_size * 2)  # 大文件用更大块
            else:
                chunk_size = self.config.stream_chunk_size
            
            downloaded = 0
            last_progress_time = time.time()
            start_time = time.time()
            
            async with aiofiles.open(local_path, 'wb') as f:
                async for chunk in response.iter_chunks(chunk_size):
                    await f.write(chunk)
                    downloaded += len(chunk)
                    
                    # 优化的进度更新频率
                    current_time = time.time()
                    if current_time - last_progress_time >= 1.0:  # 1秒更新一次
                        if file_size > 0:
                            progress = (downloaded / file_size) * 100
                            speed = downloaded / (current_time - start_time) if current_time > start_time else 0
                            speed_mb = speed / (1024 * 1024)
                            
                            if progress_callback:
                                progress_callback(
                                    f"🖼️  PNG流式下载: {progress:.1f}% "
                                    f"({downloaded/1024/1024:.1f}MB/{file_size/1024/1024:.1f}MB) "
                                    f"速度:{speed_mb:.1f}MB/s"
                                )
                        
                        last_progress_time = current_time
            
            elapsed_time = time.time() - start_time
            if progress_callback:
                avg_speed = (downloaded / elapsed_time) / (1024 * 1024) if elapsed_time > 0 else 0
                progress_callback(
                    f"✅ PNG流式下载完成: {downloaded/1024/1024:.1f}MB "
                    f"(平均{avg_speed:.1f}MB/s, 块大小:{chunk_size/1024:.1f}KB)"
                )
            
            return True
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"❌ PNG流式优化失败: {str(e)}")
            return False
    
    def should_use_streaming(self, file_item: FileItem) -> bool:
        """判断是否应该使用流式传输"""
        category = FileTypeAnalyzer.categorize_file(file_item)
        file_size = getattr(file_item, 'size', 0) or 0
        
        # PNG文件超过阈值时使用流式传输
        if category in [FileCategory.PNG_MEDIUM, FileCategory.PNG_LARGE]:
            return file_size >= self.config.png_stream_threshold
        
        # 大JSON文件也可以考虑流式传输
        if category == FileCategory.JSON_LARGE:
            return file_size >= 500 * 1024  # 500KB以上的JSON文件
        
        return False


class CompressionManager:
    """压缩传输管理器 - 统一门面"""
    
    def __init__(self, config: CompressionConfig = None):
        self.config = config or CompressionConfig()
        self.optimizer = CompressionOptimizer(self.config)
        self.streaming = StreamingOptimizer(self.config)
        self.session_start_time = time.time()
    
    def analyze_file_requirements(self, file_item: FileItem) -> Dict[str, Any]:
        """分析文件的传输优化需求"""
        category = FileTypeAnalyzer.categorize_file(file_item)
        
        analysis = {
            'category': category.value,
            'should_compress': FileTypeAnalyzer.should_compress(file_item, self.config),
            'should_stream': self.streaming.should_use_streaming(file_item),
            'optimal_headers': self.optimizer.optimize_request_headers(file_item),
            'estimated_savings': self._estimate_compression_savings(file_item)
        }
        
        return analysis
    
    def _estimate_compression_savings(self, file_item: FileItem) -> Dict[str, Union[float, str]]:
        """估算压缩节省效果"""
        category = FileTypeAnalyzer.categorize_file(file_item)
        file_size = getattr(file_item, 'size', 0) or 0
        
        if category in [FileCategory.JSON_SMALL, FileCategory.JSON_LARGE]:
            # JSON文件通常有70-80%的压缩比
            estimated_ratio = 0.25  # 压缩后大小为原来的25%
            estimated_savings = file_size * (1 - estimated_ratio)
            return {
                'compression_ratio': estimated_ratio,
                'estimated_savings_bytes': estimated_savings,
                'estimated_savings_percent': (1 - estimated_ratio) * 100,
                'method': 'gzip'
            }
        elif category in [FileCategory.PNG_SMALL, FileCategory.PNG_MEDIUM, FileCategory.PNG_LARGE]:
            # PNG文件已经压缩，主要优化传输效率
            return {
                'compression_ratio': 1.0,
                'estimated_savings_bytes': 0,
                'estimated_savings_percent': 0,
                'method': 'streaming_optimization'
            }
        else:
            return {
                'compression_ratio': 1.0,
                'estimated_savings_bytes': 0,
                'estimated_savings_percent': 0,
                'method': 'none'
            }
    
    async def optimize_download(self, response, file_item: FileItem, 
                              local_path: Path,
                              progress_callback: Optional[Callable] = None) -> bool:
        """优化下载过程"""
        
        # 检查是否需要流式处理
        if self.streaming.should_use_streaming(file_item):
            return await self.streaming.optimize_png_streaming(
                response, file_item, local_path, progress_callback
            )
        
        # 常规处理
        return False
    
    async def process_response_data(self, response_data: bytes,
                                  content_encoding: Optional[str],
                                  file_item: FileItem,
                                  progress_callback: Optional[Callable] = None) -> bytes:
        """处理响应数据"""
        return await self.optimizer.process_compressed_response(
            response_data, content_encoding, file_item, progress_callback
        )
    
    def get_session_summary(self) -> Dict[str, Any]:
        """获取会话摘要"""
        session_time = time.time() - self.session_start_time
        compression_summary = self.optimizer.get_compression_summary()
        
        summary = {
            'session_duration': session_time,
            'compression_stats': compression_summary,
            'optimization_enabled': {
                'json_compression': self.config.force_json_compression,
                'png_streaming': self.config.enable_png_optimization,
                'performance_tracking': self.config.enable_performance_tracking
            }
        }
        
        return summary
    
    def reset_session_stats(self):
        """重置会话统计"""
        self.optimizer.stats = CompressionStats()
        self.session_start_time = time.time() 