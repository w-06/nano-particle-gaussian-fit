"""可视化绑图模块

生成纳米材料粒径高斯拟合的可视化图表：
1. 柱状图 — 各组 Mean ± SD 对比
2. 分布拟合曲线网格 — 原始数据散点 + 拟合曲线
"""

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from fitting import gaussian


# 配色方案
COLORS_SCATTER = ["#4A90D9", "#E67E22", "#2ECC71", "#E74C3C", "#9B59B6", "#1ABC9C"]
COLORS_CONDITION = {"-c": "#4A90D9", "-w": "#E67E22", "default": "#1565C0"}


def _setup_chinese_font():
    """配置中文字体支持，自动适配 Windows / Linux 系统"""
    import matplotlib.font_manager as fm
    import os

    plt.rcParams["axes.unicode_minus"] = False

    # 按优先级搜索系统中存在的中文字体
    candidate_fonts = [
        "SimHei", "Microsoft YaHei", "SimSun", "KaiTi", "FangSong",
        "Noto Sans CJK SC", "Noto Sans SC", "WenQuanYi Micro Hei",
        "WenQuanYi Zen Hei", "AR PL UMing CN", "AR PL UKai CN",
        "Source Han Sans SC", "Source Han Sans CN",
    ]

    available_fonts = {f.name for f in fm.fontManager.ttflist}
    selected = None
    for font_name in candidate_fonts:
        if font_name in available_fonts:
            selected = font_name
            break

    if selected:
        plt.rcParams["font.sans-serif"] = [selected, "DejaVu Sans", "Arial"]
    else:
        # 回退：尝试用 font_manager 查找任意支持 CJK 的字体
        import glob
        # Windows 字体目录
        for search_dir in ["C:/Windows/Fonts", "/usr/share/fonts", "/usr/local/share/fonts"]:
            for pattern in ["*.ttf", "*.ttc", "*.otf"]:
                for fp in glob.glob(os.path.join(search_dir, pattern)):
                    try:
                        f = fm.FontEntry(fname=fp)
                        if "CJK" in f.name or "Hei" in f.name or "Song" in f.name or "Ming" in f.name:
                            fm.fontManager.addfont(fp)
                            plt.rcParams["font.sans-serif"] = [f.name, "DejaVu Sans", "Arial"]
                            selected = f.name
                            break
                    except Exception:
                        continue
                if selected:
                    break
            if selected:
                break

    if not selected:
        plt.rcParams["font.family"] = "sans-serif"
        plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial"]


