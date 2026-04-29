"""纳米材料粒径高斯拟合核心逻辑模块

提供对数正态分布（对数空间高斯）拟合功能，用于处理 DLS 粒径分布数据。
"""

import numpy as np
from scipy.optimize import curve_fit


def gaussian(x, A, mu, sigma):
    """高斯函数"""
    return A * np.exp(-((x - mu) ** 2) / (2 * sigma ** 2))


def fit_gaussian_log(x, y):
    """在 log10 空间对粒径分布数据进行高斯拟合

    参数:
        x: 粒径值数组（线性空间，单位 nm）
        y: 强度分布值数组

    返回:
        拟合结果字典，包含 mean_nm（几何平均粒径）、geo_sigma（几何标准差）、
        R²、拟合曲线坐标等；若拟合失败返回 None
    """
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
        "A": A,
        "mu_log": mu_log,
        "sigma_log": sigma_abs,
        "mean_nm": mean_nm,
        "geo_sigma": geo_sigma,
        "R2": r2,
        "x_fit": x_fit,
        "y_fit": y_fit,
        "log_x_fit": log_x,
    }


def auto_detect_structure(df):
    """自动检测 Excel 数据表结构

    假设第一列为粒径值（X 轴），其余列为各样本强度分布。
    若第一行为字符串（样本名），则作为列标题。

    返回:
        (x_data, sample_names, data_columns) 元组
        - x_data: 粒径值数组
        - sample_names: 样本名称列表
        - data_columns: 数据列索引列表（从 1 开始）
    """
    # 判断第一行是否为表头（包含非数字内容）
    first_row = df.iloc[0, :]
    has_header = False
    for val in first_row:
        if isinstance(val, str) and val.strip():
            has_header = True
            break

    if has_header:
        x_start = 1  # 粒径数据从第二行开始
        sample_names = [str(df.iloc[0, c]) for c in range(1, df.shape[1])]
    else:
        x_start = 0
        sample_names = [f"样本 {c}" for c in range(1, df.shape[1])]

    x_data = df.iloc[x_start:, 0].values.astype(float)
    data_columns = list(range(1, df.shape[1]))

    # 清理样本名中的空白字符
    sample_names = [name.strip() for name in sample_names]

    return x_data, sample_names, data_columns, x_start
