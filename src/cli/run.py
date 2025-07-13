"""実行管理コマンド.

このモジュールは実行履歴の一覧表示、詳細表示、更新、削除機能を提供します。
"""

from typing import Optional, Tuple

import click
from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError

from src.models.database import Model, Run, RunLora
from src.utils.db_utils import (
    get_images_for_run,
    get_loras_for_run,
    get_tags_for_run,
)

from .utils import (
    CliState,
    confirm_dangerous_action,
    display_error,
    display_info,
    display_success,
    display_table,
    display_warning,
    format_datetime,
    format_status,
    handle_database_error,
    output_json,
    output_yaml,
)


@click.group(name='run')
@click.pass_context
def run_commands(ctx: click.Context) -> None:
    """実行管理コマンド.

    実行履歴の一覧表示、詳細表示、更新、削除機能を提供します。
    """
    pass


@run_commands.command()
@click.option(
    '--status',
    type=click.Choice(['Purchased', 'Tried', 'Tuned', 'Final']),
    multiple=True,
    help='フィルタするステータス（複数指定可能）'
)
@click.option(
    '--model',
    default=None,
    help='使用モデルでフィルタ'
)
@click.option(
    '--limit',
    type=int,
    default=20,
    help='表示件数の制限'
)
@click.option(
    '--offset',
    type=int,
    default=0,
    help='表示開始位置'
)
@click.option(
    '--sort-by',
    type=click.Choice(['created_at', 'updated_at', 'title', 'status']),
    default='created_at',
    help='ソート基準'
)
@click.option(
    '--order',
    type=click.Choice(['asc', 'desc']),
    default='desc',
    help='ソート順'
)
@click.option(
    '--output', '-o',
    type=click.Choice(['table', 'json', 'yaml']),
    default='table',
    help='出力形式'
)
@click.pass_context
def list(
    ctx: click.Context,
    status: Tuple,
    model: Optional[str],
    limit: int,
    offset: int,
    sort_by: str,
    order: str,
    output: str
) -> None:
    """実行履歴一覧を表示します.

    指定された条件で実行履歴をフィルタリングして表示します。
    """
    state = CliState(ctx)

    try:
        db_manager = state.db_manager

        # フィルタ条件を構築
        if status:
            # 複数ステータスの場合は、ここではFilteringできないので後でSQLクエリで対応
            pass

        with db_manager.get_session() as session:
            query_obj = session.query(Run)

            # ステータスフィルタ
            if status:
                query_obj = query_obj.filter(Run.status.in_(status))

            # モデルフィルタ
            if model:
                query_obj = query_obj.join(Model).filter(Model.name.contains(model))

            # ソート
            sort_column = getattr(Run, sort_by)
            if order == 'desc':
                query_obj = query_obj.order_by(desc(sort_column))
            else:
                query_obj = query_obj.order_by(sort_column)

            # 総件数を取得
            total_count = query_obj.count()

            # ページネーション
            results = query_obj.offset(offset).limit(limit).all()

            # セッションから切り離し
            for result in results:
                session.expunge(result)

        if not results:
            display_warning("指定された条件にマッチする実行履歴が見つかりません")
            return

        display_info(f"実行履歴: {len(results)}件 (全{total_count}件中 {offset+1}-{offset+len(results)})")

        if output == 'table':
            table_data = []
            for run in results:
                # プロンプトを短縮
                prompt_preview = run.prompt[:40] + '...' if len(run.prompt) > 40 else run.prompt
                model_name = run.model.name if run.model else 'N/A'
                if len(model_name) > 15:
                    model_name = model_name[:15] + '...'

                table_data.append([
                    str(run.run_id),
                    run.title[:25] + '...' if len(run.title) > 25 else run.title,
                    prompt_preview,
                    format_status(run.status),
                    model_name,
                    f"{run.cfg:.1f}",
                    str(run.steps),
                    format_datetime(run.created_at)
                ])

            display_table(
                ['ID', 'タイトル', 'プロンプト', 'ステータス', 'モデル', 'CFG', 'Steps', '作成日時'],
                table_data,
                '実行履歴一覧'
            )

            if total_count > offset + limit:
                display_info(f"さらに結果があります。--offset {offset + limit} で続きを表示できます")

        elif output == 'json':
            output_json(results)
        elif output == 'yaml':
            output_yaml(results)

    except Exception as e:
        handle_database_error(e)


