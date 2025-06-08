"""
文件表格模型
"""
from typing import List, Any, Optional
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex, Signal
from PySide6.QtGui import QColor

from core import FileItem, DownloadStatus, MD5VerifyStatus


class FileTableModel(QAbstractTableModel):
    """文件列表表格模型"""
    
    # 信号定义
    selection_changed = Signal()
    
    # 表格列定义
    COLUMNS = [
        ("选择", "checked"),
        ("文件名", "filename"),
        ("MD5", "md5"),
        ("状态", "status"),
        ("进度", "progress"),
        ("大小", "size"),
        ("已下载", "downloaded_size"),
        ("本地路径", "local_path")
    ]
    
    def __init__(self):
        super().__init__()
        self._file_items: List[FileItem] = []
        self._filtered_items: List[FileItem] = []  # 过滤后的条目
        self._checked_items: set = set()  # 选中的行索引
        self._current_filters = {'status': None, 'search': ''}
        
        # 新增：提供 O(1) 访问的映射表
        #   1) _filename_map 用于通过文件名快速获取 FileItem
        #   2) _filtered_row_map 用于通过文件名快速获取在过滤后列表中的行号
        # 这些映射避免了在 4 万行列表里线性搜索，显著提升 UI 更新性能
        self._filename_map: dict[str, FileItem] = {}
        self._filtered_row_map: dict[str, int] = {}
        # 映射表状态追踪，避免不必要的重建
        self._filename_map_valid = False
        self._filtered_row_map_valid = False
    
    # --------------------------- 私有辅助方法 ---------------------------
    def _ensure_filename_map(self):
        """延迟构建文件名映射表，只有在需要时才构建"""
        if not self._filename_map_valid:
            self._filename_map = {item.filename: item for item in self._file_items}
            self._filename_map_valid = True

    def _ensure_filtered_row_map(self):
        """延迟构建过滤后行号映射表，只有在需要时才构建"""
        if not self._filtered_row_map_valid:
            self._filtered_row_map = {
                item.filename: idx for idx, item in enumerate(self._filtered_items)
            }
            self._filtered_row_map_valid = True

    def _invalidate_filename_map(self):
        """标记文件名映射表为无效，下次访问时将重建"""
        self._filename_map_valid = False
        self._filename_map.clear()
    
    def _invalidate_filtered_row_map(self):
        """标记过滤映射表为无效，下次访问时将重建"""
        self._filtered_row_map_valid = False
        self._filtered_row_map.clear()
    
    def set_file_items(self, file_items: List[FileItem]):
        """设置文件项列表"""
        self.beginResetModel()
        self._file_items = file_items
        self._filtered_items = file_items.copy()  # 初始时显示所有项目
        # 默认全选所有文件
        self._checked_items = set(range(len(self._filtered_items)))
        # 标记映射表为无效，但不立即构建（延迟到真正需要时）
        self._invalidate_filename_map()
        self._invalidate_filtered_row_map()
        self.endResetModel()
        # 发送选择变化信号
        self.selection_changed.emit()
    
    def get_file_items(self) -> List[FileItem]:
        """获取所有文件项"""
        return self._file_items
    
    def get_checked_items(self) -> List[FileItem]:
        """获取选中的文件项"""
        return [self._filtered_items[i] for i in self._checked_items if i < len(self._filtered_items)]
    
    def get_file_item(self, row: int) -> Optional[FileItem]:
        """获取指定行的文件项"""
        if 0 <= row < len(self._filtered_items):
            return self._filtered_items[row]
        return None
    
    def update_file_item(self, file_item: FileItem):
        """更新文件项信息"""
        try:
            # 找到在过滤后列表中的行索引
            row = self._filtered_items.index(file_item)
            
            # 发出信号更新这一行
            self.dataChanged.emit(
                self.index(row, 0),
                self.index(row, self.columnCount() - 1)
            )
            
        except ValueError:
            # 如果文件不在过滤后的视图中，则无需更新
            pass
    
    def check_all(self, checked: bool = True):
        """全选/全不选"""
        if checked:
            self._checked_items = set(range(len(self._filtered_items)))
        else:
            self._checked_items.clear()
        
        # 通知复选框列变化
        if self._filtered_items:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._filtered_items) - 1, 0)
            )
        self.selection_changed.emit()
    
    def check_by_status(self, status: DownloadStatus, checked: bool = True):
        """按状态选择"""
        for i, item in enumerate(self._filtered_items):
            if item.status == status:
                if checked:
                    self._checked_items.add(i)
                else:
                    self._checked_items.discard(i)
        
        # 通知复选框列变化
        if self._filtered_items:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._filtered_items) - 1, 0)
            )
        self.selection_changed.emit()
    
    def apply_filters(self, status_filter=None, search_text: str = ''):
        """应用过滤条件"""
        self._current_filters['status'] = status_filter
        self._current_filters['search'] = search_text
        
        # 保存当前选中的文件项的MD5（用作唯一标识符）
        currently_checked_md5s = set(item.md5 for item in self.get_checked_items())
        
        self.beginResetModel()
        
        # 重置过滤列表
        self._filtered_items = []
        
        for item in self._file_items:
            # 状态过滤
            if status_filter is not None and item.status != status_filter:
                continue
            
            # 搜索过滤
            if search_text:
                if (search_text not in item.filename.lower() and 
                    search_text not in item.md5.lower()):
                    continue
            
            self._filtered_items.append(item)
        
        # 重新设置选中状态：只选择在过滤后列表中且之前被选中的项目
        self._checked_items.clear()
        for i, item in enumerate(self._filtered_items):
            if item.md5 in currently_checked_md5s:
                self._checked_items.add(i)
        
        # 过滤结果变化后需要重建行号映射
        self._invalidate_filtered_row_map()
        
        self.endResetModel()
        self.selection_changed.emit()
    
    # QAbstractTableModel 必需方法
    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._filtered_items)
    
    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)
    
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if 0 <= section < len(self.COLUMNS):
                return self.COLUMNS[section][0]
        return None
    
    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._filtered_items):
            return None
        
        file_item = self._filtered_items[index.row()]
        column_key = self.COLUMNS[index.column()][1]
        
        if role == Qt.DisplayRole:
            return self._get_display_data(file_item, column_key, index.row())
        elif role == Qt.CheckStateRole and column_key == "checked":
            return Qt.Checked if index.row() in self._checked_items else Qt.Unchecked
        elif role == Qt.BackgroundRole:
            return self._get_background_color(file_item, column_key)
        elif role == Qt.ToolTipRole:
            return self._get_tooltip(file_item, column_key)
        
        return None
    
    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        if not index.isValid() or index.row() >= len(self._filtered_items):
            return False
        
        column_key = self.COLUMNS[index.column()][1]
        
        # 处理复选框点击
        if role == Qt.CheckStateRole and column_key == "checked":
            row = index.row()
            # Qt 传递的 value 可能是整数或枚举，需要正确处理
            if value == Qt.Checked or value == 2:  # Qt.Checked 的值是 2
                self._checked_items.add(row)
            else:
                self._checked_items.discard(row)
            
            self.dataChanged.emit(index, index)
            self.selection_changed.emit()
            return True
        
        return False
    
    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags
        
        column_key = self.COLUMNS[index.column()][1]
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        
        if column_key == "checked":
            flags |= Qt.ItemIsUserCheckable
        
        return flags
    
    def _get_display_data(self, file_item: FileItem, column_key: str, row: int) -> str:
        """获取显示数据"""
        if column_key == "checked":
            return ""
        elif column_key == "filename":
            return file_item.filename
        elif column_key == "md5":
            return file_item.md5
        elif column_key == "status":
            return file_item.status.value
        elif column_key == "progress":
            if file_item.status == DownloadStatus.DOWNLOADING:
                return f"{file_item.progress:.1f}%"
            elif file_item.status == DownloadStatus.COMPLETED:
                return "100%"
            else:
                return "-"
        elif column_key == "size":
            if file_item.size:
                return self._format_size(file_item.size)
            return "-"
        elif column_key == "downloaded_size":
            if file_item.downloaded_size > 0:
                return self._format_size(file_item.downloaded_size)
            return "-"
        elif column_key == "local_path":
            if file_item.local_path:
                return str(file_item.local_path.name)
            return "-"
        
        return ""
    
    def _get_background_color(self, file_item: FileItem, column_key: str) -> Optional[QColor]:
        """根据下载状态获取背景色"""
        # 所有列根据下载状态显示颜色
        if file_item.status == DownloadStatus.COMPLETED:
            return QColor(200, 255, 200)  # 浅绿色 - 已完成
        elif file_item.status == DownloadStatus.FAILED:
            return QColor(255, 200, 200)  # 浅红色 - 下载失败
        elif file_item.status == DownloadStatus.VERIFY_FAILED:
            return QColor(255, 180, 100)  # 橙色 - 验证失败
        elif file_item.status == DownloadStatus.DOWNLOADING:
            return QColor(200, 200, 255)  # 浅蓝色 - 下载中
        elif file_item.status == DownloadStatus.SKIPPED:
            return QColor(255, 255, 200)  # 浅黄色 - 已跳过
        elif file_item.status == DownloadStatus.CANCELLED:
            return QColor(220, 220, 220)  # 浅灰色 - 已取消
        
        return None
    
    def _get_tooltip(self, file_item: FileItem, column_key: str) -> str:
        """获取工具提示"""
        if column_key == "filename":
            return f"完整文件名: {file_item.full_filename}"
        elif column_key == "md5":
            return f"完整MD5: {file_item.md5}"
        elif column_key == "status":
            tooltip = f"状态: {file_item.status.value}"
            if file_item.error_message:
                tooltip += f"\n错误: {file_item.error_message}"
            return tooltip
        elif column_key == "local_path" and file_item.local_path:
            return str(file_item.local_path)
        
        return ""
    
    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        size = float(size_bytes)
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        return f"{size:.1f} {units[unit_index]}"
    
    # --------------------------- 快速访问/更新接口 ---------------------------
    def get_item_by_filename(self, filename: str) -> Optional[FileItem]:
        """O(1) 根据文件名获取 FileItem"""
        self._ensure_filename_map()
        return self._filename_map.get(filename)

    def update_file_by_filename(self, filename: str):
        """O(1) 根据文件名高效刷新表格中的对应行"""
        self._ensure_filtered_row_map()
        row = self._filtered_row_map.get(filename)
        if row is not None:
            self.dataChanged.emit(
                self.index(row, 0),
                self.index(row, self.columnCount() - 1)
            ) 