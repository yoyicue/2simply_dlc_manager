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
    QLineEdit, QCheckBox, QSpinBox, QMenuBar
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
        self.verify_md5_btn.setText("验证MD5")
        self.verify_md5_btn.setToolTip("验证选中文件的MD5完整性")
        self.status_label.setText("正在取消MD5验证...")
        self._log("用户取消了MD5验证")
    
    @qasync.asyncSlot()
    async def _verify_selected_files(self):
        """验证选中文件的MD5"""
        try:
            if not self.current_output_dir:
                QMessageBox.warning(self, "警告", "请先选择下载目录")
                return

            checked_items = self.file_table_model.get_checked_items()
            if not checked_items:
                QMessageBox.warning(self, "警告", "请至少选择一个文件进行验证")
                return

            # 过滤出只有已完成的文件进行验证
            files_to_verify = []
            for item in checked_items:
                file_path = self.current_output_dir / item.full_filename
                if file_path.exists():
                    files_to_verify.append(item)

            if not files_to_verify:
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
            self.status_label.setText("开始MD5验证...")

            self._log(f"开始验证 {len(files_to_verify)} 个文件的MD5...")

            # 导入验证相关模块
            from core.resume import IntegrityManager, ResumeConfig

            # 创建验证管理器
            config = ResumeConfig()
            integrity_manager = IntegrityManager(config)

            verified_count = 0
            success_count = 0
            failed_count = 0

            for idx, item in enumerate(files_to_verify):
                # 检查取消标志
                if self._verification_cancelled:
                    self._log(f"在验证第 {idx+1} 个文件时用户取消了验证")
                    break

                file_path = self.current_output_dir / item.full_filename
                
                # 更新进度
                progress = (idx / len(files_to_verify)) * 100
                self.progress_bar.setValue(int(progress))
                self.status_label.setText(f"验证中... {idx+1}/{len(files_to_verify)} - {item.filename}")

                # 标记为验证中
                item.mark_md5_verifying()
                self.file_table_model.update_file_by_filename(item.filename)

                # 让UI有机会响应用户操作
                await asyncio.sleep(0.01)
                
                # 再次检查取消标志（在实际验证前）
                if self._verification_cancelled:
                    # 恢复为未验证状态
                    item.reset_md5_verify_status()
                    self.file_table_model.update_file_by_filename(item.filename)
                    break

                # 执行验证
                def progress_callback(message):
                    # 在进度回调中也检查取消标志
                    if not self._verification_cancelled:
                        self._log(f"[{item.filename}] {message}")

                try:
                    result = integrity_manager.verify_integrity_enhanced(
                        item, file_path, progress_callback
                    )

                    # 检查是否在验证过程中被取消
                    if self._verification_cancelled:
                        item.reset_md5_verify_status()
                        self.file_table_model.update_file_by_filename(item.filename)
                        break

                    # 更新验证结果和下载状态
                    item.mark_md5_verified(result.calculated_hash, result.is_valid)
                    
                    if result.is_valid:
                        # 验证成功，保持已完成状态（如果原来是已完成的话）
                        success_count += 1
                        self._log(f"✅ {item.filename} - MD5验证成功")
                    else:
                        # 验证失败，更改状态为验证失败，方便后续重新下载
                        item.status = DownloadStatus.VERIFY_FAILED
                        item.error_message = result.error_message or "MD5哈希值不匹配"
                        failed_count += 1
                        self._log(f"❌ {item.filename} - MD5验证失败，已标记为需重新下载: {item.error_message}")

                except Exception as e:
                    if not self._verification_cancelled:
                        failed_count += 1
                        item.mark_md5_verified("", False)
                        item.status = DownloadStatus.VERIFY_FAILED
                        item.error_message = f"MD5验证异常: {str(e)}"
                        self._log(f"❌ {item.filename} - MD5验证出错，已标记为需重新下载: {str(e)}")

                # 更新表格显示（O(1)）
                self.file_table_model.update_file_by_filename(item.filename)
                # 仍然强制刷新表格视图，确保颜色等视觉元素即时更新
                if hasattr(self, 'file_table_view') and self.file_table_view:
                    self.file_table_view.viewport().update()
                    self.file_table_view.repaint()
                
                verified_count += 1

                # 每验证5个文件保存一次状态（减少I/O频率）
                if verified_count % 5 == 0 or verified_count == len(files_to_verify):
                    try:
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(
                            None,
                            self.data_manager.save_state,
                            self.file_table_model.get_file_items(),
                            self.current_output_dir
                        )
                    except Exception as e:
                        self._log(f"保存状态失败: {e}")
                
                # 让UI有机会响应（特别是对于大量文件）
                if idx % 10 == 0:  # 每10个文件给UI一次响应机会
                    await asyncio.sleep(0.05)

            # 验证完成
            self.progress_bar.setVisible(False)
            
            # 恢复按钮状态
            self.verify_md5_btn.setText("验证MD5")
            self.verify_md5_btn.setToolTip("验证选中文件的MD5完整性")
            
            if self._verification_cancelled:
                self.status_label.setText("MD5验证已取消")
                self._log(f"MD5验证已取消 - 已验证: {verified_count}/{len(files_to_verify)}")
                
                # 显示取消摘要
                if verified_count > 0:
                    QMessageBox.information(
                        self, 
                        "验证已取消", 
                        f"MD5验证已被用户取消！\n\n"
                        f"总文件数: {len(files_to_verify)}\n"
                        f"已验证: {verified_count}\n"
                        f"验证成功: {success_count}\n"
                        f"验证失败: {failed_count}\n"
                        f"未验证: {len(files_to_verify) - verified_count}\n\n"
                        f"详细结果请查看MD5列的颜色显示"
                    )
            else:
                self.status_label.setText(f"MD5验证完成 - 成功: {success_count}, 失败: {failed_count}")
                self._log(f"✅ MD5验证完成 - 总计: {verified_count}, 成功: {success_count}, 失败: {failed_count}")

                # 显示验证结果摘要
                if verified_count > 0:
                    QMessageBox.information(
                        self, 
                        "验证完成", 
                        f"MD5验证完成！\n\n"
                        f"验证文件数: {verified_count}\n"
                        f"验证成功: {success_count}\n"
                        f"验证失败: {failed_count}\n\n"
                        f"详细结果请查看MD5列的颜色显示"
                    )

        except Exception as e:
            error_msg = f"MD5验证过程中发生错误: {str(e)}"
            self._log(error_msg)
            QMessageBox.critical(self, "验证错误", error_msg)
            
            # 打印完整的错误信息到控制台用于调试
            import traceback
            print("=== MD5验证错误详情 ===")
            traceback.print_exc()
            print("=== 错误详情结束 ===")
        
        finally:
            # 重置验证状态
            self._is_verifying = False
            self._verification_cancelled = False
            
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
        is_verifying = hasattr(self, '_is_verifying') and self._is_verifying
        
        # 更新按钮状态
        self.start_download_btn.setEnabled(
            has_files and has_output_dir and has_selection and not is_downloading and not is_verifying
        )
        self.cancel_download_btn.setEnabled(is_downloading)
        # MD5验证按钮：验证过程中也保持可点击（用于取消），但不能在下载时点击
        self.verify_md5_btn.setEnabled(
            has_files and has_output_dir and has_selection and not is_downloading
        )
        
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
        """文件下载完成"""
        # 阶段一优化：减少重复的"文件已存在"日志输出
        if not (success and message == "文件已存在"):
            status = "成功" if success else "失败"
            self._log(f"文件下载完成: {filename} - {status} ({message})")
        
        # 更新表格显示（O(1)）
        self.file_table_model.update_file_by_filename(filename)
        
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
        
        # 异步保存状态，避免阻塞UI
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.data_manager.save_state,
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