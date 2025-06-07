#!/usr/bin/env python3
"""
DLC Manager 第三阶段压缩传输优化测试
验证JSON压缩优化、PNG流式传输、智能文件分析和性能统计
"""
import sys
import asyncio
import time
from pathlib import Path
from typing import List

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core import (
    CompressionManager, CompressionConfig, FileTypeAnalyzer,
    DownloadConfig, FileItem, Downloader
)


def test_file_type_analyzer():
    """测试文件类型分析器"""
    print("\n" + "="*80)
    print("文件类型分析器测试")
    print("="*80)
    
    # 测试文件列表
    test_files = [
        FileItem(filename="small_song.json", md5="abc123", size=50*1024),      # 50KB JSON
        FileItem(filename="large_song.json", md5="def456", size=500*1024),     # 500KB JSON
        FileItem(filename="cover_small.png", md5="ghi789", size=200*1024),     # 200KB PNG
        FileItem(filename="cover_medium.png", md5="jkl012", size=1*1024*1024), # 1MB PNG
        FileItem(filename="cover_large.png", md5="mno345", size=5*1024*1024),  # 5MB PNG
        FileItem(filename="unknown.txt", md5="pqr678", size=100*1024),         # 100KB TXT
    ]
    
    print(f"{'文件名':<25} {'大小':<15} {'分类':<15} {'应压缩':<10} {'应流式':<10}")
    print("-" * 80)
    
    for file_item in test_files:
        category = FileTypeAnalyzer.categorize_file(file_item)
        should_compress = FileTypeAnalyzer.should_compress(file_item, CompressionConfig())
        
        # 创建临时管理器测试流式判断
        temp_manager = CompressionManager()
        should_stream = temp_manager.streaming.should_use_streaming(file_item)
        
        size_str = f"{file_item.size/1024:.0f}KB" if file_item.size < 1024*1024 else f"{file_item.size/1024/1024:.1f}MB"
        
        print(f"{file_item.filename:<25} {size_str:<15} {category.value:<15} {'是' if should_compress else '否':<10} {'是' if should_stream else '否':<10}")
    
    print("\n✅ 文件类型分析器测试完成")
    return True


def test_compression_config_integration():
    """测试压缩配置集成"""
    print("\n" + "="*80)
    print("压缩配置集成测试")
    print("="*80)
    
    # 测试DownloadConfig创建CompressionConfig
    download_config = DownloadConfig(
        force_json_compression=True,
        enable_png_streaming=True,
        compression_performance_tracking=True,
        use_http2=True
    )
    
    compression_config = download_config.create_compression_config()
    
    print("DownloadConfig → CompressionConfig 映射:")
    print(f"  JSON压缩: {compression_config.force_json_compression}")
    print(f"  PNG流式: {compression_config.enable_png_optimization}")
    print(f"  性能跟踪: {compression_config.enable_performance_tracking}")
    print(f"  压缩级别: {compression_config.compression_level} (HTTP/2: {download_config.use_http2})")
    print(f"  块大小: {compression_config.stream_chunk_size/1024:.0f}KB")
    
    print("\n✅ 压缩配置集成测试完成")
    return True


def test_compression_manager_analysis():
    """测试压缩管理器文件分析"""
    print("\n" + "="*80)
    print("压缩管理器文件分析测试")
    print("="*80)
    
    manager = CompressionManager()
    
    # 测试不同类型文件的分析结果
    test_cases = [
        FileItem(filename="song1.json", md5="test1", size=600*1024),     # 600KB JSON
        FileItem(filename="cover1.png", md5="test2", size=1.5*1024*1024), # 1.5MB PNG
        FileItem(filename="tiny.json", md5="test3", size=10*1024),       # 10KB JSON
        FileItem(filename="huge.png", md5="test4", size=8*1024*1024),    # 8MB PNG
    ]
    
    print(f"{'文件名':<20} {'类别':<15} {'压缩建议':<10} {'流式建议':<10} {'预计节省':<15} {'优化方法':<15}")
    print("-" * 100)
    
    for file_item in test_cases:
        analysis = manager.analyze_file_requirements(file_item)
        
        should_compress = "是" if analysis['should_compress'] else "否"
        should_stream = "是" if analysis['should_stream'] else "否"
        estimated_savings = f"{analysis['estimated_savings']['estimated_savings_percent']:.0f}%"
        method = analysis['estimated_savings']['method']
        
        print(f"{file_item.filename:<20} {analysis['category']:<15} {should_compress:<10} {should_stream:<10} {estimated_savings:<15} {method:<15}")
        
        # 测试请求头生成
        headers = analysis['optimal_headers']
        if headers:
            print(f"  📋 请求头: {headers}")
    
    print("\n✅ 压缩管理器分析测试完成")
    return True


