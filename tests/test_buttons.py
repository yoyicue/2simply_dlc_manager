#!/usr/bin/env python3
"""
测试选择按钮功能
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.models import FileItem, DownloadStatus
from ui.file_table_model import FileTableModel

def test_check_by_status():
    """测试按状态选择功能"""
    print("=== 测试按状态选择功能 ===")
    
    # 创建测试数据
    file_items = [
        FileItem("file1.txt", "md5_1", DownloadStatus.PENDING),
        FileItem("file2.txt", "md5_2", DownloadStatus.FAILED),
        FileItem("file3.txt", "md5_3", DownloadStatus.COMPLETED),
        FileItem("file4.txt", "md5_4", DownloadStatus.PENDING),
        FileItem("file5.txt", "md5_5", DownloadStatus.FAILED),
    ]
    
    # 创建模型
    model = FileTableModel()
    model.set_file_items(file_items)
    
    print(f"总文件数: {len(file_items)}")
    print(f"初始选中数: {len(model.get_checked_items())}")
    
    # 清除所有选择
    model.check_all(False)
    print(f"清除后选中数: {len(model.get_checked_items())}")
    
    # 测试选择失败的文件
    print("\n--- 测试选择失败文件 ---")
    model.check_by_status(DownloadStatus.FAILED)
    checked_items = model.get_checked_items()
    print(f"选择失败文件后的选中数: {len(checked_items)}")
    
    failed_files = [item.filename for item in checked_items if item.status == DownloadStatus.FAILED]
    print(f"选中的失败文件: {failed_files}")
    
    # 测试选择待下载的文件
    print("\n--- 测试选择待下载文件 ---")
    model.check_all(False)  # 先清除
    model.check_by_status(DownloadStatus.PENDING)
    checked_items = model.get_checked_items()
    print(f"选择待下载文件后的选中数: {len(checked_items)}")
    
    pending_files = [item.filename for item in checked_items if item.status == DownloadStatus.PENDING]
    print(f"选中的待下载文件: {pending_files}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_check_by_status() 