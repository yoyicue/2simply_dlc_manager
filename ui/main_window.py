"""
主窗口界面
"""
import asyncio
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, 
    QTableView, QPlainTextEdit, QSplitter, QPushButton,
    QLabel, QProgressBar, QFileDialog, QMessageBox,
    QToolBar, QStatusBar, QGroupBox, QComboBox,
    QLineEdit, QCheckBox, QSpinBox
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QIcon
import qasync

from core import FileItem, DownloadStatus, DownloadConfig, Downloader, DataManager
from .file_table_model import FileTableModel


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DLC Manager - 下载管理工具")
        self.setMinimumSize(1200, 800)
        
        # 核心组件
        self.data_manager = DataManager()
        self.downloader: Optional[Downloader] = None
        self.current_output_dir: Optional[Path] = None
        
        # UI组件
        self.file_table_model = FileTableModel()
        self.file_table_view: Optional[QTableView] = None
        self.log_text_edit: Optional[QPlainTextEdit] = None
        self.progress_bar: Optional[QProgressBar] = None
        self.status_label: Optional[QLabel] = None
        
        # 控制组件
        self.load_file_btn: Optional[QPushButton] = None
        self.select_dir_btn: Optional[QPushButton] = None
        self.start_download_btn: Optional[QPushButton] = None
        self.cancel_download_btn: Optional[QPushButton] = None
        self.check_all_btn: Optional[QPushButton] = None
        
        # 配置组件
        self.concurrent_spin: Optional[QSpinBox] = None
        self.timeout_spin: Optional[QSpinBox] = None
        self.batch_size_spin: Optional[QSpinBox] = None
        
        # 过滤组件
        self.status_filter_combo: Optional[QComboBox] = None
        self.search_line_edit: Optional[QLineEdit] = None
        
        self._setup_ui()
        self._connect_signals()
        self._load_saved_state()
    
    def _setup_ui(self):
        """设置用户界面"""
        # 中央组件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 工具栏区域
        toolbar_widget = self._create_toolbar_widget()
        main_layout.addWidget(toolbar_widget)
        
        # 文件信息和控制区域
        control_widget = self._create_control_widget()
        main_layout.addWidget(control_widget)
        
        # 主分割区域
        splitter = QSplitter(Qt.Vertical)
        
        # 文件表格
        self.file_table_view = self._create_table_view()
        splitter.addWidget(self.file_table_view)
        
        # 日志面板
        log_group = QGroupBox("日志信息")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text_edit = QPlainTextEdit()
        self.log_text_edit.setMaximumBlockCount(1000)  # 限制日志行数
        self.log_text_edit.setReadOnly(True)
        log_layout.addWidget(self.log_text_edit)
        
        splitter.addWidget(log_group)
        
        # 设置分割比例
        splitter.setStretchFactor(0, 3)  # 表格占3/4
        splitter.setStretchFactor(1, 1)  # 日志占1/4
        
        main_layout.addWidget(splitter)
        
        # 状态栏
        self._create_status_bar()
    
    def _create_toolbar_widget(self) -> QWidget:
        """创建工具栏区域"""
        toolbar_widget = QWidget()
        layout = QHBoxLayout(toolbar_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 文件操作
        self.load_file_btn = QPushButton("加载文件映射")
        self.load_file_btn.setToolTip("加载BigFilesMD5s.json文件")
        layout.addWidget(self.load_file_btn)
        
        self.select_dir_btn = QPushButton("选择下载目录")
        layout.addWidget(self.select_dir_btn)
        
        layout.addWidget(self._create_separator())
        
        # 下载控制
        self.start_download_btn = QPushButton("开始下载")
        self.start_download_btn.setObjectName("start_download_btn")
        self.start_download_btn.setEnabled(False)
        layout.addWidget(self.start_download_btn)
        
        self.cancel_download_btn = QPushButton("取消下载")
        self.cancel_download_btn.setObjectName("cancel_download_btn")
        self.cancel_download_btn.setEnabled(False)
        layout.addWidget(self.cancel_download_btn)
        
        layout.addWidget(self._create_separator())
        
        # 选择控制
        self.check_all_btn = QPushButton("全选")
        layout.addWidget(self.check_all_btn)
        
        select_failed_btn = QPushButton("选择失败")
        select_failed_btn.clicked.connect(
            lambda: self.file_table_model.check_by_status(DownloadStatus.FAILED)
        )
        layout.addWidget(select_failed_btn)
        
        select_pending_btn = QPushButton("选择待下载")
        select_pending_btn.clicked.connect(
            lambda: self.file_table_model.check_by_status(DownloadStatus.PENDING)
        )
        layout.addWidget(select_pending_btn)
        
        layout.addStretch()
        return toolbar_widget
    
    def _create_control_widget(self) -> QWidget:
        """创建控制面板"""
        control_widget = QWidget()
        layout = QHBoxLayout(control_widget)
        
        # 文件路径信息
        path_group = QGroupBox("路径信息")
        path_layout = QVBoxLayout(path_group)
        
        self.mapping_file_label = QLabel("映射文件: 未选择")
        self.output_dir_label = QLabel("下载目录: 未选择")
        path_layout.addWidget(self.mapping_file_label)
        path_layout.addWidget(self.output_dir_label)
        
        layout.addWidget(path_group)
        
        # 下载配置
        config_group = QGroupBox("下载配置")
        config_layout = QHBoxLayout(config_group)
        
        config_layout.addWidget(QLabel("并发数:"))
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 100)  # 提高最大并发数到100
        self.concurrent_spin.setValue(50)  # 默认值设为50
        self.concurrent_spin.setToolTip("同时下载的文件数量，建议10-50之间")
        config_layout.addWidget(self.concurrent_spin)
        
        config_layout.addWidget(QLabel("超时(秒):"))
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(30, 600)  # 增加最大超时时间
        self.timeout_spin.setValue(120)  # 默认值设为120秒
        self.timeout_spin.setToolTip("单个文件下载超时时间")
        config_layout.addWidget(self.timeout_spin)
        
        config_layout.addWidget(QLabel("批次大小:"))
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 100)  # 提高最大批次大小
        self.batch_size_spin.setValue(20)  # 默认值设为20
        self.batch_size_spin.setToolTip("每个批次处理的文件数量")
        config_layout.addWidget(self.batch_size_spin)
        
        layout.addWidget(config_group)
        
        # 过滤搜索
        filter_group = QGroupBox("过滤搜索")
        filter_layout = QHBoxLayout(filter_group)
        
        filter_layout.addWidget(QLabel("状态:"))
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItem("全部", None)
        for status in DownloadStatus:
            self.status_filter_combo.addItem(status.value, status)
        filter_layout.addWidget(self.status_filter_combo)
        
        filter_layout.addWidget(QLabel("搜索:"))
        self.search_line_edit = QLineEdit()
        self.search_line_edit.setPlaceholderText("输入文件名或MD5搜索...")
        filter_layout.addWidget(self.search_line_edit)
        
        layout.addWidget(filter_group)
        
        return control_widget
    
    def _create_table_view(self) -> QTableView:
        """创建文件表格视图"""
        table_view = QTableView()
        table_view.setModel(self.file_table_model)
        table_view.setAlternatingRowColors(True)
        table_view.setSelectionBehavior(QTableView.SelectRows)
        table_view.setSortingEnabled(True)
        
        # 调整列宽
        header = table_view.horizontalHeader()
        header.setStretchLastSection(True)
        
        # 设置列宽
        table_view.setColumnWidth(0, 50)   # 选择
        table_view.setColumnWidth(1, 200)  # 文件名
        table_view.setColumnWidth(2, 260)  # MD5 - 调整宽度以显示完整32位MD5
        table_view.setColumnWidth(3, 80)   # 状态
        table_view.setColumnWidth(4, 80)   # 进度
        table_view.setColumnWidth(5, 80)   # 大小
        table_view.setColumnWidth(6, 80)   # 已下载
        
        return table_view
    
    def _create_status_bar(self):
        """创建状态栏"""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        
        # 状态标签
        self.status_label = QLabel("就绪")
        status_bar.addWidget(self.status_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(300)
        status_bar.addPermanentWidget(self.progress_bar)
        
        # 统计信息
        self.stats_label = QLabel()
        status_bar.addPermanentWidget(self.stats_label)
    
    def _create_separator(self) -> QWidget:
        """创建分隔符"""
        separator = QWidget()
        separator.setFixedWidth(1)
        separator.setStyleSheet("background-color: #cccccc;")
        return separator
    
    def _connect_signals(self):
        """连接信号和槽"""
        # 文件操作
        self.load_file_btn.clicked.connect(self._load_file_mapping)
        self.select_dir_btn.clicked.connect(self._select_output_directory)
        
        # 下载控制
        self.start_download_btn.clicked.connect(self._start_download)
        self.cancel_download_btn.clicked.connect(self._cancel_download)
        
        # 选择控制
        self.check_all_btn.clicked.connect(self._toggle_check_all)
        
        # 表格模型信号
        self.file_table_model.selection_changed.connect(self._update_ui_state)
        
        # 过滤搜索
        self.status_filter_combo.currentTextChanged.connect(self._apply_filters)
        self.search_line_edit.textChanged.connect(self._apply_filters)
    
    def _load_saved_state(self):
        """加载保存的状态"""
        try:
            file_items, output_dir = self.data_manager.load_state()
            if file_items:
                self.file_table_model.set_file_items(file_items)
                self._log(f"加载了 {len(file_items)} 个文件的保存状态")
            
            if output_dir:
                self.current_output_dir = output_dir
                self.output_dir_label.setText(f"下载目录: {output_dir}")
                
            self._update_ui_state()
            self._update_statistics()
        except Exception as e:
            self._log(f"加载保存状态失败: {e}")
    
    def _load_file_mapping(self):
        """加载文件映射"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择BigFilesMD5s.json文件",
            "",
            "JSON文件 (*.json);;所有文件 (*)"
        )
        
        if not file_path:
            return
        
        try:
            file_items = self.data_manager.load_file_mapping(Path(file_path))
            self.file_table_model.set_file_items(file_items)
            
            self.mapping_file_label.setText(f"映射文件: {Path(file_path).name}")
            self._log(f"成功加载 {len(file_items)} 个文件，已默认全选")
            self._update_ui_state()
            self._update_statistics()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载文件映射失败:\n{e}")
            self._log(f"加载文件映射失败: {e}")
    
    def _select_output_directory(self):
        """选择输出目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择下载目录",
            str(self.current_output_dir) if self.current_output_dir else ""
        )
        
        if not dir_path:
            return
        
        self.current_output_dir = Path(dir_path)
        self.output_dir_label.setText(f"下载目录: {self.current_output_dir}")
        self._update_ui_state()
        self._log(f"设置下载目录: {self.current_output_dir}")
    
    @qasync.asyncSlot()
    async def _start_download(self):
        """开始下载"""
        try:
            if not self.current_output_dir:
                QMessageBox.warning(self, "警告", "请先选择下载目录")
                return

            checked_items = self.file_table_model.get_checked_items()
            if not checked_items:
                QMessageBox.warning(self, "警告", "请至少选择一个文件进行下载")
                return

            # 创建下载配置
            config = DownloadConfig(
                concurrent_requests=self.concurrent_spin.value(),
                timeout=self.timeout_spin.value(),
                batch_size=self.batch_size_spin.value()
            )

            # 创建下载器
            self.downloader = Downloader(config)

            # 连接下载器信号
            self.downloader.progress_updated.connect(self._on_progress_updated)
            self.downloader.file_completed.connect(self._on_file_completed)
            self.downloader.overall_progress.connect(self._on_overall_progress)
            self.downloader.check_progress.connect(self._on_check_progress)
            self.downloader.log_message.connect(self._log)
            self.downloader.download_started.connect(self._on_download_started)
            self.downloader.download_finished.connect(self._on_download_finished)
            self.downloader.download_cancelled.connect(self._on_download_cancelled)

            # 开始下载
            self._log(f"开始下载 {len(checked_items)} 个文件到 {self.current_output_dir}")
            await self.downloader.download_files(checked_items, self.current_output_dir)
            
        except Exception as e:
            error_msg = f"下载过程中发生错误: {str(e)}"
            self._log(error_msg)
            QMessageBox.critical(self, "下载错误", error_msg)
            
            # 重置下载状态
            if hasattr(self, 'downloader'):
                self.downloader = None
            self._update_ui_state()
            
            # 打印完整的错误信息到控制台用于调试
            import traceback
            print("=== 下载错误详情 ===")
            traceback.print_exc()
            print("=== 错误详情结束 ===")
        
        finally:
            # 确保UI状态正确更新
            self._update_ui_state()
    
    def _cancel_download(self):
        """取消下载"""
        if self.downloader:
            self.downloader.cancel_download()
    
    def _toggle_check_all(self):
        """切换全选状态"""
        checked_count = len(self.file_table_model.get_checked_items())
        filtered_count = self.file_table_model.rowCount()  # 获取过滤后的项目数
        
        # 如果全部选中，则取消全选；否则全选
        check_all = checked_count < filtered_count
        self.file_table_model.check_all(check_all)
        
        self.check_all_btn.setText("取消全选" if check_all else "全选")
    
    def _apply_filters(self):
        """应用过滤条件"""
        status_filter = self.status_filter_combo.currentData()
        search_text = self.search_line_edit.text().lower().strip()
        
        # 应用过滤到模型
        self.file_table_model.apply_filters(status_filter, search_text)
        
        # 更新UI状态和统计信息
        self._update_ui_state()
        self._update_statistics()
    
    def _update_ui_state(self):
        """更新UI状态"""
        has_files = len(self.file_table_model.get_file_items()) > 0
        has_output_dir = self.current_output_dir is not None
        has_selection = len(self.file_table_model.get_checked_items()) > 0
        is_downloading = bool(self.downloader and self.downloader.is_downloading)
        
        # 更新按钮状态
        self.start_download_btn.setEnabled(
            has_files and has_output_dir and has_selection and not is_downloading
        )
        self.cancel_download_btn.setEnabled(is_downloading)
        
        # 更新全选按钮文本
        checked_count = len(self.file_table_model.get_checked_items())
        filtered_count = self.file_table_model.rowCount()  # 获取过滤后的项目数
        
        if checked_count == 0:
            self.check_all_btn.setText("全选")
        elif checked_count == filtered_count:
            self.check_all_btn.setText("取消全选")
        else:
            self.check_all_btn.setText(f"全选 ({checked_count}/{filtered_count})")
    
    def _update_statistics(self):
        """更新统计信息"""
        file_items = self.file_table_model.get_file_items()
        stats = self.data_manager.get_statistics(file_items)
        
        stats_text = (
            f"总计: {stats['total']} | "
            f"完成: {stats['completed']} | "
            f"失败: {stats['failed']} | "
            f"待下载: {stats['pending']}"
        )
        self.stats_label.setText(stats_text)
    
    def _log(self, message: str):
        """添加日志"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text_edit.appendPlainText(f"[{timestamp}] {message}")
    
    # 下载器信号处理方法
    def _on_progress_updated(self, filename: str, progress: float):
        """文件进度更新"""
        # 在表格中找到对应文件并更新
        for item in self.file_table_model.get_file_items():
            if item.filename == filename:
                self.file_table_model.update_file_item(item)
                break
    
    def _on_file_completed(self, filename: str, success: bool, message: str):
        """文件下载完成"""
        status = "成功" if success else "失败"
        self._log(f"文件下载完成: {filename} - {status} ({message})")
        
        # 更新表格显示
        for item in self.file_table_model.get_file_items():
            if item.filename == filename:
                self.file_table_model.update_file_item(item)
                break
        
        self._update_statistics()
        
        # 更新全局进度显示
        all_file_items = self.file_table_model.get_file_items()
        global_stats = self.data_manager.get_statistics(all_file_items)
        global_completed = global_stats['completed'] + global_stats['skipped']
        global_total = global_stats['total']
        global_progress = (global_completed / global_total * 100) if global_total > 0 else 0
        
        # 如果正在下载，更新进度条
        if self.downloader and self.downloader.is_downloading:
            self.progress_bar.setValue(int(global_progress))
            self.status_label.setText(f"下载中... {global_completed}/{global_total} ({global_progress:.1f}%)")
        
        # 保存状态
        try:
            self.data_manager.save_state(
                self.file_table_model.get_file_items(),
                self.current_output_dir
            )
        except Exception as e:
            self._log(f"保存状态失败: {e}")
    
    def _on_overall_progress(self, progress: float, completed_count: int, total_count: int):
        """整体进度更新"""
        # 获取全局统计信息
        all_file_items = self.file_table_model.get_file_items()
        global_stats = self.data_manager.get_statistics(all_file_items)
        
        # 计算全局进度
        global_completed = global_stats['completed'] + global_stats['skipped']  # 包含跳过的文件
        global_total = global_stats['total']
        global_progress = (global_completed / global_total * 100) if global_total > 0 else 0
        
        # 更新进度条和状态显示
        self.progress_bar.setValue(int(global_progress))
        self.status_label.setText(f"下载中... {global_completed}/{global_total} ({global_progress:.1f}%)")
    
    def _on_check_progress(self, progress: float):
        """文件检查进度更新"""
        self.progress_bar.setValue(int(progress))
        self.status_label.setText(f"检查文件存在性... {progress:.1f}%")
    
    def _on_download_started(self):
        """下载开始"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("下载中...")
        self._update_ui_state()
    
    def _on_download_finished(self, success_count: int, failed_count: int):
        """下载完成"""
        self.progress_bar.setVisible(False)
        self.status_label.setText(
            f"下载完成 - 成功: {success_count}, 失败: {failed_count}"
        )
        self.downloader = None
        self._update_ui_state()
        self._update_statistics()
    
    def _on_download_cancelled(self):
        """下载取消"""
        self.progress_bar.setVisible(False)
        self.status_label.setText("下载已取消")
        self.downloader = None
        self._update_ui_state() 