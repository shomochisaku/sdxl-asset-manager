"""Database utilities for basic operations.

このモジュールは接続管理、セッション管理、基本的なCRUD操作を提供します。
"""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Type, TypeVar, cast

from sqlalchemy import desc, or_
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, joinedload, sessionmaker

from src.models.database import Base, Image, Model, Run, RunLora, RunTag
from src.utils.db_init import get_session_factory, initialize_database

# TypeVarを定義してジェネリック型をサポート
ModelType = TypeVar("ModelType", bound=Base)


class DatabaseManager:
    """データベース管理クラス.

    エンジンとセッションファクトリを管理し、データベース操作の
    コンテキストマネージャとユーティリティメソッドを提供します。
    """

    def __init__(self, db_path: Optional[str] = None):
        """DatabaseManagerを初期化します.

        Args:
            db_path: データベースファイルのパス（Noneの場合は環境変数から取得）
        """
        self.engine: Engine = initialize_database(db_path)
        self.session_factory: sessionmaker[Session] = get_session_factory(self.engine)

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """データベースセッションのコンテキストマネージャ.

        Yields:
            SQLAlchemy Session インスタンス

        Raises:
            SQLAlchemyError: データベース操作エラー
        """
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_record(self, model_class: Type[ModelType], **kwargs) -> ModelType:
        """新しいレコードを作成します.

        Args:
            model_class: モデルクラス
            **kwargs: レコードの属性

        Returns:
            作成されたレコードインスタンス

        Raises:
            SQLAlchemyError: データベース操作エラー
        """
        with self.get_session() as session:
            record = model_class(**kwargs)
            session.add(record)
            session.flush()  # IDを取得するためにflush
            session.refresh(record)  # 最新の状態を取得
            session.expunge(record)  # セッションから切り離してDetachedInstanceErrorを防ぐ
            return record

    def get_record_by_id(
        self, model_class: Type[ModelType], record_id: int
    ) -> Optional[ModelType]:
        """IDでレコードを取得します.

        Args:
            model_class: モデルクラス
            record_id: レコードID

        Returns:
            レコードインスタンス（見つからない場合はNone）
        """
        with self.get_session() as session:
            # SQLAlchemy introspection to get primary key column
            primary_key = next(iter(model_class.__table__.primary_key))
            record = session.query(model_class).filter(primary_key == record_id).first()
            if record:
                session.expunge(record)  # セッションから切り離してDetachedInstanceErrorを防ぐ
            return cast(Optional[ModelType], record)

    def get_records(
        self,
        model_class: Type[ModelType],
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[ModelType]:
        """条件に基づいてレコードを取得します.

        Args:
            model_class: モデルクラス
            filters: フィルタ条件の辞書
            order_by: ソート用カラム名
            limit: 取得件数制限
            offset: オフセット

        Returns:
            レコードインスタンスのリスト
        """
        with self.get_session() as session:
            query = session.query(model_class)

            # フィルタを適用
            if filters:
                for key, value in filters.items():
                    if hasattr(model_class, key):
                        query = query.filter(getattr(model_class, key) == value)

            # ソートを適用
            if order_by:
                if hasattr(model_class, order_by):
                    query = query.order_by(getattr(model_class, order_by))

            # ページネーションを適用
            if offset is not None:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)

            records = query.all()
            for record in records:
                session.expunge(record)  # セッションから切り離してDetachedInstanceErrorを防ぐ
            return cast(List[ModelType], records)

    def update_record(
        self, model_class: Type[ModelType], record_id: int, **kwargs
    ) -> Optional[ModelType]:
        """レコードを更新します.

        Args:
            model_class: モデルクラス
            record_id: レコードID
            **kwargs: 更新する属性

        Returns:
            更新されたレコードインスタンス（見つからない場合はNone）

        Raises:
            SQLAlchemyError: データベース操作エラー
        """
        with self.get_session() as session:
            # SQLAlchemy introspection to get primary key column
            primary_key = next(iter(model_class.__table__.primary_key))
            record = session.query(model_class).filter(primary_key == record_id).first()

            if record:
                for key, value in kwargs.items():
                    if hasattr(record, key):
                        setattr(record, key, value)
                session.flush()
                session.refresh(record)
                session.expunge(record)  # セッションから切り離してDetachedInstanceErrorを防ぐ
                return record
            return None

    def delete_record(self, model_class: Type[ModelType], record_id: int) -> bool:
        """レコードを削除します.

        Args:
            model_class: モデルクラス
            record_id: レコードID

        Returns:
            True: 削除成功、False: レコードが見つからない

        Raises:
            SQLAlchemyError: データベース操作エラー
        """
        with self.get_session() as session:
            # SQLAlchemy introspection to get primary key column
            primary_key = next(iter(model_class.__table__.primary_key))
            record = session.query(model_class).filter(primary_key == record_id).first()

            if record:
                session.delete(record)
                return True
            return False


