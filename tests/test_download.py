#!/usr/bin/env python3
"""
DLC Manager 下载功能测试
"""
import sys
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_download_config():
    """测试下载配置"""
    print("🔍 测试下载配置...")
    
    try:
        from core.models import DownloadConfig
        
        # 测试默认配置
        config = DownloadConfig()
        assert config.concurrent_requests == 50
        assert config.timeout == 120
        assert config.batch_size == 20
        
        # 测试自定义配置
        config = DownloadConfig(
            concurrent_requests=5,
            timeout=30,
            batch_size=5
        )
        assert config.concurrent_requests == 5
        assert config.timeout == 30
        assert config.batch_size == 5
        
        print("✅ 下载配置测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 下载配置测试失败: {e}")
        return False

def test_downloader_creation():
    """测试下载器创建"""
    print("🔍 测试下载器创建...")
    
    try:
        from core import Downloader, DownloadConfig, FileItem, DownloadStatus
        
        # 创建下载配置
        config = DownloadConfig(concurrent_requests=2, timeout=10)
        
        # 创建下载器
        downloader = Downloader(config)
        assert downloader.config.concurrent_requests == 2
        assert downloader.config.timeout == 10
        assert not downloader.is_downloading
        
        # 测试信号连接（简单检查信号存在）
        assert hasattr(downloader, 'progress_updated')
        assert hasattr(downloader, 'file_completed')
        assert hasattr(downloader, 'overall_progress')
        
        print("✅ 下载器创建测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 下载器创建测试失败: {e}")
        return False

async def test_simple_download():
    """测试简单下载功能"""
    print("🔍 测试简单下载功能...")
    
    try:
        from core import Downloader, DownloadConfig, FileItem, DownloadStatus
        import tempfile
        
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 创建测试文件项（使用一个可能不存在的小文件）
            test_item = FileItem(
                filename="test.json",
                md5="nonexistent123456789",  # 假的MD5，测试会失败但不会崩溃
                status=DownloadStatus.PENDING
            )
            
            # 创建下载器
            config = DownloadConfig(concurrent_requests=1, timeout=5, max_retries=1)
            downloader = Downloader(config)
            
            # 记录信号
            signals_received = []
            
            def on_log_message(message):
                signals_received.append(('log', message))
            
            def on_file_completed(filename, success, message):
                signals_received.append(('completed', filename, success, message))
            
            def on_download_started():
                signals_received.append(('started',))
            
            def on_download_finished(success_count, failed_count):
                signals_received.append(('finished', success_count, failed_count))
            
            # 连接信号
            downloader.log_message.connect(on_log_message)
            downloader.file_completed.connect(on_file_completed)
            downloader.download_started.connect(on_download_started)
            downloader.download_finished.connect(on_download_finished)
            
            # 开始下载（预期会失败，但能测试整个流程）
            result = await downloader.download_files([test_item], temp_path)
            
            # 检查结果
            assert isinstance(result, dict)
            assert 'test.json' in result
            assert result['test.json'] == False  # 预期失败
            
            # 检查信号
            signal_types = [s[0] for s in signals_received]
            assert 'started' in signal_types
            assert 'log' in signal_types
            assert 'completed' in signal_types
            assert 'finished' in signal_types
            
            print("✅ 简单下载功能测试通过（预期失败但流程正常）")
            return True
        
    except Exception as e:
        print(f"❌ 简单下载功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_qasync_integration():
    """测试qasync集成"""
    print("🔍 测试qasync集成...")
    
    try:
        import qasync
        from PySide6.QtWidgets import QApplication
        from ui import MainWindow
        
        # 创建应用
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建主窗口
        window = MainWindow()
        
        # 检查异步方法
        assert hasattr(window, '_start_download')
        
        print("✅ qasync集成测试通过")
        return True
        
    except Exception as e:
        print(f"❌ qasync集成测试失败: {e}")
        return False

async def main():
    """主测试函数"""
    print("🧪 DLC Manager 下载功能测试")
    print("=" * 50)
    
    tests = [
        test_download_config,
        test_downloader_creation,
        test_qasync_integration,
    ]
    
    async_tests = [
        test_simple_download,
    ]
    
    passed = 0
    total = len(tests) + len(async_tests)
    
    # 运行同步测试
    for test in tests:
        if test():
            passed += 1
    
    # 运行异步测试
    for test in async_tests:
        if await test():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有下载功能测试通过！")
        print("\n💡 下载功能已准备就绪，可以尝试在GUI中下载文件")
    else:
        print("❌ 部分测试失败，请检查错误信息")
        return 1
    
    return 0

if __name__ == "__main__":
    # 使用asyncio运行测试
    sys.exit(asyncio.run(main())) 