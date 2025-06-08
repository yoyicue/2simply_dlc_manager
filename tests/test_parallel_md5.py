#!/usr/bin/env python3
"""
测试并行MD5计算器性能和功能
"""
import asyncio
import os
import sys
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.verification import ParallelMD5Calculator
from core.models import FileItem, DownloadConfig


def create_test_files():
    """创建测试文件"""
    test_dir = Path("test_md5_files")
    test_dir.mkdir(exist_ok=True)
    
    test_files = []
    
    # 创建不同大小的测试文件
    files_info = [
        ("small_file_1.txt", b"Hello World!" * 100),  # ~1.2KB
        ("small_file_2.json", b'{"test": "data"}' * 500),  # ~7KB
        ("medium_file.png", b"PNG_DATA" * 5000),  # ~40KB
        ("large_file.mp4", b"VIDEO_DATA" * 50000),  # ~500KB
    ]
    
    for filename, content in files_info:
        file_path = test_dir / filename
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # 计算真实MD5
        import hashlib
        real_md5 = hashlib.md5(content).hexdigest()
        
        # 创建FileItem (使用真实MD5确保验证成功)
        base_name = filename.split('.')[0]
        ext = '.' + filename.split('.')[-1]
        
        file_item = FileItem(
            filename=filename,
            md5=real_md5,
            size=len(content)
        )
        
        # 重命名文件为包含MD5的格式
        new_filename = f"{base_name}-{real_md5}{ext}"
        new_path = test_dir / new_filename
        file_path.rename(new_path)
        
        test_files.append(file_item)
        print(f"✅ 创建测试文件: {new_filename} ({len(content)} bytes, MD5: {real_md5})")
    
    return test_files, test_dir


async def test_parallel_md5():
    """测试并行MD5计算"""
    print("🚀 开始测试并行MD5计算器")
    print("=" * 50)
    
    # 创建测试文件
    test_files, test_dir = create_test_files()
    
    # 创建配置
    config = DownloadConfig(
        concurrent_requests=8,
        batch_size=2
    )
    
    # 创建并行MD5计算器
    calculator = ParallelMD5Calculator(config)
    
    # 连接信号处理
    def on_log(message):
        print(f"[LOG] {message}")
    
    def on_file_completed(filename, success, message):
        status = "✅" if success else "❌"
        print(f"[FILE] {status} {filename} - {message}")
    
    def on_progress(progress, completed, total):
        print(f"[PROGRESS] {progress:.1f}% ({completed}/{total})")
    
    calculator.log_message.connect(on_log)
    calculator.file_completed.connect(on_file_completed)
    calculator.overall_progress.connect(on_progress)
    
    # 开始计算
    start_time = time.time()
    
    try:
        results = await calculator.calculate_md5_parallel(test_files, test_dir)
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        print("=" * 50)
        print(f"🎉 测试完成！耗时: {elapsed:.2f} 秒")
        print(f"📊 处理了 {len(results)} 个文件")
        
        # 统计结果
        success_count = sum(1 for r in results.values() if r.success and not r.error)
        failed_count = len(results) - success_count
        
        print(f"✅ 成功: {success_count}")
        print(f"❌ 失败: {failed_count}")
        
        # 详细结果
        print("\n📋 详细结果:")
        for filename, result in results.items():
            status = "✅" if result.success and not result.error else "❌"
            time_info = f"{result.elapsed_time:.3f}s" if result.elapsed_time > 0 else "N/A"
            size_info = f"{result.file_size/1024:.1f}KB" if result.file_size > 0 else "N/A"
            print(f"  {status} {filename} ({size_info}, {time_info})")
            if result.error:
                print(f"      错误: {result.error}")
        
        # 性能统计
        if success_count > 0:
            total_size = sum(r.file_size for r in results.values() if r.success)
            total_time = sum(r.elapsed_time for r in results.values() if r.success)
            
            if total_time > 0:
                throughput = (total_size / 1024 / 1024) / total_time
                files_per_sec = success_count / total_time
                print(f"\n📈 性能统计:")
                print(f"  吞吐量: {throughput:.2f} MB/s")
                print(f"  文件处理速度: {files_per_sec:.1f} 文件/秒")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理测试文件
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir)
            print(f"\n🧹 已清理测试目录: {test_dir}")


async def test_cancellation():
    """测试取消功能"""
    print("\n🛑 测试取消功能")
    print("-" * 30)
    
    # 创建更多测试文件来测试取消
    test_dir = Path("test_cancel_files")
    test_dir.mkdir(exist_ok=True)
    
    test_files = []
    for i in range(10):  # 创建10个文件
        filename = f"cancel_test_{i}.txt"
        content = b"CANCEL_TEST_DATA" * 1000  # ~16KB
        file_path = test_dir / filename
        
        with open(file_path, 'wb') as f:
            f.write(content)
        
        import hashlib
        real_md5 = hashlib.md5(content).hexdigest()
        
        # 重命名文件
        new_filename = f"cancel_test_{i}-{real_md5}.txt"
        new_path = test_dir / new_filename
        file_path.rename(new_path)
        
        file_item = FileItem(filename=filename, md5=real_md5, size=len(content))
        test_files.append(file_item)
    
    print(f"✅ 创建了 {len(test_files)} 个测试文件")
    
    # 创建计算器
    config = DownloadConfig(concurrent_requests=4, batch_size=3)
    calculator = ParallelMD5Calculator(config)
    
    # 连接信号
    def on_log(message):
        print(f"[CANCEL_LOG] {message}")
    
    calculator.log_message.connect(on_log)
    
    # 启动计算任务
    async def run_calculation():
        try:
            await calculator.calculate_md5_parallel(test_files, test_dir)
        except Exception as e:
            print(f"计算任务异常: {e}")
    
    # 启动任务
    calc_task = asyncio.create_task(run_calculation())
    
    # 2秒后取消
    await asyncio.sleep(2)
    print("🛑 发送取消信号...")
    calculator.cancel_calculation()
    
    # 等待任务完成
    try:
        await calc_task
        print("✅ 取消测试完成")
    except Exception as e:
        print(f"取消测试异常: {e}")
    
    # 清理
    import shutil
    if test_dir.exists():
        shutil.rmtree(test_dir)
        print(f"🧹 已清理取消测试目录: {test_dir}")


async def main():
    """主测试函数"""
    print("🧪 并行MD5计算器测试套件")
    print("=" * 60)
    
    # 基本功能测试
    await test_parallel_md5()
    
    # 取消功能测试
    await test_cancellation()
    
    print("\n🎉 所有测试完成！")


if __name__ == "__main__":
    # 检测当前平台
    import platform
    print(f"🖥️  平台信息: {platform.system()} {platform.machine()}")
    print(f"🔧 CPU核心数: {os.cpu_count()}")
    print(f"🐍 Python版本: {platform.python_version()}")
    print()
    
    # 运行测试
    asyncio.run(main()) 