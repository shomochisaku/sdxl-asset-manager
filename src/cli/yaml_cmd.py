"""YAML操作コマンド.

このモジュールはYAMLファイルの読み込み、検証、エクスポート機能を提供します。
"""

import json
from pathlib import Path
from typing import Optional

import click
import yaml

from src.models.database import Run
from src.yaml_loader import (
    YAMLLoader,
    YAMLLoaderError,
    YAMLValidationError,
)

from .utils import (
    CliState,
    display_error,
    display_info,
    display_success,
    display_table,
    display_warning,
    format_datetime,
    handle_database_error,
    output_json,
    output_yaml,
    progress_bar,
)


@click.group(name='yaml')
@click.pass_context
def yaml_commands(ctx: click.Context) -> None:
    """YAML操作コマンド.

    YAMLファイルの読み込み、検証、エクスポート機能を提供します。
    """
    pass


@yaml_commands.command()
@click.argument('path', type=click.Path(exists=True))
@click.option(
    '--recursive', '-r',
    is_flag=True,
    help='サブディレクトリも含めて再帰的に処理'
)
@click.option(
    '--skip-validation',
    is_flag=True,
    help='バリデーションをスキップ'
)
@click.option(
    '--dry-run',
    is_flag=True,
    help='実際には読み込まず、処理内容のみ表示'
)
@click.option(
    '--continue-on-error',
    is_flag=True,
    help='エラーが発生しても処理を継続'
)
@click.pass_context
def load(
    ctx: click.Context,
    path: str,
    recursive: bool,
    skip_validation: bool,
    dry_run: bool,
    continue_on_error: bool
) -> None:
    """YAMLファイルをデータベースに読み込みます.

    指定されたファイルまたはディレクトリのYAMLファイルを
    バリデーション後にデータベースに挿入します。
    """
    state = CliState(ctx)

    try:
        db_manager = state.db_manager
        loader = YAMLLoader(db_manager)
        path_obj = Path(path)

        # ファイルリストを取得
        yaml_files = []
        if path_obj.is_file():
            if path_obj.suffix.lower() in ['.yaml', '.yml']:
                yaml_files = [path_obj]
            else:
                display_error(f"指定されたファイルはYAMLファイルではありません: {path}")
                ctx.exit(1)
                return
        elif path_obj.is_dir():
            if recursive:
                yaml_files = list(path_obj.rglob("*.yaml")) + list(path_obj.rglob("*.yml"))
            else:
                yaml_files = list(path_obj.glob("*.yaml")) + list(path_obj.glob("*.yml"))
        else:
            display_error(f"無効なパス: {path}")
            ctx.exit(1)
            return

        if not yaml_files:
            display_warning(f"YAMLファイルが見つかりません: {path}")
            return

        display_info(f"処理対象ファイル: {len(yaml_files)}件")

        if dry_run:
            display_info("ドライランモード: 実際の読み込みは実行されません")
            for yaml_file in yaml_files:
                click.echo(f"  - {yaml_file}")
            return

        # ファイルを処理
        successful_loads = []
        failed_loads = []
        skipped_files = []

        for yaml_file in progress_bar(yaml_files, "YAMLファイルを処理中"):
            try:
                # 重複チェック
                yaml_data = loader.load_yaml_file(yaml_file)

                existing_run = loader.check_duplicate_run(yaml_data)
                if existing_run:
                    skipped_files.append((yaml_file, f"重複: Run ID {existing_run.run_id}"))
                    continue

                # バリデーション
                if not skip_validation:
                    loader.validator.validate(yaml_data)

                # データベースに挿入
                run = loader.load_and_insert(yaml_file)
                successful_loads.append((yaml_file, run))

            except (YAMLValidationError, YAMLLoaderError) as e:
                failed_loads.append((yaml_file, str(e)))
                if not continue_on_error:
                    display_error(f"エラーが発生しました: {yaml_file}: {e}")
                    ctx.exit(1)
            except Exception as e:
                failed_loads.append((yaml_file, f"予期しないエラー: {e}"))
                if not continue_on_error:
                    display_error(f"予期しないエラーが発生しました: {yaml_file}: {e}")
                    ctx.exit(1)

        # 結果を表示
        if successful_loads:
            display_success(f"{len(successful_loads)}件のYAMLファイルを正常に読み込みました")

            if state.verbose:
                success_data = []
                for yaml_file, run in successful_loads:
                    success_data.append([
                        str(run.run_id),
                        run.title[:30] + '...' if len(run.title) > 30 else run.title,
                        yaml_file.name
                    ])

                display_table(
                    ['Run ID', 'タイトル', 'ファイル名'],
                    success_data,
                    '読み込み成功'
                )

        if skipped_files:
            display_warning(f"{len(skipped_files)}件のファイルをスキップしました")

            if state.verbose:
                skip_data = []
                for yaml_file, reason in skipped_files:
                    skip_data.append([yaml_file.name, reason])

                display_table(
                    ['ファイル名', '理由'],
                    skip_data,
                    'スキップしたファイル'
                )

        if failed_loads:
            display_error(f"{len(failed_loads)}件のファイルでエラーが発生しました")

            error_data = []
            for yaml_file, error in failed_loads:
                error_data.append([yaml_file.name, error[:50] + '...' if len(error) > 50 else error])

            display_table(
                ['ファイル名', 'エラー'],
                error_data,
                'エラーが発生したファイル'
            )

            if not continue_on_error:
                ctx.exit(1)

    except Exception as e:
        handle_database_error(e)


