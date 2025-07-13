"""Database initialization utilities.

このモジュールはデータベースの初期化とセットアップ機能を提供します。
"""

import os
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.models.database import Base


def get_database_path() -> str:
    """環境変数からデータベースパスを取得します.

    Returns:
        データベースファイルの絶対パス

    Raises:
        ValueError: DATABASE_PATHが設定されていない場合
    """
    db_path = os.getenv("DATABASE_PATH")
    if not db_path:
        raise ValueError("DATABASE_PATH environment variable is not set")

    # 絶対パスに変換
    if not os.path.isabs(db_path):
        current_dir = os.getcwd()
        db_path = os.path.join(current_dir, db_path)

    return db_path


def create_database_directory(db_path: str) -> None:
    """データベースファイル用のディレクトリを作成します.

    Args:
        db_path: データベースファイルのパス
    """
    db_dir = os.path.dirname(db_path)
    if db_dir:
        Path(db_dir).mkdir(parents=True, exist_ok=True)


def create_engine_for_database(db_path: Optional[str] = None) -> Engine:
    """SQLAlchemyエンジンを作成します.

    Args:
        db_path: データベースファイルのパス（Noneの場合は環境変数から取得）

    Returns:
        SQLAlchemy Engine インスタンス

    Raises:
        ValueError: データベースパスが無効な場合
    """
    if db_path is None:
        db_path = get_database_path()

    # データベースディレクトリを作成
    create_database_directory(db_path)

    # SQLite接続文字列を作成
    database_url = f"sqlite:///{db_path}"

    # エンジンを作成（外部キー制約を有効化）
    engine = create_engine(
        database_url,
        echo=False,  # SQLログを無効化（本番環境用）
        connect_args={"check_same_thread": False}  # SQLiteのスレッド制限を無効化
    )

    # 外部キー制約を有効化
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.commit()

    return engine


def create_tables(engine: Engine) -> None:
    """データベーステーブルを作成します.

    Args:
        engine: SQLAlchemy Engine インスタンス
    """
    # SQLAlchemyモデルからテーブルを作成
    Base.metadata.create_all(engine)


def create_indexes(engine: Engine) -> None:
    """データベースインデックスを作成します.

    Args:
        engine: SQLAlchemy Engine インスタンス
    """
    # schema.sqlに基づくインデックスを作成
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status)",
        "CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_models_type ON models(type)",
        "CREATE INDEX IF NOT EXISTS idx_images_run_id ON images(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_images_hash ON images(hash)",
    ]

    with engine.connect() as conn:
        for index_sql in indexes:
            conn.execute(text(index_sql))
        conn.commit()


def create_triggers(engine: Engine) -> None:
    """データベーストリガーを作成します.

    Note:
        SQLAlchemyのeventシステムでupdated_atの自動更新を実装しているため、
        このメソッドは将来の拡張用として空実装にしています。

    Args:
        engine: SQLAlchemy Engine インスタンス
    """
    # SQLAlchemyのeventシステムを使用してupdated_atを自動更新しているため、
    # ここでは追加のトリガーは作成しません
    pass


def initialize_database(db_path: Optional[str] = None) -> Engine:
    """データベースを初期化します.

    この関数はテーブル、インデックス、トリガーを作成し、
    完全に設定されたデータベースを準備します。

    Args:
        db_path: データベースファイルのパス（Noneの場合は環境変数から取得）

    Returns:
        初期化されたSQLAlchemy Engine インスタンス

    Raises:
        ValueError: データベース設定が無効な場合
        Exception: データベース初期化に失敗した場合
    """
    try:
        # エンジンを作成
        engine = create_engine_for_database(db_path)

        # テーブルを作成
        create_tables(engine)

        # インデックスを作成
        create_indexes(engine)

        # トリガーを作成（現在は空実装）
        create_triggers(engine)

        return engine

    except Exception as e:
        raise Exception(f"Database initialization failed: {e}") from e


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    """セッションファクトリを作成します.

    Args:
        engine: SQLAlchemy Engine インスタンス

    Returns:
        セッションファクトリ
    """
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def verify_database_setup(engine: Engine) -> bool:
    """データベースのセットアップを検証します.

    Args:
        engine: SQLAlchemy Engine インスタンス

    Returns:
        True: セットアップが正常
        False: セットアップに問題がある
    """
    try:
        # テーブルの存在を確認
        with engine.connect() as conn:
            tables = [
                "models",
                "runs",
                "images",
                "tags",
                "run_loras",
                "run_tags"
            ]

            for table in tables:
                result = conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name=:table"),
                    {"table": table}
                )
                if not result.fetchone():
                    return False

            # 外部キー制約が有効かを確認
            result = conn.execute(text("PRAGMA foreign_keys"))
            row = result.fetchone()
            if row is None:
                return False
            foreign_keys_enabled = row[0]
            if not foreign_keys_enabled:
                return False

        return True

    except Exception:
        return False
