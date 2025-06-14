![DLC Manager UI界面](https://raw.githubusercontent.com/yoyicue/2simply_dlc_manager/refs/heads/master/resources/ui.png)

# DLC Manager

一个使用 PySide6 的某应用程序的 DLC Songs 的乐谱下载管理工具，支持高效异步下载和可视化进度管理。

## ✨ 功能特性

### 核心下载功能
- 🚀 **高性能异步下载**：支持多达50个并发请求，智能批次处理
- 🔄 **智能断点续传**：支持大文件断点续传、网络中断恢复、完整性校验
- 📡 **压缩传输优化**：智能文件分析，JSON压缩优化（节省75%），PNG流式传输
- ✅ **文件完整性校验**：支持MD5等算法计算完整性，缓存机制优化
- 🎯 **智能跳过**：自动检测已存在文件，避免重复下载
- 🧠 **智能状态合并**：重新加载文件时自动diff，保留已完成的下载状态

### 用户体验
- 🎨 **现代化界面**：基于PySide6的响应式GUI，实时进度显示
- 📊 **状态管理**：直观显示文件状态和下载进度，支持验证失败状态
- 📈 **性能监控**：实时传输速度和压缩比统计

## 📋 系统要求

- **Python**: 3.8或更高版本
- **操作系统**: Windows、macOS、Linux
- **内存**: 建议4GB以上（处理大量文件时）

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 运行应用
```bash
python main.py
```

## 📁 项目结构

```
dlc_manager/
├── core/                      # 核心功能模块
│   ├── downloader.py         # 异步下载器
│   ├── models.py             # 数据模型
│   ├── persistence.py        # 状态持久化
│   ├── compression.py        # 压缩传输优化 
│   ├── resume.py             # 智能断点续传
│   └── network.py            # 网络层优化
├── ui/                        # 用户界面
│   ├── main_window.py        # 主窗口
│   ├── file_table_model.py   # 文件表格
│   └── about_dialog.py       # 关于对话框
├── resources/                 # 资源文件
│   ├── style.qss             # 界面样式
│   └── icons/                # 应用图标
├── tests/                     # 测试套件
├── utils/                     # 工具模块
├── main.py                   # 程序入口
├── build.py                  # 构建脚本
└── requirements.txt          # 依赖列表
```

## 📖 使用说明

### 基本使用流程

1. **启动应用**
   ```bash
   python main.py
   ```

2. **加载数据源**
   - 点击"加载BigFilesMD5s.json"
   - 选择 `BigFilesMD5s.json` 文件
   - 应用会自动与现有下载状态进行diff合并，保留已完成的下载

3. **设置下载目录**
   - 点击"选择下载目录"
   - 选择文件保存位置

4. **开始下载**
   - 选择要下载的文件（支持单选/多选/全选）
   - 点击"开始下载"
   - 实时查看下载进度

### 配置选项

#### 基础下载配置
| 参数 | 默认值 | 说明 |
|------|--------|------|
| 并发请求数 | 50 | 同时进行的下载任务数量 |
| 超时时间 | 120秒 | 单个请求的超时时间 |
| 批次大小 | 20 | 每批处理的文件数量 |
| 重试次数 | 5 | 下载失败时的重试次数 |

#### 断点续传配置
| 参数 | 默认值 | 说明 |
|------|--------|------|
| 最小续传大小 | 2MB | 文件大于此值才启用断点续传 |
| 块大小 | 64KB | 流式下载的块大小 |
| 完整性缓存 | 启用 | 缓存文件校验结果 |
| 支持算法 | MD5/SHA1/SHA256 | 完整性校验支持的算法 |

#### 压缩优化配置
| 参数 | 默认值 | 说明 |
|------|--------|------|
| JSON强制压缩 | 启用 | JSON文件强制请求压缩传输 |
| PNG流式阈值 | 500KB | 大于此值的PNG使用流式处理 |
| 压缩级别 | 6 | gzip压缩级别(1-9) |
| 性能监控 | 启用 | 跟踪压缩比和传输节省 |

## 🔧 构建和分发

### 创建可执行文件
```bash
# 一键构建
python build.py

# 手动构建
pyinstaller build.spec --clean --noconfirm
```

构建完成后，可执行文件将在 `dist/` 目录中。

### 开发环境设置
```bash
# 安装开发依赖
pip install -r requirements.txt

# 运行测试
python tests/run_tests.py
```

## 🧪 测试

```bash
# 运行所有测试
python tests/run_tests.py

# 运行特定测试模块
python -m pytest tests/test_compression_optimization.py -v  # 压缩优化测试
python -m pytest tests/test_verify_failed_status.py -v      # 验证状态测试
python -m pytest tests/test_http2.py -v                     # HTTP/2 测试
```

## 📝 文件状态说明

### 下载状态
- **待下载**: 等待下载的文件
- **下载中**: 正在下载的文件  
- **已完成**: 下载成功的文件
- **失败**: 下载失败的文件
- **已跳过**: 文件已存在，跳过下载

### MD5验证状态颜色
- **浅灰色**: 未验证状态
- **浅黄色**: 验证中状态
- **浅绿色**: 验证成功状态
- **浅红色**: 验证失败状态（自动标记重新下载）

## 🔧 故障排除

### 常见问题

**下载速度慢**
- 检查网络连接状况
- 适当降低并发请求数
- 增加超时时间设置
- 启用压缩传输优化（JSON文件可节省75%传输量）

**下载失败较多**
- 确认JSON文件格式正确
- 检查网络连接稳定性
- 增加重试次数
- 启用断点续传功能

**MD5验证失败**
- 文件可能在传输中损坏
- 验证失败的文件会自动标记为重新下载
- 检查网络连接稳定性

**界面无响应**
- 可能正在处理大量文件
- 等待处理完成或重启应用
- 查看日志面板了解当前处理状态

### 性能优化特性

**智能压缩传输**
- JSON文件自动请求gzip/brotli压缩，可节省高达75%的传输量
- PNG文件智能流式传输优化
- 实时压缩比统计和传输节省监控

**智能断点续传**
- 大文件（>2MB）自动启用断点续传
- 网络中断自动恢复下载
- 支持Range请求探测和优化

**完整性校验优化**
- 多种哈希算法支持（MD5/SHA1/SHA256）
- 智能缓存机制，避免重复校验
- 验证失败自动标记重新下载

### 日志查看

应用运行时的日志信息会显示在界面下侧的日志面板中，包含：
- 下载进度和状态信息
- 错误和警告消息
- 性能统计数据
- 压缩传输节省统计
- 完整性校验结果
- 断点续传恢复信息

## 📄 许可证

本项目基于 MIT 许可证开源。

## 🤝 贡献

欢迎通过以下方式参与项目：
- 提交 Issue 报告问题
- 提交 Pull Request 改进代码
- 完善文档和测试

---

 **让DLC下载变得简单高效！**