@run_commands.command()
@click.argument('run_id', type=int)
@click.option(
    '--output', '-o',
    type=click.Choice(['table', 'json', 'yaml']),
    default='table',
    help='出力形式'
)
@click.pass_context
def show(ctx: click.Context, run_id: int, output: str) -> None:
    """実行履歴の詳細情報を表示します.

    指定されたRun IDの詳細情報、関連するLoRA、画像、タグを表示します。
    """
    state = CliState(ctx)

    try:
        db_manager = state.db_manager

        # 実行履歴を取得
        run = db_manager.get_record_by_id(Run, run_id)
        if not run:
            display_error(f"Run ID {run_id} が見つかりません")
            ctx.exit(1)
            return

        # 関連データを取得
        images = get_images_for_run(db_manager, run_id)
        loras = get_loras_for_run(db_manager, run_id)
        tags = get_tags_for_run(db_manager, run_id)

        if output == 'table':
            # 基本情報
            display_info(f"実行履歴詳細: Run ID {run_id}")

            basic_info = [
                ['ID', str(run.run_id)],
                ['タイトル', run.title],
                ['ステータス', format_status(run.status)],
                ['モデル', run.model.name if run.model else 'N/A'],
                ['CFG', f"{run.cfg:.1f}"],
                ['Steps', str(run.steps)],
                ['サンプラー', run.sampler],
                ['シード', str(run.seed) if run.seed is not None else 'N/A'],
                ['サイズ', f"{run.width}x{run.height}"],
                ['作成日時', format_datetime(run.created_at)],
                ['更新日時', format_datetime(run.updated_at)]
            ]

            if run.scheduler:
                basic_info.insert(-2, ['スケジューラー', run.scheduler])
            if run.source:
                basic_info.insert(-2, ['ソース', run.source])

            display_table(['項目', '値'], basic_info, '基本情報')

            # プロンプト情報
            prompt_info = [
                ['プロンプト', run.prompt],
            ]
            if run.negative:
                prompt_info.append(['ネガティブ', run.negative])

            display_table(['項目', '内容'], prompt_info, 'プロンプト情報')

            # LoRA情報
            if loras:
                lora_data = []
                for run_lora in loras:
                    lora_data.append([
                        run_lora.lora_model.name,
                        f"{run_lora.weight:.2f}"
                    ])
                display_table(['LoRA名', '重み'], lora_data, '使用LoRA')
            else:
                display_info("使用LoRA: なし")

            # 画像情報
            if images:
                image_data = []
                for image in images:
                    file_size = f"{image.file_size / 1024 / 1024:.1f} MB" if image.file_size else 'N/A'
                    size = f"{image.width}x{image.height}" if image.width and image.height else 'N/A'

                    image_data.append([
                        image.filename,
                        size,
                        file_size,
                        format_datetime(image.created_at)
                    ])
                display_table(['ファイル名', 'サイズ', 'ファイルサイズ', '作成日時'], image_data, '生成画像')
            else:
                display_info("生成画像: なし")

            # タグ情報
            if tags:
                tag_data = []
                for run_tag in tags:
                    tag_data.append([
                        run_tag.tag.name,
                        run_tag.tag.category or 'N/A'
                    ])
                display_table(['タグ名', 'カテゴリ'], tag_data, 'タグ')
            else:
                display_info("タグ: なし")

        elif output == 'json':
            # JSONにはすべての関連データを含める
            run_data = {
                'run': run,
                'images': images,
                'loras': loras,
                'tags': tags
            }
            output_json(run_data)
        elif output == 'yaml':
            # YAMLにはすべての関連データを含める
            run_data = {
                'run': run,
                'images': images,
                'loras': loras,
                'tags': tags
            }
            output_yaml(run_data)

    except Exception as e:
        handle_database_error(e)


