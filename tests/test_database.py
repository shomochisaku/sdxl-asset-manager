"""Comprehensive tests for database models and utilities.

このモジュールはSQLAlchemyモデルとデータベースユーティリティの
全機能をテストします。
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src.models.database import Base, Image, Model, Run, RunLora, RunTag, Tag
from src.utils.db_init import (
    create_engine_for_database,
    initialize_database,
    verify_database_setup,
)
from src.utils.db_utils import (
    DatabaseManager,
    create_run_with_loras,
    get_images_for_run,
    get_loras_for_run,
    get_models_by_type,
    get_recent_runs,
    get_runs_by_status,
    get_tags_for_run,
    search_runs_by_prompt,
)


@pytest.fixture
def temp_db_path():
    """テスト用の一時データベースパスを提供します."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp_file:
        db_path = tmp_file.name
    yield db_path
    # クリーンアップ
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def db_manager(temp_db_path):
    """テスト用のDatabaseManagerインスタンスを提供します."""
    # DATABASE_PATH環境変数を設定
    os.environ["DATABASE_PATH"] = temp_db_path
    manager = DatabaseManager()
    yield manager
    # クリーンアップ
    if "DATABASE_PATH" in os.environ:
        del os.environ["DATABASE_PATH"]


@pytest.fixture
def sample_model_data():
    """テスト用のモデルデータを提供します."""
    return {
        "name": "test_model",
        "type": "checkpoint",
        "filename": "test_model.safetensors",
        "source": "https://example.com/model",
        "notes": "Test model for unit testing",
    }


@pytest.fixture
def sample_run_data():
    """テスト用の実行履歴データを提供します."""
    return {
        "title": "Test Generation",
        "prompt": "a beautiful landscape",
        "negative": "blurry, low quality",
        "cfg": 7.5,
        "steps": 25,
        "sampler": "DPM++ 2M",
        "width": 512,
        "height": 768,
        "status": "Tried",
    }


class TestDatabaseModels:
    """SQLAlchemyモデルのテストクラス."""

    def test_model_creation(self, db_manager, sample_model_data):
        """Modelの作成をテストします."""
        model = db_manager.create_record(Model, **sample_model_data)
        
        assert model.model_id is not None
        assert model.name == sample_model_data["name"]
        assert model.type == sample_model_data["type"]
        assert model.filename == sample_model_data["filename"]
        assert model.source == sample_model_data["source"]
        assert model.notes == sample_model_data["notes"]
        assert isinstance(model.created_at, datetime)
        assert isinstance(model.updated_at, datetime)

    def test_model_unique_constraint(self, db_manager, sample_model_data):
        """Modelの名前のユニーク制約をテストします."""
        db_manager.create_record(Model, **sample_model_data)
        
        with pytest.raises(IntegrityError):
            db_manager.create_record(Model, **sample_model_data)

    def test_run_creation(self, db_manager, sample_run_data):
        """Runの作成をテストします."""
        run = db_manager.create_record(Run, **sample_run_data)
        
        assert run.run_id is not None
        assert run.title == sample_run_data["title"]
        assert run.prompt == sample_run_data["prompt"]
        assert run.cfg == sample_run_data["cfg"]
        assert run.steps == sample_run_data["steps"]
        assert run.status == sample_run_data["status"]
        assert isinstance(run.created_at, datetime)

    def test_run_with_model_relationship(self, db_manager, sample_model_data, sample_run_data):
        """RunとModelの関連をテストします."""
        model = db_manager.create_record(Model, **sample_model_data)
        
        sample_run_data["model_id"] = model.model_id
        run = db_manager.create_record(Run, **sample_run_data)
        
        # 関連が正しく設定されているかチェック
        retrieved_run = db_manager.get_record_by_id(Run, run.run_id)
        assert retrieved_run.model_id == model.model_id

    def test_image_creation(self, db_manager, sample_run_data):
        """Imageの作成をテストします."""
        run = db_manager.create_record(Run, **sample_run_data)
        
        image_data = {
            "run_id": run.run_id,
            "filename": "test_image.png",
            "filepath": "/test/path/test_image.png",
            "width": 512,
            "height": 768,
            "file_size": 1024 * 1024,
            "hash": "abc123def456",
            "image_metadata": '{"prompt": "test"}',
        }
        
        image = db_manager.create_record(Image, **image_data)
        assert image.image_id is not None
        assert image.run_id == run.run_id
        assert image.filename == "test_image.png"
        assert image.width == 512
        assert image.height == 768

    def test_tag_creation(self, db_manager):
        """Tagの作成をテストします."""
        tag_data = {
            "name": "portrait",
            "category": "style",
        }
        
        tag = db_manager.create_record(Tag, **tag_data)
        assert tag.tag_id is not None
        assert tag.name == "portrait"
        assert tag.category == "style"

    def test_run_lora_relationship(self, db_manager, sample_model_data, sample_run_data):
        """RunLoRAの多対多関連をテストします."""
        # チェックポイントモデルを作成
        checkpoint_model = db_manager.create_record(Model, **sample_model_data)
        
        # LoRAモデルを作成
        lora_data = sample_model_data.copy()
        lora_data["name"] = "test_lora"
        lora_data["type"] = "lora"
        lora_model = db_manager.create_record(Model, **lora_data)
        
        # 実行履歴を作成
        sample_run_data["model_id"] = checkpoint_model.model_id
        run = db_manager.create_record(Run, **sample_run_data)
        
        # RunLoRA関連を作成
        run_lora_data = {
            "run_id": run.run_id,
            "lora_id": lora_model.model_id,
            "weight": 0.8,
        }
        
        run_lora = db_manager.create_record(RunLora, **run_lora_data)
        assert run_lora.run_id == run.run_id
        assert run_lora.lora_id == lora_model.model_id
        assert run_lora.weight == 0.8

    def test_run_tag_relationship(self, db_manager, sample_run_data):
        """RunTagの多対多関連をテストします."""
        # 実行履歴を作成
        run = db_manager.create_record(Run, **sample_run_data)
        
        # タグを作成
        tag = db_manager.create_record(Tag, name="test_tag", category="style")
        
        # RunTag関連を作成
        run_tag_data = {
            "run_id": run.run_id,
            "tag_id": tag.tag_id,
        }
        
        run_tag = db_manager.create_record(RunTag, **run_tag_data)
        assert run_tag.run_id == run.run_id
        assert run_tag.tag_id == tag.tag_id


