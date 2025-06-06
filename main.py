#!/usr/bin/env python3
"""
DLC Manager 主程序
一个基于 PySide6 的 DLC 下载管理工具
"""
import sys
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication
import qasync

from ui import MainWindow


class DLCManagerApp:
    """DLC管理器应用程序"""
    
    def __init__(self):
        # 设置应用程序信息
        QCoreApplication.setApplicationName("DLC Manager")
        QCoreApplication.setApplicationVersion("1.0.0")
        QCoreApplication.setOrganizationName("DLC Tools")
        
        # 创建Qt应用
        self.app = QApplication(sys.argv)
        
        # 设置应用程序样式
        self.app.setStyle('Fusion')  # 使用Fusion样式以获得现代外观
        
        # 加载样式表
        self._load_stylesheet()
        
        # 应用程序图标
        # self.app.setWindowIcon(QIcon("resources/icon.png"))  # 如果有图标文件
        
        # 创建主窗口
        self.main_window = MainWindow()
    
    def _load_stylesheet(self):
        """加载样式表"""
        try:
            style_file = Path(__file__).parent / "resources" / "style.qss"
            if style_file.exists():
                with open(style_file, 'r', encoding='utf-8') as f:
                    self.app.setStyleSheet(f.read())
        except Exception as e:
            print(f"加载样式表失败: {e}")
        
    def run(self):
        """运行应用程序"""
        # 显示主窗口
        self.main_window.show()
        
        # 设置Qt事件循环与asyncio集成
        loop = qasync.QEventLoop(self.app)
        asyncio.set_event_loop(loop)
        
        try:
            # 运行事件循环
            with loop:
                loop.run_forever()
        except KeyboardInterrupt:
            print("\n用户中断，正在退出...")
        except Exception as e:
            print(f"事件循环错误: {e}")
        finally:
            # 清理资源
            self._cleanup()
            # 确保事件循环正确关闭
            try:
                if not loop.is_closed():
                    loop.close()
            except:
                pass
    
    def _cleanup(self):
        """清理应用程序资源"""
        try:
            # 取消正在进行的下载
            if (hasattr(self.main_window, 'downloader') and 
                self.main_window.downloader and 
                self.main_window.downloader.is_downloading):
                self.main_window.downloader.cancel_download()
            
            # 保存当前状态
            if hasattr(self.main_window, 'data_manager'):
                try:
                    self.main_window.data_manager.save_state(
                        self.main_window.file_table_model.get_file_items(),
                        self.main_window.current_output_dir
                    )
                except Exception as e:
                    print(f"保存状态失败: {e}")
            
        except Exception as e:
            print(f"清理资源时发生错误: {e}")


def main():
    """主函数"""
    try:
        # 创建并运行应用程序
        app = DLCManagerApp()
        app.run()
        
    except Exception as e:
        print(f"应用程序启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main() 