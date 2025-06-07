# DLC Manager 构建和分发指南

## 🎯 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 一键构建
```bash
python build.py
```

### 3. 运行应用
- **macOS**: 双击 `dist/DLC Manager.app`
- **Windows**: 双击 `dist/DLC Manager.exe`
- **Linux**: 运行 `dist/DLC Manager`

## 📦 构建详情

### 核心组件说明

#### 1. 应用图标 (`resources/icons/`)
- `app_icon.png` - 通用PNG图标 (128x128)
- `app_icon.ico` - Windows ICO图标

#### 2. 安装脚本 (`setup.py`)
- 支持 `pip install` 安装
- 配置入口点和依赖
- 包含资源文件

#### 3. 打包配置 (`build.spec`)
- PyInstaller 配置文件
- 自动包含所有资源
- 支持 macOS App Bundle

#### 4. 异常处理 (`utils/exception_handler.py`)
- 全局异常捕获
- 用户友好的错误对话框
- 自动日志记录

#### 5. 关于对话框 (`ui/about_dialog.py`)
- 应用信息展示
- 系统信息查看
- 许可证信息

## 🔧 手动构建步骤

### 1. 准备环境
```bash
# 安装构建工具
pip install pyinstaller

# 检查必要文件
ls resources/icons/app_icon.png
ls build.spec
ls main.py
```

### 2. 清理旧构建
```bash
rm -rf build/ dist/ __pycache__/
find . -name "*.pyc" -delete
```

### 3. 执行构建
```bash
pyinstaller build.spec --clean --noconfirm
```

### 4. 验证结果
```bash
# macOS
ls -la "dist/DLC Manager.app"

# Windows/Linux
ls -la "dist/DLC Manager"*
```

## 📋 分发清单

### 必要文件
- ✅ 可执行文件或应用包
- ✅ 资源文件 (自动包含)
- ✅ 依赖库 (自动包含)

### 可选文件
- 📄 README.md (使用说明)
- 📄 LICENSE (许可证)
- 📄 CHANGELOG.md (更新日志)

## 🚀 分发方式

### 1. 直接分发
将 `dist/` 目录中的应用文件直接分发给用户

### 2. 压缩包分发
```bash
# 自动创建压缩包
python build.py  # 会自动创建 DLC_Manager_v1.0.0_*.zip

# 手动创建
cd dist/
zip -r DLC_Manager_v1.0.0.zip "DLC Manager"*
```

### 3. 安装包分发 (高级)
```bash
# 使用 setup.py 创建安装包
python setup.py sdist bdist_wheel

# 安装到系统
pip install dist/dlc-manager-1.0.0.tar.gz
```

## 🔍 故障排除

### 常见问题

#### 1. 图标不显示
- 检查 `resources/icons/app_icon.png` 是否存在
- 确保图标文件格式正确

#### 2. 资源文件缺失
- 检查 `build.spec` 中的 `datas` 配置
- 确保所有资源文件都在正确位置

#### 3. 依赖库错误
- 检查 `requirements.txt` 中的版本
- 使用虚拟环境避免冲突

#### 4. 启动失败
- 查看控制台错误信息
- 检查 `logs/` 目录中的日志文件

### 调试技巧

#### 1. 启用控制台输出
在 `build.spec` 中设置 `console=True`

#### 2. 查看详细错误
```bash
# 直接运行 Python 脚本
python main.py

# 查看 PyInstaller 详细输出
pyinstaller build.spec --clean --noconfirm --debug all
```

#### 3. 测试依赖
```bash
# 检查导入
python -c "import PySide6; print('PySide6 OK')"
python -c "import aiohttp; print('aiohttp OK')"
```

## 📈 版本管理

### 更新版本号
1. 修改 `setup.py` 中的 `version`
2. 修改 `build.spec` 中的版本信息
3. 修改 `ui/about_dialog.py` 中的版本显示
4. 更新 `build.py` 中的压缩包名称

### 发布流程
1. 更新版本号
2. 测试应用功能
3. 执行完整构建
4. 创建发布包
5. 编写更新日志

## 🎉 完成！

现在你的 DLC Manager 已经是一个完整的、可分发的 PyQt 应用了！

### 特性清单
- ✅ 专业的应用图标
- ✅ 完整的安装脚本
- ✅ 自动化打包配置
- ✅ 全局异常处理
- ✅ 关于对话框和版本信息
- ✅ 用户友好的菜单系统
- ✅ 自动化构建脚本
- ✅ 完整的分发包 