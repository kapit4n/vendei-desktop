from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


@dataclass(frozen=True)
class DbConfig:
    sqlite_path: Path

    @staticmethod
    def default() -> "DbConfig":
        base = Path.cwd() / "data"
        base.mkdir(parents=True, exist_ok=True)
        return DbConfig(sqlite_path=base / "vendei.sqlite")


def create_sqlite_engine(cfg: DbConfig) -> Engine:
    # SQLite concurrency tuning: WAL + busy timeout.
    url = f"sqlite:///{cfg.sqlite_path}"
    engine = create_engine(
        url,
        echo=False,
        future=True,
        connect_args={"timeout": 60},
    )
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
        conn.exec_driver_sql("PRAGMA busy_timeout=60000;")
        conn.exec_driver_sql("PRAGMA foreign_keys=ON;")
        conn.commit()
    return engine


def create_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