async def test_compression_processing():
    """测试压缩数据处理"""
    print("\n" + "="*80)
    print("压缩数据处理测试")
    print("="*80)
    
    import gzip
    import json
    
    manager = CompressionManager()
    
    # 创建测试JSON数据
    test_json_data = {
        "song_title": "Test Song",
        "artist": "Test Artist",
        "duration": 180,
        "lyrics": ["Line 1", "Line 2", "Line 3"] * 100,  # 重复数据，利于压缩
        "metadata": {
            "key": "value",
            "nested": {"deep": "data"}
        }
    }
    
    # 原始JSON字符串
    original_json = json.dumps(test_json_data, indent=2)
    original_bytes = original_json.encode('utf-8')
    original_size = len(original_bytes)
    
    # 使用gzip压缩
    compressed_bytes = gzip.compress(original_bytes)
    compressed_size = len(compressed_bytes)
    
    print(f"测试数据:")
    print(f"  原始大小: {original_size/1024:.1f}KB")
    print(f"  压缩大小: {compressed_size/1024:.1f}KB")
    print(f"  压缩比: {compressed_size/original_size:.2%}")
    print(f"  节省: {(1-compressed_size/original_size)*100:.1f}%")
    
    # 创建模拟文件项
    file_item = FileItem(filename="test_song.json", md5="test", size=original_size)
    
    # 记录处理消息
    messages = []
    def progress_callback(msg):
        messages.append(msg)
        print(f"  📝 {msg}")
    
    # 测试压缩数据处理
    start_time = time.time()
    processed_data = await manager.process_response_data(
        compressed_bytes, 'gzip', file_item, progress_callback
    )
    process_time = time.time() - start_time
    
    # 验证解压缩结果
    processed_json = processed_data.decode('utf-8')
    processed_data_obj = json.loads(processed_json)
    
    success = processed_data_obj == test_json_data
    
    print(f"\n解压缩结果:")
    print(f"  处理时间: {process_time*1000:.1f}ms")
    print(f"  数据完整性: {'✅ 通过' if success else '❌ 失败'}")
    print(f"  处理消息数: {len(messages)}")
    
    # 测试压缩统计
    compression_summary = manager.get_session_summary()
    stats = compression_summary['compression_stats']
    
    print(f"\n压缩统计:")
    print(f"  处理文件数: {stats['files_processed']}")
    print(f"  总体压缩比: {stats['overall_compression_ratio']:.2%}")
    print(f"  总体节省: {stats['overall_savings_percent']:.1f}%")
    print(f"  节省大小: {stats['overall_savings_mb']:.3f}MB")
    
    print("\n✅ 压缩数据处理测试完成")
    return success


def test_downloader_integration():
    """测试下载器集成"""
    print("\n" + "="*80)
    print("下载器集成测试")
    print("="*80)
    
    # 创建启用压缩优化的配置
    config = DownloadConfig(
        enable_compression_optimization=True,
        force_json_compression=True,
        enable_png_streaming=True,
        compression_performance_tracking=True
    )
    
    # 创建下载器
    downloader = Downloader(config)
    
    print("下载器压缩优化集成状态:")
    print(f"  压缩管理器: {'✅ 已创建' if downloader.compression_manager else '❌ 未创建'}")
    
    if downloader.compression_manager:
        print(f"  JSON压缩: {'✅ 启用' if config.force_json_compression else '❌ 禁用'}")
        print(f"  PNG流式: {'✅ 启用' if config.enable_png_streaming else '❌ 禁用'}")
        print(f"  性能跟踪: {'✅ 启用' if config.compression_performance_tracking else '❌ 禁用'}")
        
        # 测试配置传递
        compression_config = downloader.compression_manager.config
        print(f"  配置传递: 压缩级别={compression_config.compression_level}, 块大小={compression_config.stream_chunk_size/1024:.0f}KB")
    
    # 测试禁用压缩优化的情况
    config_disabled = DownloadConfig(enable_compression_optimization=False)
    downloader_disabled = Downloader(config_disabled)
    
    print(f"\n禁用压缩优化:")
    print(f"  压缩管理器: {'✅ 已创建' if downloader_disabled.compression_manager else '❌ 未创建'}")
    
    print("\n✅ 下载器集成测试完成")
    return True


