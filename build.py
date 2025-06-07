#!/usr/bin/env python3
"""
DLC Manager 构建脚本
自动化打包和分发流程
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def run_command(cmd, description=""):
    """运行命令并处理错误"""
    print(f"🔄 {description or cmd}")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 命令执行失败: {cmd}")
        print(f"错误输出: {e.stderr}")
        return False

def check_dependencies():
    """检查构建依赖"""
    print("🔍 检查构建依赖...")
    
    # 检查Python版本
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"✅ Python版本: {python_version}")
    
    # 检查 PyInstaller
    try:
        import PyInstaller
        print(f"✅ PyInstaller 已安装: {PyInstaller.__version__}")
    except ImportError:
        print("❌ PyInstaller 未安装，正在安装...")
        if not run_command("pip install pyinstaller", "安装 PyInstaller"):
            return False
    
    # 检查必要文件
    required_files = [
        "main.py",
        "build.spec",
        "resources/icons/app_icon.png",
        "resources/style.qss"
    ]
    
    for file_path in required_files:
        if not Path(file_path).exists():
            print(f"❌ 缺少必要文件: {file_path}")
            return False
        print(f"✅ 找到文件: {file_path}")
    
    # 检查DLC目录（提示用户）
    dlc_path = Path("dlc")
    if dlc_path.exists():
        print("💡 检测到dlc目录，已排除在构建包外（避免15GB+文件）")
    else:
        print("📌 未检测到dlc目录 - 用户可稍后添加DLC文件")
    
    return True

def clean_build():
    """清理构建目录"""
    print("🧹 清理构建目录...")
    
    dirs_to_clean = ["build", "dist", "__pycache__"]
    for dir_name in dirs_to_clean:
        if Path(dir_name).exists():
            shutil.rmtree(dir_name)
            print(f"✅ 清理目录: {dir_name}")
    
    # 清理 .pyc 文件
    for pyc_file in Path(".").rglob("*.pyc"):
        pyc_file.unlink()
    
    print("✅ 清理完成")

def build_app():
    """构建应用"""
    print("🔨 开始构建应用...")
    
    # 使用 PyInstaller 构建
    cmd = "pyinstaller build.spec --clean --noconfirm"
    if not run_command(cmd, "使用 PyInstaller 构建应用"):
        return False
    
    # macOS: 删除多余的独立可执行文件
    if sys.platform == "darwin":
        standalone_exe = Path("dist/DLC Manager")
        if standalone_exe.exists():
            standalone_exe.unlink()
            print("🗑️  已删除多余的独立可执行文件")
    
    print("✅ 应用构建完成")
    return True

def verify_build():
    """验证构建结果"""
    print("🔍 验证构建结果...")
    
    # 检查输出文件
    if sys.platform == "darwin":  # macOS
        app_path = Path("dist/DLC Manager.app")
        if app_path.exists():
            print(f"✅ macOS 应用包已创建: {app_path}")
            # 确认没有独立可执行文件
            standalone_exe = Path("dist/DLC Manager")
            if not standalone_exe.exists():
                print("✅ 已优化：仅生成 .app 文件")
            return True
    else:  # Windows/Linux
        exe_path = Path("dist/DLC Manager.exe" if sys.platform == "win32" else "dist/DLC Manager")
        if exe_path.exists():
            print(f"✅ 可执行文件已创建: {exe_path}")
            return True
    
    print("❌ 构建验证失败，未找到输出文件")
    return False

def create_installer():
    """创建分发包"""
    print("📦 创建分发包...")
    
    dist_dir = Path("dist")
    if not dist_dir.exists():
        print("❌ dist 目录不存在")
        return False
    
    # 创建压缩包
    import zipfile
    import platform
    
    # 更好的平台名称
    platform_name = {
        'win32': 'Windows',
        'darwin': 'macOS', 
        'linux': 'Linux'
    }.get(sys.platform, sys.platform)
    
    arch = platform.machine()
    zip_name = f"DLC_Manager_v1.0.0_{platform_name}_{arch}.zip"
    zip_path = Path("dist") / zip_name
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in dist_dir.rglob("*"):
            if file_path.name != zip_name and file_path.is_file():
                arcname = file_path.relative_to(dist_dir)
                zipf.write(file_path, arcname)
    
    file_size = zip_path.stat().st_size / (1024 * 1024)  # MB
    print(f"✅ 分发包已创建: {zip_path} ({file_size:.1f} MB)")
    return True

def main():
    """主函数"""
    print("🚀 DLC Manager 构建脚本")
    print("=" * 50)
    
    # 检查依赖
    if not check_dependencies():
        print("❌ 依赖检查失败")
        sys.exit(1)
    
    # 清理构建目录
    clean_build()
    
    # 构建应用
    if not build_app():
        print("❌ 应用构建失败")
        sys.exit(1)
    
    # 验证构建
    if not verify_build():
        print("❌ 构建验证失败")
        sys.exit(1)
    
    # 创建分发包
    create_installer()
    
    print("\n🎉 构建完成！")
    print("=" * 50)
    print("📁 输出目录: dist/")
    
    if sys.platform == "darwin":
        print("🍎 macOS 应用: dist/DLC Manager.app")
    else:
        exe_name = "DLC Manager.exe" if sys.platform == "win32" else "DLC Manager"
        print(f"💻 可执行文件: dist/{exe_name}")
    
    print("\n📋 使用说明:")
    print("1. 运行应用测试功能")
    print("2. 分发 dist/ 目录中的文件")
    if sys.platform == "darwin":
        print("3. 用户双击 .app 文件运行")
        print("💡 已优化：仅生成 .app 文件，减少混淆和文件大小")
    else:
        print("3. 用户可以直接运行可执行文件")

if __name__ == "__main__":
    main() 