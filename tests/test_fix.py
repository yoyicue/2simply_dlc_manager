#!/usr/bin/env python3
"""
DLC Manager 修复验证测试
专门用于验证修复的问题
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_ui_state_update():
    """测试UI状态更新"""
    print("🔍 测试UI状态更新...")
    
    try:
        from PySide6.QtWidgets import QApplication
        from ui import MainWindow
        import qasync
        
        app = QApplication(sys.argv)
        window = MainWindow()
        
        # 测试_update_ui_state方法
        window._update_ui_state()
        print("✅ _update_ui_state 方法正常工作")
        
        # 测试_apply_filters方法
        window._apply_filters()
        print("✅ _apply_filters 方法正常工作")
        
        return True
        
    except Exception as e:
        print(f"❌ UI测试失败: {e}")
        return False

def test_file_loading():
    """测试文件加载"""
    print("🔍 测试文件加载...")
    
    try:
        from core import DataManager
        
        # 检查 BigFilesMD5s.json 是否存在
        json_file = project_root / "BigFilesMD5s.json"
        if not json_file.exists():
            print("⚠️  BigFilesMD5s.json 文件不存在，跳过文件加载测试")
            return True
        
        data_manager = DataManager()
        file_items = data_manager.load_file_mapping(json_file)
        
        print(f"✅ 成功加载 {len(file_items)} 个文件条目")
        
        # 测试前几个条目
        for i, item in enumerate(file_items[:3]):
            print(f"  {i+1}. {item.filename} ({item.md5[:8]}...)")
        
        return True
        
    except Exception as e:
        print(f"❌ 文件加载测试失败: {e}")
        return False

def test_setEnabled_bug_fix():
    """测试setEnabled()传入None的Bug修复"""
    print("🔍 测试setEnabled()传入None的Bug修复...")
    
    try:
        from PySide6.QtWidgets import QApplication
        from ui import MainWindow
        
        # 重用已存在的QApplication实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        window = MainWindow()
        
        # 模拟没有downloader的情况
        window.downloader = None
        
        # 这之前会报错：'PySide6.QtWidgets.QWidget.setEnabled' called with wrong argument types
        window._update_ui_state()
        print("✅ setEnabled()参数类型错误已修复")
        
        # 测试各种状态组合
        window.current_output_dir = Path("/tmp")
        window._update_ui_state()
        print("✅ 有输出目录时的状态更新正常")
        
        return True
        
    except Exception as e:
        print(f"❌ setEnabled Bug修复测试失败: {e}")
        return False

if __name__ == "__main__":
    print("="*50)
    print("     DLC Manager 修复验证测试")
    print("="*50)
    
    tests = [
        test_ui_state_update,
        test_file_loading,
        test_setEnabled_bug_fix
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("="*50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有修复验证测试通过！")
        print("\n💡 现在可以尝试运行应用程序：")
        print("   python main.py")
    else:
        print("❌ 部分测试失败，需要进一步检查")
    
    print("="*50) 