# 専用のヘルパー関数

def get_models_by_type(db_manager: DatabaseManager, model_type: str) -> List[Model]:
    """タイプ別にモデルを取得します.

    Args:
        db_manager: DatabaseManagerインスタンス
        model_type: モデルタイプ（checkpoint, lora, vae, controlnet）

    Returns:
        指定されたタイプのモデルリスト
    """
    return db_manager.get_records(Model, filters={"type": model_type})


def get_runs_by_status(db_manager: DatabaseManager, status: str) -> List[Run]:
    """ステータス別に実行履歴を取得します.

    Args:
        db_manager: DatabaseManagerインスタンス
        status: ステータス（Purchased, Tried, Tuned, Final）

    Returns:
        指定されたステータスの実行履歴リスト
    """
    return db_manager.get_records(Run, filters={"status": status})


def get_recent_runs(db_manager: DatabaseManager, limit: int = 10) -> List[Run]:
    """最近の実行履歴を取得します.

    Args:
        db_manager: DatabaseManagerインスタンス
        limit: 取得件数

    Returns:
        最近の実行履歴リスト
    """
    with db_manager.get_session() as session:
        records = (
            session.query(Run)
            .order_by(desc(Run.created_at))
            .limit(limit)
            .all()
        )
        for record in records:
            session.expunge(record)  # セッションから切り離してDetachedInstanceErrorを防ぐ
        return records


def search_runs_by_prompt(
    db_manager: DatabaseManager, search_term: str, limit: int = 50
) -> List[Run]:
    """プロンプトで実行履歴を検索します.

    Args:
        db_manager: DatabaseManagerインスタンス
        search_term: 検索キーワード
        limit: 取得件数制限

    Returns:
        検索にマッチした実行履歴リスト
    """
    with db_manager.get_session() as session:
        records = (
            session.query(Run)
            .filter(
                or_(
                    Run.prompt.contains(search_term),
                    Run.title.contains(search_term),
                )
            )
            .order_by(desc(Run.created_at))
            .limit(limit)
            .all()
        )
        for record in records:
            session.expunge(record)  # セッションから切り離してDetachedInstanceErrorを防ぐ
        return records


def get_images_for_run(db_manager: DatabaseManager, run_id: int) -> List[Image]:
    """指定された実行履歴の画像を取得します.

    Args:
        db_manager: DatabaseManagerインスタンス
        run_id: 実行履歴ID

    Returns:
        指定された実行履歴の画像リスト
    """
    return db_manager.get_records(Image, filters={"run_id": run_id})


def get_loras_for_run(db_manager: DatabaseManager, run_id: int) -> List[RunLora]:
    """指定された実行履歴のLoRA情報を取得します.

    Args:
        db_manager: DatabaseManagerインスタンス
        run_id: 実行履歴ID

    Returns:
        指定された実行履歴のLoRA関連付けリスト
    """
    return db_manager.get_records(RunLora, filters={"run_id": run_id})


def get_tags_for_run(db_manager: DatabaseManager, run_id: int) -> List[RunTag]:
    """指定された実行履歴のタグ情報を取得します.

    Args:
        db_manager: DatabaseManagerインスタンス
        run_id: 実行履歴ID

    Returns:
        指定された実行履歴のタグ関連付けリスト
    """
    return db_manager.get_records(RunTag, filters={"run_id": run_id})


