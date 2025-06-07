#!/usr/bin/env python3
"""
DLC Manager 安装脚本
"""

from setuptools import setup, find_packages
import os

# 读取 requirements.txt
def get_requirements():
    with open('requirements.txt', 'r', encoding='utf-8') as f:
        return [line.strip() for line in f.readlines() if line.strip() and not line.startswith('#')]

# 读取 README.md
def get_long_description():
    if os.path.exists('README.md'):
        with open('README.md', 'r', encoding='utf-8') as f:
            return f.read()
    return "DLC Manager - 现代化的 DLC 下载管理工具"

setup(
    name="dlc-manager",
    version="1.0.0",
    author="DLC Manager Team",
    author_email="",
    description="现代化的 DLC 下载管理工具",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    url="",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=get_requirements(),
    entry_points={
        'console_scripts': [
            'dlc-manager=main:main',
        ],
        'gui_scripts': [
            'dlc-manager-gui=main:main',
        ],
    },
    include_package_data=True,
    package_data={
        '': ['*.qss', '*.qrc'],
        'resources': ['*.qss', '*.qrc', 'icons/*'],
    },
    data_files=[
        ('resources', ['resources/style.qss', 'resources/resources.qrc']),
        ('resources/icons', ['resources/icons/app_icon.png', 'resources/icons/app_icon.ico']),
    ],
    keywords="dlc manager download qt gui",
    project_urls={
        "Bug Reports": "",
        "Source": "",
    },
) 