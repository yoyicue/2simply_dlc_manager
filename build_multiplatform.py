#!/usr/bin/env python3
"""
多平台构建脚本
支持 Windows、macOS、Linux 的自动化构建
"""

import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path


class MultiPlatformBuilder:
    """多平台构建器"""
    
    def __init__(self):
        self.platform = sys.platform
        self.arch = platform.machine()
        self.project_root = Path.cwd()
        
    def detect_platform(self):
        """检测当前平台"""
        platform_info = {
            'platform': self.platform,
            'arch': self.arch,
            'os_name': platform.system(),
            'os_version': platform.release(),
        }
        
        print("🔍 平台信息:")
        for key, value in platform_info.items():
            print(f"  {key}: {value}")
        
        return platform_info
    
    def check_dependencies(self):
        """检查依赖"""
        print("🔍 检查构建依赖...")
        
        # 检查Python版本
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        print(f"✅ Python版本: {python_version}")
        
        # 检查PyInstaller
        try:
            import PyInstaller
            print(f"✅ PyInstaller: {PyInstaller.__version__}")
        except ImportError:
            print("❌ PyInstaller 未安装")
            return False
        
        # 检查必要文件 (不包括dlc目录，因为它太大了~15GB)
        required_files = [
            "main.py",
            "requirements.txt",
            "resources/icons/app_icon.png",
            "core",  # 核心代码目录
        ]
        
        for file_path in required_files:
            if (self.project_root / file_path).exists():
                print(f"✅ 找到文件: {file_path}")
            else:
                print(f"❌ 缺少文件: {file_path}")
                return False
        
        return True
    
    def check_dlc_directory(self):
        """检查dlc目录并给出提示"""
        dlc_path = self.project_root / "dlc"
        if dlc_path.exists():
            try:
                # 检查dlc目录大小
                import subprocess
                result = subprocess.run(
                    ["du", "-sh", str(dlc_path)], 
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    size = result.stdout.split()[0]
                    print(f"⚠️  dlc目录大小: {size}")
                    print(f"💡 dlc目录已排除在构建包外，运行时程序会从此目录加载DLC文件")
                else:
                    print(f"⚠️  检测到dlc目录，已排除在构建包外")
            except:
                print(f"⚠️  检测到dlc目录，已排除在构建包外")
        else:
            print(f"📌 未检测到dlc目录 - 这是正常的，用户可以稍后添加DLC文件")
    
    def create_platform_spec(self):
        """为当前平台创建spec文件"""
        spec_content = self._get_base_spec()
        
        # 根据平台添加特定配置
        if self.platform == 'win32':
            spec_content += self._get_windows_config()
        elif self.platform == 'darwin':
            spec_content += self._get_macos_config()
        else:  # Linux
            spec_content += self._get_linux_config()
        
        # 写入spec文件
        spec_path = self.project_root / f"build_{self.platform}.spec"
        with open(spec_path, 'w', encoding='utf-8') as f:
            f.write(spec_content)
        
        print(f"✅ 创建平台专用spec文件: {spec_path}")
        return spec_path
    
    def _get_base_spec(self):
        """获取基础spec配置"""
        return '''# -*- mode: python ; coding: utf-8 -*-
"""
DLC Manager 多平台构建配置
"""

import os
import sys
from pathlib import Path

# 获取项目根目录
project_root = Path.cwd()

# 数据文件配置 - 只包含必要的资源，排除大文件目录
datas = [
    ('resources', 'resources'),
    ('core', 'core'),
    # 注意：dlc目录包含大量数据文件(~15GB)，不应包含在构建包中
    # 用户需要单独下载或提供dlc文件
]

# 隐藏导入模块
hiddenimports = [
    'qasync',
    'aiofiles',
    'aiohttp',
    'rich',
    'PySide6.QtCore',
    'PySide6.QtWidgets',
    'PySide6.QtGui',
    'PySide6.QtNetwork',
    'asyncio',
    'threading',
    'concurrent.futures',
]

# 排除模块
excludes = [
    'tkinter', 'wx', 'PyQt5', 'PyQt6',
    'matplotlib', 'numpy', 'scipy', 'pandas',
    'IPython', 'jupyter', 'pytest',
]

# 分析阶段
a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

'''
    
    def _get_windows_config(self):
        """Windows特定配置"""
        return '''
# Windows EXE配置
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DLC Manager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'resources' / 'icons' / 'app_icon.ico') if (project_root / 'resources' / 'icons' / 'app_icon.ico').exists() else None,
    version_file=None,
)
'''
    
    def _get_macos_config(self):
        """macOS特定配置"""
        return '''
# macOS EXE配置
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DLC Manager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'resources' / 'icons' / 'app_icon.ico') if (project_root / 'resources' / 'icons' / 'app_icon.ico').exists() else None,
    version_file=None,
)

# macOS App Bundle配置
# 优先使用 .icns 文件，其次使用 .ico 文件
icon_path = None
if (project_root / 'resources' / 'icons' / 'app_icon.icns').exists():
    icon_path = str(project_root / 'resources' / 'icons' / 'app_icon.icns')
elif (project_root / 'resources' / 'icons' / 'app_icon.ico').exists():
    icon_path = str(project_root / 'resources' / 'icons' / 'app_icon.ico')

app = BUNDLE(
    exe,
    name='DLC Manager.app',
    icon=icon_path,
    bundle_identifier='com.dlcmanager.app',
    info_plist={
        'CFBundleDisplayName': 'DLC Manager',
        'CFBundleGetInfoString': 'DLC Manager v1.0.0',
        'CFBundleIdentifier': 'com.dlcmanager.app',
        'CFBundleInfoDictionaryVersion': '6.0',
        'CFBundleName': 'DLC Manager',
        'CFBundlePackageType': 'APPL',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
    },
)
'''
    
    def _get_linux_config(self):
        """Linux特定配置"""
        return '''
# Linux可执行文件配置
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DLC Manager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'resources' / 'icons' / 'app_icon.ico') if (project_root / 'resources' / 'icons' / 'app_icon.ico').exists() else None,
    version_file=None,
)
'''
    
    def run_command(self, cmd, description=""):
        """运行命令"""
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
    
    def clean_build(self):
        """清理构建目录"""
        print("🧹 清理构建目录...")
        
        dirs_to_clean = ["build", "dist"]
        for dir_name in dirs_to_clean:
            if Path(dir_name).exists():
                shutil.rmtree(dir_name)
                print(f"✅ 清理目录: {dir_name}")
    
    def build(self):
        """执行构建"""
        print(f"🔨 开始构建 ({self.platform})...")
        
        # 创建平台专用spec文件
        spec_path = self.create_platform_spec()
        
        # 运行PyInstaller
        cmd = f"pyinstaller {spec_path} --clean --noconfirm"
        success = self.run_command(cmd, f"使用PyInstaller构建 ({self.platform})")
        
        # 清理spec文件
        if spec_path.exists():
            spec_path.unlink()
            print(f"🧹 清理临时spec文件: {spec_path}")
        
        return success
    
    def verify_build(self):
        """验证构建结果"""
        print("🔍 验证构建结果...")
        
        if self.platform == 'darwin':
            app_path = Path("dist/DLC Manager.app")
            exe_path = app_path / "Contents/MacOS/DLC Manager"
        elif self.platform == 'win32':
            exe_path = Path("dist/DLC Manager.exe")
        else:  # Linux
            exe_path = Path("dist/DLC Manager")
        
        if exe_path.exists():
            size = exe_path.stat().st_size / (1024 * 1024)  # MB
            print(f"✅ 构建成功: {exe_path} ({size:.1f} MB)")
            return True
        else:
            print(f"❌ 构建失败: 未找到 {exe_path}")
            return False
    
    def create_distribution(self):
        """创建分发包"""
        print("📦 创建分发包...")
        
        import zipfile
        
        # 确定分发包名称
        platform_name = {
            'win32': 'Windows',
            'darwin': 'macOS',
            'linux': 'Linux'
        }.get(self.platform, self.platform)
        
        zip_name = f"DLC_Manager_v1.0.0_{platform_name}_{self.arch}.zip"
        zip_path = Path("dist") / zip_name
        
        # 创建压缩包
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            dist_dir = Path("dist")
            for file_path in dist_dir.rglob("*"):
                if file_path.name != zip_name and file_path.is_file():
                    arcname = file_path.relative_to(dist_dir)
                    zipf.write(file_path, arcname)
        
        print(f"✅ 分发包已创建: {zip_path}")
        return zip_path


def main():
    """主函数"""
    print("🚀 DLC Manager 多平台构建器")
    print("=" * 50)
    
    builder = MultiPlatformBuilder()
    
    # 检测平台
    platform_info = builder.detect_platform()
    print()
    
    # 检查依赖
    if not builder.check_dependencies():
        print("❌ 依赖检查失败")
        sys.exit(1)
    print()
    
    # 检查DLC目录
    builder.check_dlc_directory()
    print()
    
    # 清理
    builder.clean_build()
    print()
    
    # 构建
    if not builder.build():
        print("❌ 构建失败")
        sys.exit(1)
    print()
    
    # 验证
    if not builder.verify_build():
        print("❌ 构建验证失败")
        sys.exit(1)
    print()
    
    # 创建分发包
    dist_path = builder.create_distribution()
    
    print("\n🎉 构建完成！")
    print("=" * 50)
    print(f"📁 输出目录: dist/")
    print(f"📦 分发包: {dist_path}")
    
    # 平台特定说明
    if platform_info['platform'] == 'darwin':
        print("🍎 macOS: 可以直接运行 DLC Manager.app")
    elif platform_info['platform'] == 'win32':
        print("🪟 Windows: 可以直接运行 DLC Manager.exe")
    else:
        print("🐧 Linux: 可以直接运行 DLC Manager")
    
    print("\n📋 重要说明:")
    print("• DLC文件未包含在构建包中（避免15GB+的巨大文件）")
    print("• 用户需要单独下载或提供DLC文件到程序运行目录")
    print("• 程序会在运行时从本地dlc目录加载DLC文件")


if __name__ == "__main__":
    main() 