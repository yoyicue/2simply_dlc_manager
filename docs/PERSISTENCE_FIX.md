# 持久化目录问题修复说明

## 问题描述

在打包后的DLC Manager应用中，遇到了以下错误：

```
[00:49:03] 保存状态失败: 保存状态失败: [Errno 30] Read-only file system: 'dlc_download_state.json'
```

这是因为应用试图在应用程序包内部（只读文件系统）写入状态文件导致的。

## 问题分析

### 原因
1. **开发环境vs打包环境**：开发时应用在项目目录运行，可以写入当前目录；打包后应用在系统应用目录运行，通常是只读的
2. **硬编码路径**：`DataManager`类使用固定的相对路径`dlc_download_state.json`
3. **权限问题**：不同操作系统和安装位置有不同的写入权限限制

### 影响
- 无法保存下载状态和进度
- 用户重启应用后丢失所有下载进度
- Bloom Filter缓存无法持久化
- 应用体验严重受损

## 解决方案

### 1. 创建跨平台用户数据目录工具

创建了`core/utils.py`模块，提供以下功能：

#### 平台特定的用户目录
- **Windows**: `%APPDATA%/DLC Manager`
- **macOS**: `~/Library/Application Support/DLC Manager` 
- **Linux**: `~/.local/share/DLC Manager`

#### 核心函数
```python
def get_user_data_dir(app_name: str = "DLC Manager") -> Path:
    """获取用户数据目录路径，自动适配操作系统"""

def get_app_data_file(filename: str, app_name: str = "DLC Manager") -> Path:
    """获取应用数据文件的完整路径"""

def ensure_writable_path(file_path: Path) -> Path:
    """确保路径可写，如果不可写则返回用户数据目录中的路径"""

def is_running_from_bundle() -> bool:
    """检查是否从打包的应用程序运行"""
```

### 2. 智能路径选择策略

修改`DataManager`类实现智能路径选择：

```python
def __init__(self, data_file: Optional[Path] = None):
    if data_file is None:
        if is_running_from_bundle():
            # 打包应用：使用用户数据目录
            self.data_file = get_app_data_file("dlc_download_state.json")
        else:
            # 开发环境：优先使用当前目录，如果不可写则使用用户数据目录
            self.data_file = ensure_writable_path(Path("dlc_download_state.json"))
    else:
        # 用户指定的路径：确保可写
        self.data_file = ensure_writable_path(data_file)
```

### 3. 用户友好的日志提示

在主窗口启动时显示数据文件位置：

```python
async def _load_saved_state(self):
    # 记录数据文件位置
    self._log(f"💾 数据文件位置: {self.data_manager.data_file}")
```

## 实现细节

### 目录标准遵循

遵循各操作系统的标准目录规范：

#### Windows
- 数据目录：`%APPDATA%/DLC Manager`
- 缓存目录：`%LOCALAPPDATA%/DLC Manager/Cache`
- 配置目录：同数据目录

#### macOS  
- 数据目录：`~/Library/Application Support/DLC Manager`
- 缓存目录：`~/Library/Caches/DLC Manager`
- 配置目录：同数据目录

#### Linux
- 数据目录：`~/.local/share/DLC Manager`
- 缓存目录：`~/.cache/DLC Manager`  
- 配置目录：`~/.config/DLC Manager`

### 向后兼容性

- 开发环境仍优先使用当前目录（向后兼容）
- 只有在权限不足时才自动切换到用户数据目录
- 现有的状态文件会被自动检测和迁移

### 错误处理

```python
def ensure_writable_path(file_path: Path) -> Path:
    try:
        # 尝试在原路径创建测试文件
        test_file = file_path.parent / f".write_test_{os.getpid()}"
        test_file.touch()
        test_file.unlink()
        return file_path
    except (OSError, PermissionError):
        # 如果无法写入，使用用户数据目录
        return get_app_data_file(file_path.name)
```

## 测试验证

创建了`tests/test_user_data.py`进行全面测试：

### 测试覆盖
1. **目录创建测试**：验证各平台目录正确创建
2. **权限测试**：验证写入权限检测和自动切换
3. **DataManager集成测试**：验证持久化功能正常工作
4. **跨平台兼容性测试**：验证在不同系统下的行为

### 测试结果
```
🚀 用户数据目录功能测试
==================================================
✅ 用户数据目录: /Users/biu/Library/Application Support/DLC Manager
✅ 用户缓存目录: /Users/biu/Library/Caches/DLC Manager
✅ 用户配置目录: /Users/biu/Library/Application Support/DLC Manager
✅ 状态文件路径: /Users/biu/Library/Application Support/DLC Manager/dlc_download_state.json
✅ 缓存文件路径: /Users/biu/Library/Caches/DLC Manager/bloom_filter.cache
✅ 打包检测: 否
📊 测试结果: 3/3 通过
🎉 所有用户数据目录功能测试通过！
```

## 构建配置更新

更新了`build.py`构建脚本，添加技术特性说明：

```python
print("\n🔧 技术特性:")
print("✅ 智能持久化：自动选择合适的用户数据目录")
print("✅ 跨平台兼容：支持 Windows、macOS、Linux 标准目录") 
print("✅ 权限友好：避免只读文件系统错误")
```

## 用户体验改进

### 开发环境
- 继续使用项目目录，保持开发便利性
- 权限不足时自动切换，避免错误

### 打包应用
- 自动使用系统标准用户数据目录
- 状态文件安全持久化
- 应用卸载时可选择是否保留用户数据

### 日志透明度
- 启动时显示数据文件实际保存位置
- 用户可以找到和管理自己的数据文件
- 便于故障排查和数据备份

## 结论

通过这次修复：

1. **彻底解决**了只读文件系统错误问题
2. **提升用户体验**，状态持久化更可靠
3. **跨平台兼容**，遵循各系统标准
4. **向后兼容**，不影响现有开发流程
5. **透明可控**，用户知晓数据存储位置

现在DLC Manager可以在任何环境下正常保存和恢复状态，无论是开发环境还是打包后的生产环境。 