@run_commands.command()
@click.argument('run_id', type=int)
@click.option(
    '--title',
    default=None,
    help='タイトルを更新'
)
@click.option(
    '--status',
    type=click.Choice(['Purchased', 'Tried', 'Tuned', 'Final']),
    default=None,
    help='ステータスを更新'
)
@click.option(
    '--prompt',
    default=None,
    help='プロンプトを更新'
)
@click.option(
    '--negative',
    default=None,
    help='ネガティブプロンプトを更新'
)
@click.option(
    '--cfg',
    type=float,
    default=None,
    help='CFG値を更新'
)
@click.option(
    '--steps',
    type=int,
    default=None,
    help='Steps値を更新'
)
@click.option(
    '--source',
    default=None,
    help='ソース情報を更新'
)
@click.pass_context
def update(
    ctx: click.Context,
    run_id: int,
    title: Optional[str],
    status: Optional[str],
    prompt: Optional[str],
    negative: Optional[str],
    cfg: Optional[float],
    steps: Optional[int],
    source: Optional[str]
) -> None:
    """実行履歴の情報を更新します.

    指定されたRun IDの情報を更新します。
    """
    state = CliState(ctx)

    try:
        db_manager = state.db_manager

        # 更新するフィールドを収集
        updates = {}
        if title is not None:
            updates['title'] = title
        if status is not None:
            updates['status'] = status
        if prompt is not None:
            updates['prompt'] = prompt
        if negative is not None:
            updates['negative'] = negative
        if cfg is not None:
            updates['cfg'] = str(cfg)
        if steps is not None:
            updates['steps'] = str(steps)
        if source is not None:
            updates['source'] = source

        if not updates:
            display_error("更新する項目が指定されていません")
            ctx.exit(1)
            return

        # 実行履歴が存在するか確認
        existing_run = db_manager.get_record_by_id(Run, run_id)
        if not existing_run:
            display_error(f"Run ID {run_id} が見つかりません")
            ctx.exit(1)
            return

        # 更新内容を表示
        display_info(f"Run ID {run_id} を更新します:")
        for field, value in updates.items():
            click.echo(f"  {field}: {value}")

        if not confirm_dangerous_action("この内容で更新しますか？"):
            display_info("更新をキャンセルしました")
            return

        # 更新実行
        updated_run = db_manager.update_record(Run, run_id, **updates)

        if updated_run:
            display_success(f"Run ID {run_id} を正常に更新しました")

            # 更新後の情報を表示
            if state.verbose:
                updated_info = []
                for field in updates.keys():
                    value = getattr(updated_run, field)
                    if field == 'status':
                        value = format_status(value)
                    updated_info.append([field, str(value)])

                display_table(['項目', '更新後の値'], updated_info, '更新結果')
        else:
            display_error("更新に失敗しました")
            ctx.exit(1)

    except Exception as e:
        handle_database_error(e)


@run_commands.command()
@click.argument('run_ids', nargs=-1, type=int, required=True)
@click.option(
    '--force', '-f',
    is_flag=True,
    help='確認なしで削除を実行'
)
@click.option(
    '--cascade',
    is_flag=True,
    help='関連する画像やLoRAの関連付けも削除'
)
@click.pass_context
def delete(ctx: click.Context, run_ids: Tuple, force: bool, cascade: bool) -> None:
    """実行履歴を削除します.

    指定されたRun IDの実行履歴を削除します。
    複数のIDを指定することで一括削除も可能です。
    """
    state = CliState(ctx)

    try:
        db_manager = state.db_manager

        # 存在確認
        existing_runs = []
        missing_ids = []

        for run_id in run_ids:
            run = db_manager.get_record_by_id(Run, run_id)
            if run:
                existing_runs.append(run)
            else:
                missing_ids.append(run_id)

        if missing_ids:
            display_warning(f"以下のRun IDが見つかりません: {', '.join(map(str, missing_ids))}")

        if not existing_runs:
            display_error("削除対象の実行履歴が見つかりません")
            ctx.exit(1)
            return

        # 削除対象を表示
        display_info(f"削除対象: {len(existing_runs)}件の実行履歴")

        if state.verbose:
            delete_info = []
            for run in existing_runs:
                title_preview = run.title[:30] + '...' if len(run.title) > 30 else run.title
                delete_info.append([
                    str(run.run_id),
                    title_preview,
                    format_status(run.status),
                    format_datetime(run.created_at)
                ])

            display_table(
                ['ID', 'タイトル', 'ステータス', '作成日時'],
                delete_info,
                '削除対象一覧'
            )

        # 関連データの確認
        total_images = 0
        total_loras = 0
        total_tags = 0

        for run in existing_runs:
            images = get_images_for_run(db_manager, run.run_id)
            loras = get_loras_for_run(db_manager, run.run_id)
            tags = get_tags_for_run(db_manager, run.run_id)

            total_images += len(images)
            total_loras += len(loras)
            total_tags += len(tags)

        if total_images > 0 or total_loras > 0 or total_tags > 0:
            display_warning("関連データも削除されます:")
            if total_images > 0:
                click.echo(f"  - 画像レコード: {total_images}件")
            if total_loras > 0:
                click.echo(f"  - LoRA関連付け: {total_loras}件")
            if total_tags > 0:
                click.echo(f"  - タグ関連付け: {total_tags}件")

        # 確認
        message = f"{len(existing_runs)}件の実行履歴を削除します。この操作は取り消せません。"
        if not confirm_dangerous_action(message, force):
            display_info("削除をキャンセルしました")
            return

        # 削除実行
        deleted_count = 0
        failed_deletes = []

        for run in existing_runs:
            try:
                success = db_manager.delete_record(Run, run.run_id)
                if success:
                    deleted_count += 1
                else:
                    failed_deletes.append(run.run_id)
            except SQLAlchemyError as e:
                failed_deletes.append(run.run_id)
                if state.verbose:
                    display_error(f"Run ID {run.run_id} の削除に失敗: {e}")

        # 結果を表示
        if deleted_count > 0:
            display_success(f"{deleted_count}件の実行履歴を削除しました")

        if failed_deletes:
            display_error(f"以下のRun IDの削除に失敗しました: {', '.join(map(str, failed_deletes))}")
            ctx.exit(1)

    except Exception as e:
        handle_database_error(e)