def plot_bar_chart(bar_data, results, title="粒径测量结果对比"):
    """绘制分组柱状图（均值 ± 标准差）

    参数:
        bar_data: 列表，每项含 group/mean/sd/n
        results: 拟合结果字典（用于叠加原始散点）
        title: 图表标题

    返回:
        (fig, ax) matplotlib 图形对象
    """
    _setup_chinese_font()

    fig, ax = plt.subplots(figsize=(10, 6))
    bar_width = 0.35
    groups = sorted(set(d["group"] for d in bar_data))
    x_pos = np.arange(len(groups))

    # 自动检测条件后缀，兼容原格式和其他格式
    conditions = list(set(
        d["group"].split("-")[-1] if "-" in d["group"] else "default"
        for d in bar_data
    ))

    for ci, cond in enumerate(conditions):
        means, sds, cond_groups = [], [], []
        for g in groups:
            if (cond == "default" and "-" not in g) or g.endswith(f"-{cond}"):
                d = next((b for b in bar_data if b["group"] == g), None)
                if d:
                    means.append(d["mean"])
                    sds.append(d["sd"])
                    cond_groups.append(g)

        if not means:
            continue

        offset = (ci - (len(conditions) - 1) / 2) * bar_width
        color = COLORS_CONDITION.get(cond, "#1565C0")
        label_map = {"-c": "离心组 (Centrifuged)", "-w": "洗涤组 (Washed)"}
        label = label_map.get(f"-{cond}", cond)

        bars = ax.bar(x_pos[:len(means)] + offset, means, bar_width,
                      yerr=sds, label=label, color=color,
                      edgecolor="black", linewidth=0.8, capsize=5,
                      error_kw={"linewidth": 1.2, "capthick": 1.2})

        for j, (m, s) in enumerate(zip(means, sds)):
            ax.text(x_pos[j] + offset, m + s + max(means) * 0.02,
                    f"{m:.0f}", ha="center", va="bottom",
                    fontsize=9, fontweight="bold")

        # 叠加原始重复数据散点
        for j, g_name in enumerate(cond_groups):
            gr = results.get(g_name, [])
            for r in gr:
                ax.scatter(x_pos[j] + offset, r["mean_nm"],
                           s=25, color="white", edgecolors="black",
                           linewidths=0.6, zorder=5)

    ax.set_xticks(x_pos)
    ax.set_xticklabels(groups, fontsize=11)
    ax.set_ylabel("粒径 (nm)", fontsize=12)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.legend(fontsize=10, loc="upper left")
    ax.tick_params(labelsize=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    all_max = [d["mean"] + d["sd"] for d in bar_data]
    ax.set_ylim(0, max(all_max) * 1.3 if all_max else 100)

    fig.tight_layout()
    return fig, ax


def plot_distribution_grid(results, title="DLS 粒径分布 — 对数正态拟合"):
    """绘制分布拟合曲线网格图

    参数:
        results: 拟合结果字典，key 为组名，value 为拟合结果列表
        title: 图表总标题

    返回:
        fig  matplotlib 图形对象
    """
    _setup_chinese_font()

    n_groups = len(results)
    if n_groups == 0:
        return None

    n_cols = min(3, n_groups)
    n_rows = (n_groups + n_cols - 1) // n_cols
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 4.5 * n_rows))
    if n_groups == 1:
        axes = [axes]
    else:
        axes = axes.flatten()

    for idx, (group_name, group_results) in enumerate(results.items()):
        ax = axes[idx]
        if not group_results:
            ax.set_title(group_name, fontsize=12)
            continue

        for i, r in enumerate(group_results):
            color = COLORS_SCATTER[i % len(COLORS_SCATTER)]
            ax.scatter(r["x_fit"], r["y_fit"], s=10, alpha=0.5,
                       color=color, edgecolors="none", zorder=3)
            log_smooth = np.linspace(r["log_x_fit"].min() - 0.1,
                                     r["log_x_fit"].max() + 0.1, 500)
            y_smooth = gaussian(log_smooth, r["A"], r["mu_log"], r["sigma_log"])
            ax.plot(10 ** log_smooth, y_smooth, color=color,
                    linewidth=1.5, zorder=4,
                    label=f"{r.get('sample_name', '')} ({r['mean_nm']:.0f} nm)")

        # 组平均曲线
        mu_log_avg = np.mean([r["mu_log"] for r in group_results])
        sigma_log_avg = np.mean([r["sigma_log"] for r in group_results])
        A_avg = np.mean([r["A"] for r in group_results])
        log_smooth = np.linspace(mu_log_avg - 3 * sigma_log_avg,
                                 mu_log_avg + 3 * sigma_log_avg, 500)
        ax.plot(10 ** log_smooth, gaussian(log_smooth, A_avg, mu_log_avg, sigma_log_avg),
                color="black", linewidth=2, linestyle="--", zorder=5,
                label=f"平均 ({10 ** mu_log_avg:.0f} nm)")

        ax.set_xscale("log")
        ax.set_xlabel("粒径 (nm)", fontsize=10)
        ax.set_ylabel("强度 (%)", fontsize=10)
        ax.set_title(group_name, fontsize=12, fontweight="bold")
        ax.tick_params(labelsize=8)
        ax.legend(fontsize=7, loc="upper right")
        ax.set_xlim(1, 10000)
        ax.set_ylim(bottom=0)

    # 隐藏多余的子图
    for idx in range(n_groups, len(axes)):
        axes[idx].set_visible(False)

    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    return fig