@yaml_commands.command()
@click.argument('files', nargs=-1, type=click.Path(exists=True))
@click.option(
    '--strict',
    is_flag=True,
    help='厳密バリデーション（警告もエラーとして扱う）'
)
@click.pass_context
def validate(ctx: click.Context, files: tuple, strict: bool) -> None:
    """YAMLファイルの形式を検証します.

    指定されたYAMLファイルのスキーマと値の妥当性を検証します。
    """
    state = CliState(ctx)

    try:
        from src.yaml_loader import YAMLValidator

        validator = YAMLValidator()

        # ファイルリストを準備
        if not files:
            # ファイルが指定されていない場合はdata/yamls/を検証
            yaml_dir = Path("data/yamls")
            if yaml_dir.exists():
                yaml_files = list(yaml_dir.glob("*.yaml")) + list(yaml_dir.glob("*.yml"))
            else:
                display_error("data/yamls ディレクトリが見つかりません")
                ctx.exit(3)
                return
        else:
            yaml_files = []
            for file_path in files:
                path_obj = Path(file_path)
                if path_obj.is_file():
                    yaml_files.append(path_obj)
                elif path_obj.is_dir():
                    yaml_files.extend(path_obj.glob("*.yaml"))
                    yaml_files.extend(path_obj.glob("*.yml"))

        if not yaml_files:
            display_warning("検証対象のYAMLファイルが見つかりません")
            return

        display_info(f"検証対象ファイル: {len(yaml_files)}件")

        valid_files = []
        invalid_files = []
        warnings = []

        for yaml_file in progress_bar(yaml_files, "YAMLファイルを検証中"):
            try:
                # YAMLファイルを読み込み
                with open(yaml_file, encoding='utf-8') as f:
                    yaml_data = yaml.safe_load(f)

                if not isinstance(yaml_data, dict):
                    invalid_files.append((yaml_file, "YAMLファイルは辞書形式である必要があります"))
                    continue

                # バリデーション実行
                validator.validate(yaml_data)

                # 追加の警告チェック
                file_warnings = []

                # オプショナルフィールドの確認
                if 'negative' not in yaml_data:
                    file_warnings.append("negative プロンプトが設定されていません")

                if 'seed' not in yaml_data or yaml_data['seed'] is None:
                    file_warnings.append("seed が設定されていません（再現性に影響）")

                if 'model' not in yaml_data:
                    file_warnings.append("model が指定されていません")

                # 警告がある場合
                if file_warnings:
                    warnings.append((yaml_file, file_warnings))
                    if strict:
                        invalid_files.append((yaml_file, "警告項目があります: " + ", ".join(file_warnings)))
                        continue

                valid_files.append(yaml_file)

            except YAMLValidationError as e:
                invalid_files.append((yaml_file, str(e)))
            except yaml.YAMLError as e:
                invalid_files.append((yaml_file, f"YAML形式エラー: {e}"))
            except Exception as e:
                invalid_files.append((yaml_file, f"予期しないエラー: {e}"))

        # 結果を表示
        if valid_files:
            display_success(f"{len(valid_files)}件のファイルが正常です")

        if warnings and not strict:
            display_warning(f"{len(warnings)}件のファイルに警告があります")

            if state.verbose:
                warning_data = []
                for yaml_file, file_warnings in warnings:
                    for warning in file_warnings:
                        warning_data.append([yaml_file.name, warning])

                display_table(
                    ['ファイル名', '警告'],
                    warning_data,
                    '警告項目'
                )

        if invalid_files:
            display_error(f"{len(invalid_files)}件のファイルでエラーが発生しました")

            error_data = []
            for yaml_file, error in invalid_files:
                error_data.append([yaml_file.name, error[:60] + '...' if len(error) > 60 else error])

            display_table(
                ['ファイル名', 'エラー'],
                error_data,
                'エラーが発生したファイル'
            )

            ctx.exit(1)

        if not valid_files and not invalid_files:
            display_info("検証対象のファイルがありませんでした")

    except Exception as e:
        handle_database_error(e)


