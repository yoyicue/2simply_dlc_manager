#!/usr/bin/env python3
"""
关于对话框
显示应用的版本信息和相关信息
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTextBrowser, QTabWidget, QWidget
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPixmap, QFont, QDesktopServices
from pathlib import Path
import sys

class AboutDialog(QDialog):
    """关于对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于 DLC Manager")
        self.setFixedSize(450, 350)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        self._setup_ui()
        self._setup_style()
    
    def _setup_ui(self):
        """设置用户界面"""
        layout = QVBoxLayout()
        
        # 创建标签页
        tab_widget = QTabWidget()
        
        # 关于标签页
        about_tab = self._create_about_tab()
        tab_widget.addTab(about_tab, "关于")
        
        # 系统信息标签页
        system_tab = self._create_system_tab()
        tab_widget.addTab(system_tab, "系统信息")
        
        # 许可证标签页
        license_tab = self._create_license_tab()
        tab_widget.addTab(license_tab, "许可证")
        
        layout.addWidget(tab_widget)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        ok_button = QPushButton("确定")
        ok_button.setMinimumWidth(80)
        ok_button.clicked.connect(self.accept)
        ok_button.setDefault(True)
        
        button_layout.addWidget(ok_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def _create_about_tab(self):
        """创建关于标签页"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 应用图标
        icon_layout = QHBoxLayout()
        icon_layout.addStretch()
        
        icon_label = QLabel()
        icon_path = Path("resources/icons/app_icon.png")
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path))
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                icon_label.setPixmap(scaled_pixmap)
        else:
            icon_label.setText("📦")
            icon_label.setStyleSheet("font-size: 48px;")
        
        icon_layout.addWidget(icon_label)
        icon_layout.addStretch()
        layout.addLayout(icon_layout)
        
        # 应用名称
        title = QLabel("DLC Manager")
        title.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # 版本信息
        version = QLabel("版本 1.0.0")
        version.setAlignment(Qt.AlignCenter)
        version.setStyleSheet("color: #666; margin: 5px;")
        layout.addWidget(version)
        
        # 描述
        description = QLabel("***REMOVED***")
        description.setAlignment(Qt.AlignCenter)
        description.setWordWrap(True)
        description.setStyleSheet("margin: 10px; color: #333;")
        layout.addWidget(description)
        
        layout.addStretch()
        
        # 版权信息
        copyright_label = QLabel("© 2024 yoyicue")
        copyright_label.setAlignment(Qt.AlignCenter)
        copyright_label.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(copyright_label)
        
        widget.setLayout(layout)
        return widget
    
    def _create_system_tab(self):
        """创建系统信息标签页"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 系统信息文本
        system_info = QTextBrowser()
        system_info.setMaximumHeight(200)
        
        info_text = f"""
<h3>系统信息</h3>
<p><b>Python 版本:</b> {sys.version}</p>
<p><b>操作系统:</b> {sys.platform}</p>
<p><b>架构:</b> {sys.version.split('[')[1].split(']')[0] if '[' in sys.version else 'Unknown'}</p>
        """
        
        # 添加 Qt 版本信息
        try:
            from PySide6 import __version__ as pyside_version
            info_text += f"<p><b>PySide6 版本:</b> {pyside_version}</p>"
        except ImportError:
            pass
        
        # 添加核心依赖信息（只显示真正重要的）
        core_dependencies = []
        
        # 获取库版本的安全函数（避免pkg_resources依赖问题）
        def get_package_version(package_name):
            try:
                # 直接导入模块获取版本
                if package_name == "PySide6":
                    import PySide6
                    return getattr(PySide6, '__version__', '已安装')
                elif package_name == "aiohttp":
                    import aiohttp
                    return getattr(aiohttp, '__version__', '已安装')
                elif package_name == "qasync":
                    import qasync
                    return getattr(qasync, '__version__', '已安装')
                else:
                    return "已安装"
            except ImportError:
                return "未安装"
            except:
                return "已安装"
        
        # 只显示核心功能依赖
        core_libs = [
            ("PySide6", "Qt GUI框架"),
            ("aiohttp", "异步HTTP客户端"),
            ("qasync", "Qt异步事件循环")
        ]
        
        for lib_name, description in core_libs:
            try:
                version = get_package_version(lib_name)
                core_dependencies.append(f"{lib_name}: {version}")
            except:
                pass
        
        if core_dependencies:
            info_text += "<h4>核心依赖:</h4>"
            for dep in core_dependencies:
                info_text += f"<p>• {dep}</p>"
        
        system_info.setHtml(info_text)
        layout.addWidget(system_info)
        
        widget.setLayout(layout)
        return widget
    
    def _create_license_tab(self):
        """创建许可证标签页"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        license_text = QTextBrowser()
        license_content = """
<h3>MIT 许可证</h3>
<p>Copyright (c) 2024 DLC Manager Team</p>

<p>特此免费授予任何获得本软件副本和相关文档文件（"软件"）的人不受限制地处理本软件的权利，
包括但不限于使用、复制、修改、合并、发布、分发、再许可和/或出售软件副本的权利，
并允许向其提供软件的人员这样做，但须符合以下条件：</p>

<p>上述版权声明和本许可声明应包含在软件的所有副本或主要部分中。</p>

<p><b>本软件按"原样"提供，不提供任何形式的明示或暗示保证，包括但不限于适销性、
特定用途适用性和非侵权保证。在任何情况下，作者或版权持有人均不对任何索赔、
损害或其他责任负责，无论是在合同诉讼、侵权行为还是其他方面，
由软件或软件的使用或其他交易引起、由此产生或与之相关。</b></p>
        """
        
        license_text.setHtml(license_content)
        layout.addWidget(license_text)
        
        widget.setLayout(layout)
        return widget
    
    def _setup_style(self):
        """设置样式"""
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                background-color: white;
            }
            QTabWidget::tab-bar {
                alignment: center;
            }
            QTabBar::tab {
                background-color: #f0f0f0;
                border: 1px solid #c0c0c0;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom-color: white;
            }
            QTabBar::tab:hover {
                background-color: #e0e0e0;
            }
            QPushButton {
                background-color: #007acc;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
            QPushButton:pressed {
                background-color: #004080;
            }
            QTextBrowser {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                background-color: #fafafa;
                padding: 10px;
            }
        """)


def show_about_dialog(parent=None):
    """显示关于对话框的便捷函数"""
    dialog = AboutDialog(parent)
    return dialog.exec() 