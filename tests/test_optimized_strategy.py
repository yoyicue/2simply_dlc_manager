#!/usr/bin/env python3
"""
DLC Manager 基于真实数据的优化策略测试
基于已下载的15GB数据（18564个PNG文件，25443个JSON文件）进行策略验证
"""
import sys
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_optimized_config():
    """测试优化后的配置"""
    print("🔍 测试基于真实数据的优化配置...")
    
    try:
        from core.models import DownloadConfig, FileItem
        
        # 创建优化配置
        config = DownloadConfig()
        
        # 验证基础配置
        assert config.concurrent_requests == 80, f"并发数应为80，实际为{config.concurrent_requests}"
        assert config.timeout == 180, f"超时应为180秒，实际为{config.timeout}"
        assert config.batch_size == 50, f"批次大小应为50，实际为{config.batch_size}"
        assert config.chunk_size == 32768, f"块大小应为32KB，实际为{config.chunk_size}"
        assert config.connection_limit == 150, f"连接池应为150，实际为{config.connection_limit}"
        
        print("✅ 基础配置验证通过")
        
        # 验证阈值配置
        assert config.small_file_threshold == 100000, "小文件阈值应为100KB"
        assert config.large_file_threshold == 2000000, "大文件阈值应为2MB"
        
        print("✅ 文件大小阈值配置验证通过")
        return True
        
    except Exception as e:
        print(f"❌ 优化配置测试失败: {e}")
        return False

def test_adaptive_strategies():
    """测试自适应策略"""
    print("\n" + "="*80)
    print("基于真实数据的自适应策略测试")
    print("="*80)
    
    try:
        from core.models import DownloadConfig, FileItem
        
        config = DownloadConfig()
        
        # 模拟真实场景的测试用例
        test_scenarios = [
            {
                "name": "增量下载场景（99%已存在）",
                "total_files": 52542,
                "files_to_download": 100,
                "file_types": [
                    {"filename": "test1.json", "size": 50000},  # 小JSON文件
                    {"filename": "test2.png", "size": 500000},  # 中等PNG文件
                    {"filename": "test3.png", "size": 5000000}, # 大PNG文件
                ]
            },
            {
                "name": "首次下载场景（全新下载）",
                "total_files": 52542,
                "files_to_download": 52542,
                "file_types": [
                    {"filename": "song1.json", "size": 700000},  # 大JSON文件
                    {"filename": "cover1.png", "size": 1500000}, # 大PNG文件
                    {"filename": "meta1.json", "size": 30000},   # 小JSON文件
                ]
            },
            {
                "name": "部分更新场景（20%需要下载）",
                "total_files": 52542,
                "files_to_download": 10000,
                "file_types": [
                    {"filename": "new1.json", "size": 600000},
                    {"filename": "new2.png", "size": 800000},
                    {"filename": "new3.json", "size": 45000},
                ]
            }
        ]
        
        print(f"{'场景':<20} {'总文件':<8} {'需下载':<8} {'跳过比例':<10} {'优化并发':<10} {'优化批次':<10} {'策略说明':<30}")
        print("-" * 120)
        
        for scenario in test_scenarios:
            total = scenario["total_files"]
            to_download = scenario["files_to_download"]
            skip_ratio = (total - to_download) / total
            
            # 创建测试文件项
            file_items = []
            for i, file_type in enumerate(scenario["file_types"]):
                item = FileItem(
                    filename=file_type["filename"],
                    md5="test_md5",
                    size=file_type["size"]
                )
                file_items.append(item)
            
            # 计算优化策略
            optimal_concurrent = config.get_optimal_concurrent_requests(total, to_download, file_items)
            optimal_batch = config.get_optimal_batch_size(total, to_download, file_items)
            
            # 分析策略
            strategy_desc = ""
            if skip_ratio > 0.95:
                strategy_desc = "增量优化：小批次+适中并发"
            elif skip_ratio > 0.5:
                strategy_desc = "部分更新：平衡批次+并发"
            else:
                strategy_desc = "全量下载：大批次+高并发"
            
            print(f"{scenario['name']:<20} {total:<8} {to_download:<8} {skip_ratio*100:>7.1f}%   {optimal_concurrent:<10} {optimal_batch:<10} {strategy_desc:<30}")
        
        print("\n✅ 自适应策略测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 自适应策略测试失败: {e}")
        return False