@yaml_commands.command()
@click.option(
    '--output', '-o',
    type=click.Path(),
    default=None,
    help='出力ファイルパス（指定しない場合は標準出力）'
)
@click.option(
    '--format', '-f',
    type=click.Choice(['yaml', 'json']),
    default='yaml',
    help='出力形式'
)
@click.option(
    '--status',
    type=click.Choice(['Purchased', 'Tried', 'Tuned', 'Final']),
    default=None,
    help='エクスポート対象のステータス'
)
@click.option(
    '--limit',
    type=int,
    default=None,
    help='エクスポート件数の制限'
)
@click.option(
    '--run-ids',
    default=None,
    help='エクスポート対象のRun ID（カンマ区切り）'
)
@click.option(
    '--since',
    default=None,
    help='開始日時（YYYY-MM-DD形式）'
)
@click.option(
    '--until',
    default=None,
    help='終了日時（YYYY-MM-DD形式）'
)
@click.pass_context
def export(
    ctx: click.Context,
    output: Optional[str],
    format: str,
    status: Optional[str],
    limit: Optional[int],
    run_ids: Optional[str],
    since: Optional[str],
    until: Optional[str]
) -> None:
    """データベースからYAML/JSON形式でデータをエクスポートします.

    実行履歴をYAMLまたはJSON形式でエクスポートします。
    """
    state = CliState(ctx)

    try:
        from src.utils.db_utils import export_runs_with_relations
        
        db_manager = state.db_manager

        # エクスポート条件を構築
        filters = {}
        if status:
            filters['status'] = status

        # Run IDリストを準備
        run_id_list = None
        if run_ids:
            try:
                run_id_list = [int(id.strip()) for id in run_ids.split(',')]
            except ValueError:
                display_error("無効なRun ID形式です（数値をカンマ区切りで指定してください）")
                ctx.exit(1)
                return

        # 日付バリデーション
        since_date = None
        until_date = None
        if since:
            try:
                from datetime import datetime
                since_dt = datetime.strptime(since, '%Y-%m-%d')
                since_date = since_dt.isoformat()
            except ValueError:
                display_error("無効な開始日時形式です（YYYY-MM-DD形式で指定してください）")
                ctx.exit(1)
                return

        if until:
            try:
                from datetime import datetime
                until_dt = datetime.strptime(until, '%Y-%m-%d')
                until_date = until_dt.isoformat()
            except ValueError:
                display_error("無効な終了日時形式です（YYYY-MM-DD形式で指定してください）")
                ctx.exit(1)
                return

        # データをエクスポート
        try:
            export_data = export_runs_with_relations(
                db_manager=db_manager,
                filters=filters,
                run_ids=run_id_list,
                since_date=since_date,
                until_date=until_date,
                limit=limit,
                order_by='created_at'
            )
        except ValueError as e:
            display_error(str(e))
            ctx.exit(1)
            return

        # Run IDが指定されていて見つからないものがあれば警告
        if run_id_list:
            found_ids = {data['_metadata']['run_id'] for data in export_data}
            missing_ids = set(run_id_list) - found_ids
            for missing_id in missing_ids:
                display_warning(f"Run ID {missing_id} が見つかりません")

        if not export_data:
            display_warning("エクスポート対象のデータが見つかりません")
            return

        display_info(f"エクスポート対象: {len(export_data)}件")

        # 出力
        if output:
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                if format == 'json':
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                else:  # yaml
                    yaml.dump(export_data, f, allow_unicode=True, default_flow_style=False)

            display_success(f"データをエクスポートしました: {output}")
        else:
            # 標準出力
            if format == 'json':
                output_json(export_data)
            else:  # yaml
                output_yaml(export_data)

    except Exception as e:
        handle_database_error(e)


