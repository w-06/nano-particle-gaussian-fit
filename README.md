# 🔬 纳米材料粒径高斯拟合曲线工具

> 一款面向纳米材料研究领域的高斯拟合曲线在线工具，用于处理纳米材料粒径（DLS）实验数据，支持直接读取 Excel 表格完成拟合计算，一键导出拟合曲线图片和 PDF 报告。

[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat&logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 📖 项目简介

本工具针对科研人员**手动处理实验数据繁琐、拟合操作门槛高**的痛点设计：

- ✅ **直接读取 Excel** — 无需手动转录数据，上传即用
- ✅ **自动拟合计算** — 对数正态分布（对数空间高斯）拟合，输出平均粒径、几何标准差（GSD）、R²
- ✅ **可视化展示** — 自动生成柱状对比图和分布拟合曲线图
- ✅ **一键导出** — 下载高清 PNG 图片和完整 PDF 报告

## 🚀 在线使用

> 🌐 **在线地址：** [点击使用](https://你的应用名.streamlit.app) *(部署后更新)*

无需安装任何软件，浏览器打开即可使用。

## 📸 功能截图

*（部署后可添加截图链接）*

## 📊 数据格式说明

Excel 文件需满足以下格式之一：

| 格式 | 说明 |
|------|------|
| **格式 A**（带表头） | 第 1 行：样本名称；第 1 列：粒径值 (nm)；其余列：强度分布数据 |
| **格式 B**（纯数据） | 第 1 列：粒径值 (nm)；其余列：强度分布数据 |

示例数据文件：`lcy.xls`

## 🖥 本地运行

### 1. 克隆仓库

```bash
git clone https://github.com/你的用户名/纳米材料粒径高斯拟合曲线.git
cd 纳米材料粒径高斯拟合曲线
```

### 2. 创建虚拟环境并安装依赖

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 启动应用

```bash
streamlit run app.py
```

浏览器打开 `http://localhost:8501` 即可使用。

## 🛠 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | [Streamlit](https://streamlit.io) |
| 科学计算 | NumPy, SciPy, Pandas |
| 数据可视化 | Matplotlib |
| PDF 生成 | fpdf2 |
| 部署平台 | Streamlit Community Cloud |

## 📄 拟合模型

采用**对数正态分布**（Log-Normal Distribution）模型，即在对数空间进行高斯拟合：

$$f(x) = A \cdot \exp\left(-\frac{(\log_{10}x - \mu)^2}{2\sigma^2}\right)$$

- **平均粒径** = $10^\mu$ (nm)
- **几何标准差 (GSD)** = $10^\sigma$

## 📝 使用流程

1. 上传含有 DLS 粒径分布数据的 Excel 文件
2. 选择数据所在的工作表
3. 工具自动检测数据结构，可手动调整样本分组
4. 点击"开始拟合"执行计算
5. 查看拟合参数汇总表和可视化图表
6. 下载 PNG 图片或 PDF 综合报告

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 开源协议

本项目基于 MIT 协议开源。

---

*Made with ❤️ for nanomaterials researchers*
