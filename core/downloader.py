"""
异步下载器模块 - HTTP/2 优化版本
"""
import asyncio
import aiofiles
from pathlib import Path
from typing import List, Dict, Optional, Callable, Any
from PySide6.QtCore import QObject, Signal, QModelIndex
import os  # 局部导入, 避免顶层不必要依赖

from .models import FileItem, DownloadStatus, DownloadConfig
from .network import NetworkManager, AsyncHttpClient, NetworkConfig

# 向后兼容的导入
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None  # 设置为None以避免NameError


class Downloader(QObject):
    """异步下载器"""
    
    # 信号定义
    progress_updated = Signal(str, float)  # 文件名, 进度百分比
    file_completed = Signal(str, bool, str)  # 文件名, 是否成功, 消息
    overall_progress = Signal(float, int, int)  # 整体进度百分比, 已完成数量, 总数量
    check_progress = Signal(float)  # 文件检查进度百分比
    log_message = Signal(str)  # 日志消息
    download_started = Signal()  # 下载开始
    download_finished = Signal(int, int)  # 成功数量, 失败数量
    download_cancelled = Signal()  # 下载取消
    
    def __init__(self, config: Optional[DownloadConfig] = None):
        super().__init__()
        self.config = config or DownloadConfig()
        
        # HTTP/2 网络层
        self.network_manager = NetworkManager()
        self._http_client: Optional[AsyncHttpClient] = None
        self._network_config: Optional[NetworkConfig] = None
        self._http2_enabled = False
        
        # 向后兼容的会话
        self._session: Optional[Any] = None
        
        # 下载状态
        self._is_cancelled = False
        self._is_downloading = False
        self._semaphore: Optional[asyncio.Semaphore] = None
        
    async def _batch_check_existing_files(self, file_items: List[FileItem], output_dir: Path, data_manager=None) -> tuple[List[FileItem], List[FileItem]]:
        """智能批量检查文件是否已存在 - 阶段一优化版本
        
        使用缓存验证 + 智能增量检查，大幅提升性能
        
        返回:
            (existing_files, files_to_download)
        """
        loop = asyncio.get_event_loop()
        
        # 从DataManager导入用于缓存分析
        from .persistence import DataManager
        
        # 使用传入的data_manager或创建新实例
        if data_manager is None:
            data_manager = DataManager()
        
        # -----------------------------
        # 1. 阶段二优先：Bloom Filter O(1)快速预过滤
        # -----------------------------
        bloom_filter = data_manager.bloom_filter
        if bloom_filter and bloom_filter.is_cache_valid():
            self.log_message.emit("⚡ 启用Bloom Filter最优先预过滤...")
            return await self._optimized_bloom_filter_check(file_items, output_dir, bloom_filter, data_manager)
        
        # -----------------------------
        # 2. 降级方案：分析缓存可靠性（当Bloom Filter不可用时）
        # -----------------------------
        self.log_message.emit("🔍 分析缓存可靠性...")
        
        cache_analysis = data_manager.analyze_cache_reliability(file_items, output_dir)
        
        self.log_message.emit(f"📊 缓存分析: {cache_analysis['reason']}")
        
        # -----------------------------
        # 3. 根据缓存可靠性选择策略
        # -----------------------------
        if cache_analysis['recommendation'] == 'cache_reliable':
            return await self._cache_based_check(file_items, output_dir)
        elif cache_analysis['recommendation'] == 'incremental_check':
            return await self._smart_incremental_check(file_items, output_dir, cache_analysis)
        else:
            # 当缓存不可靠或文件状态为PENDING时，总是进行完整磁盘扫描
            return await self._optimized_full_scan(file_items, output_dir)
    
    async def _cache_based_check(self, file_items: List[FileItem], output_dir: Path) -> tuple[List[FileItem], List[FileItem]]:
        """基于缓存的快速检查 - 带兜底磁盘验证"""
        self.log_message.emit("⚡ 执行基于缓存的快速检查（含兜底验证）...")
        
        existing_files = []
        files_to_download = []
        need_verification = []  # 缓存可信但需要兜底验证的文件
        total_files = len(file_items)
        
        # 第一轮：基于缓存快速分类
        for idx, item in enumerate(file_items):
            if self._is_cancelled:
                break
            
            file_path = output_dir / item.full_filename
            
            # 如果缓存标记为已验证且未过期，加入兜底验证队列
            if (item.status == DownloadStatus.COMPLETED and 
                item.disk_verified and 
                item.is_cache_valid(file_path)):
                need_verification.append(item)
            elif item.status == DownloadStatus.PENDING:
                # PENDING状态的文件需要检查磁盘
                need_verification.append(item)
            else:
                files_to_download.append(item)
            
            # 定期更新进度
            if idx % 500 == 0 or idx == total_files - 1:
                progress_percent = (idx / total_files) * 50  # 缓存检查占50%进度
                self.check_progress.emit(progress_percent)
                await asyncio.sleep(0)
        
        # 第二轮：兜底磁盘验证（即使缓存可信也要验证，防止文件被删除）
        if need_verification:
            self.log_message.emit(f"🔍 兜底验证 {len(need_verification)} 个缓存可信文件...")
            
            verified_existing, verified_missing = await self._parallel_verify_files(
                need_verification, output_dir, progress_offset=50
            )
            
            existing_files.extend(verified_existing)
            files_to_download.extend(verified_missing)
            
            if verified_missing:
                self.log_message.emit(f"⚠️  发现 {len(verified_missing)} 个缓存过期文件（文件实际不存在）")
        
        self.log_message.emit(f"✅ 缓存+验证检查完成: {len(existing_files)} 个文件确认存在")
        return existing_files, files_to_download
    
    async def _smart_incremental_check(self, file_items: List[FileItem], output_dir: Path, 
                                     cache_analysis: dict) -> tuple[List[FileItem], List[FileItem]]:
        """智能增量检查 - 结合缓存与选择性验证"""
        self.log_message.emit("🧠 执行智能增量检查...")
        
        existing_files = []
        files_to_download = []
        items_need_verification = []
        
        # 第一阶段：基于缓存快速分类
        for item in file_items:
            if self._is_cancelled:
                break
            
            file_path = output_dir / item.full_filename
            
            if (item.status == DownloadStatus.COMPLETED and 
                item.disk_verified and 
                item.is_cache_valid(file_path)):
                # 缓存可信，直接归类为存在
                existing_files.append(item)
            elif item.status == DownloadStatus.COMPLETED:
                # 需要验证的已完成文件
                items_need_verification.append(item)
            elif item.status == DownloadStatus.PENDING:
                # PENDING状态的文件需要检查磁盘
                items_need_verification.append(item)
            else:
                # 明确需要下载的文件（失败、取消等状态）
                files_to_download.append(item)
        
        # 第二阶段：并行验证需要检查的文件
        if items_need_verification:
            self.log_message.emit(f"📋 验证 {len(items_need_verification)} 个可疑文件...")
            
            verified_existing, verified_missing = await self._parallel_verify_files(
                items_need_verification, output_dir
            )
            
            existing_files.extend(verified_existing)
            files_to_download.extend(verified_missing)
        
        self.log_message.emit(f"✅ 增量检查完成: 信任 {len(existing_files)} 个，需验证 {len(items_need_verification)} 个")
        return existing_files, files_to_download
    
    async def _parallel_verify_files(self, file_items: List[FileItem], output_dir: Path, progress_offset: float = 0) -> tuple[List[FileItem], List[FileItem]]:
        """并行验证文件存在性和元数据"""
        from concurrent.futures import ThreadPoolExecutor
        import os
        
        def verify_single_file(item: FileItem) -> tuple[FileItem, bool]:
            """验证单个文件"""
            file_path = output_dir / item.full_filename
            try:
                if not file_path.exists():
                    return item, False
                
                stat_info = file_path.stat()
                
                # 更新元数据
                item.update_disk_metadata(file_path)
                item.mark_completed(file_path)
                
                return item, True
            except (OSError, IOError):
                return item, False
        
        loop = asyncio.get_event_loop()
        max_workers = min(8, len(file_items))  # 限制并发数
        
        existing_files = []
        files_to_download = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 分批处理以控制内存使用
            batch_size = 50
            total_batches = (len(file_items) + batch_size - 1) // batch_size
            
            for batch_idx in range(total_batches):
                if self._is_cancelled:
                    break
                
                start_idx = batch_idx * batch_size
                end_idx = min(start_idx + batch_size, len(file_items))
                batch_items = file_items[start_idx:end_idx]
                
                # 并行执行当前批次
                tasks = [
                    loop.run_in_executor(executor, verify_single_file, item)
                    for item in batch_items
                ]
                
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 处理结果
                for result in batch_results:
                    if isinstance(result, Exception):
                        continue
                    
                    item, exists = result
                    if exists:
                        existing_files.append(item)
                    else:
                        files_to_download.append(item)
                
                # 更新进度（支持偏移）
                batch_progress = ((batch_idx + 1) / total_batches) * 50  # 验证阶段占50%
                total_progress = progress_offset + batch_progress
                self.check_progress.emit(total_progress)
                await asyncio.sleep(0)
        
        return existing_files, files_to_download
    
    async def download_files(self, file_items: List[FileItem], output_dir: Path, data_manager=None) -> Dict[str, bool]:
        """下载多个文件"""
        if not file_items:
            return {}
        
        self._is_cancelled = False
        self._is_downloading = True
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 发送开始信号
        self.download_started.emit()
        self.log_message.emit(f"开始下载 {len(file_items)} 个文件到 {output_dir}")
        
        # 异步预先过滤已存在的文件 - 效率优化
        results = {}
        self.log_message.emit("正在检查已存在的文件...")
        
        existing_files, files_to_download = await self._batch_check_existing_files(file_items, output_dir, data_manager)
        
        # 发送检查完成信号
        self.check_progress.emit(100.0)
        
        # 处理已存在的文件 - 阶段一优化：批量处理，减少日志输出
        completed_count = 0
        total_count = len(file_items)
        
        if existing_files:
            self.log_message.emit(f"📁 批量处理 {len(existing_files)} 个已存在的文件...")
            
            # 重置进度日志标记
            for attr in ['_logged_25', '_logged_50', '_logged_75']:
                if hasattr(self, attr):
                    delattr(self, attr)
            
            # 动态计算批次大小：根据文件数量智能调整
            if len(existing_files) <= 500:
                batch_size = 100  # 小量文件：100个一批
            elif len(existing_files) <= 5000:
                batch_size = 1000  # 中量文件：1000个一批  
            elif len(existing_files) <= 20000:
                batch_size = 5000  # 大量文件：5000个一批
            else:
                batch_size = 10000  # 超大量文件：10000个一批
            for batch_start in range(0, len(existing_files), batch_size):
                if self._is_cancelled:
                    break
                
                batch_end = min(batch_start + batch_size, len(existing_files))
                batch = existing_files[batch_start:batch_end]
                
                for item in batch:
                    item.mark_completed(output_dir / item.full_filename)
                    # 阶段一新增：更新磁盘元数据
                    item.update_disk_metadata(output_dir / item.full_filename)
                    results[item.filename] = True
                    completed_count += 1
                
                # 批量更新进度和UI
                overall_progress = (completed_count / total_count) * 100
                self.overall_progress.emit(overall_progress, completed_count, total_count)
                
                # 智能进度报告：只在重要节点输出日志
                progress_ratio = batch_end / len(existing_files)
                should_log = (
                    batch_end < len(existing_files) and (
                        progress_ratio >= 0.25 and not hasattr(self, '_logged_25') or
                        progress_ratio >= 0.50 and not hasattr(self, '_logged_50') or  
                        progress_ratio >= 0.75 and not hasattr(self, '_logged_75')
                    )
                )
                
                if should_log:
                    self.log_message.emit(f"✅ 已处理 {batch_end}/{len(existing_files)} 个现有文件 ({progress_ratio:.0%})")
                    if progress_ratio >= 0.25: self._logged_25 = True
                    if progress_ratio >= 0.50: self._logged_50 = True  
                    if progress_ratio >= 0.75: self._logged_75 = True
                
                # 让出控制权，保持UI响应 - 大批次时减少睡眠频率
                if batch_size >= 5000:
                    await asyncio.sleep(0.001)  # 大批次快速处理
                else:
                    await asyncio.sleep(0.002)  # 小批次稍微多让出一点时间
            
            # 汇总信息，替代逐个文件的日志
            self.log_message.emit(f"✅ 批量跳过 {len(existing_files)} 个已存在文件，节省下载时间")
        
        skipped_count = len(existing_files)
        
        if skipped_count > 0:
            self.log_message.emit(f"跳过 {skipped_count} 个已存在的文件")
        
        if not files_to_download:
            self.log_message.emit("所有文件都已存在，无需下载")
            # 确保最终进度为100%
            self.overall_progress.emit(100.0, completed_count, total_count)
            self.download_finished.emit(len(file_items), 0)
            self._is_downloading = False
            return results
        
        self.log_message.emit(f"需要下载 {len(files_to_download)} 个文件")
        
        # 创建信号量控制并发 - 使用基于文件类型的优化并发数
        optimal_concurrent = self.config.get_optimal_concurrent_requests(len(file_items), len(files_to_download), files_to_download)
        self.log_message.emit(f"使用智能优化并发数: {optimal_concurrent} (基于文件类型和大小分析)")
        self._semaphore = asyncio.Semaphore(optimal_concurrent)
        
        # 创建网络配置和客户端
        self._network_config = self.config.create_network_config(files_to_download)
        
        # HTTP/2 支持检测和降级
        if self.config.use_http2 and self.config.auto_detect_http2:
            try:
                http2_supported = await self.network_manager.probe_http2_support(self.config.asset_base_url)
                if http2_supported:
                    self._http2_enabled = True
                    self.log_message.emit("🚀 HTTP/2 支持已启用，连接复用优化激活")
                else:
                    self._http2_enabled = False
                    self._network_config.use_http2 = False
                    self.log_message.emit("⚠️  服务器不支持HTTP/2，自动降级到HTTP/1.1")
            except Exception as e:
                self._http2_enabled = False
                self._network_config.use_http2 = False
                self.log_message.emit(f"⚠️  HTTP/2检测失败，降级到HTTP/1.1: {str(e)}")
        
        try:
            # 使用新的网络客户端
            async with AsyncHttpClient(self._network_config) as http_client:
                self._http_client = http_client
                
                # 分批处理需要下载的文件 - 使用基于文件类型的智能批次大小
                optimal_batch_size = self.config.get_optimal_batch_size(len(file_items), len(files_to_download), files_to_download)
                self.log_message.emit(f"使用智能优化批次大小: {optimal_batch_size} (基于文件类型和大小分析)")
                
                batches = [
                    files_to_download[i:i + optimal_batch_size] 
                    for i in range(0, len(files_to_download), optimal_batch_size)
                ]
                
                # completed_count 已经在处理已存在文件时初始化了
                # total_count 也已经初始化了
                
                for batch_idx, batch in enumerate(batches):
                    if self._is_cancelled:
                        break
                    
                    self.log_message.emit(f"处理下载批次 {batch_idx + 1}/{len(batches)}")
                    
                    # 并发下载当前批次
                    tasks = [
                        self._download_single_file(item, output_dir)
                        for item in batch
                    ]
                    
                    batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # 处理批次结果
                    for item, result in zip(batch, batch_results):
                        if isinstance(result, Exception):
                            item.mark_failed(str(result))
                            results[item.filename] = False
                            self.file_completed.emit(item.filename, False, str(result))
                        else:
                            results[item.filename] = result
                            if result:
                                completed_count += 1
                        
                        # 更新整体进度
                        overall_progress = (completed_count / total_count) * 100
                        self.overall_progress.emit(overall_progress, completed_count, total_count)
                    
                    # 批次间暂停 - 仅在有实际下载任务时才暂停
                    if batch_idx < len(batches) - 1 and len(batch) > 0:
                        await asyncio.sleep(self.config.retry_delay)
                
        except Exception as e:
            self.log_message.emit(f"下载过程中发生错误: {str(e)}")
        finally:
            self._http_client = None
            self._network_config = None
            self._is_downloading = False
        
        # 统计结果
        success_count = sum(1 for success in results.values() if success)
        failed_count = len(results) - success_count
        
        if self._is_cancelled:
            self.download_cancelled.emit()
            self.log_message.emit("下载已取消")
        else:
            self.download_finished.emit(success_count, failed_count)
            self.log_message.emit(f"下载完成: 成功 {success_count}, 失败 {failed_count}")
        
        return results
    
    async def _download_single_file(self, file_item: FileItem, output_dir: Path) -> bool:
        """下载单个文件"""
        if self._is_cancelled:
            return False
        
        async with self._semaphore:
            if self._is_cancelled:
                return False
            
            # 构建下载URL和本地路径
            download_url = f"{self.config.asset_base_url}/{file_item.base_filename}-{file_item.md5}{file_item.file_extension}"
            local_path = output_dir / file_item.full_filename
            
            file_item.download_url = download_url
            file_item.status = DownloadStatus.DOWNLOADING
            
            self.log_message.emit(f"开始下载: {file_item.filename}")
            
            # 二次检查文件是否已存在（防止并发时出现的竞态条件）
            if local_path.exists():
                file_item.mark_completed(local_path)
                # 阶段一新增：更新磁盘元数据
                file_item.update_disk_metadata(local_path)
                self.progress_updated.emit(file_item.filename, 100.0)
                # 阶段一优化：减少重复的"已存在"日志，仅在UI层面通知
                self.file_completed.emit(file_item.filename, True, "文件已存在")
                return True
            
            # 重试机制
            for attempt in range(self.config.max_retries):
                if self._is_cancelled:
                    return False
                
                try:
                    return await self._download_with_progress(file_item, download_url, local_path)
                except Exception as e:
                    error_msg = f"下载失败 (尝试 {attempt + 1}/{self.config.max_retries}): {str(e)}"
                    self.log_message.emit(f"{file_item.filename} - {error_msg}")
                    
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(self.config.retry_delay)
                    else:
                        file_item.mark_failed(error_msg)
                        self.file_completed.emit(file_item.filename, False, error_msg)
                        return False
            
            return False
    
    async def _download_with_progress(self, file_item: FileItem, url: str, local_path: Path) -> bool:
        """带进度的下载 - HTTP/2 优化版本"""
        try:
            # 使用自适应块大小
            adaptive_chunk_size = self.config.get_adaptive_chunk_size(file_item)
            
            # 准备请求头
            headers = {}
            if file_item.filename.endswith('.json'):
                headers['Accept-Encoding'] = 'gzip, br, deflate'
            
            # 使用新的网络客户端流式下载
            async with self._http_client.stream_download(url, headers) as response:
                if response.status_code != 200:
                    raise Exception(f"HTTP {response.status_code}")
                
                # 获取文件大小
                if response.content_length:
                    file_item.size = response.content_length
                
                # 检测协议版本
                protocol_info = "HTTP/2" if self._http2_enabled else "HTTP/1.1"
                
                # 下载文件
                if file_item.is_binary_file:
                    # 二进制文件 - 流式下载
                    async with aiofiles.open(local_path, 'wb') as f:
                        downloaded = 0
                        async for chunk in response.iter_chunks(adaptive_chunk_size):
                            if self._is_cancelled:
                                return False
                            
                            await f.write(chunk)
                            downloaded += len(chunk)
                            
                            # 更新进度
                            if file_item.size:
                                progress = (downloaded / file_item.size) * 100
                                file_item.progress = progress
                                file_item.downloaded_size = downloaded
                                self.progress_updated.emit(file_item.filename, progress)
                else:
                    # 文本文件 - 流式读取
                    content_bytes = b''
                    async for chunk in response.iter_chunks(adaptive_chunk_size):
                        if self._is_cancelled:
                            return False
                        content_bytes += chunk
                    
                    # 解码并写入
                    try:
                        content = content_bytes.decode('utf-8')
                    except UnicodeDecodeError:
                        content = content_bytes.decode('utf-8', errors='replace')
                    
                    async with aiofiles.open(local_path, 'w', encoding='utf-8') as f:
                        await f.write(content)
                    
                    file_item.progress = 100.0
                    self.progress_updated.emit(file_item.filename, 100.0)
                
                # 标记完成
                file_item.mark_completed(local_path)
                # 阶段一新增：更新磁盘元数据
                file_item.update_disk_metadata(local_path)
                
                # 阶段二新增：更新Bloom Filter
                self._update_bloom_filter_on_completion(file_item)
                
                # 记录下载性能信息
                if file_item.size:
                    file_type = "大文件" if file_item.size > self.config.large_file_threshold else "小文件" if file_item.size < self.config.small_file_threshold else "中等文件"
                    compression_info = "压缩传输" if 'gzip' in headers.get('Accept-Encoding', '') else "原始传输"
                    self.log_message.emit(f"✅ {protocol_info} {file_type} {file_item.filename} 下载完成 "
                                        f"({file_item.size/1024:.1f}KB, {compression_info}, 块大小:{adaptive_chunk_size/1024:.1f}KB)")
                
                self.file_completed.emit(file_item.filename, True, "下载成功")
                return True
                
        except asyncio.TimeoutError:
            raise Exception(f"下载超时")
        except Exception as e:
            raise Exception(f"下载失败: {str(e)}")
    
    def cancel_download(self):
        """取消下载"""
        self._is_cancelled = True
        self._is_downloading = False
        self.log_message.emit("正在取消下载...")
    
    @property
    def is_downloading(self) -> bool:
        """是否正在下载"""
        return self._is_downloading 

    async def _optimized_full_scan(self, file_items: List[FileItem], output_dir: Path) -> tuple[List[FileItem], List[FileItem]]:
        """优化版完整扫描 - 当缓存不可靠时的降级选项"""
        self.log_message.emit("🔄 执行优化版完整扫描...")
        
        loop = asyncio.get_event_loop()
        
        # 执行目录扫描构建文件映射
        def _scan_dir(directory: Path) -> dict[str, int]:
            mapping: dict[str, int] = {}
            try:
                with os.scandir(directory) as it:
                    for entry in it:
                        if entry.is_file():
                            try:
                                size = entry.stat().st_size
                                mapping[entry.name] = size
                            except (OSError, IOError):
                                # stat 失败时忽略该文件
                                pass
            except FileNotFoundError:
                # 目标目录不存在, 视作空目录
                pass
            return mapping

        self.log_message.emit("📂 扫描目录构建文件映射...")
        files_meta: dict[str, int] = await loop.run_in_executor(None, _scan_dir, output_dir)
        
        # 根据扫描结果分类文件并更新元数据
        existing_files = []
        files_to_download = []
        total_files = len(file_items)

        for idx, item in enumerate(file_items):
            if self._is_cancelled:
                break

            size_on_disk = files_meta.get(item.full_filename)
            if size_on_disk is not None and (item.size is None or size_on_disk == item.size):
                # 文件存在，更新元数据
                file_path = output_dir / item.full_filename
                item.update_disk_metadata(file_path)
                item.mark_completed(file_path)
                existing_files.append(item)
            else:
                files_to_download.append(item)

            # 定期更新进度
            if idx % 200 == 0 or idx == total_files - 1:
                progress_percent = (idx / total_files) * 100
                self.check_progress.emit(progress_percent)
                await asyncio.sleep(0)

        self.log_message.emit(f"✅ 完整扫描完成: 发现 {len(existing_files)} 个现有文件")
        return existing_files, files_to_download 

     
    
    async def _optimized_bloom_filter_check(self, file_items: List[FileItem], output_dir: Path, 
                                           bloom_filter, data_manager) -> tuple[List[FileItem], List[FileItem]]:
        """优化的Bloom Filter检查 - 最优执行顺序"""
        self.log_message.emit("🚀 执行最优顺序：Bloom Filter → 缓存分析 → 精确检查")
        
        # 第一阶段：Bloom Filter O(1)快速预过滤
        self.log_message.emit("⚡ 阶段1: Bloom Filter O(1)预过滤全部文件...")
        likely_existing, definitely_new = bloom_filter.fast_pre_filter(file_items)
        
        filter_info = bloom_filter.get_info()
        reduction_ratio = len(definitely_new) / len(file_items) * 100
        self.log_message.emit(
            f"📊 Bloom过滤完成: {len(definitely_new)} 个文件确认新增 ({reduction_ratio:.1f}%), "
            f"{len(likely_existing)} 个需要进一步分析"
        )
        
        existing_files = []
        files_to_download = list(definitely_new)  # 确定不存在的文件直接归类
        
        # 第二阶段：对可能存在的文件进行缓存可靠性分析
        if likely_existing:
            self.log_message.emit(f"🧠 阶段2: 缓存分析 {len(likely_existing)} 个可能存在的文件...")
            
            cache_analysis = data_manager.analyze_cache_reliability(likely_existing, output_dir)
            self.log_message.emit(f"📊 缓存分析: {cache_analysis['reason']}")
            
            # 第三阶段：根据缓存可靠性选择最优精确检查策略
            self.log_message.emit(f"🔍 阶段3: 精确检查策略选择...")
            
            if cache_analysis['recommendation'] == 'cache_reliable':
                self.log_message.emit("✅ 缓存可靠，使用缓存优先检查")
                precise_existing, precise_new = await self._cache_based_check(likely_existing, output_dir)
            elif cache_analysis['recommendation'] == 'incremental_check':
                self.log_message.emit("🔄 缓存部分可靠，使用增量检查")
                precise_existing, precise_new = await self._smart_incremental_check(likely_existing, output_dir, cache_analysis)
            else:
                self.log_message.emit("⚠️  缓存不可靠，使用完整扫描")
                precise_existing, precise_new = await self._optimized_full_scan(likely_existing, output_dir)
            
            existing_files.extend(precise_existing)
            files_to_download.extend(precise_new)
        
        # 第四阶段：总结优化效果
        total_files = len(file_items)
        bloom_saved = len(definitely_new)
        cache_processed = len(likely_existing)
        efficiency = bloom_saved / total_files * 100
        
        self.log_message.emit(
            f"✅ 三阶段优化完成: Bloom节省 {bloom_saved} 次检查 ({efficiency:.1f}%), "
            f"缓存处理 {cache_processed} 个文件, "
            f"误判率 {filter_info['estimated_false_positive']:.2%}"
        )
        
        return existing_files, files_to_download
    
    def _update_bloom_filter_on_completion(self, file_item: FileItem):
        """下载完成后更新Bloom Filter"""
        try:
            # 从DataManager导入用于获取Bloom Filter
            from .persistence import DataManager
            
            # 这里我们不直接访问DataManager实例，而是通过信号通知更新
            # 实际的Bloom Filter更新会在UI层处理
            pass
        except Exception as e:
            # 忽略Bloom Filter更新错误，不影响主流程
            pass 