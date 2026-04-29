import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import matplotlib
matplotlib.use("Agg")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

# ============ 1. 读取 Sheet3 的粒径分布数据 ============
df = pd.read_excel("lcy.xls", sheet_name="Sheet3", header=None)
x_data = df.iloc[1:, 0].values.astype(float)

sample_groups = {
    "60nm-c":  [1, 2, 3],
    "100nm-c": [4, 5, 6],
    "200nm-c": [7, 8, 9],
    "60nm-w":  [10, 11, 12],
    "100nm-w": [13, 14, 15],
    "200nm-w": [16, 17, 18],
}

# ============ 2. 高斯拟合（log 空间） ============
def gaussian(x, A, mu, sigma):
    return A * np.exp(-((x - mu) ** 2) / (2 * sigma ** 2))


def fit_gaussian_log(x, y):
    mask = (y > 0) & ~np.isnan(y) & ~np.isinf(y) & (x > 0)
    x_fit, y_fit = x[mask], y[mask]
    if len(x_fit) < 5:
        return None

    log_x = np.log10(x_fit)
    p0 = [np.max(y_fit), log_x[np.argmax(y_fit)], np.std(log_x)]
    try:
        popt, _ = curve_fit(gaussian, log_x, y_fit, p0=p0, maxfev=10000)
    except RuntimeError:
        return None

    A, mu_log, sigma_log = popt
    sigma_abs = abs(sigma_log)
    mean_nm = 10 ** mu_log
    geo_sigma = 10 ** sigma_abs

    y_pred = gaussian(log_x, *popt)
    ss_res = np.sum((y_fit - y_pred) ** 2)
    ss_tot = np.sum((y_fit - np.mean(y_fit)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    return {
        "A": A, "mu_log": mu_log, "sigma_log": sigma_abs,
        "mean_nm": mean_nm, "geo_sigma": geo_sigma, "R2": r2,
        "x_fit": x_fit, "y_fit": y_fit, "log_x_fit": log_x,
    }


# ============ 3. 拟合所有样本 ============
results = {}
for group_name, cols in sample_groups.items():
    group_results = []
    for col in cols:
        y = df.iloc[1:, col].values.astype(float)
        res = fit_gaussian_log(x_data, y)
        if res:
            res["sample_name"] = df.iloc[0, col]
            group_results.append(res)
    results[group_name] = group_results

# ============ 4. 输出汇总表 ============
print("=" * 80)
print(f"{'样本组':<12s} {'样本名':<22s} {'Mean(nm)':>10s} {'GSD':>8s} {'R2':>10s}")
print("-" * 80)
for group_name, group_results in results.items():
    for r in group_results:
        print(f"{group_name:<12s} {r['sample_name']:<22s} {r['mean_nm']:10.1f} {r['geo_sigma']:8.2f} {r['R2']:10.6f}")
    if group_results:
        mu_avg = np.mean([r["mean_nm"] for r in group_results])
        gs_avg = np.mean([r["geo_sigma"] for r in group_results])
        print(f"{'  平均':<12s} {'':22s} {mu_avg:10.1f} {gs_avg:8.2f}")
    print()

# ============ 5. 柱状图：Mean ± SD（组内标准差） ============
plt.rcParams["font.family"] = ["Arial", "Times New Roman"]
plt.rcParams["axes.unicode_minus"] = False

# 计算每组的 Mean 和 SD（组内 3 个重复的标准差）
bar_data = []
for group_name, group_results in results.items():
    means = [r["mean_nm"] for r in group_results]
    bar_data.append({
        "group": group_name,
        "mean": np.mean(means),
        "sd": np.std(means, ddof=1) if len(means) > 1 else 0,
        "n": len(means),
    })

# 分类
sizes = ["60nm", "100nm", "200nm"]
conditions = ["-c", "-w"]
cond_labels = {"-c": "Centrifuged", "-w": "Washed"}

fig, ax = plt.subplots(figsize=(10, 6))

bar_width = 0.3
x_pos = np.arange(len(sizes))
colors = {"-c": "#4A90D9", "-w": "#E67E22"}

for ci, cond in enumerate(conditions):
    means = []
    sds = []
    for size in sizes:
        key = f"{size}{cond}"
        d = next((b for b in bar_data if b["group"] == key), None)
        if d:
            means.append(d["mean"])
            sds.append(d["sd"])
        else:
            means.append(0)
            sds.append(0)

    offset = (ci - 0.5) * bar_width
    bars = ax.bar(x_pos + offset, means, bar_width, yerr=sds,
                  label=cond_labels[cond], color=colors[cond],
                  edgecolor="black", linewidth=0.8, capsize=5,
                  error_kw={"linewidth": 1.2, "capthick": 1.2})

    # 在每个柱子上标注数值
    for j, (m, s) in enumerate(zip(means, sds)):
        ax.text(x_pos[j] + offset, m + s + 8, f"{m:.0f}",
                ha="center", va="bottom", fontsize=10, fontweight="bold")

    # 叠加散点（3 个重复的实际值）
    for size in sizes:
        key = f"{size}{cond}"
        j = sizes.index(size)
        gr = results.get(key, [])
        for r in gr:
            ax.scatter(x_pos[j] + offset, r["mean_nm"],
                       s=30, color="white", edgecolors="black",
                       linewidths=0.8, zorder=5)

ax.set_xticks(x_pos)
ax.set_xticklabels(["60 nm", "100 nm", "200 nm"], fontsize=13)
ax.set_ylabel("Particle Diameter (nm)", fontsize=13)
ax.set_xlabel("Nominal Size", fontsize=13)
ax.set_title("DLS Measured Size: Centrifuged vs Washed", fontsize=14, fontweight="bold")
ax.legend(fontsize=12, loc="upper left")
ax.tick_params(labelsize=11)
ax.set_ylim(0, max(d["mean"] + d["sd"] for d in bar_data) * 1.25)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

plt.tight_layout()
plt.savefig("gaussian_fit_bar.png", dpi=200)
plt.savefig("gaussian_fit_bar.pdf")
print("柱状图已保存为 gaussian_fit_bar.png / .pdf")

# ============ 6. 附带分布拟合曲线（2×3） ============
fig2, axes = plt.subplots(2, 3, figsize=(15, 9))
axes = axes.flatten()
colors_scatter = ["#4A90D9", "#E67E22", "#2ECC71"]

for idx, (group_name, group_results) in enumerate(results.items()):
    ax = axes[idx]
    if not group_results:
        ax.set_title(group_name, fontsize=13)
        continue

    for i, r in enumerate(group_results):
        ax.scatter(r["x_fit"], r["y_fit"], s=12, alpha=0.6,
                   color=colors_scatter[i], edgecolors="none", zorder=3)
        log_smooth = np.linspace(r["log_x_fit"].min() - 0.1,
                                  r["log_x_fit"].max() + 0.1, 500)
        y_smooth = gaussian(log_smooth, r["A"], r["mu_log"], r["sigma_log"])
        ax.plot(10 ** log_smooth, y_smooth, color=colors_scatter[i],
                linewidth=1.8, zorder=4,
                label=f"{r['sample_name']} ({r['mean_nm']:.0f} nm)")

    mu_log_avg = np.mean([r["mu_log"] for r in group_results])
    sigma_log_avg = np.mean([r["sigma_log"] for r in group_results])
    A_avg = np.mean([r["A"] for r in group_results])
    log_smooth = np.linspace(mu_log_avg - 3 * sigma_log_avg,
                              mu_log_avg + 3 * sigma_log_avg, 500)
    ax.plot(10 ** log_smooth, gaussian(log_smooth, A_avg, mu_log_avg, sigma_log_avg),
            color="black", linewidth=2.2, linestyle="--", zorder=5,
            label=f"Avg ({10 ** mu_log_avg:.0f} nm)")

    ax.set_xscale("log")
    ax.set_xlabel("Diameter (nm)", fontsize=11)
    ax.set_ylabel("Intensity (%)", fontsize=11)
    ax.set_title(group_name, fontsize=13, fontweight="bold")
    ax.tick_params(labelsize=9)
    ax.legend(fontsize=8, loc="upper right")
    ax.set_xlim(1, 10000)
    ax.set_ylim(bottom=0)

fig2.suptitle("DLS Size Distribution with Log-Normal Fit",
              fontsize=15, fontweight="bold", y=0.98)
plt.tight_layout(rect=[0, 0, 1, 0.95])
plt.savefig("gaussian_fit_result.png", dpi=200)
plt.savefig("gaussian_fit_result.pdf")
print("分布拟合图已保存为 gaussian_fit_result.png / .pdf")
