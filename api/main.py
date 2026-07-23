"""纳米材料粒径高斯拟合 — FastAPI RESTful 接口

提供文件上传拟合、历史记录查询、报告/图表下载等 API 端点。
启动方式：uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import io
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from fitting import fit_gaussian_log, auto_detect_structure
from visualization import plot_bar_chart, plot_distribution_grid
from report_generator import generate_pdf_report
from api.models import AnalysisRecord, get_db, SessionLocal
from api.schemas import (
    FitResponse, FitResultItem, GroupResult, BarDataItem,
    AnalysisSummary, AnalysisListResponse, HealthResponse,
)

# ── 应用初始化 ────────────────────────────────────────────

app = FastAPI(
    title="纳米材料粒径高斯拟合 API",
    description="""
基于对数正态分布（Log-Normal）模型的 DLS 粒径高斯拟合 RESTful 接口。

## 功能

- **上传 Excel 并拟合**：上传 DLS 粒径分布 Excel 文件，自动完成高斯拟合
- **历史记录查询**：查看所有历史分析记录
- **报告下载**：下载 PDF 综合报告、PNG 柱状图和分布曲线图

## 技术栈

- **Web 框架**：FastAPI
- **ORM**：SQLAlchemy + SQLite
- **科学计算**：NumPy + SciPy + Pandas
- **可视化**：Matplotlib
    """.strip(),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"

# ── 工具函数 ──────────────────────────────────────────────

class NumpyEncoder(json.JSONEncoder):
    """JSON 序列化：将 numpy 数组和标量转为 Python 原生类型"""
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        return super().default(obj)


def _reconstruct_results(stored: dict) -> dict:
    """从数据库 JSON 重建完整拟合结果（列表 → numpy 数组）"""
    out = {}
    for gname, grp in stored.items():
        out[gname] = []
        for r in grp:
            rec = dict(r)
            for key in ("x_fit", "y_fit", "log_x_fit"):
                if key in rec and isinstance(rec[key], list):
                    rec[key] = np.array(rec[key])
            out[gname].append(rec)
    return out


def _compute_bar_data(results: dict) -> list[dict]:
    """从拟合结果计算柱状图数据"""
    bar_data = []
    for gname, group_results in results.items():
        means = [r["mean_nm"] for r in group_results]
        bar_data.append({
            "group": gname,
            "mean": float(np.mean(means)),
            "sd": float(np.std(means, ddof=1)) if len(means) > 1 else 0.0,
            "n": len(means),
        })
    return bar_data


# ── 辅助：执行拟合工作流 ──────────────────────────────────

def _execute_fit(
    file_content: bytes,
    sheet_name: str | None,
    groups_config: dict | None,
) -> tuple[dict, list[dict], plt.Figure, plt.Figure | None]:
    """执行完整的拟合流程，返回 (results, bar_data, bar_fig, dist_fig)"""

    xls = pd.ExcelFile(io.BytesIO(file_content))
    available_sheets = xls.sheet_names

    # 选择工作表
    if sheet_name and sheet_name in available_sheets:
        selected = sheet_name
    else:
        selected = available_sheets[0]

    df = pd.read_excel(io.BytesIO(file_content), sheet_name=selected, header=None)
    x_data, sample_names, data_cols, x_start = auto_detect_structure(df)

    # 分组配置：默认所有列归入"全部样本"
    if not groups_config:
        groups_config = {"全部样本": data_cols}

    results: dict[str, list] = {}
    for gname, cols in groups_config.items():
        group_results = []
        for col_idx in cols:
            if col_idx >= df.shape[1]:
                continue
            y = df.iloc[x_start:, col_idx].values.astype(float)
            res = fit_gaussian_log(x_data, y)
            if res:
                res["sample_name"] = sample_names[col_idx - 1]
                res["col_index"] = col_idx
                group_results.append(res)
        if group_results:
            results[gname] = group_results

    if not results:
        raise ValueError("所有分组拟合均失败，请检查数据格式和分组配置")

    bar_data = _compute_bar_data(results)
    bar_fig, _ = plot_bar_chart(bar_data, results)
    dist_fig = plot_distribution_grid(results)

    return results, bar_data, bar_fig, dist_fig


# ═══════════════════════════════════════════════════════════
#  API 路由
# ═══════════════════════════════════════════════════════════

# ── 健康检查 ──────────────────────────────────────────────

@app.get(
    f"{API_PREFIX}/health",
    response_model=HealthResponse,
    tags=["系统"],
    summary="健康检查",
)
def health_check():
    """返回 API 服务运行状态"""
    return HealthResponse(status="ok", version=app.version)


# ── 上传并拟合（核心端点）─────────────────────────────────

@app.post(
    f"{API_PREFIX}/fit",
    response_model=FitResponse,
    tags=["拟合分析"],
    summary="上传 Excel 文件并执行高斯拟合",
    description="""
