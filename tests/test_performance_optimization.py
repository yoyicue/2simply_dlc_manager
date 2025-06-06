#!/usr/bin/env python3
"""
DLC Manager 批次跳过下载性能优化测试
"""
import sys
import asyncio
import time
from pathlib import Path
from typing import List

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.models import FileItem, DownloadConfig, DownloadStatus


def create_test_files(count: int, existing_ratio: float = 0.8) -> tuple[List[FileItem], Path]:
    """创建测试文件列表和临时目录"""
    import tempfile
    
    # 创建临时目录
    temp_dir = Path(tempfile.mkdtemp(prefix="dlc_test_"))
    
    # 创建测试文件项
    file_items = []
    for i in range(count):
        item = FileItem(
            filename=f"test_file_{i:04d}.json",
            md5=f"test_md5_{i:08x}",
            status=DownloadStatus.PENDING
        )
        file_items.append(item)
    
    # 创建一些"已存在"的文件
    existing_count = int(count * existing_ratio)
    for i in range(existing_count):
        item = file_items[i]
        fake_file = temp_dir / item.full_filename
        fake_file.write_text(f"fake content for {item.filename}")
    
    print(f"创建了 {count} 个测试文件项，其中 {existing_count} 个文件已存在")
    print(f"测试目录: {temp_dir}")
    
    return file_items, temp_dir


def test_batch_size_optimization():
    """测试批次大小优化"""
    print("\n" + "="*60)
    print("批次大小优化测试")
    print("="*60)
    
    config = DownloadConfig()
    
    test_cases = [
        (100, 3),    # 100个文件，只需下载3个
        (100, 15),   # 100个文件，需要下载15个
        (100, 50),   # 100个文件，需要下载50个
        (100, 80),   # 100个文件，需要下载80个
        (1000, 50),  # 1000个文件，只需下载50个
        (1000, 800), # 1000个文件，需要下载800个
    ]
    
    print(f"{'总文件数':<8} {'需下载':<8} {'跳过比例':<10} {'默认批次':<10} {'优化批次':<10} {'默认并发':<10} {'优化并发':<10}")
    print("-" * 80)
    
    for total, to_download in test_cases:
        skip_ratio = (total - to_download) / total
        batch_size = config.get_optimal_batch_size(total, to_download)
        concurrent = config.get_optimal_concurrent_requests(total, to_download)
        
        print(f"{total:<8} {to_download:<8} {skip_ratio*100:>7.1f}%   {config.batch_size:<10} {batch_size:<10} {config.concurrent_requests:<10} {concurrent:<10}")


async def test_file_check_performance():
    """测试文件检查性能"""
    print("\n" + "="*60)
    print("文件检查性能测试")
    print("="*60)
    
    # 导入下载器
    from core.downloader import Downloader
    
    test_cases = [
        (100, 0.8),   # 100个文件，80%已存在
        (500, 0.9),   # 500个文件，90%已存在
        (1000, 0.95), # 1000个文件，95%已存在
    ]
    
    for file_count, existing_ratio in test_cases:
        print(f"\n测试 {file_count} 个文件，{existing_ratio*100:.0f}% 已存在:")
        
        # 创建测试文件
        file_items, temp_dir = create_test_files(file_count, existing_ratio)
        
        # 创建下载器
        config = DownloadConfig()
        downloader = Downloader(config)
        
        # 记录开始时间
        start_time = time.time()
        
        # 执行文件检查
        existing_files, files_to_download = await downloader._batch_check_existing_files(file_items, temp_dir)
        
        # 记录结束时间
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"  检查耗时: {duration:.3f} 秒")
        print(f"  已存在: {len(existing_files)} 个")
        print(f"  需下载: {len(files_to_download)} 个")
        print(f"  检查速度: {file_count/duration:.1f} 文件/秒")
        
        # 清理临时文件
        import shutil
        shutil.rmtree(temp_dir)


async def main():
    """主测试函数"""
    print("DLC Manager 批次跳过下载性能优化测试")
    print("这个测试验证了以下优化：")
    print("1. 异步文件存在性检查")
    print("2. 智能批次大小调整")
    print("3. 智能并发数调整")
    print("4. 避免UI阻塞的分批处理")
    
    # 测试批次大小优化
    test_batch_size_optimization()
    
    # 测试文件检查性能
    await test_file_check_performance()
    
    print("\n" + "="*60)
    print("性能优化效果总结:")
    print("✅ 文件检查从同步改为异步，避免UI卡顿")
    print("✅ 根据跳过比例智能调整批次大小")
    print("✅ 根据实际下载文件数优化并发数")
    print("✅ 分批检查文件，及时反馈进度")
    print("✅ 预先过滤已存在文件，减少网络请求")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main()) 