"""在应用启动时以编程方式执行 Alembic 迁移到最新版本。

后端容器启动时调用 :func:`run_migrations`，等价于在容器内执行
``alembic upgrade head``：新库会跑 baseline 建表+灌种子，已是最新则什么都不做（幂等）。
Worker 不调用本函数——单一后端负责迁移，避免多进程并发迁移竞争。
"""

from pathlib import Path

from alembic import command
from alembic.config import Config


def alembic_config() -> Config:
    """构造指向本项目 alembic.ini / alembic 目录的 Config（使用绝对路径，
    不依赖运行时的当前工作目录）。"""
    backend_root = Path(__file__).resolve().parents[2]
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    return cfg


def run_migrations() -> None:
    command.upgrade(alembic_config(), "head")
