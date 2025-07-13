"""Comprehensive tests for YAML loader functionality.

このモジュールはYAMLローダーとバリデーション機能の
全機能をテストします。
"""

import os
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from src.models.database import Model, Run, RunLora
from src.utils.db_utils import DatabaseManager
from src.yaml_loader import (
    YAMLLoader,
    YAMLLoaderError,
    YAMLValidationError,
    YAMLValidator,
    load_single_yaml_file,
    load_yaml_files_from_data_directory,
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
    os.environ["DATABASE_PATH"] = temp_db_path
    manager = DatabaseManager()
    yield manager
    # クリーンアップ
    if "DATABASE_PATH" in os.environ:
        del os.environ["DATABASE_PATH"]


@pytest.fixture
def yaml_loader(db_manager):
    """テスト用のYAMLLoaderインスタンスを提供します."""
    return YAMLLoader(db_manager)


@pytest.fixture
def valid_yaml_data():
    """有効なYAMLデータを提供します."""
    return {
        "run_title": "Test Generation",
        "model": "SDXL-Turbo-0.9",
        "loras": ["test_lora_1", "test_lora_2"],
        "vae": "sdxl_vae.safetensors",
        "prompt": "masterpiece, 1girl, best quality",
        "negative": "lowres, bad anatomy, watermark",
        "cfg": 7.5,
        "steps": 25,
        "sampler": "DPM++ 2M",
        "seed": 123456,
        "width": 1024,
        "height": 1024,
        "source": "Test Source",
        "status": "Purchased"
    }


@pytest.fixture
def minimal_yaml_data():
    """最小限のYAMLデータを提供します."""
    return {
        "run_title": "Minimal Test",
        "prompt": "test prompt",
        "cfg": 7.0,
        "steps": 20,
        "sampler": "DPM++ 2M"
    }


@pytest.fixture
def temp_yaml_file(valid_yaml_data):
    """テスト用の一時YAMLファイルを提供します."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as tmp_file:
        yaml.dump(valid_yaml_data, tmp_file, default_flow_style=False, allow_unicode=True)
        tmp_file_path = tmp_file.name
    
    yield tmp_file_path
    
    # クリーンアップ
    if os.path.exists(tmp_file_path):
        os.unlink(tmp_file_path)


@pytest.fixture
def temp_yaml_directory():
    """テスト用の一時YAMLディレクトリを提供します."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


class TestYAMLValidator:
    """YAMLValidatorのテストクラス."""

    def test_validate_required_fields_success(self, valid_yaml_data):
        """必須フィールドの検証が成功することをテストします."""
        # 有効なデータでは例外が発生しないはず
        YAMLValidator.validate_required_fields(valid_yaml_data)

    def test_validate_required_fields_missing(self):
        """必須フィールドが不足している場合のエラーをテストします."""
        incomplete_data = {
            "run_title": "Test",
            # prompt, cfg, steps, sampler が不足
        }
        
        with pytest.raises(YAMLValidationError) as exc_info:
            YAMLValidator.validate_required_fields(incomplete_data)
        
        assert "Required fields missing" in str(exc_info.value)
        assert "prompt" in str(exc_info.value)

    def test_validate_data_types_success(self, valid_yaml_data):
        """データ型の検証が成功することをテストします."""
        # 有効なデータでは例外が発生しないはず
        YAMLValidator.validate_data_types(valid_yaml_data)

    def test_validate_data_types_invalid_string(self):
        """文字列フィールドが無効な場合のエラーをテストします."""
        invalid_data = {
            "run_title": 123,  # 数値（文字列でない）
            "prompt": "valid prompt",
            "cfg": 7.0,
            "steps": 25,
            "sampler": "DPM++ 2M"
        }
        
        with pytest.raises(YAMLValidationError) as exc_info:
            YAMLValidator.validate_data_types(invalid_data)
        
        assert "must be a string" in str(exc_info.value)

    def test_validate_data_types_invalid_cfg(self):
        """CFGが無効な型の場合のエラーをテストします."""
        invalid_data = {
            "run_title": "Test",
            "prompt": "test prompt",
            "cfg": "not_a_number",  # 文字列（数値でない）
            "steps": 25,
            "sampler": "DPM++ 2M"
        }
        
        with pytest.raises(YAMLValidationError) as exc_info:
            YAMLValidator.validate_data_types(invalid_data)
        
        assert "cfg" in str(exc_info.value)
        assert "number" in str(exc_info.value)

    def test_validate_data_types_invalid_loras(self):
        """LoRAリストが無効な場合のエラーをテストします."""
        invalid_data = {
            "run_title": "Test",
            "prompt": "test prompt",
            "cfg": 7.0,
            "steps": 25,
            "sampler": "DPM++ 2M",
            "loras": "not_a_list"  # 文字列（リストでない）
        }
        
        with pytest.raises(YAMLValidationError) as exc_info:
            YAMLValidator.validate_data_types(invalid_data)
        
        assert "loras" in str(exc_info.value)
        assert "list" in str(exc_info.value)

    def test_validate_ranges_success(self, valid_yaml_data):
        """範囲の検証が成功することをテストします."""
        # 有効なデータでは例外が発生しないはず
        YAMLValidator.validate_ranges(valid_yaml_data)

    def test_validate_ranges_cfg_out_of_range(self):
        """CFGが範囲外の場合のエラーをテストします."""
        invalid_data = {
            "run_title": "Test",
            "prompt": "test prompt",
            "cfg": 50.0,  # 範囲外（30.0を超える）
            "steps": 25,
            "sampler": "DPM++ 2M"
        }
        
        with pytest.raises(YAMLValidationError) as exc_info:
            YAMLValidator.validate_ranges(invalid_data)
        
        assert "cfg must be between" in str(exc_info.value)

    def test_validate_ranges_steps_out_of_range(self):
        """Stepsが範囲外の場合のエラーをテストします."""
        invalid_data = {
            "run_title": "Test",
            "prompt": "test prompt",
            "cfg": 7.0,
            "steps": 500,  # 範囲外（300を超える）
            "sampler": "DPM++ 2M"
        }
        
        with pytest.raises(YAMLValidationError) as exc_info:
            YAMLValidator.validate_ranges(invalid_data)
        
        assert "steps must be between" in str(exc_info.value)

    def test_validate_status_success(self, valid_yaml_data):
        """ステータスの検証が成功することをテストします."""
        # 有効なデータでは例外が発生しないはず
        YAMLValidator.validate_status(valid_yaml_data)

    def test_validate_status_invalid(self):
        """無効なステータスの場合のエラーをテストします."""
        invalid_data = {
            "run_title": "Test",
            "prompt": "test prompt",
            "cfg": 7.0,
            "steps": 25,
            "sampler": "DPM++ 2M",
            "status": "InvalidStatus"  # 無効なステータス
        }
        
        with pytest.raises(YAMLValidationError) as exc_info:
            YAMLValidator.validate_status(invalid_data)
        
        assert "status must be one of" in str(exc_info.value)

    def test_validate_complete_success(self, valid_yaml_data):
        """完全なバリデーションが成功することをテストします."""
        # 有効なデータでは例外が発生しないはず
        YAMLValidator.validate(valid_yaml_data)

    def test_validate_complete_minimal_success(self, minimal_yaml_data):
        """最小限のデータでバリデーションが成功することをテストします."""
        # 最小限のデータでも例外が発生しないはず
        YAMLValidator.validate(minimal_yaml_data)


class TestYAMLLoader:
    """YAMLLoaderのテストクラス."""

    def test_load_yaml_file_success(self, yaml_loader, temp_yaml_file):
        """YAMLファイルの読み込みが成功することをテストします."""
        data = yaml_loader.load_yaml_file(temp_yaml_file)
        
        assert isinstance(data, dict)
        assert "run_title" in data
        assert data["run_title"] == "Test Generation"

    def test_load_yaml_file_not_found(self, yaml_loader):
        """存在しないファイルの読み込みエラーをテストします."""
        with pytest.raises(YAMLLoaderError) as exc_info:
            yaml_loader.load_yaml_file("nonexistent_file.yaml")
        
        assert "YAML file not found" in str(exc_info.value)

    def test_load_yaml_file_invalid_format(self, yaml_loader):
        """無効なYAML形式のファイルのエラーをテストします."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            tmp_file.write("invalid: yaml: content: [")  # 無効なYAML
            tmp_file_path = tmp_file.name
        
        try:
            with pytest.raises(YAMLValidationError) as exc_info:
                yaml_loader.load_yaml_file(tmp_file_path)
            
            assert "Invalid YAML format" in str(exc_info.value)
        finally:
            os.unlink(tmp_file_path)

    def test_find_or_create_model_existing(self, yaml_loader, db_manager):
        """既存モデルの検索をテストします."""
        # 事前にモデルを作成
        existing_model = db_manager.create_record(
            Model, 
            name="existing_model", 
            type="checkpoint"
        )
        
        # 同じ名前のモデルを検索
        found_model = yaml_loader.find_or_create_model("existing_model")
        
        assert found_model.model_id == existing_model.model_id
        assert found_model.name == "existing_model"

    def test_find_or_create_model_new(self, yaml_loader):
        """新しいモデルの作成をテストします."""
        model = yaml_loader.find_or_create_model("new_model", "lora")
        
        assert model.model_id is not None
        assert model.name == "new_model"
        assert model.type == "lora"

    def test_create_lora_relationships(self, yaml_loader, db_manager):
        """LoRA関連付けの作成をテストします."""
        # 実行履歴を作成
        run = db_manager.create_record(
            Run,
            title="Test Run",
            prompt="test prompt",
            cfg=7.0,
            steps=20,
            sampler="DPM++ 2M"
        )
        
        # LoRA関連付けを作成
        lora_names = ["lora1", "lora2"]
        run_loras = yaml_loader.create_lora_relationships(run.run_id, lora_names)
        
        assert len(run_loras) == 2
        assert all(isinstance(rl, RunLora) for rl in run_loras)
        assert run_loras[0].weight == 1.0  # デフォルト重み

    def test_convert_yaml_to_run_data(self, yaml_loader, valid_yaml_data):
        """YAMLデータのRun用データ変換をテストします."""
        run_data = yaml_loader.convert_yaml_to_run_data(valid_yaml_data)
        
        assert run_data["title"] == valid_yaml_data["run_title"]
        assert run_data["prompt"] == valid_yaml_data["prompt"]
        assert run_data["cfg"] == valid_yaml_data["cfg"]
        assert run_data["steps"] == valid_yaml_data["steps"]
        assert run_data["sampler"] == valid_yaml_data["sampler"]
        assert run_data["status"] == valid_yaml_data["status"]

    def test_convert_yaml_to_run_data_minimal(self, yaml_loader, minimal_yaml_data):
        """最小限のYAMLデータの変換をテストします."""
        run_data = yaml_loader.convert_yaml_to_run_data(minimal_yaml_data)
        
        assert run_data["title"] == minimal_yaml_data["run_title"]
        assert run_data["prompt"] == minimal_yaml_data["prompt"]
        assert run_data["status"] == "Tried"  # デフォルトステータス

    def test_load_and_insert_success(self, yaml_loader, temp_yaml_file):
        """YAML読み込みとDB挿入の成功をテストします."""
        run = yaml_loader.load_and_insert(temp_yaml_file)
        
        assert run.run_id is not None
        assert run.title == "Test Generation"
        assert run.prompt == "masterpiece, 1girl, best quality"
        assert run.cfg == 7.5
        assert run.steps == 25

    def test_load_and_insert_with_loras(self, yaml_loader, temp_yaml_file, db_manager):
        """LoRA付きYAML読み込みとDB挿入をテストします."""
        run = yaml_loader.load_and_insert(temp_yaml_file)
        
        # LoRA関連付けが作成されているかチェック
        loras = db_manager.get_records(RunLora, filters={"run_id": run.run_id})
        assert len(loras) == 2  # test_lora_1, test_lora_2

    def test_load_directory_success(self, yaml_loader, temp_yaml_directory, valid_yaml_data):
        """ディレクトリからのYAML読み込みをテストします."""
        # 複数のYAMLファイルを作成
        for i in range(3):
            data = valid_yaml_data.copy()
            data["run_title"] = f"Test Run {i}"
            
            yaml_file = temp_yaml_directory / f"test_{i}.yaml"
            with open(yaml_file, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        
        # ディレクトリから読み込み
        runs = yaml_loader.load_directory(temp_yaml_directory)
        
        assert len(runs) == 3
        assert all(isinstance(run, Run) for run in runs)

    def test_load_directory_not_found(self, yaml_loader):
        """存在しないディレクトリのエラーをテストします."""
        with pytest.raises(YAMLLoaderError) as exc_info:
            yaml_loader.load_directory("nonexistent_directory")
        
        assert "Directory does not exist" in str(exc_info.value)

    def test_load_directory_no_yaml_files(self, yaml_loader, temp_yaml_directory):
        """YAMLファイルがないディレクトリのエラーをテストします."""
        # 空のディレクトリ
        with pytest.raises(YAMLLoaderError) as exc_info:
            yaml_loader.load_directory(temp_yaml_directory)
        
        assert "No YAML files found" in str(exc_info.value)

    def test_check_duplicate_run_none(self, yaml_loader, valid_yaml_data):
        """重複なしの場合のテストします."""
        duplicate = yaml_loader.check_duplicate_run(valid_yaml_data)
        assert duplicate is None

    def test_check_duplicate_run_found(self, yaml_loader, valid_yaml_data, db_manager):
        """重複ありの場合のテストします."""
        # 最初の実行履歴を作成
        run_data = yaml_loader.convert_yaml_to_run_data(valid_yaml_data)
        existing_run = db_manager.create_record(Run, **run_data)
        
        # 同じデータで重複チェック
        duplicate = yaml_loader.check_duplicate_run(valid_yaml_data)
        assert duplicate is not None
        assert duplicate.run_id == existing_run.run_id


class TestUtilityFunctions:
    """ユーティリティ関数のテストクラス."""

    def test_load_single_yaml_file(self, db_manager, temp_yaml_file):
        """単一YAMLファイル読み込み関数をテストします."""
        run = load_single_yaml_file(db_manager, temp_yaml_file)
        
        assert run.run_id is not None
        assert run.title == "Test Generation"

    def test_load_yaml_files_from_data_directory_not_found(self, db_manager):
        """data/yamlsディレクトリが存在しない場合のエラーをテストします."""
        # 現在のディレクトリにdata/yamlsが存在しないはず
        with pytest.raises(YAMLLoaderError) as exc_info:
            load_yaml_files_from_data_directory(db_manager)
        
        assert "Directory does not exist" in str(exc_info.value)


class TestErrorHandling:
    """エラーハンドリングのテストクラス."""

    def test_validation_error_propagation(self, yaml_loader):
        """バリデーションエラーの伝播をテストします."""
        invalid_data = {
            "run_title": "Test",
            # 必須フィールドが不足
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            yaml.dump(invalid_data, tmp_file)
            tmp_file_path = tmp_file.name
        
        try:
            with pytest.raises(YAMLValidationError):
                yaml_loader.load_and_insert(tmp_file_path)
        finally:
            os.unlink(tmp_file_path)

    def test_database_error_handling(self, yaml_loader, temp_yaml_file):
        """データベースエラーのハンドリングをテストします."""
        # データベース接続を破壊
        yaml_loader.db_manager.engine.dispose()
        
        with pytest.raises(YAMLLoaderError) as exc_info:
            yaml_loader.load_and_insert(temp_yaml_file)
        
        assert "Database error" in str(exc_info.value)


class TestEdgeCases:
    """エッジケースのテストクラス."""

    def test_yaml_with_null_values(self, yaml_loader):
        """NULL値を含むYAMLの処理をテストします."""
        data_with_nulls = {
            "run_title": "Test with Nulls",
            "prompt": "test prompt",
            "cfg": 7.0,
            "steps": 25,
            "sampler": "DPM++ 2M",
            "seed": None,  # NULL値
            "negative": None,  # NULL値
            "loras": None  # NULL値
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            yaml.dump(data_with_nulls, tmp_file, default_flow_style=False)
            tmp_file_path = tmp_file.name
        
        try:
            run = yaml_loader.load_and_insert(tmp_file_path)
            assert run.run_id is not None
            assert run.seed is None
            assert run.negative is None
        finally:
            os.unlink(tmp_file_path)

    def test_yaml_with_unicode_content(self, yaml_loader):
        """Unicode文字を含むYAMLの処理をテストします."""
        unicode_data = {
            "run_title": "日本語タイトル",
            "prompt": "美しい風景, masterpiece, 1girl",
            "negative": "低品質, ぼやけた",
            "cfg": 7.0,
            "steps": 25,
            "sampler": "DPM++ 2M",
            "source": "作者名 / URL"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as tmp_file:
            yaml.dump(unicode_data, tmp_file, default_flow_style=False, allow_unicode=True)
            tmp_file_path = tmp_file.name
        
        try:
            run = yaml_loader.load_and_insert(tmp_file_path)
            assert run.run_id is not None
            assert run.title == "日本語タイトル"
            assert "美しい風景" in run.prompt
        finally:
            os.unlink(tmp_file_path)

    def test_yaml_with_extreme_values(self, yaml_loader):
        """極端な値を含むYAMLの処理をテストします."""
        extreme_data = {
            "run_title": "Extreme Values",
            "prompt": "test prompt",
            "cfg": 0.1,  # 最小値
            "steps": 300,  # 最大値
            "sampler": "DPM++ 2M",
            "seed": 2**32 - 1  # 最大値
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            yaml.dump(extreme_data, tmp_file)
            tmp_file_path = tmp_file.name
        
        try:
            run = yaml_loader.load_and_insert(tmp_file_path)
            assert run.run_id is not None
            assert run.cfg == 0.1
            assert run.steps == 300
            assert run.seed == 2**32 - 1
        finally:
            os.unlink(tmp_file_path)