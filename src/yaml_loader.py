"""YAML loader and validation functionality.

このモジュールはYAMLファイルからデータを読み込み、バリデーションを行って
データベースに格納する機能を提供します。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from sqlalchemy.exc import SQLAlchemyError

from src.models.database import Model, Run, RunLora
from src.utils.db_utils import DatabaseManager


class YAMLValidationError(Exception):
    """YAML バリデーションエラー."""
    pass


class YAMLLoaderError(Exception):
    """YAML ローダーエラー."""
    pass


class YAMLValidator:
    """YAML データのバリデーション機能を提供するクラス."""

    # 必須フィールド
    REQUIRED_FIELDS = {
        "run_title",
        "prompt",
        "cfg",
        "steps",
        "sampler"
    }

    # 有効なステータス
    VALID_STATUSES = {"Purchased", "Tried", "Tuned", "Final"}

    # 有効な範囲
    CFG_RANGE = (0.1, 30.0)
    STEPS_RANGE = (1, 300)
    SEED_RANGE = (0, 2**32 - 1)

    @staticmethod
    def validate_required_fields(data: Dict[str, Any]) -> None:
        """必須フィールドの存在をチェックします.

        Args:
            data: バリデーション対象のYAMLデータ

        Raises:
            YAMLValidationError: 必須フィールドが不足している場合
        """
        missing_fields = YAMLValidator.REQUIRED_FIELDS - set(data.keys())
        if missing_fields:
            raise YAMLValidationError(
                f"Required fields missing: {', '.join(missing_fields)}"
            )

    @staticmethod
    def validate_data_types(data: Dict[str, Any]) -> None:
        """データ型の妥当性をチェックします.

        Args:
            data: バリデーション対象のYAMLデータ

        Raises:
            YAMLValidationError: データ型が不正な場合
        """
        # 文字列フィールド
        string_fields = ["run_title", "prompt", "sampler", "source", "status"]
        for field in string_fields:
            if field in data and not isinstance(data[field], str):
                raise YAMLValidationError(f"Field '{field}' must be a string")

        # 数値フィールド
        if "cfg" in data and not isinstance(data["cfg"], (int, float)):
            raise YAMLValidationError("Field 'cfg' must be a number")

        if "steps" in data and not isinstance(data["steps"], int):
            raise YAMLValidationError("Field 'steps' must be an integer")

        if "seed" in data and data["seed"] is not None:
            if not isinstance(data["seed"], int):
                raise YAMLValidationError("Field 'seed' must be an integer or null")

        # リストフィールド
        if "loras" in data and data["loras"] is not None:
            if not isinstance(data["loras"], list):
                raise YAMLValidationError("Field 'loras' must be a list")
            for lora in data["loras"]:
                if not isinstance(lora, str):
                    raise YAMLValidationError("LoRA names must be strings")

    @staticmethod
    def validate_ranges(data: Dict[str, Any]) -> None:
        """値の範囲をチェックします.

        Args:
            data: バリデーション対象のYAMLデータ

        Raises:
            YAMLValidationError: 値が範囲外の場合
        """
        # CFG範囲チェック
        if "cfg" in data:
            cfg = data["cfg"]
            if not (YAMLValidator.CFG_RANGE[0] <= cfg <= YAMLValidator.CFG_RANGE[1]):
                raise YAMLValidationError(
                    f"cfg must be between {YAMLValidator.CFG_RANGE[0]} and {YAMLValidator.CFG_RANGE[1]}"
                )

        # Steps範囲チェック
        if "steps" in data:
            steps = data["steps"]
            if not (YAMLValidator.STEPS_RANGE[0] <= steps <= YAMLValidator.STEPS_RANGE[1]):
                raise YAMLValidationError(
                    f"steps must be between {YAMLValidator.STEPS_RANGE[0]} and {YAMLValidator.STEPS_RANGE[1]}"
                )

        # Seed範囲チェック
        if "seed" in data and data["seed"] is not None:
            seed = data["seed"]
            if not (YAMLValidator.SEED_RANGE[0] <= seed <= YAMLValidator.SEED_RANGE[1]):
                raise YAMLValidationError(
                    f"seed must be between {YAMLValidator.SEED_RANGE[0]} and {YAMLValidator.SEED_RANGE[1]}"
                )

    @staticmethod
    def validate_status(data: Dict[str, Any]) -> None:
        """ステータスの妥当性をチェックします.

        Args:
            data: バリデーション対象のYAMLデータ

        Raises:
            YAMLValidationError: ステータスが無効な場合
        """
        if "status" in data:
            status = data["status"]
            if status not in YAMLValidator.VALID_STATUSES:
                raise YAMLValidationError(
                    f"status must be one of: {', '.join(YAMLValidator.VALID_STATUSES)}"
                )

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> None:
        """YAML データの完全なバリデーションを実行します.

        Args:
            data: バリデーション対象のYAMLデータ

        Raises:
            YAMLValidationError: バリデーションエラーが発生した場合
        """
        cls.validate_required_fields(data)
        cls.validate_data_types(data)
        cls.validate_ranges(data)
        cls.validate_status(data)


class YAMLLoader:
    """YAML ファイルの読み込みとデータベース挿入を行うクラス."""

    def __init__(self, db_manager: DatabaseManager):
        """YAMLLoaderを初期化します.

        Args:
            db_manager: データベース管理インスタンス
        """
        self.db_manager = db_manager
        self.validator = YAMLValidator()

    def load_yaml_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """YAML ファイルを読み込みます.

        Args:
            file_path: YAMLファイルのパス

        Returns:
            パースされたYAMLデータ

        Raises:
            YAMLLoaderError: ファイル読み込みエラー
            YAMLValidationError: YAMLパースエラー
        """
        try:
            with open(file_path, encoding='utf-8') as file:
                data = yaml.safe_load(file)

            if not isinstance(data, dict):
                raise YAMLValidationError("YAML file must contain a dictionary")

            return data

        except FileNotFoundError as e:
            raise YAMLLoaderError(f"YAML file not found: {file_path}") from e
        except yaml.YAMLError as e:
            raise YAMLValidationError(f"Invalid YAML format: {e}") from e
        except Exception as e:
            raise YAMLLoaderError(f"Error reading YAML file: {e}") from e

    def find_or_create_model(self, model_name: str, model_type: str = "checkpoint") -> Model:
        """モデルを検索し、存在しない場合は作成します.

        Args:
            model_name: モデル名
            model_type: モデルタイプ（デフォルト: "checkpoint"）

        Returns:
            Modelインスタンス

        Raises:
            YAMLLoaderError: モデル操作エラー
        """
        try:
            # 既存モデルを検索
            models = self.db_manager.get_records(Model, filters={"name": model_name})

            if models:
                return models[0]

            # モデルが存在しない場合は作成
            model = self.db_manager.create_record(
                Model,
                name=model_name,
                type=model_type
            )
            return model

        except SQLAlchemyError as e:
            raise YAMLLoaderError(f"Database error while handling model '{model_name}': {e}") from e

    def create_lora_relationships(
        self,
        run_id: int,
        lora_names: List[str],
        default_weight: float = 1.0
    ) -> List[RunLora]:
        """LoRA関連付けを作成します.

        Args:
            run_id: 実行履歴ID
            lora_names: LoRA名のリスト
            default_weight: デフォルトの重み

        Returns:
            作成されたRunLoraインスタンスのリスト

        Raises:
            YAMLLoaderError: LoRA関連付け作成エラー
        """
        run_loras = []

        try:
            for lora_name in lora_names:
                # LoRAモデルを検索または作成
                lora_model = self.find_or_create_model(lora_name, "lora")

                # RunLora関連付けを作成
                run_lora = self.db_manager.create_record(
                    RunLora,
                    run_id=run_id,
                    lora_id=lora_model.model_id,
                    weight=default_weight
                )
                run_loras.append(run_lora)

            return run_loras

        except SQLAlchemyError as e:
            raise YAMLLoaderError(f"Database error while creating LoRA relationships: {e}") from e

    def convert_yaml_to_run_data(self, yaml_data: Dict[str, Any]) -> Dict[str, Any]:
        """YAML データを Run モデル用のデータに変換します.

        Args:
            yaml_data: YAMLから読み込んだデータ

        Returns:
            Runモデル用のデータ辞書
        """
        # YAMLフィールドをRunモデルフィールドにマッピング
        run_data = {
            "title": yaml_data["run_title"],
            "prompt": yaml_data["prompt"],
            "cfg": yaml_data["cfg"],
            "steps": yaml_data["steps"],
            "sampler": yaml_data["sampler"],
        }

        # オプショナルフィールド
        if "negative" in yaml_data:
            run_data["negative"] = yaml_data["negative"]

        if "seed" in yaml_data:
            run_data["seed"] = yaml_data["seed"]

        if "width" in yaml_data:
            run_data["width"] = yaml_data["width"]

        if "height" in yaml_data:
            run_data["height"] = yaml_data["height"]

        if "source" in yaml_data:
            run_data["source"] = yaml_data["source"]

        if "status" in yaml_data:
            run_data["status"] = yaml_data["status"]
        else:
            run_data["status"] = "Tried"  # デフォルトステータス

        return run_data

    def load_and_insert(self, file_path: Union[str, Path]) -> Run:
        """YAML ファイルを読み込み、データベースに挿入します.

        Args:
            file_path: YAMLファイルのパス

        Returns:
            作成されたRunインスタンス

        Raises:
            YAMLValidationError: バリデーションエラー
            YAMLLoaderError: 読み込みまたは挿入エラー
        """
        try:
            # YAMLファイルを読み込み
            yaml_data = self.load_yaml_file(file_path)

            # バリデーション実行
            self.validator.validate(yaml_data)

            # モデルを処理
            model = None
            if "model" in yaml_data:
                model = self.find_or_create_model(yaml_data["model"])

            # Runデータを変換
            run_data = self.convert_yaml_to_run_data(yaml_data)
            if model:
                run_data["model_id"] = model.model_id

            # Runレコードを作成
            run = self.db_manager.create_record(Run, **run_data)

            # LoRA関連付けを作成
            if "loras" in yaml_data and yaml_data["loras"]:
                self.create_lora_relationships(run.run_id, yaml_data["loras"])

            return run

        except (YAMLValidationError, YAMLLoaderError):
            # 既知のエラーはそのまま再発生
            raise
        except SQLAlchemyError as e:
            raise YAMLLoaderError(f"Database error during insertion: {e}") from e
        except Exception as e:
            raise YAMLLoaderError(f"Unexpected error during load_and_insert: {e}") from e

    def load_directory(self, directory_path: Union[str, Path]) -> List[Run]:
        """ディレクトリ内のすべての YAML ファイルを読み込みます.

        Args:
            directory_path: YAMLファイルを含むディレクトリのパス

        Returns:
            作成されたRunインスタンスのリスト

        Raises:
            YAMLLoaderError: ディレクトリ処理エラー
        """
        directory = Path(directory_path)
        if not directory.exists():
            raise YAMLLoaderError(f"Directory does not exist: {directory_path}")

        if not directory.is_dir():
            raise YAMLLoaderError(f"Path is not a directory: {directory_path}")

        yaml_files = list(directory.glob("*.yaml")) + list(directory.glob("*.yml"))

        if not yaml_files:
            raise YAMLLoaderError(f"No YAML files found in directory: {directory_path}")

        runs = []
        errors = []

        for yaml_file in yaml_files:
            try:
                run = self.load_and_insert(yaml_file)
                runs.append(run)
            except (YAMLValidationError, YAMLLoaderError) as e:
                errors.append(f"Error in {yaml_file.name}: {e}")

        if errors:
            error_message = "Errors occurred while processing YAML files:\n" + "\n".join(errors)
            raise YAMLLoaderError(error_message)

        return runs

    def check_duplicate_run(self, yaml_data: Dict[str, Any]) -> Optional[Run]:
        """重複する実行履歴をチェックします.

        Args:
            yaml_data: チェック対象のYAMLデータ

        Returns:
            重複する実行履歴があればそのインスタンス、なければNone
        """
        try:
            # タイトルとプロンプトで重複チェック
            title = yaml_data["run_title"]
            prompt = yaml_data["prompt"]

            # 同じタイトルとプロンプトの実行履歴を検索
            existing_runs = self.db_manager.get_records(
                Run,
                filters={"title": title}
            )

            for run in existing_runs:
                if run.prompt == prompt:
                    return run

            return None

        except Exception:
            # エラーが発生した場合は重複なしとして処理
            return None


def load_yaml_files_from_data_directory(db_manager: DatabaseManager) -> List[Run]:
    """data/yamls/ ディレクトリからYAMLファイルを読み込みます.

    Args:
        db_manager: データベース管理インスタンス

    Returns:
        作成されたRunインスタンスのリスト

    Raises:
        YAMLLoaderError: 読み込みエラー
    """
    # プロジェクトルートを取得
    current_dir = Path.cwd()
    yaml_dir = current_dir / "data" / "yamls"

    loader = YAMLLoader(db_manager)
    return loader.load_directory(yaml_dir)


def load_single_yaml_file(
    db_manager: DatabaseManager,
    file_path: Union[str, Path]
) -> Run:
    """単一の YAML ファイルを読み込みます.

    Args:
        db_manager: データベース管理インスタンス
        file_path: YAMLファイルのパス

    Returns:
        作成されたRunインスタンス

    Raises:
        YAMLValidationError: バリデーションエラー
        YAMLLoaderError: 読み込みエラー
    """
    loader = YAMLLoader(db_manager)
    return loader.load_and_insert(file_path)