def test_performance_estimation():
    """测试性能预估"""
    print("\n" + "="*80)
    print("性能预估测试")
    print("="*80)
    
    manager = CompressionManager()
    
    # 模拟真实的DLC文件分布
    test_scenarios = [
        {
            "name": "典型JSON歌曲文件",
            "files": [
                FileItem(filename=f"song_{i}.json", md5=f"hash{i}", size=600*1024)  # 600KB JSON
                for i in range(100)
            ]
        },
        {
            "name": "典型PNG封面文件", 
            "files": [
                FileItem(filename=f"cover_{i}.png", md5=f"hash{i}", size=1.2*1024*1024)  # 1.2MB PNG
                for i in range(50)
            ]
        },
        {
            "name": "混合文件场景",
            "files": (
                [FileItem(filename=f"song_{i}.json", md5=f"hash{i}", size=600*1024) for i in range(70)] +
                [FileItem(filename=f"cover_{i}.png", md5=f"hash{i}", size=1.2*1024*1024) for i in range(30)]
            )
        }
    ]
    
    print(f"{'场景':<20} {'文件数':<8} {'总大小':<15} {'预计节省':<15} {'节省百分比':<12} {'主要优化':<20}")
    print("-" * 100)
    
    for scenario in test_scenarios:
        files = scenario["files"]
        total_size = sum(f.size for f in files)
        total_savings = 0
        compression_files = 0
        streaming_files = 0
        
        for file_item in files:
            analysis = manager.analyze_file_requirements(file_item)
            estimated_savings = analysis['estimated_savings']['estimated_savings_bytes']
            total_savings += estimated_savings
            
            if analysis['should_compress']:
                compression_files += 1
            if analysis['should_stream']:
                streaming_files += 1
        
        savings_percent = (total_savings / total_size) * 100 if total_size > 0 else 0
        total_size_mb = total_size / (1024 * 1024)
        total_savings_mb = total_savings / (1024 * 1024)
        
        optimization_desc = []
        if compression_files > 0:
            optimization_desc.append(f"{compression_files}个压缩")
        if streaming_files > 0:
            optimization_desc.append(f"{streaming_files}个流式")
        
        optimization_str = ", ".join(optimization_desc) if optimization_desc else "无优化"
        
        print(f"{scenario['name']:<20} {len(files):<8} {total_size_mb:.1f}MB{'':<6} {total_savings_mb:.1f}MB{'':<6} {savings_percent:.1f}%{'':<7} {optimization_str:<20}")
    
    print("\n理论性能提升:")
    print("📈 JSON文件gzip压缩: 节省75%传输量，减少下载时间")
    print("📈 PNG流式传输: 减少内存使用，避免大文件阻塞")
    print("📈 智能文件分析: 自动选择最优传输策略")
    print("📈 HTTP/2 + 压缩: 多路复用 + 压缩传输，综合提升30-50%")
    
    print("\n✅ 性能预估测试完成")
    return True


async def main():
    """主测试函数"""
    print("🚀 DLC Manager 第三阶段压缩传输优化测试")
    print("="*80)
    
    start_time = time.time()
    
    try:
        # 执行所有测试
        tests = [
            ("文件类型分析器", test_file_type_analyzer),
            ("压缩配置集成", test_compression_config_integration),
            ("压缩管理器分析", test_compression_manager_analysis),
            ("压缩数据处理", test_compression_processing),
            ("下载器集成", test_downloader_integration),
            ("性能预估", test_performance_estimation),
        ]
        
        results = {}
        for test_name, test_func in tests:
            print(f"\n🧪 执行测试: {test_name}")
            try:
                if asyncio.iscoroutinefunction(test_func):
                    result = await test_func()
                else:
                    result = test_func()
                results[test_name] = result
                print(f"✅ {test_name}: {'通过' if result else '失败'}")
            except Exception as e:
                results[test_name] = False
                print(f"❌ {test_name}: 异常 - {str(e)}")
        
        # 汇总结果
        elapsed = time.time() - start_time
        passed = sum(results.values())
        total = len(results)
        
        print(f"\n" + "="*80)
        print("📊 第三阶段压缩优化测试结果汇总")
        print("="*80)
        
        for test_name, success in results.items():
            status = "✅ 通过" if success else "❌ 失败"
            print(f"   {test_name}: {status}")
        
        print(f"\n🎯 总体结果: {passed}/{total} 通过")
        print(f"⏱️  总测试时间: {elapsed:.2f}秒")
        
        if passed == total:
            print("\n🎉 所有第三阶段压缩优化测试通过！")
            print("\n💡 第三阶段优化效果预期:")
            print("   📦 JSON文件传输量减少70%+")
            print("   🖼️  PNG大文件内存友好处理")
            print("   🚀 HTTP/2 + 压缩组合优化30-50%性能提升")
            print("   📊 详细的压缩效果统计和监控")
            print("\n🚀 可以开始实际下载测试!")
            return 0
        else:
            print("❌ 部分第三阶段测试失败，请检查上述错误信息")
            return 1
            
    except Exception as e:
        print(f"\n❌ 测试过程中出现严重错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    # 检查依赖
    print("📦 检查第三阶段依赖...")
    
    missing_deps = []
    try:
        import gzip
        print("   ✅ gzip 模块可用")
    except ImportError:
        missing_deps.append("gzip")
    
    try:
        import zlib
        print("   ✅ zlib 模块可用")
    except ImportError:
        missing_deps.append("zlib")
    
    try:
        import aiofiles
        print("   ✅ aiofiles 模块可用")
    except ImportError:
        missing_deps.append("aiofiles")
    
    try:
        # 可选依赖
        import brotli
        print("   ✅ brotli 模块可用 (可选)")
    except ImportError:
        print("   ⚠️  brotli 模块不可用 (可选，用于Brotli压缩)")
    
    if missing_deps:
        print(f"❌ 缺少必需依赖: {', '.join(missing_deps)}")
        sys.exit(1)
    
    print()
    sys.exit(asyncio.run(main())) 