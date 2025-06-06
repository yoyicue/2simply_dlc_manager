"""
异步下载器模块
"""
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from typing import List, Dict, Optional, Callable
from PySide6.QtCore import QObject, Signal, QModelIndex
import os  # 局部导入, 避免顶层不必要依赖

from .models import FileItem, DownloadStatus, DownloadConfig


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
        self._session: Optional[aiohttp.ClientSession] = None
        self._is_cancelled = False
        self._is_downloading = False
        self._semaphore: Optional[asyncio.Semaphore] = None
        
    async def _batch_check_existing_files(self, file_items: List[FileItem], output_dir: Path) -> tuple[List[FileItem], List[FileItem]]:
        """异步批量检查文件是否已存在
        
        返回:
            (existing_files, files_to_download)
        
        该实现通过一次性扫描输出目录, 构建 {文件名: 文件大小} 映射, 避免对每个条目都执行磁盘 IO, 大幅提升性能。
        """
        loop = asyncio.get_event_loop()

        # -----------------------------
        # 1. 扫描目录(在线程池中执行, 防止阻塞事件循环)
        # -----------------------------
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

        files_meta: dict[str, int] = await loop.run_in_executor(None, _scan_dir, output_dir)

        # -----------------------------
        # 2. 根据扫描结果分类文件
        # -----------------------------
        existing_files: list[FileItem] = []
        files_to_download: list[FileItem] = []
        total_files = len(file_items)

        for idx, item in enumerate(file_items):
            if self._is_cancelled:
                break

            size_on_disk = files_meta.get(item.full_filename)
            if size_on_disk is not None and (item.size is None or size_on_disk == item.size):
                existing_files.append(item)
            else:
                files_to_download.append(item)

            # 仅在一定间隔更新进度, 减少信号数量
            if idx % 200 == 0 or idx == total_files - 1:
                progress_percent = (idx / total_files) * 100
                self.check_progress.emit(progress_percent)
                await asyncio.sleep(0)  # 让出控制权, 保证 UI 流畅

        return existing_files, files_to_download
    
    async def download_files(self, file_items: List[FileItem], output_dir: Path) -> Dict[str, bool]:
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
        
        existing_files, files_to_download = await self._batch_check_existing_files(file_items, output_dir)
        
        # 发送检查完成信号
        self.check_progress.emit(100.0)
        
        # 处理已存在的文件
        completed_count = 0
        total_count = len(file_items)
        
        for item in existing_files:
            if self._is_cancelled:
                break
            item.mark_completed(output_dir / item.full_filename)
            results[item.filename] = True
            completed_count += 1
            
            # 更新进度
            overall_progress = (completed_count / total_count) * 100
            self.progress_updated.emit(item.filename, 100.0)
            self.file_completed.emit(item.filename, True, "文件已存在，跳过下载")
            self.overall_progress.emit(overall_progress, completed_count, total_count)
            
            # 让出控制权，避免长时间占用
            await asyncio.sleep(0)
        
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
        
        # 创建信号量控制并发 - 使用优化的并发数
        optimal_concurrent = self.config.get_optimal_concurrent_requests(len(file_items), len(files_to_download))
        self.log_message.emit(f"使用优化并发数: {optimal_concurrent}")
        self._semaphore = asyncio.Semaphore(optimal_concurrent)
        
        # 配置 aiohttp 会话 - 性能优化版本
        timeout = aiohttp.ClientTimeout(
            total=self.config.timeout,
            connect=min(30, self.config.timeout / 4),
            sock_read=min(60, self.config.timeout / 2)
        )
        
        connector = aiohttp.TCPConnector(
            limit=self.config.connection_limit,
            limit_per_host=self.config.connection_limit_per_host,
            force_close=False,
            enable_cleanup_closed=True,
            keepalive_timeout=30,
            ttl_dns_cache=300,
            use_dns_cache=True,
            happy_eyeballs_delay=0.25,
            ssl=False
        )
        
        try:
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                raise_for_status=False
            ) as session:
                self._session = session
                
                # 分批处理需要下载的文件 - 使用智能批次大小
                optimal_batch_size = self.config.get_optimal_batch_size(len(file_items), len(files_to_download))
                self.log_message.emit(f"使用优化批次大小: {optimal_batch_size}")
                
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
            self._session = None
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
                self.progress_updated.emit(file_item.filename, 100.0)
                self.file_completed.emit(file_item.filename, True, "文件已存在，跳过下载")
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
        """带进度的下载"""
        try:
            async with self._session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")
                
                # 获取文件大小
                content_length = response.headers.get('content-length')
                if content_length:
                    file_item.size = int(content_length)
                
                # 下载文件
                if file_item.is_binary_file:
                    # 二进制文件 - 性能优化版本
                    async with aiofiles.open(local_path, 'wb') as f:
                        downloaded = 0
                        chunk_size = self.config.chunk_size
                        async for chunk in response.content.iter_chunked(chunk_size):
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
                    # 文本文件
                    content = await response.text()
                    async with aiofiles.open(local_path, 'w', encoding='utf-8') as f:
                        await f.write(content)
                    
                    file_item.progress = 100.0
                    self.progress_updated.emit(file_item.filename, 100.0)
                
                # 标记完成
                file_item.mark_completed(local_path)
                self.file_completed.emit(file_item.filename, True, "下载成功")
                return True
                
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