@run_commands.command()
@click.option(
    '--run-ids',
    default=None,
    help='コピー対象のRun ID（カンマ区切り）'
)
@click.option(
    '--title-prefix',
    default='Copy of ',
    help='コピー後のタイトルに付けるプレフィックス'
)
@click.option(
    '--new-status',
    type=click.Choice(['Purchased', 'Tried', 'Tuned', 'Final']),
    default='Tried',
    help='コピー後のステータス'
)
@click.pass_context
def copy(
    ctx: click.Context,
    run_ids: Optional[str],
    title_prefix: str,
    new_status: str
) -> None:
    """実行履歴をコピーします.

    指定された実行履歴をコピーして新しい実行履歴を作成します。
    """
    state = CliState(ctx)

    try:
        db_manager = state.db_manager

        if not run_ids:
            display_error("コピー対象のRun IDを指定してください (--run-ids)")
            ctx.exit(1)
            return

        # Run IDリストを解析
        try:
            id_list = [int(id.strip()) for id in run_ids.split(',')]
        except ValueError:
            display_error("無効なRun ID形式です（数値をカンマ区切りで指定してください）")
            ctx.exit(1)
            return

        # 対象実行履歴を取得
        source_runs = []
        missing_ids = []

        for run_id in id_list:
            run = db_manager.get_record_by_id(Run, run_id)
            if run:
                source_runs.append(run)
            else:
                missing_ids.append(run_id)

        if missing_ids:
            display_warning(f"以下のRun IDが見つかりません: {', '.join(map(str, missing_ids))}")

        if not source_runs:
            display_error("コピー対象の実行履歴が見つかりません")
            ctx.exit(1)
            return

        # コピー対象を表示
        display_info(f"コピー対象: {len(source_runs)}件の実行履歴")

        copy_info = []
        for run in source_runs:
            new_title = title_prefix + run.title
            copy_info.append([
                str(run.run_id),
                run.title[:25] + '...' if len(run.title) > 25 else run.title,
                new_title[:25] + '...' if len(new_title) > 25 else new_title,
                new_status
            ])

        display_table(
            ['元ID', '元タイトル', '新タイトル', '新ステータス'],
            copy_info,
            'コピー設定'
        )

        if not confirm_dangerous_action(f"{len(source_runs)}件の実行履歴をコピーしますか？"):
            display_info("コピーをキャンセルしました")
            return

        # コピー実行
        copied_runs = []
        failed_copies = []

        for source_run in source_runs:
            try:
                # 新しい実行履歴データを準備
                new_run_data = {
                    'title': title_prefix + source_run.title,
                    'prompt': source_run.prompt,
                    'negative': source_run.negative,
                    'cfg': source_run.cfg,
                    'steps': source_run.steps,
                    'sampler': source_run.sampler,
                    'scheduler': source_run.scheduler,
                    'seed': source_run.seed,
                    'width': source_run.width,
                    'height': source_run.height,
                    'batch_size': source_run.batch_size,
                    'status': new_status,
                    'source': source_run.source,
                    'model_id': source_run.model_id
                }

                # 実行履歴を作成
                new_run = db_manager.create_record(Run, **new_run_data)

                # LoRA関連付けをコピー
                source_loras = get_loras_for_run(db_manager, source_run.run_id)
                for run_lora in source_loras:
                    db_manager.create_record(
                        RunLora,
                        run_id=new_run.run_id,
                        lora_id=run_lora.lora_id,
                        weight=run_lora.weight
                    )

                copied_runs.append((source_run.run_id, new_run.run_id))

            except Exception as e:
                failed_copies.append((source_run.run_id, str(e)))

        # 結果を表示
        if copied_runs:
            display_success(f"{len(copied_runs)}件の実行履歴をコピーしました")

            if state.verbose:
                copy_result = []
                for source_id, new_id in copied_runs:
                    copy_result.append([str(source_id), str(new_id)])

                display_table(
                    ['元Run ID', '新Run ID'],
                    copy_result,
                    'コピー結果'
                )

        if failed_copies:
            display_error(f"{len(failed_copies)}件のコピーに失敗しました")

            if state.verbose:
                failure_info = []
                for source_id, error in failed_copies:
                    error_msg = error[:50] + '...' if len(error) > 50 else error
                    failure_info.append([str(source_id), error_msg])

                display_table(
                    ['Run ID', 'エラー'],
                    failure_info,
                    'コピー失敗'
                )

            ctx.exit(1)

    except Exception as e:
        handle_database_error(e)
