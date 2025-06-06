"""
数据持久化模块
"""
import json
from pathlib import Path
from typing import List, Dict, Optional
from .models import FileItem, DownloadStatus


class DataManager:
    """数据管理器"""
    
    def __init__(self, data_file: Optional[Path] = None):
        self.data_file = data_file or Path("dlc_download_state.json")
    
    def load_file_mapping(self, json_file: Path) -> List[FileItem]:
        """从BigFilesMD5s.json加载文件映射"""
        try:
            content = json_file.read_text(encoding='utf-8')
            content = content.strip()
            
            # 处理可能的JSON格式问题
            if content.endswith(',}'):
                content = content[:-2] + '}'
            elif content.endswith(','):
                content = content[:-1]
            
            file_mapping = json.loads(content)
            
            file_items = []
            for filename, md5 in file_mapping.items():
                item = FileItem(filename=filename, md5=md5)
                file_items.append(item)
            
            return file_items
        
        except Exception as e:
            raise Exception(f"加载文件映射失败: {str(e)}")
    
    def save_state(self, file_items: List[FileItem], output_dir: Path):
        """保存下载状态"""
        try:
            state_data = {
                'output_dir': str(output_dir),
                'files': []
            }
            
            for item in file_items:
                file_data = {
                    'filename': item.filename,
                    'md5': item.md5,
                    'status': item.status.value,
                    'progress': item.progress,
                    'size': item.size,
                    'downloaded_size': item.downloaded_size,
                    'local_path': str(item.local_path) if item.local_path else None,
                    'error_message': item.error_message,
                    'download_url': item.download_url
                }
                state_data['files'].append(file_data)
            
            self.data_file.write_text(
                json.dumps(state_data, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            
        except Exception as e:
            raise Exception(f"保存状态失败: {str(e)}")
    
    def load_state(self) -> tuple[List[FileItem], Optional[Path]]:
        """加载下载状态"""
        if not self.data_file.exists():
            return [], None
        
        try:
            state_data = json.loads(self.data_file.read_text(encoding='utf-8'))
            
            output_dir = Path(state_data.get('output_dir', '')) if state_data.get('output_dir') else None
            file_items = []
            
            for file_data in state_data.get('files', []):
                # 查找状态枚举
                status = DownloadStatus.PENDING
                for status_enum in DownloadStatus:
                    if status_enum.value == file_data.get('status', '待下载'):
                        status = status_enum
                        break
                
                item = FileItem(
                    filename=file_data['filename'],
                    md5=file_data['md5'],
                    status=status,
                    progress=file_data.get('progress', 0.0),
                    size=file_data.get('size'),
                    downloaded_size=file_data.get('downloaded_size', 0),
                    local_path=Path(file_data['local_path']) if file_data.get('local_path') else None,
                    error_message=file_data.get('error_message'),
                    download_url=file_data.get('download_url')
                )
                file_items.append(item)
            
            return file_items, output_dir
            
        except Exception as e:
            raise Exception(f"加载状态失败: {str(e)}")
    
    def clear_state(self):
        """清除保存的状态"""
        if self.data_file.exists():
            self.data_file.unlink()
    
    def get_statistics(self, file_items: List[FileItem]) -> Dict[str, int]:
        """获取下载统计信息"""
        stats = {
            'total': len(file_items),
            'pending': 0,
            'downloading': 0,
            'completed': 0,
            'failed': 0,
            'cancelled': 0,
            'skipped': 0
        }
        
        for item in file_items:
            if item.status == DownloadStatus.PENDING:
                stats['pending'] += 1
            elif item.status == DownloadStatus.DOWNLOADING:
                stats['downloading'] += 1
            elif item.status == DownloadStatus.COMPLETED:
                stats['completed'] += 1
            elif item.status == DownloadStatus.FAILED:
                stats['failed'] += 1
            elif item.status == DownloadStatus.CANCELLED:
                stats['cancelled'] += 1
            elif item.status == DownloadStatus.SKIPPED:
                stats['skipped'] += 1
        
        return stats
    
    def get_total_size(self, file_items: List[FileItem]) -> tuple[int, int]:
        """获取总大小和已下载大小（字节）"""
        total_size = 0
        downloaded_size = 0
        
        for item in file_items:
            if item.size:
                total_size += item.size
            downloaded_size += item.downloaded_size
        
        return total_size, downloaded_size
    
    def format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        size = float(size_bytes)
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        return f"{size:.2f} {units[unit_index]}"
    
    def filter_files(self, file_items: List[FileItem], 
                    status_filter: Optional[DownloadStatus] = None,
                    search_text: str = "") -> List[FileItem]:
        """过滤文件列表"""
        filtered_items = file_items
        
        # 按状态过滤
        if status_filter:
            filtered_items = [item for item in filtered_items if item.status == status_filter]
        
        # 按搜索文本过滤
        if search_text:
            search_text = search_text.lower()
            filtered_items = [
                item for item in filtered_items 
                if search_text in item.filename.lower() or search_text in item.md5.lower()
            ]
        
        return filtered_items 