class TestDatabaseInitialization:
    """データベース初期化のテストクラス."""

    def test_database_initialization(self, temp_db_path):
        """データベース初期化をテストします."""
        os.environ["DATABASE_PATH"] = temp_db_path
        
        try:
            engine = initialize_database()
            assert engine is not None
            assert verify_database_setup(engine)
        finally:
            if "DATABASE_PATH" in os.environ:
                del os.environ["DATABASE_PATH"]

    def test_create_engine_for_database(self, temp_db_path):
        """エンジン作成をテストします."""
        engine = create_engine_for_database(temp_db_path)
        assert engine is not None
        
        # 外部キー制約が有効かチェック
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA foreign_keys"))
            assert result.fetchone()[0] == 1

    def test_verify_database_setup(self, db_manager):
        """データベースセットアップ検証をテストします."""
        assert verify_database_setup(db_manager.engine)


class TestDatabaseUtilities:
    """データベースユーティリティのテストクラス."""

    def test_crud_operations(self, db_manager, sample_model_data):
        """基本的なCRUD操作をテストします."""
        # Create
        model = db_manager.create_record(Model, **sample_model_data)
        assert model.model_id is not None
        
        # Read
        retrieved_model = db_manager.get_record_by_id(Model, model.model_id)
        assert retrieved_model is not None
        assert retrieved_model.name == sample_model_data["name"]
        
        # Update
        updated_model = db_manager.update_record(
            Model, model.model_id, notes="Updated notes"
        )
        assert updated_model is not None
        assert updated_model.notes == "Updated notes"
        
        # Delete
        success = db_manager.delete_record(Model, model.model_id)
        assert success
        
        # Verify deletion
        deleted_model = db_manager.get_record_by_id(Model, model.model_id)
        assert deleted_model is None

    def test_get_records_with_filters(self, db_manager, sample_model_data):
        """フィルタ付きレコード取得をテストします."""
        # 複数のモデルを作成
        model1_data = sample_model_data.copy()
        model1_data["name"] = "model1"
        model1_data["type"] = "checkpoint"
        
        model2_data = sample_model_data.copy()
        model2_data["name"] = "model2"
        model2_data["type"] = "lora"
        
        db_manager.create_record(Model, **model1_data)
        db_manager.create_record(Model, **model2_data)
        
        # フィルタでLoRAモデルのみ取得
        lora_models = db_manager.get_records(Model, filters={"type": "lora"})
        assert len(lora_models) == 1
        assert lora_models[0].type == "lora"

    def test_get_models_by_type(self, db_manager, sample_model_data):
        """タイプ別モデル取得をテストします."""
        # チェックポイントモデルを作成
        checkpoint_data = sample_model_data.copy()
        checkpoint_data["type"] = "checkpoint"
        db_manager.create_record(Model, **checkpoint_data)
        
        # LoRAモデルを作成
        lora_data = sample_model_data.copy()
        lora_data["name"] = "test_lora"
        lora_data["type"] = "lora"
        db_manager.create_record(Model, **lora_data)
        
        # チェックポイントモデルのみ取得
        checkpoint_models = get_models_by_type(db_manager, "checkpoint")
        assert len(checkpoint_models) == 1
        assert checkpoint_models[0].type == "checkpoint"

    def test_get_runs_by_status(self, db_manager, sample_run_data):
        """ステータス別実行履歴取得をテストします."""
        # 異なるステータスの実行履歴を作成
        run1_data = sample_run_data.copy()
        run1_data["title"] = "Run 1"
        run1_data["status"] = "Tried"
        
        run2_data = sample_run_data.copy()
        run2_data["title"] = "Run 2"
        run2_data["status"] = "Final"
        
        db_manager.create_record(Run, **run1_data)
        db_manager.create_record(Run, **run2_data)
        
        # Triedステータスのみ取得
        tried_runs = get_runs_by_status(db_manager, "Tried")
        assert len(tried_runs) == 1
        assert tried_runs[0].status == "Tried"

    def test_search_runs_by_prompt(self, db_manager, sample_run_data):
        """プロンプト検索をテストします."""
        # 検索対象の実行履歴を作成
        run1_data = sample_run_data.copy()
        run1_data["title"] = "Landscape Test"
        run1_data["prompt"] = "beautiful mountain landscape"
        
        run2_data = sample_run_data.copy()
        run2_data["title"] = "Portrait Test"
        run2_data["prompt"] = "portrait of a woman"
        
        db_manager.create_record(Run, **run1_data)
        db_manager.create_record(Run, **run2_data)
        
        # プロンプトで検索
        landscape_runs = search_runs_by_prompt(db_manager, "landscape")
        assert len(landscape_runs) == 1
        assert "landscape" in landscape_runs[0].prompt

    def test_create_run_with_loras(self, db_manager, sample_model_data, sample_run_data):
        """LoRA付き実行履歴作成をテストします."""
        # モデルを作成
        checkpoint_model = db_manager.create_record(Model, **sample_model_data)
        
        lora_data = sample_model_data.copy()
        lora_data["name"] = "test_lora"
        lora_data["type"] = "lora"
        lora_model = db_manager.create_record(Model, **lora_data)
        
        # LoRA設定
        lora_configs = [
            {"lora_id": lora_model.model_id, "weight": 0.8}
        ]
        
        # LoRA付き実行履歴を作成
        sample_run_data["model_id"] = checkpoint_model.model_id
        run = create_run_with_loras(db_manager, sample_run_data, lora_configs)
        
        assert run.run_id is not None
        
        # LoRA関連付けが作成されているかチェック
        loras = get_loras_for_run(db_manager, run.run_id)
        assert len(loras) == 1
        assert loras[0].lora_id == lora_model.model_id
        assert loras[0].weight == 0.8

    def test_get_recent_runs(self, db_manager, sample_run_data):
        """最近の実行履歴取得をテストします."""
        # 複数の実行履歴を作成
        for i in range(5):
            run_data = sample_run_data.copy()
            run_data["title"] = f"Run {i}"
            db_manager.create_record(Run, **run_data)
        
        # 最近の3件を取得
        recent_runs = get_recent_runs(db_manager, limit=3)
        assert len(recent_runs) == 3
        
        # 作成日時の降順でソートされているかチェック
        for i in range(len(recent_runs) - 1):
            assert recent_runs[i].created_at >= recent_runs[i + 1].created_at

    def test_cascade_deletion(self, db_manager, sample_run_data):
        """カスケード削除をテストします."""
        # 実行履歴を作成
        run = db_manager.create_record(Run, **sample_run_data)
        
        # 画像を作成
        image_data = {
            "run_id": run.run_id,
            "filename": "test.png",
            "filepath": "/test/test.png",
        }
        image = db_manager.create_record(Image, **image_data)
        
        # 実行履歴を削除
        db_manager.delete_record(Run, run.run_id)
        
        # 画像も削除されているかチェック
        deleted_image = db_manager.get_record_by_id(Image, image.image_id)
        assert deleted_image is None


class TestErrorHandling:
    """エラーハンドリングのテストクラス."""

    def test_missing_database_path(self):
        """DATABASE_PATH環境変数が未設定の場合のエラーをテストします."""
        # 環境変数を削除
        if "DATABASE_PATH" in os.environ:
            del os.environ["DATABASE_PATH"]
        
        with pytest.raises(Exception, match="Database initialization failed"):
            DatabaseManager()

    def test_invalid_record_id(self, db_manager):
        """存在しないレコードIDでの操作をテストします."""
        # 存在しないIDでの取得
        model = db_manager.get_record_by_id(Model, 99999)
        assert model is None
        
        # 存在しないIDでの更新
        updated_model = db_manager.update_record(Model, 99999, name="Updated")
        assert updated_model is None
        
        # 存在しないIDでの削除
        success = db_manager.delete_record(Model, 99999)
        assert not success