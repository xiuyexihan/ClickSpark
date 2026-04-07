# ✨ ClickSpark — 鼠标点击特效

一个轻量级 Windows 鼠标点击特效工具，支持多种特效、自定义颜色、开机启动等功能。

---

## 📦 快速开始

### 方法一：直接运行（推荐新手）
1. 确保已安装 **Python 3.10+**（https://www.python.org/downloads/）
2. 双击运行 `run.bat`，自动安装依赖并启动

### 方法二：手动安装
```bash
pip install -r requirements.txt
python main.py
```

### 方法三：打包为 .exe（无需 Python 环境）
```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name ClickSpark main.py
# 生成文件在 dist/ClickSpark.exe
```

---

## 🎮 功能列表

| 功能 | 说明 |
|------|------|
| **6 种特效** | 粒子爆炸、火花拖尾、涟漪扩散、Emoji飞溅、文字弹出、烟花 |
| **颜色模式** | 随机颜色 / 固定颜色 / 彩虹渐变 |
| **参数调节** | 粒子数量、大小、持续时间、透明度 |
| **自定义内容** | 自定义 Emoji 列表、弹出文字 |
| **开机启动** | 注册表写入，开机自动后台运行 |
| **系统托盘** | 右键菜单快速切换特效、暂停/启用 |
| **配置导入导出** | 分享你的特效配置给朋友 |
| **鼠标穿透** | 特效窗口完全透明穿透，不影响正常操作 |
| **资源极省** | 有粒子才渲染，空闲自动休眠 |

---

## 📁 文件结构

```
ClickSpark/
├── main.py          # 主程序
├── requirements.txt # 依赖列表
├── run.bat          # 一键启动脚本
└── README.md        # 说明文档

配置文件自动保存在:
%APPDATA%\ClickSpark\config.json
```

---

## 🔧 使用说明

- **双击托盘图标** → 打开设置
- **右键托盘图标** → 快速菜单（暂停/切换特效/退出）
- **设置 → 高级** → 开启开机启动、导入导出配置

---

## ❓ 常见问题

**Q: 运行后没有特效？**
A: 确认托盘图标是彩色（非灰色），灰色表示已暂停。

**Q: 打包后文件很大？**
A: 正常现象，PyQt6 体积约 30MB，可用 UPX 压缩：
`pyinstaller --noconsole --onefile --upx-dir=/path/to/upx main.py`

**Q: 如何卸载开机启动？**
A: 打开设置 → 高级 → 取消勾选"开机自动启动"。
