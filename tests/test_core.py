#!/usr/bin/env python3
"""
DLC Manager 核心功能测试
"""

import sys
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_imports():
    """测试所有必要的模块导入"""
    print("🔍 测试模块导入...")
    
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QCoreApplication
        import qasync
        import aiohttp
        import aiofiles
        print("✅ 所有依赖模块导入成功")
    except ImportError as e:
        print(f"❌ 模块导入失败: {e}")
        return False
    
    try:
        from core import FileItem, DownloadStatus, DownloadConfig, Downloader, DataManager
        from ui import MainWindow, FileTableModel
        print("✅ 项目模块导入成功")
    except ImportError as e:
        print(f"❌ 项目模块导入失败: {e}")
        return False
    
    return True

def test_data_models():
    """测试数据模型"""
    print("\n🔍 测试数据模型...")
    
    try:
        from core.models import FileItem, DownloadStatus, DownloadConfig
        
        # 测试FileItem
        item = FileItem(
            filename="test.json",
            md5="abc123def456",
            status=DownloadStatus.PENDING
        )
        
        assert item.file_extension == ".json"
        assert item.base_filename == "test"
        assert item.full_filename == "test-abc123def456.json"
        
        # 测试DownloadConfig
        config = DownloadConfig(concurrent_requests=5, timeout=30)
        assert config.concurrent_requests == 5
        assert config.timeout == 30
        
        print("✅ 数据模型测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 数据模型测试失败: {e}")
        return False

def test_data_manager():
    """测试数据管理器"""
    print("\n🔍 测试数据管理器...")
    
    try:
        from core.persistence import DataManager
        from core.models import FileItem, DownloadStatus
        
        # 创建测试数据
        test_data = {
            "test1.json": "abc123",
            "test2.png": "def456"
        }
        
        # 创建临时JSON文件
        test_file = project_root / "test_mapping.json"
        with open(test_file, 'w') as f:
            json.dump(test_data, f)
        
        # 测试加载
        manager = DataManager()
        file_items = manager.load_file_mapping(test_file)
        
        assert len(file_items) == 2
        assert file_items[0].filename == "test1.json"
        assert file_items[0].md5 == "abc123"
        assert file_items[1].filename == "test2.png"
        assert file_items[1].md5 == "def456"
        
        # 清理测试文件
        test_file.unlink()
        
        print("✅ 数据管理器测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 数据管理器测试失败: {e}")
        return False

def test_gui_components():
    """测试GUI组件"""
    print("\n🔍 测试GUI组件...")
    
    try:
        from PySide6.QtWidgets import QApplication
        from ui import MainWindow, FileTableModel
        from core.models import FileItem, DownloadStatus
        
        # 创建应用程序实例（但不显示）
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 测试表格模型
        model = FileTableModel()
        test_items = [
            FileItem("test1.json", "abc123", DownloadStatus.PENDING),
            FileItem("test2.png", "def456", DownloadStatus.COMPLETED)
        ]
        
        model.set_file_items(test_items)
        assert model.rowCount() == 2
        assert model.columnCount() == len(model.COLUMNS)
        
        # 测试过滤
        model.apply_filters(DownloadStatus.PENDING, "")
        assert model.rowCount() == 1
        
        model.apply_filters(None, "test1")
        assert model.rowCount() == 1
        
        # 测试主窗口创建
        window = MainWindow()
        assert window is not None
        
        print("✅ GUI组件测试通过")
        return True
        
    except Exception as e:
        print(f"❌ GUI组件测试失败: {e}")
        return False

def test_bigfiles_json():
    """测试BigFilesMD5s.json文件"""
    print("\n🔍 测试BigFilesMD5s.json文件...")
    
    try:
        json_file = project_root / "BigFilesMD5s.json"
        if not json_file.exists():
            print("⚠️  BigFilesMD5s.json 文件不存在，跳过测试")
            return True
        
        from core.persistence import DataManager
        
        manager = DataManager()
        file_items = manager.load_file_mapping(json_file)
        
        print(f"✅ 成功加载 {len(file_items)} 个文件条目")
        
        # 显示前几个条目作为示例
        for i, item in enumerate(file_items[:3]):
            print(f"   {i+1}. {item.filename} ({item.md5[:8]}...)")
        
        if len(file_items) > 3:
            print(f"   ... 还有 {len(file_items) - 3} 个文件")
        
        return True
        
    except Exception as e:
        print(f"❌ BigFilesMD5s.json 测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🧪 DLC Manager 核心功能测试")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_data_models,
        test_data_manager,
        test_gui_components,
        test_bigfiles_json
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！应用程序已准备就绪。")
        print("\n💡 运行 'python main.py' 启动应用程序")
    else:
        print("❌ 部分测试失败，请检查错误信息")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 