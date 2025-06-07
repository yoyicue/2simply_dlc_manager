#!/usr/bin/env python3
"""
DLC Manager 测试运行器
运行所有测试并生成汇总报告
"""

import sys
import subprocess
from pathlib import Path

def run_test_file(test_file: Path) -> bool:
    """运行单个测试文件"""
    print(f"\n{'='*60}")
    print(f"🧪 运行测试: {test_file.name}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            [sys.executable, str(test_file)],
            capture_output=True,
            text=True,
            cwd=test_file.parent.parent  # 在项目根目录运行
        )
        
        # 打印输出
        print(result.stdout)
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ 运行测试失败: {e}")
        return False

def main():
    """主函数"""
    print("🚀 DLC Manager 测试套件")
    print("="*60)
    
    tests_dir = Path(__file__).parent
    
    # 查找所有测试文件
    test_files = [
        tests_dir / "test_core.py",
        tests_dir / "test_fix.py",
        tests_dir / "test_download.py",
        tests_dir / "test_asyncio.py",
        tests_dir / "test_user_data.py"
    ]
    
    # 过滤存在的测试文件
    existing_tests = [f for f in test_files if f.exists()]
    
    if not existing_tests:
        print("❌ 没有找到测试文件！")
        return 1
    
    print(f"📋 发现 {len(existing_tests)} 个测试文件:")
    for test_file in existing_tests:
        print(f"   - {test_file.name}")
    
    # 运行所有测试
    results = {}
    for test_file in existing_tests:
        results[test_file.name] = run_test_file(test_file)
    
    # 汇总结果
    print(f"\n{'='*60}")
    print("📊 测试结果汇总")
    print(f"{'='*60}")
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, success in results.items():
        status = "✅ 通过" if success else "❌ 失败"
        print(f"   {test_name}: {status}")
    
    print(f"\n🎯 总体结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！应用程序已准备就绪。")
        print("\n💡 运行 'python main.py' 启动应用程序")
        return 0
    else:
        print("❌ 部分测试失败，请检查上述错误信息")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 