def create_run_with_loras(
    db_manager: DatabaseManager,
    run_data: Dict[str, Any],
    lora_configs: List[Dict[str, Any]],
) -> Run:
    """LoRA設定付きの実行履歴を作成します.

    Args:
        db_manager: DatabaseManagerインスタンス
        run_data: 実行履歴データ
        lora_configs: LoRA設定のリスト [{"lora_id": int, "weight": float}, ...]

    Returns:
        作成された実行履歴インスタンス

    Raises:
        SQLAlchemyError: データベース操作エラー
    """
    with db_manager.get_session() as session:
        # 実行履歴を作成
        run = Run(**run_data)
        session.add(run)
        session.flush()  # run_idを取得

        # LoRA関連付けを作成
        for lora_config in lora_configs:
            run_lora = RunLora(
                run_id=run.run_id,
                lora_id=lora_config["lora_id"],
                weight=lora_config.get("weight", 1.0),
            )
            session.add(run_lora)

        session.flush()
        session.refresh(run)
        session.expunge(run)  # セッションから切り離してDetachedInstanceErrorを防ぐ
        return run


def export_runs_with_relations(
    db_manager: DatabaseManager,
    filters: Optional[Dict[str, Any]] = None,
    run_ids: Optional[List[int]] = None,
    since_date: Optional[str] = None,
    until_date: Optional[str] = None,
    limit: Optional[int] = None,
    order_by: str = "created_at"
) -> List[Dict[str, Any]]:
    """関連データを含む実行履歴をエクスポート用に取得します.

    このファンクションは適切なeager loadingを使用してDetachedInstanceErrorを回避し、
    session.expunge()後にも安全にアクセスできるシリアライズ済みデータを返します。

    Args:
        db_manager: DatabaseManagerインスタンス
        filters: フィルタ条件の辞書
        run_ids: 特定のRun IDのリスト
        since_date: 開始日時（ISO 8601形式）
        until_date: 終了日時（ISO 8601形式）
        limit: 取得件数制限
        order_by: ソート用カラム名

    Returns:
        シリアライズ済みの実行履歴データのリスト

    Raises:
        ValueError: 日付形式が無効な場合
        SQLAlchemyError: データベース操作エラー
    """
    with db_manager.get_session() as session:
        # Eager loadingで関連データを先読み
        query = session.query(Run).options(
            joinedload(Run.model),
            joinedload(Run.loras).joinedload(RunLora.lora_model),
            joinedload(Run.images),
            joinedload(Run.tags).joinedload(RunTag.tag)
        )

        # フィルタを適用
        if filters:
            for key, value in filters.items():
                if hasattr(Run, key):
                    query = query.filter(getattr(Run, key) == value)

        # Run IDが指定されている場合
        if run_ids:
            query = query.filter(Run.run_id.in_(run_ids))

        # 日付範囲フィルタ
        if since_date:
            from datetime import datetime
            try:
                since_dt = datetime.fromisoformat(since_date.replace('Z', '+00:00'))
                query = query.filter(Run.created_at >= since_dt)
            except ValueError as e:
                raise ValueError(f"Invalid since_date format: {since_date}") from e

        if until_date:
            from datetime import datetime
            try:
                until_dt = datetime.fromisoformat(until_date.replace('Z', '+00:00'))
                query = query.filter(Run.created_at <= until_dt)
            except ValueError as e:
                raise ValueError(f"Invalid until_date format: {until_date}") from e

        # ソートを適用
        if order_by and hasattr(Run, order_by):
            query = query.order_by(getattr(Run, order_by))

        # 制限を適用
        if limit is not None:
            query = query.limit(limit)

        # データを取得
        runs = query.all()

        # sessionが生きている間にto_dict()を実行してシリアライズ
        serialized_runs = []
        for run in runs:
            serialized_runs.append(run.to_dict())

        return serialized_runs
