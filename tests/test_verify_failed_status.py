#!/usr/bin/env python3
"""
测试新的"验证失败"状态功能
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent.parent))

from core import FileItem, DownloadStatus, MD5VerifyStatus


def test_verify_failed_status():
    """测试验证失败状态的功能"""
    print("🧪 测试验证失败状态功能...")
    
    # 创建测试文件项
    test_item = FileItem(
        filename="test_file.json",
        md5="abcd1234567890abcd1234567890abcd"
    )
    
    # 初始状态
    print(f"初始状态: {test_item.status.value}")
    print(f"初始MD5验证状态: {test_item.md5_verify_status.value}")
    
    # 模拟下载完成
    test_item.status = DownloadStatus.COMPLETED
    print(f"下载完成后状态: {test_item.status.value}")
    
    # 模拟MD5验证失败
    test_item.mark_md5_verified("wrong_hash", False)
    test_item.status = DownloadStatus.VERIFY_FAILED
    test_item.error_message = "MD5哈希值不匹配"
    
    print(f"验证失败后状态: {test_item.status.value}")
    print(f"验证失败后MD5状态: {test_item.md5_verify_status.value}")
    print(f"错误信息: {test_item.error_message}")
    
    # 模拟重新下载成功
    fake_path = Path("test_file.json")
    test_item.mark_completed(fake_path)
    
    print(f"重新下载后状态: {test_item.status.value}")
    print(f"重新下载后MD5状态: {test_item.md5_verify_status.value}")
    
    # 验证状态枚举
    print("\n📋 所有可用的下载状态:")
    for status in DownloadStatus:
        print(f"  - {status.value}")
    
    print("\n✅ 验证失败状态功能测试完成!")


if __name__ == "__main__":
    test_verify_failed_status() 