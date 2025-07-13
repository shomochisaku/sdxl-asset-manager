"""データベース管理コマンド.

このモジュールはデータベースの初期化、統計表示、バックアップ機能を提供します。
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from src.models.database import Image, Model, Run, Tag
from src.utils.db_init import initialize_database, verify_database_setup

from .utils import (
    CliState,
    confirm_dangerous_action,
    display_error,
    display_info,
    display_success,
    display_table,
    display_warning,
    format_datetime,
    handle_database_error,
)


@click.group(name='db')
@click.pass_context
def db_commands(ctx: click.Context) -> None:
    """データベース管理コマンド.

    データベースの初期化、統計表示、バックアップ・復元機能を提供します。
    """
    pass


@db_commands.command()
@click.option(
    '--force', '-f',
    is_flag=True,
    help='既存のデータベースを上書きする'
)
@click.pass_context
def init(ctx: click.Context, force: bool) -> None:
    """データベースを初期化します.

    新しいデータベースファイルを作成し、テーブル構造を設定します。
    """
    state = CliState(ctx)

    try:
        db_path = state.db_path or "data/asset_manager.db"

        # 既存データベースのチェック
        if Path(db_path).exists() and not force:
            if not confirm_dangerous_action(
                f"データベースファイル '{db_path}' が既に存在します。上書きしますか？",
                force
            ):
                display_info("データベース初期化をキャンセルしました")
                return

        # データベースディレクトリを作成
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        # データベースを初期化
        display_info(f"データベースを初期化中: {db_path}")
        engine = initialize_database(db_path)

        # セットアップを検証
        if verify_database_setup(engine):
            display_success(f"データベースが正常に初期化されました: {db_path}")
        else:
            display_error("データベースの検証に失敗しました")
            ctx.exit(2)

    except Exception as e:
        handle_database_error(e)


@db_commands.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """データベースの統計情報を表示します.

    各テーブルのレコード数、データベースサイズなどの統計を表示します。
    """
    state = CliState(ctx)

    try:
        db_manager = state.db_manager

        # データベースファイルの情報
        db_path = state.db_path or "data/asset_manager.db"

        if Path(db_path).exists():
            file_size = Path(db_path).stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            display_info(f"データベースファイル: {db_path}")
            display_info(f"ファイルサイズ: {file_size_mb:.2f} MB")
        else:
            display_warning(f"データベースファイルが見つかりません: {db_path}")
            ctx.exit(3)
            return

        # テーブル統計
        tables_stats = []

        with db_manager.get_session() as session:
            # Models テーブル
            model_count = session.query(Model).count()
            checkpoint_count = session.query(Model).filter(Model.type == 'checkpoint').count()
            lora_count = session.query(Model).filter(Model.type == 'lora').count()

            tables_stats.append(['Models', str(model_count), f'Checkpoints: {checkpoint_count}, LoRAs: {lora_count}'])

            # Runs テーブル
            run_count = session.query(Run).count()
            status_counts = {}
            for status in ['Purchased', 'Tried', 'Tuned', 'Final']:
                count = session.query(Run).filter(Run.status == status).count()
                status_counts[status] = count

            status_summary = ', '.join([f'{k}: {v}' for k, v in status_counts.items()])
            tables_stats.append(['Runs', str(run_count), status_summary])

            # Images テーブル
            image_count = session.query(Image).count()
            tables_stats.append(['Images', str(image_count), '生成された画像'])

            # Tags テーブル
            tag_count = session.query(Tag).count()
            tables_stats.append(['Tags', str(tag_count), 'カテゴリ分類用タグ'])

        # 統計テーブルを表示
        display_table(
            ['テーブル', 'レコード数', '詳細'],
            tables_stats,
            'データベース統計'
        )

        # 最近のアクティビティ
        display_info("\n最近のアクティビティ:")
        recent_runs = db_manager.get_records(Run, order_by='created_at', limit=5)

        if recent_runs:
            recent_data = []
            for run in recent_runs:
                recent_data.append([
                    str(run.run_id),
                    run.title[:30] + '...' if len(run.title) > 30 else run.title,
                    run.status,
                    format_datetime(run.created_at)
                ])

            display_table(
                ['ID', 'タイトル', 'ステータス', '作成日時'],
                recent_data
            )
        else:
            display_info("実行履歴がありません")

    except Exception as e:
        handle_database_error(e)


@db_commands.command()
@click.option(
    '--output', '-o',
    type=click.Path(),
    default=None,
    help='バックアップファイルの出力パス'
)
@click.pass_context
def backup(ctx: click.Context, output: Optional[str]) -> None:
    """データベースのバックアップを作成します.

    データベースファイルを指定された場所にコピーします。
    """
    state = CliState(ctx)

    try:
        db_path = state.db_path or "data/asset_manager.db"

        if not Path(db_path).exists():
            display_error(f"データベースファイルが見つかりません: {db_path}")
            ctx.exit(3)
            return

        # バックアップファイル名を生成
        if output is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            db_name = Path(db_path).stem
            output = f"{db_name}_backup_{timestamp}.db"

        output_path = Path(output)

        # バックアップディレクトリを作成
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 既存ファイルのチェック
        if output_path.exists():
            if not confirm_dangerous_action(
                f"バックアップファイル '{output}' が既に存在します。上書きしますか？"
            ):
                display_info("バックアップをキャンセルしました")
                return

        # ファイルをコピー
        display_info(f"バックアップを作成中: {db_path} -> {output}")
        shutil.copy2(db_path, output_path)

        # ファイルサイズを確認
        original_size = Path(db_path).stat().st_size
        backup_size = output_path.stat().st_size

        if original_size == backup_size:
            display_success(f"バックアップが正常に作成されました: {output}")
            display_info(f"ファイルサイズ: {backup_size / (1024 * 1024):.2f} MB")
        else:
            display_error("バックアップファイルのサイズが一致しません")
            ctx.exit(1)

    except Exception as e:
        handle_database_error(e)


@db_commands.command()
@click.argument('backup_file', type=click.Path(exists=True))
@click.option(
    '--force', '-f',
    is_flag=True,
    help='確認なしで復元を実行'
)
@click.pass_context
def restore(ctx: click.Context, backup_file: str, force: bool) -> None:
    """バックアップからデータベースを復元します.

    指定されたバックアップファイルから現在のデータベースを復元します。
    """
    state = CliState(ctx)

    try:
        db_path = state.db_path or "data/asset_manager.db"
        backup_path = Path(backup_file)

        # バックアップファイルの確認
        if not backup_path.exists():
            display_error(f"バックアップファイルが見つかりません: {backup_file}")
            ctx.exit(3)
            return

        # 既存データベースのバックアップ
        current_backup = None
        if Path(db_path).exists():
            if not confirm_dangerous_action(
                f"現在のデータベース '{db_path}' を '{backup_file}' で置き換えます。\n"
                "現在のデータベースは失われます。続行しますか？",
                force
            ):
                display_info("復元をキャンセルしました")
                return

            # 現在のDBを一時バックアップ
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            current_backup = f"{db_path}.restore_backup_{timestamp}"
            shutil.copy2(db_path, current_backup)
            display_info(f"現在のデータベースをバックアップしました: {current_backup}")

        # データベースディレクトリを作成
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        # 復元実行
        display_info(f"データベースを復元中: {backup_file} -> {db_path}")
        shutil.copy2(backup_path, db_path)

        # 復元されたデータベースの検証
        try:
            from src.utils.db_init import create_engine_for_database
            engine = create_engine_for_database(db_path)

            if verify_database_setup(engine):
                display_success(f"データベースが正常に復元されました: {db_path}")

                # 一時バックアップの削除確認
                if current_backup and Path(current_backup).exists():
                    if click.confirm("一時バックアップファイルを削除しますか？"):
                        os.unlink(current_backup)
                        display_info("一時バックアップファイルを削除しました")
                    else:
                        display_info(f"一時バックアップファイルが残されています: {current_backup}")
            else:
                display_error("復元されたデータベースの検証に失敗しました")

                # 復元失敗時は元のデータベースを復旧
                if current_backup and Path(current_backup).exists():
                    shutil.copy2(current_backup, db_path)
                    display_info("元のデータベースを復旧しました")

                ctx.exit(2)

        except Exception as verify_error:
            display_error(f"データベース検証エラー: {verify_error}")

            # 復元失敗時は元のデータベースを復旧
            if current_backup and Path(current_backup).exists():
                shutil.copy2(current_backup, db_path)
                display_info("元のデータベースを復旧しました")

            ctx.exit(2)

    except Exception as e:
        handle_database_error(e)


@db_commands.command()
@click.option(
    '--table', '-t',
    type=click.Choice(['models', 'runs', 'images', 'tags', 'all']),
    default='all',
    help='クリーンアップ対象のテーブル'
)
@click.option(
    '--dry-run',
    is_flag=True,
    help='実際には削除せず、削除対象のみ表示'
)
@click.option(
    '--force', '-f',
    is_flag=True,
    help='確認なしでクリーンアップを実行'
)
@click.pass_context
def cleanup(ctx: click.Context, table: str, dry_run: bool, force: bool) -> None:
    """データベースの不要なデータをクリーンアップします.

    孤立したレコードや重複データを削除します。
    """
    state = CliState(ctx)

    try:
        db_manager = state.db_manager

        if dry_run:
            display_info("ドライランモード: 実際の削除は実行されません")

        cleanup_results = []

        with db_manager.get_session() as session:
            if table in ['models', 'all']:
                # 使用されていないモデルを検索
                unused_models = session.query(Model).filter(
                    ~Model.model_id.in_(
                        session.query(Run.model_id).filter(Run.model_id.isnot(None))
                    )
                ).all()

                if unused_models:
                    cleanup_results.append(f"未使用モデル: {len(unused_models)}件")
                    if not dry_run:
                        if force or confirm_dangerous_action(f"{len(unused_models)}件の未使用モデルを削除しますか？"):
                            for model in unused_models:
                                session.delete(model)
                            display_success(f"{len(unused_models)}件の未使用モデルを削除しました")

            if table in ['images', 'all']:
                # 実際のファイルが存在しない画像レコードを検索
                orphaned_images = []
                images = session.query(Image).all()

                for image in images:
                    if not Path(image.filepath).exists():
                        orphaned_images.append(image)

                if orphaned_images:
                    cleanup_results.append(f"孤立画像レコード: {len(orphaned_images)}件")
                    if not dry_run:
                        if force or confirm_dangerous_action(f"{len(orphaned_images)}件の孤立画像レコードを削除しますか？"):
                            for image in orphaned_images:
                                session.delete(image)
                            display_success(f"{len(orphaned_images)}件の孤立画像レコードを削除しました")

        if cleanup_results:
            display_table(
                ['クリーンアップ項目', '件数'],
                [[item.split(':')[0], item.split(':')[1].strip()] for item in cleanup_results],
                'クリーンアップ結果'
            )
        else:
            display_info("クリーンアップが必要なデータは見つかりませんでした")

    except Exception as e:
        handle_database_error(e)
