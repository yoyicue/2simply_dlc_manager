"""
轻量级Bloom Filter实现 - 阶段二性能优化
用于快速过滤已存在文件，减少磁盘I/O操作
"""
import hashlib
import math
from typing import Set, List


class BloomFilter:
    """
    轻量级Bloom Filter实现
    
    针对DLC文件检查优化：
    - 预期5万文件，1%误判率
    - 内存占用约200KB
    - O(1)查询性能
    """
    
    def __init__(self, expected_items: int = 50000, false_positive_rate: float = 0.01):
        """
        初始化Bloom Filter
        
        Args:
            expected_items: 预期文件数量
            false_positive_rate: 误判率（默认1%）
        """
        self.expected_items = expected_items
        self.false_positive_rate = false_positive_rate
        
        # 计算最优参数
        self.bit_array_size = self._calculate_bit_array_size()
        self.hash_functions_count = self._calculate_hash_functions_count()
        
        # 初始化位数组
        self.bit_array = bytearray(math.ceil(self.bit_array_size / 8))
        self.items_count = 0
        
    def _calculate_bit_array_size(self) -> int:
        """计算位数组大小"""
        # m = -(n * ln(p)) / (ln(2))^2
        size = -(self.expected_items * math.log(self.false_positive_rate)) / (math.log(2) ** 2)
        return int(math.ceil(size))
    
    def _calculate_hash_functions_count(self) -> int:
        """计算哈希函数数量"""
        # k = (m / n) * ln(2)
        count = (self.bit_array_size / self.expected_items) * math.log(2)
        return int(math.ceil(count))
    
    def _hash(self, item: str, seed: int) -> int:
        """生成哈希值"""
        # 使用MD5+seed生成不同的哈希值
        hash_input = f"{item}:{seed}".encode('utf-8')
        hash_digest = hashlib.md5(hash_input).hexdigest()
        return int(hash_digest[:8], 16) % self.bit_array_size
    
    def add(self, item: str):
        """添加项目到Bloom Filter"""
        for i in range(self.hash_functions_count):
            bit_index = self._hash(item, i)
            byte_index = bit_index // 8
            bit_offset = bit_index % 8
            self.bit_array[byte_index] |= (1 << bit_offset)
        
        self.items_count += 1
    
    def __contains__(self, item: str) -> bool:
        """检查项目是否可能存在"""
        for i in range(self.hash_functions_count):
            bit_index = self._hash(item, i)
            byte_index = bit_index // 8
            bit_offset = bit_index % 8
            
            if not (self.bit_array[byte_index] & (1 << bit_offset)):
                return False  # 确定不存在
        
        return True  # 可能存在（也可能是误判）
    
    def add_multiple(self, items: List[str]):
        """批量添加项目"""
        for item in items:
            self.add(item)
    
    def get_info(self) -> dict:
        """获取Bloom Filter信息"""
        memory_kb = len(self.bit_array) / 1024
        actual_false_positive = self._estimate_false_positive_rate()
        
        return {
            'expected_items': self.expected_items,
            'actual_items': self.items_count,
            'bit_array_size': self.bit_array_size,
            'hash_functions': self.hash_functions_count,
            'memory_usage_kb': round(memory_kb, 2),
            'target_false_positive': self.false_positive_rate,
            'estimated_false_positive': round(actual_false_positive, 4),
            'efficiency': round((1 - actual_false_positive) * 100, 2)
        }
    
    def _estimate_false_positive_rate(self) -> float:
        """估算当前误判率"""
        if self.items_count == 0:
            return 0.0
        
        # 计算位数组中1的比例
        ones_count = 0
        for byte in self.bit_array:
            ones_count += bin(byte).count('1')
        
        ones_ratio = ones_count / self.bit_array_size
        
        # 估算误判率: (1 - e^(-kn/m))^k
        return (1 - math.exp(-self.hash_functions_count * self.items_count / self.bit_array_size)) ** self.hash_functions_count


class FileBloomFilter(BloomFilter):
    """
    专门用于文件名过滤的Bloom Filter
    """
    
    def __init__(self, expected_files: int = 50000):
        super().__init__(expected_files, false_positive_rate=0.01)
        self._built_from_cache = False
        self._cache_timestamp = None
    
    def build_from_completed_files(self, file_items: List) -> dict:
        """从已完成文件构建Bloom Filter"""
        from datetime import datetime
        
        # 重置Bloom Filter
        self.bit_array = bytearray(math.ceil(self.bit_array_size / 8))
        self.items_count = 0
        
        completed_files = []
        for item in file_items:
            # 导入这里避免循环导入
            from core.models import DownloadStatus
            if item.status == DownloadStatus.COMPLETED and item.disk_verified:
                completed_files.append(item.full_filename)
        
        # 批量添加已完成文件
        self.add_multiple(completed_files)
        
        self._built_from_cache = True
        self._cache_timestamp = datetime.now().isoformat()
        
        build_info = self.get_info()
        build_info.update({
            'completed_files_count': len(completed_files),
            'build_timestamp': self._cache_timestamp,
            'build_source': 'completed_files_cache'
        })
        
        return build_info
    
    def fast_pre_filter(self, file_items: List) -> tuple[List, List]:
        """
        快速预过滤文件列表
        
        Returns:
            (likely_existing_files, definitely_new_files)
        """
        likely_existing = []  # 可能存在（需要精确检查）
        definitely_new = []   # 肯定不存在（直接归类为需要下载）
        
        for item in file_items:
            if item.full_filename in self:
                likely_existing.append(item)  # 可能存在（包含误判）
            else:
                definitely_new.append(item)   # 肯定不存在
        
        return likely_existing, definitely_new
    
    def is_cache_valid(self) -> bool:
        """检查Bloom Filter缓存是否有效"""
        return self._built_from_cache and self.items_count > 0 