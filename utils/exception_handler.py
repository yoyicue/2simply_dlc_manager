#!/usr/bin/env python3
"""
全局异常处理器
捕获并优雅地处理应用中的未处理异常
"""

import sys
import traceback
import logging
from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import QMessageBox, QApplication
from PySide6.QtCore import QObject, Signal, QTimer

class GlobalExceptionHandler(QObject):
    """全局异常处理器"""
    
    error_occurred = Signal(str)
    
    def __init__(self, enable_logging=True):
        super().__init__()
        self.enable_logging = enable_logging
        self._setup_logging()
        
        # 设置全局异常处理
        sys.excepthook = self.handle_exception
        
        # 连接信号
        self.error_occurred.connect(self._show_error_dialog)
        
    def _setup_logging(self):
        """设置日志记录"""
        if not self.enable_logging:
            return
            
        try:
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            
            log_file = log_dir / f"dlc_manager_{datetime.now().strftime('%Y%m%d')}.log"
            
            logging.basicConfig(
                level=logging.ERROR,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(log_file, encoding='utf-8'),
                    logging.StreamHandler()
                ]
            )
            
            self.logger = logging.getLogger(__name__)
        except Exception as e:
            print(f"⚠️ 日志系统初始化失败: {e}")
            self.enable_logging = False
    
    def handle_exception(self, exc_type, exc_value, exc_traceback):
        """处理未捕获的异常"""
        
        # 忽略 KeyboardInterrupt
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        # 格式化异常信息
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        
        # 记录到日志
        if self.enable_logging and hasattr(self, 'logger'):
            self.logger.error(f"未处理的异常:\n{error_msg}")
        
        # 打印到控制台
        print(f"❌ 未处理的异常: {error_msg}")
        
        # 发送信号显示错误对话框
        self.error_occurred.emit(str(exc_value))
    
    def _show_error_dialog(self, error_message):
        """显示错误对话框"""
        try:
            # 确保在主线程中执行
            app = QApplication.instance()
            if app is None:
                return
                
            # 使用 QTimer 确保在事件循环中执行
            QTimer.singleShot(0, lambda: self._create_error_dialog(error_message))
            
        except Exception as e:
            print(f"❌ 无法显示错误对话框: {e}")
    
    def _create_error_dialog(self, error_message):
        """创建并显示错误对话框"""
        try:
            # 创建错误消息框
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("程序错误")
            msg_box.setText("程序遇到了一个未处理的错误")
            
            # 限制错误消息长度
            if len(error_message) > 200:
                detailed_text = error_message
                error_message = error_message[:200] + "..."
            else:
                detailed_text = error_message
            
            msg_box.setInformativeText(f"错误详情:\n{error_message}\n\n程序将尝试继续运行。")
            msg_box.setDetailedText(detailed_text)
            
            # 添加按钮
            msg_box.setStandardButtons(QMessageBox.Ok | QMessageBox.Close)
            msg_box.setDefaultButton(QMessageBox.Ok)
            
            # 设置按钮文本
            ok_button = msg_box.button(QMessageBox.Ok)
            if ok_button:
                ok_button.setText("继续运行")
                
            close_button = msg_box.button(QMessageBox.Close)
            if close_button:
                close_button.setText("退出程序")
            
            # 显示对话框
            result = msg_box.exec()
            
            # 处理用户选择
            if result == QMessageBox.Close:
                app = QApplication.instance()
                if app:
                    app.quit()
                    
        except Exception as e:
            print(f"❌ 创建错误对话框失败: {e}")
    
    def log_info(self, message):
        """记录信息日志"""
        if self.enable_logging and hasattr(self, 'logger'):
            self.logger.info(message)
        print(f"ℹ️ {message}")
    
    def log_warning(self, message):
        """记录警告日志"""
        if self.enable_logging and hasattr(self, 'logger'):
            self.logger.warning(message)
        print(f"⚠️ {message}")
    
    def log_error(self, message):
        """记录错误日志"""
        if self.enable_logging and hasattr(self, 'logger'):
            self.logger.error(message)
        print(f"❌ {message}")


# 全局实例
_global_exception_handler = None

def get_exception_handler():
    """获取全局异常处理器实例"""
    global _global_exception_handler
    if _global_exception_handler is None:
        _global_exception_handler = GlobalExceptionHandler()
    return _global_exception_handler 