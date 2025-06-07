# -*- mode: python ; coding: utf-8 -*-
"""
DLC Manager PyInstaller 打包配置
使用方法: pyinstaller build.spec
"""

import os
import sys
from pathlib import Path

block_cipher = None

# 获取项目根目录
project_root = Path.cwd()

# 数据文件配置 - 只包含必要的资源
datas = [
    ('resources', 'resources'),
    ('core', 'core'),
    # 暂时排除dlc目录以加速构建，如需要可手动添加
    # ('dlc', 'dlc'),
]

# 隐藏导入模块 - 只包含必要的
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
    # 移除了标准库模块：json, pathlib
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
    excludes=[
        # GUI工具包
        'tkinter',
        'wx',
        'PyQt5',
        'PyQt6',
        # 科学计算库
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'sympy',
        'sklearn',
        # 图像处理
        'PIL.ImageTk',
        'PIL.ImageQt',
        'cv2',
        # 开发工具
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
        'setuptools',
        # 网络服务
        'flask',
        'django',
        'tornado',
        # 数据库
        'sqlite3',
        'pymongo',
        'sqlalchemy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# PYZ 阶段
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# EXE 阶段
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
    upx=False,  # 禁用UPX压缩以加速构建
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'resources' / 'icons' / 'app_icon.ico') if (project_root / 'resources' / 'icons' / 'app_icon.ico').exists() else None,
    version_file=None,
)

# 多平台配置
# macOS App 配置 (仅在 macOS 上生效)
if sys.platform == 'darwin':
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