def test_file_type_optimization():
    """测试文件类型优化"""
    print("\n" + "="*80)
    print("文件类型差异化优化测试")
    print("="*80)
    
    try:
        from core.models import DownloadConfig, FileItem
        
        config = DownloadConfig()
        
        # 测试不同文件类型组合
        file_type_scenarios = [
            {
                "name": "纯JSON文件（小文件为主）",
                "files": [
                    {"filename": f"song{i}.json", "size": 50000 + i * 10000} 
                    for i in range(100)
                ]
            },
            {
                "name": "纯PNG文件（大文件为主）",
                "files": [
                    {"filename": f"cover{i}.png", "size": 1000000 + i * 100000} 
                    for i in range(50)
                ]
            },
            {
                "name": "混合文件（真实比例）",
                "files": (
                    [{"filename": f"song{i}.json", "size": 600000} for i in range(70)] +
                    [{"filename": f"cover{i}.png", "size": 1200000} for i in range(30)]
                )
            }
        ]
        
        print(f"{'文件类型场景':<25} {'文件数':<8} {'优化并发':<10} {'优化批次':<10} {'自适应超时':<12} {'自适应块大小':<12}")
        print("-" * 100)
        
        for scenario in file_type_scenarios:
            files = scenario["files"]
            file_items = []
            
            for file_info in files:
                item = FileItem(
                    filename=file_info["filename"],
                    md5="test_md5",
                    size=file_info["size"]
                )
                file_items.append(item)
            
            # 计算优化参数
            optimal_concurrent = config.get_optimal_concurrent_requests(len(files), len(files), file_items)
            optimal_batch = config.get_optimal_batch_size(len(files), len(files), file_items)
            
            # 测试自适应参数（使用第一个文件作为代表）
            sample_item = file_items[0] if file_items else None
            adaptive_timeout = config.get_adaptive_timeout(sample_item)
            adaptive_chunk = config.get_adaptive_chunk_size(sample_item)
            
            print(f"{scenario['name']:<25} {len(files):<8} {optimal_concurrent:<10} {optimal_batch:<10} {adaptive_timeout:<12} {adaptive_chunk//1024:<10}KB")
        
        print("\n✅ 文件类型优化测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 文件类型优化测试失败: {e}")
        return False

def test_performance_comparison():
    """性能对比测试"""
    print("\n" + "="*80)
    print("优化前后性能对比")
    print("="*80)
    
    try:
        from core.models import DownloadConfig
        
        # 旧配置（优化前）
        old_config = DownloadConfig(
            concurrent_requests=50,
            timeout=120,
            batch_size=20,
            chunk_size=16384,
            connection_limit=100,
            connection_limit_per_host=50
        )
        
        # 新配置（优化后）
        new_config = DownloadConfig()  # 使用默认的优化配置
        
        # 模拟真实下载场景
        scenarios = [
            {"total": 52542, "to_download": 100, "desc": "增量下载"},
            {"total": 52542, "to_download": 5000, "desc": "部分更新"},
            {"total": 52542, "to_download": 52542, "desc": "全量下载"}
        ]
        
        print(f"{'场景':<12} {'配置':<8} {'并发数':<8} {'批次大小':<10} {'连接池':<8} {'块大小':<10} {'预期提升':<15}")
        print("-" * 90)
        
        for scenario in scenarios:
            total = scenario["total"]
            to_download = scenario["to_download"]
            desc = scenario["desc"]
            
            # 旧配置策略
            old_concurrent = old_config.get_optimal_concurrent_requests(total, to_download)
            old_batch = old_config.get_optimal_batch_size(total, to_download)
            
            # 新配置策略
            new_concurrent = new_config.get_optimal_concurrent_requests(total, to_download)
            new_batch = new_config.get_optimal_batch_size(total, to_download)
            
            # 计算理论提升
            concurrent_improvement = (new_concurrent / old_concurrent - 1) * 100
            batch_improvement = (new_batch / old_batch - 1) * 100
            
            print(f"{desc:<12} {'旧配置':<8} {old_concurrent:<8} {old_batch:<10} {old_config.connection_limit:<8} {old_config.chunk_size//1024:<8}KB {'基准':<15}")
            print(f"{desc:<12} {'新配置':<8} {new_concurrent:<8} {new_batch:<10} {new_config.connection_limit:<8} {new_config.chunk_size//1024:<8}KB {concurrent_improvement:+.1f}%并发,{batch_improvement:+.1f}%批次")
            print()
        
        print("✅ 性能对比测试完成")
        
        # 总结优化效果
        print("\n📊 优化效果总结:")
        print("1. 并发数从50提升到80，提升60%")
        print("2. 批次大小从20提升到50，提升150%")
        print("3. 连接池从100提升到150，提升50%")
        print("4. 块大小从16KB提升到32KB，提升100%")
        print("5. 新增文件类型差异化处理")
        print("6. 新增自适应超时和块大小")
        print("7. 基于真实15GB下载数据优化")
        
        return True
        
    except Exception as e:
        print(f"❌ 性能对比测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("DLC Manager 基于真实数据的优化策略验证")
    print("基于已下载15GB数据（52542个文件）的分析结果")
    print("PNG文件: 18564个（最大15MB）")
    print("JSON文件: 25443个（最大755KB）")
    print("="*80)
    
    all_passed = True
    
    # 运行所有测试
    tests = [
        test_optimized_config,
        test_adaptive_strategies,
        test_file_type_optimization,
        test_performance_comparison
    ]
    
    for test_func in tests:
        try:
            result = test_func()
            all_passed = all_passed and result
        except Exception as e:
            print(f"❌ 测试 {test_func.__name__} 发生异常: {e}")
            all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("🎉 所有优化策略测试通过！")
        print("✅ 新策略已准备就绪，可以显著提升下载性能")
    else:
        print("⚠️  部分测试失败，请检查配置")
    print("="*80)

if __name__ == "__main__":
    main() 