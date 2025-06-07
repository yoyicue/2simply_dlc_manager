"""
数据持久化模块
"""
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from .models import FileItem, DownloadStatus
from .utils import get_app_data_file, ensure_writable_path, is_running_from_bundle


class DataManager:
    """数据管理器"""
    
    def __init__(self, data_file: Optional[Path] = None):
        # 如果没有指定文件路径，自动选择合适的位置
        if data_file is None:
            if is_running_from_bundle():
                # 打包应用：使用用户数据目录
                self.data_file = get_app_data_file("dlc_download_state.json")
            else:
                # 开发环境：优先使用当前目录，如果不可写则使用用户数据目录
                self.data_file = ensure_writable_path(Path("dlc_download_state.json"))
        else:
            # 用户指定的路径：确保可写
            self.data_file = ensure_writable_path(data_file)
        
        # 阶段二新增：Bloom Filter缓存
        self.bloom_filter = None
        self._bloom_enabled = True
    
    def enable_bloom_filter(self, enabled: bool = True):
        """启用/禁用Bloom Filter"""
        self._bloom_enabled = enabled
        if not enabled:
            self.bloom_filter = None
    
    def build_bloom_filter(self, file_items: List[FileItem]) -> Optional[Dict[str, Any]]:
        """构建Bloom Filter缓存"""
        if not self._bloom_enabled:
            return None
        
        try:
            from utils.bloom_filter import FileBloomFilter
            
            # 创建文件专用Bloom Filter
            self.bloom_filter = FileBloomFilter(expected_files=len(file_items))
            
            # 从已完成文件构建
            build_info = self.bloom_filter.build_from_completed_files(file_items)
            
            return build_info
            
        except Exception as e:
            print(f"构建Bloom Filter失败: {e}")
            self.bloom_filter = None
            return None
    
    def get_bloom_filter_info(self) -> Optional[Dict[str, Any]]:
        """获取Bloom Filter信息"""
        if self.bloom_filter and self.bloom_filter.is_cache_valid():
            return self.bloom_filter.get_info()
        return None
    
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
    
    def load_file_mapping_with_state_diff(self, json_file: Path) -> tuple[List[FileItem], Dict[str, int]]:
        """从BigFilesMD5s.json加载文件映射，并与现有状态进行diff合并
        
        Returns:
            (merged_file_items, diff_info)
            diff_info包含: {'new': count, 'existing': count, 'updated': count, 'removed': count}
        """
        try:
            # 1. 加载新的文件映射
            content = json_file.read_text(encoding='utf-8')
            content = content.strip()
            
            # 处理可能的JSON格式问题
            if content.endswith(',}'):
                content = content[:-2] + '}'
            elif content.endswith(','):
                content = content[:-1]
            
            file_mapping = json.loads(content)
            
            # 2. 尝试加载现有状态
            existing_items = {}
            try:
                saved_items, _ = self.load_state()
                for item in saved_items:
                    # 使用(filename, md5)作为唯一键
                    key = (item.filename, item.md5)
                    existing_items[key] = item
            except:
                # 如果没有现有状态或加载失败，继续处理
                pass
            
            # 3. 进行diff合并
            merged_items = []
            diff_info = {'new': 0, 'existing': 0, 'updated': 0, 'removed': 0}
            
            # 处理新文件映射中的每个文件
            for filename, md5 in file_mapping.items():
                key = (filename, md5)
                
                if key in existing_items:
                    # 文件已存在，保留原有状态
                    existing_item = existing_items[key]
                    merged_items.append(existing_item)
                    diff_info['existing'] += 1
                else:
                    # 检查是否是同名文件但MD5不同（文件更新）
                    updated_existing = False
                    for (existing_filename, existing_md5), existing_item in existing_items.items():
                        if existing_filename == filename and existing_md5 != md5:
                            # 同名文件但MD5不同，重置状态
                            new_item = FileItem(filename=filename, md5=md5)
                            merged_items.append(new_item)
                            diff_info['updated'] += 1
                            updated_existing = True
                            break
                    
                    if not updated_existing:
                        # 全新文件
                        new_item = FileItem(filename=filename, md5=md5)
                        merged_items.append(new_item)
                        diff_info['new'] += 1
            
            # 计算被移除的文件（在旧状态中存在但新映射中不存在）
            new_mapping_keys = {(filename, md5) for filename, md5 in file_mapping.items()}
            for key in existing_items.keys():
                if key not in new_mapping_keys:
                    diff_info['removed'] += 1
            
            return merged_items, diff_info
            
        except Exception as e:
            raise Exception(f"加载文件映射失败: {str(e)}")
    
    def save_state(self, file_items: List[FileItem], output_dir: Path):
        """保存下载状态"""
        try:
            from datetime import datetime
            
            state_data = {
                'output_dir': str(output_dir) if output_dir else None,
                # 阶段一新增：缓存元数据
                'metadata_version': '1.0',
                'last_full_scan': datetime.now().isoformat(),
                'directory_structure': 'flat',  # 当前为平铺结构
                'total_files': len(file_items),
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
                    'download_url': item.download_url,
                    # 阶段一新增：元数据字段
                    'mtime': item.mtime,
                    'disk_verified': item.disk_verified,
                    'last_checked': item.last_checked,
                    'cache_version': item.cache_version
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
            
            # 处理 output_dir，注意字符串 "None" 的情况
            output_dir_str = state_data.get('output_dir', '')
            if output_dir_str and output_dir_str != 'None':
                output_dir = Path(output_dir_str)
            else:
                output_dir = None
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
                    download_url=file_data.get('download_url'),
                    # 阶段一新增：加载元数据字段（向后兼容）
                    mtime=file_data.get('mtime'),
                    disk_verified=file_data.get('disk_verified', False),
                    last_checked=file_data.get('last_checked'),
                    cache_version=file_data.get('cache_version', '1.0')
                )
                file_items.append(item)
            
            # 阶段二新增：自动构建Bloom Filter
            if file_items and self._bloom_enabled:
                try:
                    bloom_info = self.build_bloom_filter(file_items)
                    if bloom_info:
                        print(f"🔍 Bloom Filter构建完成: {bloom_info['completed_files_count']}个文件, "
                              f"{bloom_info['memory_usage_kb']:.1f}KB内存")
                except Exception as e:
                    print(f"Bloom Filter构建失败: {e}")
            
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
    
    def get_cache_metadata(self) -> Dict[str, Any]:
        """获取缓存元数据信息"""
        if not self.data_file.exists():
            return {}
        
        try:
            state_data = json.loads(self.data_file.read_text(encoding='utf-8'))
            return {
                'metadata_version': state_data.get('metadata_version', '0.0'),
                'last_full_scan': state_data.get('last_full_scan'),
                'directory_structure': state_data.get('directory_structure', 'flat'),
                'total_files': state_data.get('total_files', 0),
                'file_count': len(state_data.get('files', []))
            }
        except:
            return {}
    
    def analyze_cache_reliability(self, file_items: List[FileItem], output_dir: Path, 
                                sample_ratio: float = 0.05) -> Dict[str, Any]:
        """分析缓存可靠性
        
        Args:
            file_items: 文件列表
            output_dir: 输出目录
            sample_ratio: 抽样比例 (默认5%)
        
        Returns:
            分析结果字典包含可靠性评分和建议
        """
        import random
        from datetime import datetime, timedelta
        
        if not file_items:
            return {
                'reliable': False, 
                'reason': '无缓存数据', 
                'score': 0.0,
                'recommendation': 'full_scan'
            }
        
        # 筛选已完成的文件用于抽样
        completed_items = [item for item in file_items 
                         if item.status == DownloadStatus.COMPLETED and item.disk_verified]
        
        if not completed_items:
            return {
                'reliable': False, 
                'reason': '无已验证的完成文件', 
                'score': 0.0,
                'recommendation': 'full_scan'
            }
        
        # 计算抽样大小
        sample_size = max(10, int(len(completed_items) * sample_ratio))
        sample_size = min(sample_size, len(completed_items))
        
        sample_items = random.sample(completed_items, sample_size)
        
        # 执行抽样验证
        valid_count = 0
        invalid_count = 0
        outdated_count = 0
        
        for item in sample_items:
            if not item.last_checked:
                invalid_count += 1
                continue
                
            file_path = output_dir / item.full_filename
            
            try:
                # 检查文件是否存在
                if not file_path.exists():
                    invalid_count += 1
                    continue
                
                # 检查缓存是否过期（24小时）
                if not item.is_cache_valid(file_path, max_age_hours=24):
                    outdated_count += 1
                    continue
                
                valid_count += 1
                
            except Exception:
                invalid_count += 1
        
        # 计算可靠性评分
        total_checked = len(sample_items)
        reliability_score = valid_count / total_checked if total_checked > 0 else 0.0
        
        # 分析结果
        analysis = {
            'reliable': reliability_score >= 0.9,  # 90%以上认为可靠
            'score': reliability_score,
            'sample_size': sample_size,
            'valid_count': valid_count,
            'invalid_count': invalid_count,
            'outdated_count': outdated_count,
            'total_completed': len(completed_items)
        }
        
        # 添加建议
        if reliability_score >= 0.95:
            analysis['recommendation'] = 'cache_reliable'
            analysis['reason'] = f'缓存高度可靠 ({reliability_score:.1%})'
        elif reliability_score >= 0.8:
            analysis['recommendation'] = 'incremental_check'
            analysis['reason'] = f'缓存基本可靠 ({reliability_score:.1%})，建议增量检查'
        else:
            analysis['recommendation'] = 'full_scan'
            analysis['reason'] = f'缓存可靠性低 ({reliability_score:.1%})，建议完整扫描'
        
        return analysis 