上传 DLS 粒径分布 Excel 文件（.xls / .xlsx），自动完成对数正态分布高斯拟合。

- **file**：必填，Excel 数据文件
- **sheet_name**：选填，工作表名称（不传则使用第一个 sheet）
- **groups_config**：选填，JSON 格式的分组配置。
  - 示例：`{"离心组": [1,2,3], "洗涤组": [4,5,6]}`
  - 列索引从 1 开始计数（与 Excel 一致）
  - 不传则所有样本归入一个"全部样本"组
    """
)
def upload_and_fit(
    file: UploadFile = File(..., description="DLS 粒径分布 Excel 文件 (.xls/.xlsx)"),
    sheet_name: str | None = Form(None, description="工作表名称，不传则用第一个"),
    groups_config: str | None = Form(None, description="JSON 分组配置"),
    db: Session = Depends(get_db),
):
    # 校验文件类型
    if not file.filename.lower().endswith((".xls", ".xlsx")):
        raise HTTPException(400, "仅支持 .xls 或 .xlsx 格式的 Excel 文件")

    content = file.file.read()
    if len(content) > 50 * 1024 * 1024:  # 50 MB
        raise HTTPException(413, "文件大小不能超过 50 MB")

    # 解析分组配置
    groups: dict | None = None
    if groups_config:
        try:
            groups = json.loads(groups_config)
        except json.JSONDecodeError:
            raise HTTPException(400, "groups_config 不是合法的 JSON 字符串")
        if not isinstance(groups, dict):
            raise HTTPException(400, "groups_config 必须是 JSON 对象")
        for k, v in groups.items():
            if not isinstance(v, list):
                raise HTTPException(400, f"分组 '{k}' 的值必须是整数列表")
            groups[k] = [int(x) for x in v]

    # 执行拟合
    try:
        results, bar_data, bar_fig, dist_fig = _execute_fit(
            content, sheet_name, groups,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"拟合过程出错：{e}")

    # 关闭图形避免内存泄漏
    plt.close(bar_fig)
    if dist_fig:
        plt.close(dist_fig)

    # 保存到数据库
    xls = pd.ExcelFile(io.BytesIO(content))
    actual_sheet = sheet_name if sheet_name and sheet_name in xls.sheet_names else xls.sheet_names[0]

    record = AnalysisRecord(
        filename=file.filename,
        sheet_name=actual_sheet,
        results_json=json.dumps(results, cls=NumpyEncoder, ensure_ascii=False),
        groups_config_json=json.dumps(
            groups or {"全部样本": list(range(1, len(results.get(list(results.keys())[0], [])) + 1))},
            ensure_ascii=False,
        ),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # 构建响应
    group_results = []
    for gname, grp in results.items():
        items = [
            FitResultItem(
                sample_name=r.get("sample_name", ""),
                mean_nm=round(float(r["mean_nm"]), 1),
                geo_sigma=round(float(r["geo_sigma"]), 2),
                R2=round(float(r["R2"]), 4),
            )
            for r in grp
        ]
        group_results.append(GroupResult(
            group_name=gname,
            results=items,
            mean_avg=round(float(np.mean([r["mean_nm"] for r in grp])), 1),
            geo_sigma_avg=round(float(np.mean([r["geo_sigma"] for r in grp])), 2),
            r2_avg=round(float(np.mean([r["R2"] for r in grp])), 4),
        ))

    aid = record.id
    base = f"{API_PREFIX}/fit/{aid}"

    return FitResponse(
        analysis_id=aid,
        filename=file.filename,
        sheet_name=actual_sheet,
        groups=group_results,
        bar_data=[BarDataItem(**bd) for bd in bar_data],
        download_urls={
            "pdf_report": f"{base}/report/pdf",
            "bar_chart_png": f"{base}/chart/bar",
            "distribution_chart_png": f"{base}/chart/distribution",
        },
    )


# ── 历史记录列表 ──────────────────────────────────────────

@app.get(
    f"{API_PREFIX}/fit",
    response_model=AnalysisListResponse,
    tags=["历史记录"],
    summary="获取历史分析记录列表",
)
def list_analyses(
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: Session = Depends(get_db),
):
    total = db.query(AnalysisRecord).count()
    records = (
        db.query(AnalysisRecord)
        .order_by(AnalysisRecord.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items: list[AnalysisSummary] = []
    for r in records:
        try:
            stored = json.loads(r.results_json)
            sample_count = sum(len(v) for v in stored.values())
            group_count = len(stored)
        except (json.JSONDecodeError, TypeError):
            sample_count = 0
            group_count = 0

        items.append(AnalysisSummary(
            id=r.id,
            filename=r.filename,
            sheet_name=r.sheet_name,
            created_at=r.created_at.isoformat(),
            sample_count=sample_count,
            group_count=group_count,
        ))

    return AnalysisListResponse(total=total, items=items)


# ── 单条记录详情 ──────────────────────────────────────────

@app.get(
    f"{API_PREFIX}/fit/{{analysis_id}}",
    response_model=FitResponse,
    tags=["历史记录"],
    summary="获取指定分析记录的拟合结果",
)
def get_analysis(analysis_id: int, db: Session = Depends(get_db)):
    record = db.query(AnalysisRecord).filter(AnalysisRecord.id == analysis_id).first()
    if not record:
        raise HTTPException(404, f"分析记录 #{analysis_id} 不存在")

    stored = json.loads(record.results_json)
    results = _reconstruct_results(stored)
    bar_data = _compute_bar_data(results)

    group_items: list[GroupResult] = []
    for gname, grp in results.items():
        items = [
            FitResultItem(
                sample_name=r.get("sample_name", ""),
                mean_nm=round(float(r["mean_nm"]), 1),
                geo_sigma=round(float(r["geo_sigma"]), 2),
                R2=round(float(r["R2"]), 4),
            )
            for r in grp
        ]
        group_items.append(GroupResult(
            group_name=gname,
            results=items,
            mean_avg=round(float(np.mean([r["mean_nm"] for r in grp])), 1),
            geo_sigma_avg=round(float(np.mean([r["geo_sigma"] for r in grp])), 2),
            r2_avg=round(float(np.mean([r["R2"] for r in grp])), 4),
        ))

    aid = record.id
    base = f"{API_PREFIX}/fit/{aid}"

    return FitResponse(
        analysis_id=aid,
        filename=record.filename,
        sheet_name=record.sheet_name,
        groups=group_items,
        bar_data=[BarDataItem(**bd) for bd in bar_data],
        download_urls={
            "pdf_report": f"{base}/report/pdf",
            "bar_chart_png": f"{base}/chart/bar",
            "distribution_chart_png": f"{base}/chart/distribution",
        },
    )


# ── 下载 PDF 报告 ─────────────────────────────────────────

@app.get(
    f"{API_PREFIX}/fit/{{analysis_id}}/report/pdf",
    tags=["报告下载"],
    summary="下载 PDF 综合报告",
    responses={200: {"content": {"application/pdf": {}}}},
)
def download_pdf_report(analysis_id: int, db: Session = Depends(get_db)):
    record = db.query(AnalysisRecord).filter(AnalysisRecord.id == analysis_id).first()
    if not record:
        raise HTTPException(404, f"分析记录 #{analysis_id} 不存在")

    stored = json.loads(record.results_json)
    results = _reconstruct_results(stored)
    bar_data = _compute_bar_data(results)

    bar_fig, _ = plot_bar_chart(bar_data, results)
    dist_fig = plot_distribution_grid(results)

    try:
        pdf_bytes = generate_pdf_report(results, bar_fig, dist_fig)
        # fpdf2 的 output() 可能返回 bytearray，确保转为 bytes
        if isinstance(pdf_bytes, bytearray):
            pdf_bytes = bytes(pdf_bytes)
    finally:
        plt.close(bar_fig)
        if dist_fig:
            plt.close(dist_fig)

    safe_name = record.filename.rsplit(".", 1)[0]
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}_fit_report.pdf"',
        },
    )


# ── 下载柱状图 PNG ────────────────────────────────────────

@app.get(
    f"{API_PREFIX}/fit/{{analysis_id}}/chart/bar",
    tags=["报告下载"],
    summary="下载粒径均值对比柱状图 (PNG)",
    responses={200: {"content": {"image/png": {}}}},
)
def download_bar_chart(analysis_id: int, db: Session = Depends(get_db)):
    record = db.query(AnalysisRecord).filter(AnalysisRecord.id == analysis_id).first()
    if not record:
        raise HTTPException(404, f"分析记录 #{analysis_id} 不存在")

    stored = json.loads(record.results_json)
    results = _reconstruct_results(stored)
    bar_data = _compute_bar_data(results)

    fig, _ = plot_bar_chart(bar_data, results)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="image/png",
        headers={"Content-Disposition": "attachment; filename=\"bar_chart.png\""},
    )


# ── 下载分布拟合曲线 PNG ──────────────────────────────────

@app.get(
    f"{API_PREFIX}/fit/{{analysis_id}}/chart/distribution",
    tags=["报告下载"],
    summary="下载粒径分布拟合曲线图 (PNG)",
    responses={200: {"content": {"image/png": {}}}},
)
def download_distribution_chart(analysis_id: int, db: Session = Depends(get_db)):
    record = db.query(AnalysisRecord).filter(AnalysisRecord.id == analysis_id).first()
    if not record:
        raise HTTPException(404, f"分析记录 #{analysis_id} 不存在")

    stored = json.loads(record.results_json)
    results = _reconstruct_results(stored)

    fig = plot_distribution_grid(results)
    if fig is None:
        raise HTTPException(500, "无法生成分布曲线图（数据为空）")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="image/png",
        headers={"Content-Disposition": "attachment; filename=\"distribution_fit.png\""},
    )
