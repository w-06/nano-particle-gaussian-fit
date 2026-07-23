"""Pydantic 数据校验模型 — FastAPI 请求/响应"""

from pydantic import BaseModel, Field


# ── 拟合结果 ──────────────────────────────────────────────

class FitResultItem(BaseModel):
    """单个样本的拟合结果"""
    sample_name: str
    mean_nm: float = Field(description="几何平均粒径 (nm)")
    geo_sigma: float = Field(description="几何标准差 (GSD)")
    R2: float = Field(description="拟合优度 R²")


class GroupResult(BaseModel):
    """一组样本的拟合结果汇总"""
    group_name: str
    results: list[FitResultItem]
    mean_avg: float = Field(description="组内平均粒径均值 (nm)")
    geo_sigma_avg: float = Field(description="组内平均 GSD")
    r2_avg: float = Field(description="组内平均 R²")


class BarDataItem(BaseModel):
    """柱状图数据点"""
    group: str
    mean: float
    sd: float
    n: int


class FitResponse(BaseModel):
    """拟合完成后的完整响应"""
    analysis_id: int
    filename: str
    sheet_name: str
    groups: list[GroupResult]
    bar_data: list[BarDataItem]
    download_urls: dict[str, str] = Field(
        description="报告和图表下载链接",
        default_factory=dict,
    )


# ── 历史记录 ──────────────────────────────────────────────

class AnalysisSummary(BaseModel):
    """历史分析记录摘要"""
    id: int
    filename: str
    sheet_name: str
    created_at: str
    sample_count: int
    group_count: int

    class Config:
        from_attributes = True


class AnalysisListResponse(BaseModel):
    """历史分析列表"""
    total: int
    items: list[AnalysisSummary]


# ── 通用 ──────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
