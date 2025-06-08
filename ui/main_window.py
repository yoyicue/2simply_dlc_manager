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
    QLineEdit, QCheckBox, QSpinBox, QMenuBar, QApplication
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QIcon
import qasync

from core import FileItem, DownloadStatus, DownloadConfig, Downloader, DataManager, MD5VerifyStatus
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
        
        # 性能优化：大数据集处理
        self._download_completed_count = 0  # 下载完成计数器
        self._last_stats_update = 0  # 上次统计更新时间
        self._last_save_time = 0  # 上次保存时间
        
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
        
        # 延迟加载保存的状态，等事件循环启动后执行
        QTimer.singleShot(100, self._schedule_load_saved_state)
    
    def _setup_ui(self):
        """设置用户界面"""
        # 创建菜单栏
        self._create_menubar()
        
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
        self.load_file_btn = QPushButton("加载BigFilesMD5s.json")
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
        
        select_verify_failed_btn = QPushButton("选择验证失败")
        select_verify_failed_btn.clicked.connect(
            lambda: self.file_table_model.check_by_status(DownloadStatus.VERIFY_FAILED)
        )
        layout.addWidget(select_verify_failed_btn)
        
        layout.addWidget(self._create_separator())
        
        # MD5验证控制
        self.verify_md5_btn = QPushButton("验证MD5")
        self.verify_md5_btn.setToolTip("验证选中文件的MD5完整性")
        self.verify_md5_btn.setEnabled(False)
        layout.addWidget(self.verify_md5_btn)
        
        # 重新下载控制
        self.redownload_btn = QPushButton("重新下载")
        self.redownload_btn.setToolTip("重新下载验证失败的文件，将覆盖现有文件")
        self.redownload_btn.setEnabled(False)
        self.redownload_btn.setObjectName("redownload_btn")
        layout.addWidget(self.redownload_btn)
        
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
        self.concurrent_spin.setRange(1, 150)  # 提高最大并发数到150
        self.concurrent_spin.setValue(80)  # 默认值设为80（基于真实数据优化）
        self.concurrent_spin.setToolTip("同时下载的文件数量，已基于15GB下载经验优化，建议保持默认值")
        config_layout.addWidget(self.concurrent_spin)
        
        config_layout.addWidget(QLabel("超时(秒):"))
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(60, 900)  # 增加最大超时时间到15分钟
        self.timeout_spin.setValue(180)  # 默认值设为180秒（考虑15MB大文件）
        self.timeout_spin.setToolTip("基础超时时间，系统会根据文件大小自动调整")
        config_layout.addWidget(self.timeout_spin)
        
        config_layout.addWidget(QLabel("批次大小:"))
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 200)  # 提高最大批次大小到200
        self.batch_size_spin.setValue(50)  # 默认值设为50（基于44K文件总量优化）
        self.batch_size_spin.setToolTip("基础批次大小，系统会根据文件类型和跳过比例自动调整")
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
        table_view.setAlternatingRowColors(False)  # 禁用交替行颜色以显示MD5验证状态颜色
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
    
    def _schedule_load_saved_state(self):
        """调度异步加载保存的状态"""
        try:
            # 检查事件循环是否已经运行
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._load_saved_state())
            else:
                # 如果事件循环还没运行，再延迟一点
                QTimer.singleShot(200, self._schedule_load_saved_state)
        except RuntimeError:
            # 如果没有事件循环，跳过异步加载
            print("警告：无法加载保存的状态 - 没有事件循环")
    
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
        
        # MD5验证控制
        self.verify_md5_btn.clicked.connect(self._toggle_md5_verification)
        
        # 重新下载控制
        self.redownload_btn.clicked.connect(self._redownload_verify_failed)
        
        # 表格模型信号
        self.file_table_model.selection_changed.connect(self._update_ui_state)
        
        # 过滤搜索
        self.status_filter_combo.currentTextChanged.connect(self._apply_filters)
        self.search_line_edit.textChanged.connect(self._apply_filters)
    
    @qasync.asyncSlot()
    async def _toggle_md5_verification(self):
        """切换MD5验证状态（开始/取消）"""
        if hasattr(self, '_is_verifying') and self._is_verifying:
            # 当前正在验证，执行取消操作
            self._cancel_md5_verification()
        else:
            # 当前未在验证，开始验证
            await self._verify_selected_files()
    
    def _cancel_md5_verification(self):
        """取消MD5验证"""
        self._verification_cancelled = True
        
        # 如果有并行MD5计算器，取消它
        if hasattr(self, 'md5_calculator') and self.md5_calculator:
            self.md5_calculator.cancel_calculation()
        
        self.verify_md5_btn.setText("验证MD5")
        self.verify_md5_btn.setToolTip("验证选中文件的MD5完整性")
        self.status_label.setText("正在取消MD5验证...")
        self._log("用户取消了MD5验证")
    
    @qasync.asyncSlot()
    async def _verify_selected_files(self):
        """验证选中文件的MD5 - 并行版本"""
        try:
            if not self.current_output_dir:
                QMessageBox.warning(self, "警告", "请先选择下载目录")
                return

            checked_items = self.file_table_model.get_checked_items()
            if not checked_items:
                QMessageBox.warning(self, "警告", "请至少选择一个文件进行验证")
                return

            # 批量检查文件存在性 - 高效版本
            self._log(f"🔍 开始批量检查文件存在性...")
            
            # 构建文件路径列表
            file_paths = [self.current_output_dir / item.full_filename for item in checked_items]
            
            # 批量检查存在性（减少I/O调用）
            existing_files = set()
            import os
            try:
                # 使用os.listdir批量获取目录内容，比逐个exists()更高效
                if self.current_output_dir.exists():
                    for root, dirs, files in os.walk(self.current_output_dir):
                        root_path = Path(root)
                        for file in files:
                            existing_files.add(root_path / file)
            except Exception as e:
                self._log(f"⚠️ 批量检查失败，降级为逐个检查: {e}")
                # 降级方案：逐个检查
                existing_files = {path for path in file_paths if path.exists()}
            
            # 过滤出需要验证的文件
            files_to_verify = []
            already_verified_count = 0
            
            for item in checked_items:
                file_path = self.current_output_dir / item.full_filename
                if file_path in existing_files:
                    # 跳过已经验证成功的文件
                    if item.md5_verify_status == MD5VerifyStatus.VERIFIED_SUCCESS:
                        already_verified_count += 1
                        continue
                    files_to_verify.append(item)
            
            self._log(f"✅ 批量检查完成: {len(existing_files)} 个文件存在")

            # 显示跳过的已验证文件信息
            if already_verified_count > 0:
                self._log(f"⚡ 智能跳过 {already_verified_count} 个已验证成功的文件，无需重复验证")

            if not files_to_verify:
                if already_verified_count > 0:
                    QMessageBox.information(self, "提示", f"选中的文件中有 {already_verified_count} 个已验证成功，无需重复验证")
                else:
                    QMessageBox.information(self, "提示", "选中的文件中没有可验证的本地文件")
                return

            # 设置验证状态
            self._is_verifying = True
            self._verification_cancelled = False
            
            # 更新按钮状态
            self.verify_md5_btn.setText("取消验证")
            self.verify_md5_btn.setToolTip("取消正在进行的MD5验证")
            self._update_ui_state()

            # 显示进度
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.status_label.setText("开始并行MD5验证...")

            total_selected = len(checked_items)
            self._log(f"开始并行MD5验证 - 总选择: {total_selected}, 需验证: {len(files_to_verify)}, 智能跳过: {already_verified_count}")

            # 导入并行MD5验证器
            from core.verification import ParallelMD5Calculator
            
            # 创建下载配置（复用现有配置）
            config = DownloadConfig(
                concurrent_requests=self.concurrent_spin.value(),
                timeout=self.timeout_spin.value(),
                batch_size=self.batch_size_spin.value()
            )

            # 创建并行MD5计算器
            self.md5_calculator = ParallelMD5Calculator(config)
            
            # 连接信号
            self.md5_calculator.file_completed.connect(self._on_md5_file_completed)
            self.md5_calculator.overall_progress.connect(self._on_md5_overall_progress)
            self.md5_calculator.log_message.connect(self._log)
            
            # 🚀 流式处理：不再一次性持有所有结果，改为实时处理
            # 建立filename到FileItem的快速映射
            filename_to_item = {item.filename: item for item in files_to_verify}
            
            success_count = 0
            failed_count = 0
            processed_count = 0
            
            # 连接流式处理信号
            self.md5_calculator.file_completed.disconnect()  # 先断开旧连接
            
            # 使用lambda创建流式处理器，避免大结果字典
            def stream_process_result(filename: str, success: bool, message: str):
                nonlocal success_count, failed_count, processed_count
                
                # O(1)查找对应的文件项
                file_item = filename_to_item.get(filename)
                if not file_item:
                    return
                
                processed_count += 1
                
                if success:
                    # 检查MD5是否匹配 (message为空表示匹配)
                    is_match = not message
                    file_item.mark_md5_verified("", is_match)  # 流式处理不保存calculated_md5
                    
                    if is_match:
                        success_count += 1
                    else:
                        file_item.status = DownloadStatus.VERIFY_FAILED
                        file_item.error_message = message
                        failed_count += 1
                else:
                    # 计算失败
                    file_item.mark_md5_verified("", False)
                    file_item.status = DownloadStatus.VERIFY_FAILED
                    file_item.error_message = message
                    failed_count += 1
                
                # 🚀 实时UI更新，避免批量积累
                self.file_table_model.update_file_by_filename(filename)
                
                # 定期垃圾回收
                if processed_count % 100 == 0:
                    import gc
                    gc.collect()
                
                # 减少进度显示频率
                if processed_count % 1000 == 0:
                    progress = (processed_count / len(files_to_verify)) * 100
                    self.status_label.setText(f"实时处理中... {processed_count}/{len(files_to_verify)} ({progress:.1f}%)")
                    self._log(f"📊 实时处理: {processed_count}/{len(files_to_verify)} ({progress:.1f}%)")
                    QApplication.processEvents()
            
            # 连接流式处理信号
            self.md5_calculator.file_completed.connect(stream_process_result)
            
            # 🚀 内存监控：检查可用内存
            try:
                import psutil
                memory = psutil.virtual_memory()
                available_gb = memory.available / (1024**3)
                self._log(f"💾 开始流式处理，可用内存: {available_gb:.1f}GB")
            except ImportError:
                self._log(f"💾 内存监控不可用，开始流式处理")
            except Exception as e:
                self._log(f"💾 内存检查失败: {e}")
            
            self._log(f"🚀 开始流式MD5验证 - 不再累积大结果集，实时处理{len(files_to_verify)}个文件")
            
            # 开始并行计算 - 返回空字典，实际处理通过信号完成
            _ = await self.md5_calculator.calculate_md5_parallel(
                files_to_verify, 
                self.current_output_dir
            )
            
            # 验证完成统计
            self._log(f"📊 流式处理完成: 总计 {processed_count} 个文件，成功 {success_count}，失败 {failed_count}")
            
            # 保存状态
            self._log(f"💾 开始保存状态到文件...")
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    self.data_manager.save_state,
                    self.file_table_model.get_file_items(),
                    self.current_output_dir
                )
                self._log(f"💾 状态保存完成")
            except Exception as e:
                self._log(f"保存状态失败: {e}")
            
            # 强制垃圾回收，释放内存
            import gc
            gc.collect()
            self._log(f"📊 内存清理完成，强制垃圾回收")

            # 🚀 验证完成，开始恢复UI状态
            self._log(f"🎉 MD5验证流程即将完成，恢复UI状态...")
            
            # 验证完成
            self.progress_bar.setVisible(False)
            
            # 恢复按钮状态
            self.verify_md5_btn.setText("验证MD5")
            self.verify_md5_btn.setToolTip("验证选中文件的MD5完整性")
            self._log(f"🔄 按钮状态已恢复")
            
            if self._verification_cancelled:
                self.status_label.setText("MD5验证已取消")
                self._log(f"并行MD5验证已取消")
            else:
                self.status_label.setText(f"并行MD5验证完成 - 成功: {success_count}, 失败: {failed_count}")
                self._log(f"🎉 并行MD5验证已完成 - 成功: {success_count}, 失败: {failed_count}")
                
                # 显示验证结果摘要
                if len(files_to_verify) > 0 or already_verified_count > 0:
                    total_processed = len(files_to_verify) + already_verified_count
                    total_success = success_count + already_verified_count
                    
                    self._log(f"📊 准备显示结果摘要弹窗...")
                    QMessageBox.information(
                        self, 
                        "并行验证完成", 
                        f"并行MD5验证完成！\n\n"
                        f"总处理文件数: {total_processed}\n"
                        f"本次验证: {len(files_to_verify)}\n"
                        f"验证成功: {success_count}\n"
                        f"验证失败: {failed_count}\n"
                        f"智能跳过: {already_verified_count} (已验证成功)\n"
                        f"总成功率: {total_success}/{total_processed} ({total_success/total_processed*100:.1f}%)\n\n"
                        f"详细结果请查看MD5列的颜色显示"
                    )
                    self._log(f"📊 结果摘要弹窗已显示")

        except Exception as e:
            error_msg = f"并行MD5验证过程中发生错误: {str(e)}"
            self._log(error_msg)
            QMessageBox.critical(self, "验证错误", error_msg)
            
            # 打印完整的错误信息到控制台用于调试
            import traceback
            print("=== 并行MD5验证错误详情 ===")
            traceback.print_exc()
            print("=== 错误详情结束 ===")
        
        finally:
            # 🚀 流式处理：断开所有信号连接
            if hasattr(self, 'md5_calculator') and self.md5_calculator:
                try:
                    # 断开所有信号连接，包括流式处理信号
                    self.md5_calculator.file_completed.disconnect()
                    self.md5_calculator.overall_progress.disconnect()  
                    self.md5_calculator.log_message.disconnect()
                    self._log(f"🔌 流式处理信号已断开")
                except Exception as e:
                    self._log(f"⚠️ 断开信号失败: {e}")
            
            # 重置验证状态
            self._is_verifying = False
            self._verification_cancelled = False
            
            # 清理MD5计算器
            if hasattr(self, 'md5_calculator'):
                self.md5_calculator = None
            
            # 🚀 流式处理内存清理
            try:
                # 清理映射引用
                if 'filename_to_item' in locals():
                    del filename_to_item
                if 'files_to_verify' in locals():
                    del files_to_verify
                
                # 强制垃圾回收
                import gc
                gc.collect()
                self._log(f"🧹 流式处理内存清理完成")
            except Exception as e:
                self._log(f"⚠️ 内存清理失败: {e}")
            
            # 恢复按钮状态（防止异常情况下按钮状态不正确）
            self.verify_md5_btn.setText("验证MD5")
            self.verify_md5_btn.setToolTip("验证选中文件的MD5完整性")
            
            self._update_ui_state()
    
    async def _load_saved_state(self):
        """加载保存的状态"""
        try:
            # 记录数据文件位置
            self._log(f"💾 数据文件位置: {self.data_manager.data_file}")
            
            # 异步加载状态，避免启动时阻塞UI
            loop = asyncio.get_event_loop()
            file_items, output_dir = await loop.run_in_executor(
                None,
                self.data_manager.load_state
            )
            
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
    
    @qasync.asyncSlot()
    async def _load_file_mapping(self):
        """加载文件映射"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择BigFilesMD5s.json文件",
            "",
            "JSON文件 (*.json);;所有文件 (*)"
        )
        
        if not file_path:
            return
        
        # 显示加载进度
        self.status_label.setText("正在加载BigFilesMD5s.json...")
        self.load_file_btn.setEnabled(False)
        
        try:
            # 在线程池中异步加载文件，避免阻塞UI
            loop = asyncio.get_event_loop()
            file_items, diff_info = await loop.run_in_executor(
                None, 
                self.data_manager.load_file_mapping_with_state_diff, 
                Path(file_path)
            )
            
            self.file_table_model.set_file_items(file_items)
            
            self.mapping_file_label.setText(f"映射文件: {Path(file_path).name}")
            
            # 生成差异报告
            diff_msg = f"加载完成 - 总计: {len(file_items)} 个文件"
            if diff_info['existing'] > 0:
                diff_msg += f" | 保留已有状态: {diff_info['existing']}"
            if diff_info['new'] > 0:
                diff_msg += f" | 新增: {diff_info['new']}"
            if diff_info['updated'] > 0:
                diff_msg += f" | 更新: {diff_info['updated']}"
            if diff_info['removed'] > 0:
                diff_msg += f" | 移除: {diff_info['removed']}"
            
            self._log(diff_msg)
            
            # 如果有保留的状态，显示更详细的信息
            if diff_info['existing'] > 0:
                self._log(f"✅ 智能合并: 已保留 {diff_info['existing']} 个文件的下载状态，避免重复检查")
            if diff_info['new'] > 0:
                self._log(f"🆕 发现 {diff_info['new']} 个新文件，已标记为待下载")
            if diff_info['updated'] > 0:
                self._log(f"🔄 检测到 {diff_info['updated']} 个文件有更新，已重置下载状态")
            if diff_info['removed'] > 0:
                self._log(f"⚠️  {diff_info['removed']} 个文件在新映射中不存在，已从列表移除")
            
            # 阶段二新增：显示Bloom Filter信息
            bloom_info = self.data_manager.get_bloom_filter_info()
            if bloom_info:
                self._log(f"🔍 Bloom Filter已就绪: {bloom_info['actual_items']}个文件, "
                         f"{bloom_info['memory_usage_kb']:.1f}KB内存, "
                         f"{bloom_info['efficiency']:.1f}%效率")
            self._update_ui_state()
            self._update_statistics()
            self.status_label.setText("BigFilesMD5s.json加载完成")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载BigFilesMD5s.json失败:\n{e}")
            self._log(f"加载BigFilesMD5s.json失败: {e}")
            self.status_label.setText("BigFilesMD5s.json加载失败")
        finally:
            self.load_file_btn.setEnabled(True)
    
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
            # 1. 检查是否已加载文件映射
            file_items = self.file_table_model.get_file_items()
            if not file_items:
                QMessageBox.warning(
                    self, 
                    "未加载文件", 
                    "请先加载BigFilesMD5s.json文件！\n\n"
                    "点击「加载BigFilesMD5s.json」按钮来加载文件映射。"
                )
                return

            # 2. 检查是否已设置下载目录
            if not self.current_output_dir:
                QMessageBox.warning(
                    self, 
                    "未设置下载目录", 
                    "请先选择下载目录！\n\n"
                    "点击「选择下载目录」按钮来设置下载路径。"
                )
                return

            # 3. 检查是否有选中的文件
            checked_items = self.file_table_model.get_checked_items()
            if not checked_items:
                total_files = len(file_items)
                filtered_files = self.file_table_model.rowCount()
                
                if filtered_files == 0:
                    QMessageBox.information(
                        self, 
                        "没有可下载文件", 
                        f"当前过滤条件下没有文件可显示。\n\n"
                        f"总文件数: {total_files}\n"
                        f"过滤后: {filtered_files}\n\n"
                        f"请调整过滤条件或重新加载文件。"
                    )
                else:
                    QMessageBox.information(
                        self, 
                        "未选择文件", 
                        f"请至少选择一个文件进行下载！\n\n"
                        f"当前显示: {filtered_files} 个文件\n"
                        f"已选择: 0 个文件\n\n"
                        f"💡 提示: 可以使用「全选」、「选择失败」、「选择待下载」等快捷按钮。"
                    )
                return

            # 4. 显示下载准备信息
            self._log(f"🚀 准备开始下载: {len(checked_items)} 个文件")
            self._log(f"📁 下载目录: {self.current_output_dir}")

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
            # 阶段二优化：连接统计信息更新信号，避免数字跳动
            self.downloader.statistics_update_requested.connect(self._update_statistics)

            # 开始下载
            self._log(f"开始下载 {len(checked_items)} 个文件到 {self.current_output_dir}")
            await self.downloader.download_files(checked_items, self.current_output_dir, self.data_manager)
            
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
        if self.downloader and self.downloader.is_downloading:
            # 显示确认对话框
            reply = QMessageBox.question(
                self,
                "确认取消下载",
                "确定要取消正在进行的下载吗？\n\n"
                "• 已下载完成的文件将保留\n"
                "• 正在下载的文件将被中断\n"
                "• 可以稍后重新开始下载",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self._log("用户请求取消下载...")
                self.downloader.cancel_download()
                # 更新按钮状态
                self.cancel_download_btn.setEnabled(False)
                self.cancel_download_btn.setToolTip("正在取消下载...")
            else:
                self._log("用户取消了取消下载操作")
        else:
            # 当前没有下载任务
            QMessageBox.information(
                self,
                "没有下载任务",
                "当前没有正在进行的下载任务。"
            )
    
    @qasync.asyncSlot()
    async def _redownload_verify_failed(self):
        """重新下载验证失败的文件"""
        try:
            # 1. 检查前置条件
            if not self.current_output_dir:
                QMessageBox.warning(self, "警告", "请先选择下载目录")
                return

            checked_items = self.file_table_model.get_checked_items()
            if not checked_items:
                QMessageBox.warning(self, "警告", "请至少选择一个文件")
                return

            # 2. 筛选出验证失败的文件
            verify_failed_items = [item for item in checked_items 
                                 if item.status == DownloadStatus.VERIFY_FAILED]
            
            if not verify_failed_items:
                total_selected = len(checked_items)
                QMessageBox.information(
                    self,
                    "没有验证失败文件",
                    f"选中的 {total_selected} 个文件中没有验证失败的文件。\n\n"
                    f"💡 提示: 只有状态为「验证失败」的文件才能重新下载。\n"
                    f"可以使用「选择验证失败」按钮快速选择这类文件。"
                )
                return

            # 3. 检查文件是否存在，统计需要覆盖的文件
            existing_files = []
            for item in verify_failed_items:
                file_path = self.current_output_dir / item.full_filename
                if file_path.exists():
                    existing_files.append(item.filename)

            # 4. 显示确认对话框
            confirm_msg = f"确定要重新下载 {len(verify_failed_items)} 个验证失败的文件吗？\n\n"
            
            if existing_files:
                confirm_msg += f"⚠️  将覆盖现有文件:\n"
                confirm_msg += f"• 需要覆盖的文件数: {len(existing_files)} 个\n"
                confirm_msg += f"• 保持原状的文件数: {len(verify_failed_items) - len(existing_files)} 个\n\n"
            else:
                confirm_msg += f"💡 所有文件都是新下载（没有需要覆盖的文件）\n\n"
            
            confirm_msg += "重新下载说明:\n"
            confirm_msg += "• 现有文件将被完全覆盖\n"
            confirm_msg += "• 下载失败的文件状态将重置\n"
            confirm_msg += "• 下载完成后建议重新验证MD5"

            reply = QMessageBox.question(
                self,
                "确认重新下载",
                confirm_msg,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                self._log("用户取消了重新下载操作")
                return

            # 5. 重置验证失败文件的状态为待下载
            self._log(f"🔄 准备重新下载 {len(verify_failed_items)} 个验证失败的文件")
            for item in verify_failed_items:
                item.status = DownloadStatus.PENDING
                item.progress = 0.0
                item.downloaded_size = 0
                item.error_message = ""
                # 重置MD5验证状态
                item.reset_md5_verify_status()

            # 强制刷新表格显示
            self.file_table_model.beginResetModel()
            self.file_table_model.endResetModel()
            
            # 6. 开始下载（复用现有的下载逻辑）
            self._log(f"📁 下载目录: {self.current_output_dir}")
            self._log(f"📋 将覆盖 {len(existing_files)} 个现有文件")

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
            self.downloader.download_finished.connect(self._on_redownload_finished)
            self.downloader.download_cancelled.connect(self._on_download_cancelled)
            self.downloader.statistics_update_requested.connect(self._update_statistics)

            # 开始重新下载
            self._log(f"🚀 开始重新下载验证失败的文件...")
            await self.downloader.download_files(verify_failed_items, self.current_output_dir, self.data_manager)

        except Exception as e:
            error_msg = f"重新下载过程中发生错误: {str(e)}"
            self._log(error_msg)
            QMessageBox.critical(self, "重新下载错误", error_msg)
            
            # 重置下载状态
            if hasattr(self, 'downloader'):
                self.downloader = None
            self._update_ui_state()
            
            # 打印完整的错误信息到控制台用于调试
            import traceback
            print("=== 重新下载错误详情 ===")
            traceback.print_exc()
            print("=== 错误详情结束 ===")
        
        finally:
            # 确保UI状态正确更新
            self._update_ui_state()
    
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
        is_verifying = hasattr(self, '_is_verifying') and self._is_verifying
        
        # 更新开始下载按钮状态和提示
        download_enabled = has_files and has_output_dir and has_selection and not is_downloading and not is_verifying
        self.start_download_btn.setEnabled(download_enabled)
        
        if not download_enabled:
            if not has_files:
                self.start_download_btn.setToolTip("请先加载BigFilesMD5s.json文件")
            elif not has_output_dir:
                self.start_download_btn.setToolTip("请先选择下载目录")
            elif not has_selection:
                self.start_download_btn.setToolTip("请至少选择一个文件进行下载")
            elif is_downloading:
                self.start_download_btn.setToolTip("正在下载中，请等待完成")
            elif is_verifying:
                self.start_download_btn.setToolTip("正在验证MD5，请等待完成")
        else:
            self.start_download_btn.setToolTip(f"开始下载选中的 {len(self.file_table_model.get_checked_items())} 个文件")
        
        # 更新取消下载按钮状态和提示
        self.cancel_download_btn.setEnabled(is_downloading)
        if is_downloading:
            self.cancel_download_btn.setToolTip("取消正在进行的下载")
        else:
            self.cancel_download_btn.setToolTip("当前没有下载任务")
        
        # MD5验证按钮：验证过程中也保持可点击（用于取消），但不能在下载时点击
        verify_enabled = has_files and has_output_dir and has_selection and not is_downloading
        self.verify_md5_btn.setEnabled(verify_enabled)
        
        if not verify_enabled:
            if not has_files:
                self.verify_md5_btn.setToolTip("请先加载BigFilesMD5s.json文件")
            elif not has_output_dir:
                self.verify_md5_btn.setToolTip("请先选择下载目录")
            elif not has_selection:
                self.verify_md5_btn.setToolTip("请至少选择一个文件进行验证")
            elif is_downloading:
                self.verify_md5_btn.setToolTip("下载过程中无法验证MD5")
        else:
            if is_verifying:
                self.verify_md5_btn.setToolTip("取消正在进行的MD5验证")
            else:
                self.verify_md5_btn.setToolTip(f"验证选中的 {len(self.file_table_model.get_checked_items())} 个文件的MD5完整性")
        
        # 更新重新下载按钮状态和提示
        verify_failed_items = [item for item in self.file_table_model.get_checked_items() 
                             if item.status == DownloadStatus.VERIFY_FAILED]
        redownload_enabled = (has_files and has_output_dir and len(verify_failed_items) > 0 
                            and not is_downloading and not is_verifying)
        self.redownload_btn.setEnabled(redownload_enabled)
        
        if not redownload_enabled:
            if not has_files:
                self.redownload_btn.setToolTip("请先加载BigFilesMD5s.json文件")
            elif not has_output_dir:
                self.redownload_btn.setToolTip("请先选择下载目录")
            elif len(verify_failed_items) == 0:
                selected_count = len(self.file_table_model.get_checked_items())
                if selected_count == 0:
                    self.redownload_btn.setToolTip("请选择需要重新下载的验证失败文件")
                else:
                    self.redownload_btn.setToolTip("选中的文件中没有验证失败的文件")
            elif is_downloading:
                self.redownload_btn.setToolTip("下载过程中无法重新下载")
            elif is_verifying:
                self.redownload_btn.setToolTip("验证过程中无法重新下载")
        else:
            self.redownload_btn.setToolTip(f"重新下载 {len(verify_failed_items)} 个验证失败的文件（将覆盖现有文件）")
        
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
            f"验证失败: {stats['verify_failed']} | "
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
        # 通过文件名直接高效刷新表格，避免 O(n) 搜索
        self.file_table_model.update_file_by_filename(filename)
    
    @qasync.asyncSlot(str, bool, str)
    async def _on_file_completed(self, filename: str, success: bool, message: str):
        """文件下载完成 - 大数据集优化版本"""
        import time
        current_time = time.time()
        
        # 阶段一优化：减少重复的"文件已存在"日志输出
        if not (success and message == "文件已存在"):
            status = "成功" if success else "失败"
            self._log(f"文件下载完成: {filename} - {status} ({message})")
        
        # 更新表格显示（O(1)）
        self.file_table_model.update_file_by_filename(filename)
        
        # 增加完成计数
        self._download_completed_count += 1
        
        # 🚀 大数据集优化：减少频繁的统计更新
        # 只在特定条件下更新统计信息，避免每个文件都遍历50000+项
        should_update_stats = (
            current_time - self._last_stats_update > 2.0 or  # 每2秒更新一次
            self._download_completed_count % 5 == 0 or  # 每5个文件更新一次
            not (self.downloader and self.downloader.is_downloading)  # 下载结束时必须更新
        )
        
        if should_update_stats:
            self._update_statistics()
            self._last_stats_update = current_time
        
        # 🚀 轻量级进度更新：避免重复计算全局统计
        if self.downloader and self.downloader.is_downloading:
            # 使用简单的计数器更新进度，避免遍历所有文件
            selected_count = len(self.file_table_model.get_checked_items()) 
            progress = (self._download_completed_count / selected_count * 100) if selected_count > 0 else 0
            self.progress_bar.setValue(int(min(progress, 100)))
            self.status_label.setText(f"下载中... {self._download_completed_count}/{selected_count} ({progress:.1f}%)")
        
        # 🚀 大数据集优化：减少频繁的状态保存  
        # 50000+文件的JSON序列化非常耗时，改为批量保存
        should_save_state = (
            current_time - self._last_save_time > 10.0 or  # 每10秒保存一次
            self._download_completed_count % 20 == 0 or  # 每20个文件保存一次
            not (self.downloader and self.downloader.is_downloading)  # 下载结束时必须保存
        )
        
        if should_save_state:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    self.data_manager.save_state,
                    self.file_table_model.get_file_items(),
                    self.current_output_dir
                )
                self._last_save_time = current_time
            except Exception as e:
                self._log(f"保存状态失败: {e}")
    
    def _on_overall_progress(self, progress: float, completed_count: int, total_count: int):
        """整体进度更新 - 大数据集优化版本"""
        # 🚀 大数据集优化：直接使用传入的参数，避免重复计算统计信息
        # 不再调用 get_statistics() 遍历50000+文件
        
        # 使用传入的下载器进度信息
        self.progress_bar.setValue(int(progress))
        self.status_label.setText(f"下载中... {completed_count}/{total_count} ({progress:.1f}%)")
    
    def _on_check_progress(self, progress: float):
        """文件检查进度更新"""
        self.progress_bar.setValue(int(progress))
        self.status_label.setText(f"检查文件存在性... {progress:.1f}%")
    
    def _on_download_started(self):
        """下载开始"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("下载中...")
        
        # 🚀 重置性能计数器
        self._download_completed_count = 0
        import time
        self._last_stats_update = time.time()
        self._last_save_time = time.time()
        
        self._update_ui_state()
    
    def _on_download_finished(self, success_count: int, failed_count: int):
        """下载完成 - 大数据集优化版本"""
        self.progress_bar.setVisible(False)
        self.status_label.setText(
            f"下载完成 - 成功: {success_count}, 失败: {failed_count}"
        )
        self.downloader = None
        
        # 🚀 大数据集优化：下载完成时最后一次强制统计更新
        self._log(f"📊 下载完成，正在更新统计信息...")
        self._update_ui_state()
        self._update_statistics()
        
        # 🚀 强制最后一次状态保存，确保数据完整性
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            # 修复：直接使用 run_in_executor 返回的 Future，不要用 create_task 包装
            future = loop.run_in_executor(
                None,
                self.data_manager.save_state,
                self.file_table_model.get_file_items(),
                self.current_output_dir
            )
            # 可选：添加完成回调
            future.add_done_callback(lambda f: self._on_final_save_completed(f))
            self._log(f"💾 状态保存已提交，后台执行中...")
        except Exception as e:
            self._log(f"最终状态保存失败: {e}")
    
    def _on_final_save_completed(self, future):
        """最终状态保存完成回调"""
        try:
            future.result()  # 获取结果，如果有异常会抛出
            self._log(f"💾 最终状态保存完成")
        except Exception as e:
            self._log(f"最终状态保存失败: {e}")
    
    def _on_redownload_finished(self, success_count: int, failed_count: int):
        """重新下载完成"""
        self.progress_bar.setVisible(False)
        self.status_label.setText(
            f"重新下载完成 - 成功: {success_count}, 失败: {failed_count}"
        )
        self.downloader = None
        
        # 强制统计更新
        self._log(f"📊 重新下载完成，正在更新统计信息...")
        self._update_ui_state()
        self._update_statistics()
        
        # 显示重新下载完成提示
        total_redownloaded = success_count + failed_count
        if failed_count == 0:
            QMessageBox.information(
                self,
                "重新下载完成",
                f"🎉 重新下载全部成功！\n\n"
                f"总计重新下载: {total_redownloaded} 个文件\n"
                f"全部成功: {success_count} 个\n\n"
                f"💡 建议: 可以对这些文件重新验证MD5，确保完整性。"
            )
        else:
            QMessageBox.warning(
                self,
                "重新下载完成",
                f"重新下载已完成，但部分文件仍然失败。\n\n"
                f"总计重新下载: {total_redownloaded} 个文件\n"
                f"重新下载成功: {success_count} 个\n"
                f"仍然失败: {failed_count} 个\n\n"
                f"💡 建议:\n"
                f"• 检查网络连接\n"
                f"• 重新尝试失败的文件\n"
                f"• 对成功的文件验证MD5"
            )
        
        # 强制最后一次状态保存
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            future = loop.run_in_executor(
                None,
                self.data_manager.save_state,
                self.file_table_model.get_file_items(),
                self.current_output_dir
            )
            future.add_done_callback(lambda f: self._on_final_save_completed(f))
            self._log(f"💾 重新下载状态保存已提交，后台执行中...")
        except Exception as e:
            self._log(f"重新下载状态保存失败: {e}")
    
    def _on_download_cancelled(self):
        """下载取消"""
        self.progress_bar.setVisible(False)
        self.status_label.setText("下载已取消")
        self.downloader = None
        self._log("✅ 下载已成功取消")
        
        # 显示取消确认提示
        checked_count = len(self.file_table_model.get_checked_items())
        QMessageBox.information(
            self,
            "下载已取消",
            f"下载已成功取消！\n\n"
            f"💡 提示:\n"
            f"• 已下载完成的文件已保存\n"
            f"• 仍有 {checked_count} 个文件处于选中状态\n"
            f"• 可以随时点击「开始下载」继续下载"
        )
        
        self._update_ui_state()
    
    # MD5计算器信号处理方法
    def _on_md5_file_completed(self, filename: str, success: bool, message: str):
        """MD5文件计算完成 - 优化版本"""
        # 减少UI更新频率，避免主线程阻塞
        # 不在这里更新表格，改为批量更新
        
        # 记录日志（只记录失败的情况，成功的太多会刷屏）
        if not success:
            self._log(f"❌ {filename} - {message}")
    
    def _on_md5_overall_progress(self, progress: float, completed_count: int, total_count: int):
        """MD5整体进度更新 - 优化版本"""
        # 减少UI更新频率，只在关键节点更新
        if completed_count % 100 == 0 or completed_count == total_count or progress >= 100.0:
            # 更新进度条和状态显示
            self.progress_bar.setValue(int(progress))
            self.status_label.setText(f"并行MD5验证中... {completed_count}/{total_count} ({progress:.1f}%)")
            
            # 强制处理UI事件，防止界面卡死
            QApplication.processEvents()
            
            # 只在重要节点更新统计信息
            if completed_count % 500 == 0 or completed_count == total_count:
                self._update_statistics()
    
    def _create_menubar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        
        # 关于动作
        about_action = QAction("关于 DLC Manager", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        
        # 分隔符
        help_menu.addSeparator()
        
        # 退出动作
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        help_menu.addAction(exit_action)
    
    def _show_about(self):
        """显示关于对话框"""
        from .about_dialog import AboutDialog
        dialog = AboutDialog(self)
        dialog.exec() 