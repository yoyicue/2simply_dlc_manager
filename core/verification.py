"""
并行MD5验证器 - 基于现有ThreadPoolExecutor模式优化
"""
import asyncio
import hashlib
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from PySide6.QtCore import QObject, Signal

from .models import FileItem, DownloadConfig, DownloadStatus, MD5VerifyStatus


@dataclass
class MD5Result:
    """MD5计算结果"""
    filename: str
    success: bool
    md5_hash: str
    calculated_md5: str = ""
    file_size: int = 0
    elapsed_time: float = 0.0
    error: str = ""


class ParallelMD5Calculator(QObject):
    """并行MD5验证器 - 专为海量小文件优化"""
    
    # 信号定义 - 与现有UI兼容
    progress_updated = Signal(str, float)  # 文件名, 进度
    file_completed = Signal(str, bool, str)  # 文件名, 成功, 消息  
    overall_progress = Signal(float, int, int)  # 进度%, 完成数, 总数
    log_message = Signal(str)  # 日志消息
    
    def __init__(self, config: Optional[DownloadConfig] = None):
        super().__init__()
        self.config = config or DownloadConfig()
        self._cancelled = False
        
    async def calculate_md5_parallel(self, file_items: List[FileItem], 
                                   output_dir: Path) -> Dict[str, MD5Result]:
        """并行计算MD5 - 复用现有ThreadPoolExecutor模式"""
        if not file_items:
            return {}
        
        self._cancelled = False
        results = {}
        
        # 使用现有的智能并发算法
        optimal_threads = self._get_optimal_threads(file_items)
        batch_size = self._get_optimal_batch_size(file_items)
        
        self.log_message.emit(f"🚀 启动并行MD5计算: {len(file_items)} 个文件")
        self.log_message.emit(f"⚡ 使用 {optimal_threads} 线程, 批次大小 {batch_size}")
        
        # 分批处理 - 复用现有分批逻辑
        batches = self._create_batches(file_items, batch_size)
        completed_files = 0
        total_files = len(file_items)
        
        for batch_idx, batch in enumerate(batches):
            if self._cancelled:
                break
                
            self.log_message.emit(f"🔄 处理批次 {batch_idx + 1}/{len(batches)} ({len(batch)} 个文件)")
            
            # 并行处理当前批次 - 复用现有ThreadPoolExecutor模式
            batch_results = await self._process_batch_parallel(
                batch, output_dir, optimal_threads
            )
            
            # 处理批次结果
            for result in batch_results:
                results[result.filename] = result
                completed_files += 1
                
                # 发送文件完成信号
                success_msg = "MD5验证成功" if result.success and not result.error else result.error
                self.file_completed.emit(result.filename, result.success, success_msg)
                
                # 更新整体进度
                progress = (completed_files / total_files) * 100
                self.overall_progress.emit(progress, completed_files, total_files)
            
            # 批次间暂停，保持UI响应
            await asyncio.sleep(0.01)
        
        # 输出统计信息
        if not self._cancelled:
            self._log_performance_stats(results)
        
        return results
    
    async def _process_batch_parallel(self, batch: List[FileItem], 
                                    output_dir: Path, max_workers: int) -> List[MD5Result]:
        """并行处理批次 - 复用现有ThreadPoolExecutor模式"""
        loop = asyncio.get_event_loop()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 创建任务列表
            tasks = [
                loop.run_in_executor(executor, self._calculate_single_md5, item, output_dir)
                for item in batch
            ]
            
            # 等待所有任务完成，支持取消
            batch_results = []
            completed_tasks = 0
            
            for task in asyncio.as_completed(tasks):
                if self._cancelled:
                    # 取消剩余任务
                    for remaining_task in tasks:
                        if not remaining_task.done():
                            remaining_task.cancel()
                    break
                
                try:
                    result = await task
                    batch_results.append(result)
                    completed_tasks += 1
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    # 找到对应的文件项
                    corresponding_item = None
                    for item in batch:
                        if not any(r.filename == item.filename for r in batch_results):
                            corresponding_item = item
                            break
                    
                    error_result = MD5Result(
                        filename=corresponding_item.filename if corresponding_item else "unknown",
                        success=False,
                        md5_hash=corresponding_item.md5 if corresponding_item else "",
                        error=f"计算异常: {str(e)}"
                    )
                    batch_results.append(error_result)
                    completed_tasks += 1
            
            return batch_results
    
    def _calculate_single_md5(self, file_item: FileItem, output_dir: Path) -> MD5Result:
        """计算单个文件的MD5 - 优化版本"""
        start_time = time.time()
        file_path = output_dir / file_item.full_filename
        
        try:
            # 检查文件是否存在
            if not file_path.exists():
                return MD5Result(
                    filename=file_item.filename,
                    success=False,
                    md5_hash=file_item.md5,
                    error="文件不存在"
                )
            
            # 获取文件大小
            file_size = file_path.stat().st_size
            
            # 读取并计算MD5
            calculated_md5 = self._calculate_file_md5(file_path)
            
            # 验证MD5
            expected_md5 = file_item.md5.lower()
            actual_md5 = calculated_md5.lower()
            is_match = expected_md5 == actual_md5
            
            elapsed_time = time.time() - start_time
            
            return MD5Result(
                filename=file_item.filename,
                success=True,
                md5_hash=expected_md5,
                calculated_md5=actual_md5,
                file_size=file_size,
                elapsed_time=elapsed_time,
                error="" if is_match else f"MD5不匹配: 期望{expected_md5}, 实际{actual_md5}"
            )
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            return MD5Result(
                filename=file_item.filename,
                success=False,
                md5_hash=file_item.md5,
                elapsed_time=elapsed_time,
                error=f"计算MD5失败: {str(e)}"
            )
    
    def _calculate_file_md5(self, file_path: Path) -> str:
        """计算文件MD5 - Apple Silicon优化版本"""
        try:
            # 尝试使用Apple Silicon优化
            return self._calculate_md5_apple_optimized(file_path)
        except Exception as e:
            raise Exception(f"读取文件失败: {str(e)}")
    
    def _calculate_md5_apple_optimized(self, file_path: Path) -> str:
        """Apple Silicon优化的MD5计算"""
        import platform
        
        # 检测Apple Silicon
        is_apple_silicon = (platform.system() == "Darwin" and 
                           platform.machine() == "arm64")
        
        try:
            file_size = file_path.stat().st_size
            
            if is_apple_silicon:
                # Apple Silicon优化路径
                if file_size < 512 * 1024:  # <512KB小文件
                    # 统一内存架构优势：一次性读取
                    with open(file_path, 'rb') as f:
                        data = f.read()
                    
                    # 尝试硬件加速模式
                    try:
                        return hashlib.md5(data, usedforsecurity=False).hexdigest()
                    except TypeError:
                        return hashlib.md5(data).hexdigest()
                else:
                    # 使用Apple Silicon优化的16KB块大小
                    md5_hash = hashlib.md5()
                    with open(file_path, 'rb') as f:
                        while chunk := f.read(16384):  # 16KB - Apple Silicon最优
                            if self._cancelled:
                                break
                            md5_hash.update(chunk)
                    return md5_hash.hexdigest()
            else:
                # 非Apple Silicon：使用原有逻辑
                md5_hash = hashlib.md5()
                
                if file_size < 1024 * 1024:  # <1MB
                    with open(file_path, 'rb') as f:
                        md5_hash.update(f.read())
                else:
                    # 64KB块
                    with open(file_path, 'rb') as f:
                        while chunk := f.read(65536):
                            if self._cancelled:
                                break
                            md5_hash.update(chunk)
                
                return md5_hash.hexdigest()
                
        except Exception as e:
            raise Exception(f"MD5计算失败: {str(e)}")
    
    def _get_optimal_threads(self, file_items: List[FileItem]) -> int:
        """获取最优线程数 - 复用现有算法"""
        # 基于CPU核心数和文件特征
        cpu_cores = os.cpu_count() or 4
        
        # 针对海量小文件优化
        base_threads = min(cpu_cores * 4, 32)  # 最多32线程
        
        # 根据文件数量调整
        file_count = len(file_items)
        if file_count < 10:
            return min(file_count, 4)
        elif file_count < 100:
            return min(base_threads // 2, 16)
        else:
            return base_threads
    
    def _get_optimal_batch_size(self, file_items: List[FileItem]) -> int:
        """获取最优批次大小 - 基于双重性能测试优化"""
        file_count = len(file_items)
        
        # 基于不同规模的性能测试结果优化
        if file_count < 20:
            return min(file_count, 10)  # 极小数量：避免空批次
        elif file_count < 200:
            # 小规模：大批次减少调度开销，I/O竞争不激烈
            return min(50, file_count)  
        elif file_count < 1000:
            # 中规模：平衡调度开销和I/O竞争
            return 30
        elif file_count < 5000:
            # 大规模：I/O竞争开始显现，小批次更优
            return 20  
        else:
            # 海量文件：严重I/O竞争，最小批次避免磁盘争抢
            return 15
    
    def _create_batches(self, file_items: List[FileItem], batch_size: int) -> List[List[FileItem]]:
        """创建批次 - 简化版本"""
        batches = []
        for i in range(0, len(file_items), batch_size):
            batches.append(file_items[i:i + batch_size])
        return batches
    
    def _log_performance_stats(self, results: Dict[str, MD5Result]):
        """记录性能统计"""
        successful_results = [r for r in results.values() if r.success]
        failed_results = [r for r in results.values() if not r.success]
        
        success_count = len(successful_results)
        failed_count = len(failed_results)
        
        self.log_message.emit(f"✅ 并行MD5计算完成: 成功 {success_count}, 失败 {failed_count}")
        
        if successful_results:
            total_size = sum(r.file_size for r in successful_results)
            total_time = sum(r.elapsed_time for r in successful_results)
            
            if total_time > 0:
                throughput_mbs = (total_size / 1024 / 1024) / total_time
                files_per_sec = len(successful_results) / total_time
                
                self.log_message.emit(f"📈 性能统计: {throughput_mbs:.1f} MB/s, {files_per_sec:.1f} 文件/秒")
                self.log_message.emit(f"💾 处理数据: {total_size/1024/1024:.1f} MB, 耗时 {total_time:.1f} 秒")
    
    def cancel_calculation(self):
        """取消计算"""
        self._cancelled = True
        self.log_message.emit("⚠️ MD5计算已取消") 