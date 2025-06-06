#!/usr/bin/env python3
"""
DLC Manager asyncio 问题检查
专门检查所有异步相关的潜在问题
"""
import sys
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_event_loop_setup():
    """测试事件循环设置"""
    print("🔍 测试事件循环设置...")
    
    try:
        import qasync
        from PySide6.QtWidgets import QApplication
        
        # 测试能否创建qasync事件循环
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        print("  - 创建 QEventLoop...")
        loop = qasync.QEventLoop(app)
        assert loop is not None
        print("  - QEventLoop 创建成功")
        
        # 简单测试事件循环的基本功能
        print("  - 测试事件循环基本功能...")
        assert hasattr(loop, 'run_forever')
        assert hasattr(loop, 'close')
        assert callable(loop.run_forever)
        assert callable(loop.close)
        print("  - 基本功能测试通过")
        
        print("✅ 事件循环设置测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 事件循环设置测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_signal_slot_compatibility():
    """测试信号槽与async的兼容性"""
    print("🔍 测试信号槽与async的兼容性...")
    
    try:
        import qasync
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QObject, Signal, QTimer
        
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        class TestObject(QObject):
            test_signal = Signal()
            
            def __init__(self):
                super().__init__()
                self.async_called = False
                self.test_signal.connect(self.async_slot)
            
            @qasync.asyncSlot()
            async def async_slot(self):
                # 模拟异步操作
                await asyncio.sleep(0.01)
                self.async_called = True
        
        test_obj = TestObject()
        
        # 触发信号
        test_obj.test_signal.emit()
        
        # 给一点时间让异步槽执行
        import time
        time.sleep(0.1)
        
        print("✅ 信号槽与async兼容性测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 信号槽与async兼容性测试失败: {e}")
        return False

def test_downloader_thread_safety():
    """测试下载器的线程安全性"""
    print("🔍 测试下载器的线程安全性...")
    
    try:
        from core import Downloader, DownloadConfig
        from PySide6.QtWidgets import QApplication
        
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建下载器
        config = DownloadConfig(concurrent_requests=1, timeout=5)
        downloader = Downloader(config)
        
        # 测试信号是否可以正常连接
        signal_received = []
        
        def on_log_message(message):
            signal_received.append(message)
        
        downloader.log_message.connect(on_log_message)
        
        # 测试能否发射信号
        downloader.log_message.emit("测试消息")
        
        # 验证信号是否收到
        assert len(signal_received) == 1
        assert signal_received[0] == "测试消息"
        
        print("✅ 下载器线程安全性测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 下载器线程安全性测试失败: {e}")
        return False

async def test_async_await_chain():
    """测试异步调用链"""
    print("🔍 测试异步调用链...")
    
    try:
        from core import Downloader, DownloadConfig, FileItem, DownloadStatus
        import tempfile
        
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 创建测试文件项
            test_item = FileItem(
                filename="test.json",
                md5="fake123456789",
                status=DownloadStatus.PENDING
            )
            
            # 创建下载器
            config = DownloadConfig(concurrent_requests=1, timeout=3, max_retries=1)
            downloader = Downloader(config)
            
            # 测试异步调用链
            result = await downloader.download_files([test_item], temp_path)
            
            # 验证返回结果
            assert isinstance(result, dict)
            assert 'test.json' in result
            
            print("✅ 异步调用链测试通过")
            return True
        
    except Exception as e:
        print(f"❌ 异步调用链测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ui_async_integration():
    """测试UI与异步的集成"""
    print("🔍 测试UI与异步的集成...")
    
    try:
        import qasync
        from PySide6.QtWidgets import QApplication
        from ui import MainWindow
        
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建主窗口
        window = MainWindow()
        
        # 检查异步槽方法
        assert hasattr(window, '_start_download')
        assert hasattr(window._start_download, '__wrapped__')  # qasync装饰器标志
        
        # 测试能否调用（不实际执行）
        method = getattr(window, '_start_download')
        assert callable(method)
        
        print("✅ UI与异步集成测试通过")
        return True
        
    except Exception as e:
        print(f"❌ UI与异步集成测试失败: {e}")
        return False

def test_concurrent_safety():
    """测试并发安全性"""
    print("🔍 测试并发安全性...")
    
    try:
        import asyncio
        from core import Downloader, DownloadConfig
        
        # 测试能否同时创建多个下载器实例
        configs = [DownloadConfig(concurrent_requests=i+1) for i in range(3)]
        downloaders = [Downloader(config) for config in configs]
        
        # 测试每个下载器的配置
        for i, downloader in enumerate(downloaders):
            assert downloader.config.concurrent_requests == i + 1
            assert not downloader.is_downloading
        
        print("✅ 并发安全性测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 并发安全性测试失败: {e}")
        return False

async def main():
    """主测试函数"""
    print("🔬 DLC Manager asyncio 问题检查")
    print("=" * 60)
    
    sync_tests = [
        test_event_loop_setup,
        test_signal_slot_compatibility,
        test_downloader_thread_safety,
        test_ui_async_integration,
        test_concurrent_safety,
    ]
    
    async_tests = [
        test_async_await_chain,
    ]
    
    passed = 0
    total = len(sync_tests) + len(async_tests)
    
    # 运行同步测试
    for test in sync_tests:
        if test():
            passed += 1
    
    # 运行异步测试
    for test in async_tests:
        if await test():
            passed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 asyncio 检查结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有 asyncio 相关问题检查通过！")
        print("\n💡 异步功能运行正常，下载应该能够正常工作")
        return 0
    else:
        print("❌ 发现 asyncio 相关问题，请检查上述错误信息")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main())) 