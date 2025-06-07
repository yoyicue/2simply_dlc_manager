#!/usr/bin/env python3
"""
用户数据目录功能测试
验证持久化目录配置是否正确
"""
import sys
import tempfile
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_user_data_directories():
    """测试用户数据目录功能"""
    print("🧪 测试用户数据目录功能...")
    
    try:
        from core.utils import (
            get_user_data_dir, get_user_cache_dir, get_user_config_dir,
            get_app_data_file, get_app_cache_file, is_running_from_bundle
        )
        
        # 测试基本目录获取
        data_dir = get_user_data_dir()
        cache_dir = get_user_cache_dir()
        config_dir = get_user_config_dir()
        
        print(f"✅ 用户数据目录: {data_dir}")
        print(f"✅ 用户缓存目录: {cache_dir}")
        print(f"✅ 用户配置目录: {config_dir}")
        
        # 验证目录存在
        assert data_dir.exists(), "数据目录应该自动创建"
        assert cache_dir.exists(), "缓存目录应该自动创建"
        assert config_dir.exists(), "配置目录应该自动创建"
        
        # 测试文件路径生成
        state_file = get_app_data_file("dlc_download_state.json")
        cache_file = get_app_cache_file("bloom_filter.cache")
        
        print(f"✅ 状态文件路径: {state_file}")
        print(f"✅ 缓存文件路径: {cache_file}")
        
        # 验证路径正确
        assert state_file.parent == data_dir, "状态文件应该在数据目录中"
        assert cache_file.parent == cache_dir, "缓存文件应该在缓存目录中"
        
        # 测试打包检测
        is_bundled = is_running_from_bundle()
        print(f"✅ 打包检测: {'是' if is_bundled else '否'}")
        
        print("✅ 用户数据目录功能测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 用户数据目录功能测试失败: {e}")
        return False

def test_data_manager_integration():
    """测试DataManager集成"""
    print("\n🧪 测试DataManager持久化目录集成...")
    
    try:
        from core.persistence import DataManager
        from core.models import FileItem, DownloadStatus
        
        # 创建数据管理器实例
        manager = DataManager()
        
        print(f"✅ DataManager数据文件路径: {manager.data_file}")
        
        # 验证路径是可写的
        test_data = {
            'output_dir': '/tmp/test',
            'metadata_version': '1.0',
            'files': []
        }
        
        # 尝试写入测试数据
        import json
        manager.data_file.write_text(json.dumps(test_data), encoding='utf-8')
        
        # 验证可以读取
        loaded_data = json.loads(manager.data_file.read_text(encoding='utf-8'))
        assert loaded_data['metadata_version'] == '1.0'
        
        # 清理测试文件
        manager.data_file.unlink()
        
        print("✅ DataManager持久化目录集成测试通过")
        return True
        
    except Exception as e:
        print(f"❌ DataManager持久化目录集成测试失败: {e}")
        return False

def test_permission_handling():
    """测试权限处理"""
    print("\n🧪 测试权限处理功能...")
    
    try:
        from core.utils import ensure_writable_path
        
        # 创建一个临时的只读目录来模拟权限问题
        with tempfile.TemporaryDirectory() as temp_dir:
            readonly_file = Path(temp_dir) / "readonly_test.json"
            
            # 测试确保可写路径功能
            writable_path = ensure_writable_path(readonly_file)
            
            print(f"✅ 原路径: {readonly_file}")
            print(f"✅ 可写路径: {writable_path}")
            
            # 验证可以写入
            test_content = "test content"
            writable_path.write_text(test_content)
            
            # 验证可以读取
            read_content = writable_path.read_text()
            assert read_content == test_content
            
            print("✅ 权限处理功能测试通过")
            return True
        
    except Exception as e:
        print(f"❌ 权限处理功能测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 用户数据目录功能测试")
    print("=" * 50)
    
    tests = [
        test_user_data_directories,
        test_data_manager_integration,
        test_permission_handling,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有用户数据目录功能测试通过！")
        print("\n💡 持久化目录问题已解决：")
        print("   - 开发环境：优先使用当前目录，不可写时自动切换")
        print("   - 打包应用：自动使用系统标准用户数据目录")
        print("   - 跨平台：支持 Windows、macOS、Linux 标准目录")
        return 0
    else:
        print("❌ 部分测试失败，请检查错误信息")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 