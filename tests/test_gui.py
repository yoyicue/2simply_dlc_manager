#!/usr/bin/env python3
"""
DLC Manager GUI 测试脚本
用于快速测试GUI功能
"""
import sys
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
import qasync

from core import FileItem, DownloadStatus, DataManager
from ui import MainWindow


class GUITester:
    """GUI测试器"""
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.main_window = MainWindow()
        
        # 创建测试数据
        self.create_test_data()
        
        # 设置自动测试定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.auto_test)
        
    def create_test_data(self):
        """创建测试数据"""
        test_data = {
            "song1.json": "abc123def456",
            "song2.png": "789xyz012345", 
            "song3.mp3": "fedcba987654",
            "tutorial.json": "555666777888",
            "background.jpg": "111222333444",
            "audio.wav": "999888777666",
            "config.json": "aabbccddee11",
            "preview.png": "ffeedc123456"
        }
        
        # 创建测试JSON文件
        test_file = project_root / "test_files.json"
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, indent=2)
        
        print(f"📄 创建测试文件: {test_file}")
        return test_file
    
    def auto_test(self):
        """自动测试功能"""
        try:
            # 自动加载测试数据
            test_file = project_root / "test_files.json"
            if test_file.exists():
                data_manager = self.main_window.data_manager
                file_items = data_manager.load_file_mapping(test_file)
                
                # 模拟一些不同的状态
                if len(file_items) >= 4:
                    file_items[0].mark_completed(Path("fake_path.json"))
                    file_items[1].mark_failed("测试错误")
                    file_items[2].progress = 45.5
                    file_items[2].status = DownloadStatus.DOWNLOADING
                    file_items[3].mark_skipped("用户跳过")
                
                self.main_window.file_table_model.set_file_items(file_items)
                self.main_window.mapping_file_label.setText(f"映射文件: {test_file.name}")
                self.main_window._update_ui_state()
                self.main_window._update_statistics()
                self.main_window._log("🧪 自动加载测试数据完成")
                
                # 停止定时器
                self.timer.stop()
                
        except Exception as e:
            print(f"自动测试失败: {e}")
            self.timer.stop()
    
    def run(self):
        """运行测试"""
        print("🧪 启动GUI测试...")
        print("📋 功能说明:")
        print("  1. 自动加载测试数据")
        print("  2. 测试表格显示和状态")
        print("  3. 测试过滤和搜索功能")
        print("  4. 测试下载控制按钮")
        print("-" * 50)
        
        # 显示主窗口
        self.main_window.show()
        
        # 设置Qt事件循环与asyncio集成
        loop = qasync.QEventLoop(self.app)
        
        # 启动自动测试（延迟500ms）
        self.timer.start(500)
        
        try:
            with loop:
                loop.run_forever()
        except KeyboardInterrupt:
            print("\n🛑 测试中断")
        finally:
            print("🧹 清理测试资源...")
            # 清理测试文件
            test_file = project_root / "test_files.json"
            if test_file.exists():
                test_file.unlink()
                print(f"🗑️  删除测试文件: {test_file}")


def main():
    """主函数"""
    try:
        tester = GUITester()
        tester.run()
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main() 