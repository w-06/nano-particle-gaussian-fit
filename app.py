"""纳米材料粒径高斯拟合曲线工具 — Streamlit Web 应用

面向纳米材料研究领域的高斯拟合曲线在线工具，
支持直接读取 Excel 数据、自动拟合、导出图片和 PDF 报告。
"""

import sys

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO

from fitting import gaussian, fit_gaussian_log, auto_detect_structure
from visualization import plot_bar_chart, plot_distribution_grid
from report_generator import generate_pdf_report

# ==================== 页面配置 ====================
st.set_page_config(
    page_title="纳米材料粒径高斯拟合工具",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ==================== 会话状态初始化 ====================
if "df" not in st.session_state:
    st.session_state.df = None
if "x_data" not in st.session_state:
    st.session_state.x_data = None
if "sample_names" not in st.session_state:
    st.session_state.sample_names = []
if "results" not in st.session_state:
    st.session_state.results = None
if "bar_data" not in st.session_state:
    st.session_state.bar_data = None
if "groups_config" not in st.session_state:
    st.session_state.groups_config = {}
if "sheet_names" not in st.session_state:
    st.session_state.sheet_names = []
if "x_start" not in st.session_state:
    st.session_state.x_start = 0


def reset_state():
    """重置所有状态"""
    keys = ["df", "x_data", "sample_names", "results", "bar_data", "groups_config", "x_start"]
    for k in keys:
        if k in st.session_state:
            st.session_state[k] = None if k not in ("sample_names", "groups_config") else ([] if k == "sample_names" else {})
    st.session_state.x_start = 0


def load_excel(file):
    """加载 Excel 文件并缓存"""
    try:
        xls = pd.ExcelFile(file)
        sheet_names = xls.sheet_names
        st.session_state.sheet_names = sheet_names
        return xls, sheet_names
    except Exception as e:
        st.error(f"读取 Excel 文件失败：{e}")
        return None, []


# ==================== UI 渲染 ====================
# ---- 标题区 ----
st.markdown("""
<div style="text-align: center; padding: 1rem 0 0.5rem 0;">
    <h1 style="color: #1565C0; margin-bottom: 0;">🔬 纳米材料粒径高斯拟合工具</h1>
    <p style="color: #666; font-size: 1rem;">
        Nano Particle Size — Gaussian Fit Tool (Log-Normal Distribution)
    </p>
</div>
""", unsafe_allow_html=True)
st.divider()

# ---- 侧边栏：使用说明 ----
with st.sidebar:
    st.markdown("### 📖 使用说明")
    st.markdown("""
    1. **上传** DLS 粒径分布 Excel 文件
    2. **选择** 数据所在的工作表
    3. **配置** 样本分组（或使用自动检测）
    4. **点击** "开始拟合" 按钮
    5. **查看** 拟合结果和图表
    6. **下载** PNG 图片或 PDF 报告
    """)
    st.divider()
    st.markdown("### 📊 数据格式说明")
    st.markdown("""
    Excel 表格需满足以下格式之一：

    **格式 A（带表头）：**
    - 第 1 行：样本名称
    - 第 1 列：粒径值 (nm)
    - 其余列：强度分布数据

    **格式 B（纯数据）：**
    - 第 1 列：粒径值 (nm)
    - 其余列：强度分布数据
    """)
    st.divider()
    st.markdown("### 🔗 关于")
    st.markdown("""
    专为纳米材料 DLS 粒径分布数据分析设计。
    采用对数正态分布（对数空间高斯）拟合模型。

    **技术栈：** Python + Streamlit + SciPy
    """)

# ---- 步骤 1：文件上传 ----
st.markdown("### 📁 第一步：上传 Excel 数据文件")
uploaded_file = st.file_uploader(
    "拖拽或点击上传 .xls / .xlsx 文件",
    type=["xls", "xlsx"],
    help="支持 DLS 粒径分布原始数据（Excel 格式）",
    on_change=reset_state,
)

if uploaded_file is not None:
    xls, sheet_names = load_excel(uploaded_file)

    if sheet_names:
        # ---- 步骤 2：数据配置 ----
        st.markdown("### ⚙️ 第二步：数据配置")
        col1, col2 = st.columns([1, 2])

        with col1:
            selected_sheet = st.selectbox(
                "选择工作表",
                sheet_names,
                index=0 if "Sheet3" not in sheet_names else sheet_names.index("Sheet3"),
            )

        with col2:
            st.caption("提示：工具会自动检测数据结构，您也可以手动调整以下配置")

        # 读取选中 sheet 的数据
        if st.button("📋 加载数据并自动检测", type="primary", use_container_width=False):
            with st.spinner("正在读取数据..."):
                try:
                    df = pd.read_excel(uploaded_file, sheet_name=selected_sheet, header=None)
                    st.session_state.df = df
                    x_data, sample_names, data_cols, x_start = auto_detect_structure(df)
                    st.session_state.x_data = x_data
                    st.session_state.sample_names = sample_names
                    st.session_state.x_start = x_start

                    # 默认分组：全部样本归入一个"默认组"
                    st.session_state.groups_config = {
                        "全部样本": data_cols,
                    }
                    st.success(f"检测完成：{len(data_cols)} 个样本，{len(x_data)} 个数据点")
                except Exception as e:
                    st.error(f"数据解析失败：{e}")

        # 数据预览
        if st.session_state.df is not None:
            with st.expander("📋 数据预览（前10行）", expanded=False):
                st.dataframe(st.session_state.df.head(10), use_container_width=True)

            # ---- 样本分组配置 ----
            st.markdown("#### 样本分组配置")

            if st.session_state.sample_names:
                sample_options = [
                    f"列{c+1}: {st.session_state.sample_names[c]}"
                    for c in range(len(st.session_state.sample_names))
                ]

                # 分组编辑
                st.markdown("为每组输入样本列索引（逗号分隔，如 `1,2,3`），留空则删除该组")

                group_count = st.number_input(
                    "分组数量", min_value=1, max_value=10,
                    value=max(1, len(st.session_state.groups_config)),
                    step=1,
                )

                new_groups = {}
                cols = st.columns(min(group_count, 5))
                for gi in range(group_count):
                    with cols[gi % 5] if group_count <= 5 else st.container():
                        existing_keys = list(st.session_state.groups_config.keys())
                        default_name = existing_keys[gi] if gi < len(existing_keys) else f"组 {gi + 1}"
                        default_cols = (
                            ",".join(str(c) for c in st.session_state.groups_config[default_name])
                            if default_name in st.session_state.groups_config
                            else ""
                        )

                        group_name = st.text_input(
                            f"组 {gi + 1} 名称",
                            value=default_name,
                            key=f"group_name_{gi}",
                        )
                        col_str = st.text_input(
                            f"列索引（逗号分隔）",
                            value=default_cols,
                            key=f"group_cols_{gi}",
                            placeholder="如 1,2,3",
                        )

                        if group_name and col_str.strip():
                            try:
                                cols_list = [int(x.strip()) for x in col_str.split(",") if x.strip()]
                                if cols_list:
                                    new_groups[group_name] = cols_list
                            except ValueError:
                                st.warning(f"组 '{group_name}' 的列索引格式有误，请使用逗号分隔的数字")

                if new_groups:
                    st.session_state.groups_config = new_groups

            # ---- 步骤 3：执行拟合 ----
            st.markdown("### 🔬 第三步：执行拟合计算")
            if st.button("🚀 开始拟合", type="primary", use_container_width=True):
                if st.session_state.x_data is None or st.session_state.df is None:
                    st.error("请先加载数据")
                elif not st.session_state.groups_config:
                    st.error("请至少配置一个样本组")
                else:
                    with st.spinner("正在进行高斯拟合计算..."):
                        progress_bar = st.progress(0)
                        total_groups = len(st.session_state.groups_config)
                        results = {}
                        bar_data = []

                        for i, (gname, cols) in enumerate(st.session_state.groups_config.items()):
                            group_results = []
                            for col_idx in cols:
                                if col_idx >= st.session_state.df.shape[1]:
                                    st.warning(f"列索引 {col_idx} 超出范围，已跳过")
                                    continue
                                x_start = st.session_state.x_start
                                y = st.session_state.df.iloc[x_start:, col_idx].values.astype(float)
                                res = fit_gaussian_log(st.session_state.x_data, y)
                                if res:
                                    res["sample_name"] = st.session_state.sample_names[col_idx - 1]
                                    res["col_index"] = col_idx
                                    group_results.append(res)

                            if group_results:
                                results[gname] = group_results
                                means = [r["mean_nm"] for r in group_results]
                                bar_data.append({
                                    "group": gname,
                                    "mean": np.mean(means),
                                    "sd": np.std(means, ddof=1) if len(means) > 1 else 0,
                                    "n": len(means),
                                })
                            else:
                                st.warning(f"组 '{gname}' 中所有样本拟合失败，已跳过")

                            progress_bar.progress((i + 1) / total_groups)

                        if results:
                            st.session_state.results = results
                            st.session_state.bar_data = bar_data
                            st.success(f"拟合完成！成功处理 {len(results)} 组，共 {sum(len(v) for v in results.values())} 个样本")
                        else:
                            st.error("所有分组拟合均失败，请检查数据格式和分组配置")

# ---- 结果展示 ----
if st.session_state.results is not None:
    results = st.session_state.results
    bar_data = st.session_state.bar_data

    st.divider()
    st.markdown("## 📊 拟合结果")

    # ---- 参数汇总表 ----
    st.markdown("### 拟合参数汇总")
    table_data = []
    for group_name, group_results in results.items():
        for r in group_results:
            table_data.append({
                "样本组": group_name,
                "样本名": r.get("sample_name", ""),
                "平均粒径 (nm)": f"{r['mean_nm']:.1f}",
                "几何标准差 GSD": f"{r['geo_sigma']:.2f}",
                "R²": f"{r['R2']:.4f}",
            })
        # 组平均值
        if group_results:
            mu_avg = np.mean([r["mean_nm"] for r in group_results])
            gs_avg = np.mean([r["geo_sigma"] for r in group_results])
            r2_avg = np.mean([r["R2"] for r in group_results])
            table_data.append({
                "样本组": f"**{group_name} 平均**",
                "样本名": "",
                "平均粒径 (nm)": f"**{mu_avg:.1f}**",
                "几何标准差 GSD": f"**{gs_avg:.2f}**",
                "R²": f"**{r2_avg:.4f}**",
            })

    st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)

    # ---- 可视化 ----
    st.markdown("### 粒径均值对比")
    bar_fig, _ = plot_bar_chart(bar_data, results)
    st.pyplot(bar_fig)

    st.markdown("### 粒径分布拟合曲线")
    dist_fig = plot_distribution_grid(results)
    if dist_fig:
        st.pyplot(dist_fig)

    # ---- 导出下载 ----
    st.divider()
    st.markdown("## 📥 导出下载")

    col1, col2, col3 = st.columns(3)

    with col1:
        # 下载柱状图 PNG
        buf = BytesIO()
        bar_fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
        buf.seek(0)
        st.download_button(
            label="⬇ 下载柱状图 (PNG)",
            data=buf,
            file_name="粒径对比柱状图.png",
            mime="image/png",
            use_container_width=True,
        )

    with col2:
        # 下载分布图 PNG
        if dist_fig:
            buf2 = BytesIO()
            dist_fig.savefig(buf2, format="png", dpi=200, bbox_inches="tight")
            buf2.seek(0)
            st.download_button(
                label="⬇ 下载拟合曲线图 (PNG)",
                data=buf2,
                file_name="粒径分布拟合曲线.png",
                mime="image/png",
                use_container_width=True,
            )

    with col3:
        # 下载 PDF 报告
        if dist_fig:
            try:
                pdf_bytes = generate_pdf_report(results, bar_fig, dist_fig)
                st.download_button(
                    label="📄 下载完整 PDF 报告",
                    data=pdf_bytes,
                    file_name="纳米材料粒径高斯拟合报告.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as e:
                st.warning(f"PDF 报告生成失败：{e}\n请尝试下载 PNG 图片。")

    # ---- 拟合结果详情（可折叠） ----
    with st.expander("🔍 拟合详情（JSON 格式，供程序使用）", expanded=False):
        clean_results = {}
        for gname, grp in results.items():
            clean_results[gname] = []
            for r in grp:
                clean_results[gname].append({
                    "sample_name": r.get("sample_name", ""),
                    "mean_nm": round(r["mean_nm"], 1),
                    "geo_sigma": round(r["geo_sigma"], 2),
                    "R2": round(r["R2"], 4),
                })
        st.json(clean_results)

else:
    # 未上传文件时的欢迎提示
    if uploaded_file is None:
        st.info("👆 请先上传 Excel 数据文件以开始分析")
    elif st.session_state.df is None:
        st.info("👆 请点击「加载数据并自动检测」按钮以继续")
