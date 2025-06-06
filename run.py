#!/usr/bin/env python3
"""
DLC Manager 启动脚本
"""
import subprocess
import sys
from pathlib import Path

def main():
    """启动DLC Manager"""
    script_dir = Path(__file__).parent
    main_script = script_dir / "main.py"
    
    if not main_script.exists():
        print("错误: 找不到main.py文件")
        sys.exit(1)
    
    print("🚀 正在启动 DLC Manager...")
    print("📁 工作目录:", script_dir)
    print("🎯 主程序:", main_script)
    print("-" * 50)
    
    try:
        # 使用当前Python解释器运行主程序
        subprocess.run([sys.executable, str(main_script)], cwd=script_dir)
    except KeyboardInterrupt:
        print("\n👋 程序已退出")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 