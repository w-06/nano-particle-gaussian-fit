"""SQLAlchemy ORM 模型 + 数据库初始化"""

import os
from datetime import datetime, timezone

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class AnalysisRecord(Base):
    """拟合分析记录表 — 每条记录对应一次 Excel 上传 + 拟合"""

    __tablename__ = "analysis_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(256), nullable=False, comment="上传的原始文件名")
    sheet_name = Column(String(128), nullable=False, comment="选用的工作表名称")
    created_at = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="分析时间 (UTC)",
    )
    results_json = Column(Text, nullable=False, comment="完整拟合结果 JSON（含坐标数组）")
    groups_config_json = Column(Text, nullable=False, comment="分组配置 JSON")


# ── 数据库初始化 ──────────────────────────────────────────

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(_PROJECT_ROOT, "data")
DB_PATH = os.path.join(DB_DIR, "analysis.db")

os.makedirs(DB_DIR, exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 自动建表（生产环境建议用 Alembic 迁移）
Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI 依赖注入：获取数据库会话，请求结束后自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