@yaml_commands.command()
@click.argument('yaml_file', type=click.Path(exists=True))
@click.pass_context
def info(ctx: click.Context, yaml_file: str) -> None:
    """YAMLファイルの詳細情報を表示します.

    指定されたYAMLファイルの内容と検証結果を表示します。
    """
    try:
        from src.yaml_loader import YAMLValidator

        validator = YAMLValidator()
        file_path = Path(yaml_file)

        # ファイル情報
        file_stat = file_path.stat()
        display_info(f"ファイル: {yaml_file}")
        display_info(f"サイズ: {file_stat.st_size} bytes")
        display_info(f"更新日時: {format_datetime(file_stat.st_mtime)}")

        # YAMLデータを読み込み
        with open(file_path, encoding='utf-8') as f:
            yaml_data = yaml.safe_load(f)

        if not isinstance(yaml_data, dict):
            display_error("YAMLファイルは辞書形式である必要があります")
            ctx.exit(1)
            return

        # バリデーション
        try:
            validator.validate(yaml_data)
            display_success("バリデーション: 正常")
        except YAMLValidationError as e:
            display_error(f"バリデーションエラー: {e}")

        # 内容を表示
        click.echo("\n" + click.style("YAML内容:", fg='cyan', bold=True))

        # 基本情報
        basic_info = [
            ['タイトル', yaml_data.get('run_title', 'N/A')],
            ['プロンプト', yaml_data.get('prompt', 'N/A')[:60] + ('...' if len(yaml_data.get('prompt', '')) > 60 else '')],
            ['CFG', str(yaml_data.get('cfg', 'N/A'))],
            ['Steps', str(yaml_data.get('steps', 'N/A'))],
            ['Sampler', yaml_data.get('sampler', 'N/A')],
            ['Status', yaml_data.get('status', 'N/A')]
        ]

        display_table(['項目', '値'], basic_info)

        # オプション情報
        optional_info = []
        for key in ['negative', 'seed', 'width', 'height', 'model', 'source']:
            if key in yaml_data:
                value = yaml_data[key]
                if key == 'negative' and value and len(value) > 60:
                    value = value[:60] + '...'
                optional_info.append([key, str(value)])

        if optional_info:
            display_table(['オプション項目', '値'], optional_info)

        # LoRA情報
        if 'loras' in yaml_data and yaml_data['loras']:
            lora_info = [[i+1, lora] for i, lora in enumerate(yaml_data['loras'])]
            display_table(['#', 'LoRA名'], lora_info, '使用LoRA')

    except Exception as e:
        display_error(f"ファイル読み込みエラー: {e}")
        ctx.exit(1)
