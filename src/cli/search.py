"""検索機能コマンド.

このモジュールはプロンプト、モデル、LoRA、タグでの検索機能を提供します。
"""

from datetime import datetime
from typing import List, Optional

import click
from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from src.models.database import Model, Run, RunLora, RunTag, Tag
from src.utils.db_utils import search_runs_by_prompt
from .utils import (
    CliState,
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
    validate_output_format,
)


@click.group(name='search')
@click.pass_context
def search_commands(ctx: click.Context) -> None:
    """検索機能コマンド.
    
    プロンプト、モデル、LoRA、タグでの柔軟な検索機能を提供します。
    """
    pass


@search_commands.command()
@click.argument('query', required=True)
@click.option(
    '--type', '-t',
    'search_type',
    type=click.Choice(['prompt', 'title', 'all']),
    default='all',
    help='検索対象（prompt: プロンプトのみ, title: タイトルのみ, all: 両方）'
)
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
    '--lora',
    default=None,
    help='使用LoRAでフィルタ'
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
def prompt(
    ctx: click.Context,
    query: str,
    search_type: str,
    status: tuple,
    model: Optional[str],
    lora: Optional[str],
    limit: int,
    offset: int,
    sort_by: str,
    order: str,
    output: str
) -> None:
    """プロンプトとタイトルで実行履歴を検索します.
    
    指定されたキーワードでプロンプトまたはタイトルを検索します。
    """
    state = CliState(ctx)
    
    try:
        db_manager = state.db_manager
        
        with db_manager.get_session() as session:
            # ベースクエリを構築
            query_obj = session.query(Run)
            
            # テキスト検索条件
            if search_type == 'prompt':
                query_obj = query_obj.filter(Run.prompt.contains(query))
            elif search_type == 'title':
                query_obj = query_obj.filter(Run.title.contains(query))
            else:  # all
                query_obj = query_obj.filter(
                    or_(
                        Run.prompt.contains(query),
                        Run.title.contains(query)
                    )
                )
            
            # ステータスフィルタ
            if status:
                query_obj = query_obj.filter(Run.status.in_(status))
            
            # モデルフィルタ
            if model:
                query_obj = query_obj.join(Model).filter(Model.name.contains(model))
            
            # LoRAフィルタ
            if lora:
                query_obj = query_obj.join(RunLora).join(
                    Model, RunLora.lora_id == Model.model_id
                ).filter(Model.name.contains(lora))
            
            # ソート
            sort_column = getattr(Run, sort_by)
            if order == 'desc':
                query_obj = query_obj.order_by(desc(sort_column))
            else:
                query_obj = query_obj.order_by(sort_column)
            
            # ページネーション
            total_count = query_obj.count()
            results = query_obj.offset(offset).limit(limit).all()
            
            # セッションから切り離し
            for result in results:
                session.expunge(result)
        
        if not results:
            display_warning(f"'{query}' にマッチする実行履歴が見つかりません")
            return
        
        display_info(f"検索結果: {len(results)}件 (全{total_count}件中 {offset+1}-{offset+len(results)})")
        
        if output == 'table':
            # テーブル形式で表示
            table_data = []
            for run in results:
                # プロンプトを短縮
                prompt_preview = run.prompt[:40] + '...' if len(run.prompt) > 40 else run.prompt
                
                table_data.append([
                    str(run.run_id),
                    run.title[:25] + '...' if len(run.title) > 25 else run.title,
                    prompt_preview,
                    format_status(run.status),
                    run.model.name[:15] + '...' if run.model and len(run.model.name) > 15 else (run.model.name if run.model else 'N/A'),
                    format_datetime(run.created_at)
                ])
            
            display_table(
                ['ID', 'タイトル', 'プロンプト', 'ステータス', 'モデル', '作成日時'],
                table_data,
                f'検索結果: "{query}"'
            )
            
            if total_count > offset + limit:
                display_info(f"さらに結果があります。--offset {offset + limit} で続きを表示できます")
                
        elif output == 'json':
            output_json(results)
        elif output == 'yaml':
            output_yaml(results)
            
    except Exception as e:
        handle_database_error(e)


@search_commands.command()
@click.option(
    '--type', '-t',
    'model_type',
    type=click.Choice(['checkpoint', 'lora', 'vae', 'controlnet']),
    default=None,
    help='モデルタイプでフィルタ'
)
@click.option(
    '--name',
    default=None,
    help='モデル名でフィルタ（部分一致）'
)
@click.option(
    '--unused',
    is_flag=True,
    help='未使用モデルのみ表示'
)
@click.option(
    '--limit',
    type=int,
    default=50,
    help='表示件数の制限'
)
@click.option(
    '--output', '-o',
    type=click.Choice(['table', 'json', 'yaml']),
    default='table',
    help='出力形式'
)
@click.pass_context
def model(
    ctx: click.Context,
    model_type: Optional[str],
    name: Optional[str],
    unused: bool,
    limit: int,
    output: str
) -> None:
    """モデルを検索します.
    
    データベースに登録されているモデルを検索・表示します。
    """
    state = CliState(ctx)
    
    try:
        db_manager = state.db_manager
        
        with db_manager.get_session() as session:
            query_obj = session.query(Model)
            
            # タイプフィルタ
            if model_type:
                query_obj = query_obj.filter(Model.type == model_type)
            
            # 名前フィルタ
            if name:
                query_obj = query_obj.filter(Model.name.contains(name))
            
            # 未使用モデルフィルタ
            if unused:
                # 使用されていないモデルを検索
                used_model_ids = session.query(Run.model_id).filter(Run.model_id.isnot(None)).distinct()
                used_lora_ids = session.query(RunLora.lora_id).distinct()
                
                query_obj = query_obj.filter(
                    and_(
                        ~Model.model_id.in_(used_model_ids),
                        ~Model.model_id.in_(used_lora_ids)
                    )
                )
            
            results = query_obj.order_by(Model.name).limit(limit).all()
            
            # 使用回数を計算
            model_usage = {}
            for model in results:
                usage_count = 0
                if model.type == 'checkpoint':
                    usage_count = session.query(Run).filter(Run.model_id == model.model_id).count()
                elif model.type == 'lora':
                    usage_count = session.query(RunLora).filter(RunLora.lora_id == model.model_id).count()
                model_usage[model.model_id] = usage_count
            
            # セッションから切り離し
            for result in results:
                session.expunge(result)
        
        if not results:
            display_warning("条件にマッチするモデルが見つかりません")
            return
        
        display_info(f"モデル検索結果: {len(results)}件")
        
        if output == 'table':
            table_data = []
            for model in results:
                table_data.append([
                    str(model.model_id),
                    model.name[:30] + '...' if len(model.name) > 30 else model.name,
                    model.type,
                    str(model_usage.get(model.model_id, 0)),
                    format_datetime(model.created_at)
                ])
            
            display_table(
                ['ID', 'モデル名', 'タイプ', '使用回数', '登録日時'],
                table_data,
                'モデル一覧'
            )
        elif output == 'json':
            output_json(results)
        elif output == 'yaml':
            output_yaml(results)
            
    except Exception as e:
        handle_database_error(e)


@search_commands.command()
@click.argument('lora_name', required=True)
@click.option(
    '--status',
    type=click.Choice(['Purchased', 'Tried', 'Tuned', 'Final']),
    multiple=True,
    help='フィルタするステータス（複数指定可能）'
)
@click.option(
    '--limit',
    type=int,
    default=20,
    help='表示件数の制限'
)
@click.option(
    '--output', '-o',
    type=click.Choice(['table', 'json', 'yaml']),
    default='table',
    help='出力形式'
)
@click.pass_context
def lora(
    ctx: click.Context,
    lora_name: str,
    status: tuple,
    limit: int,
    output: str
) -> None:
    """指定されたLoRAを使用している実行履歴を検索します.
    
    特定のLoRAモデルを使用している実行履歴を検索・表示します。
    """
    state = CliState(ctx)
    
    try:
        db_manager = state.db_manager
        
        with db_manager.get_session() as session:
            # LoRAモデルを検索
            lora_models = session.query(Model).filter(
                and_(
                    Model.type == 'lora',
                    Model.name.contains(lora_name)
                )
            ).all()
            
            if not lora_models:
                display_warning(f"LoRAモデル '{lora_name}' が見つかりません")
                return
            
            if len(lora_models) > 1:
                display_info("複数のLoRAモデルが見つかりました:")
                for model in lora_models:
                    click.echo(f"  - {model.name}")
                display_info("最初にマッチしたLoRAを使用します")
            
            lora_model = lora_models[0]
            display_info(f"検索対象LoRA: {lora_model.name}")
            
            # 実行履歴を検索
            query_obj = session.query(Run).join(RunLora).filter(
                RunLora.lora_id == lora_model.model_id
            )
            
            # ステータスフィルタ
            if status:
                query_obj = query_obj.filter(Run.status.in_(status))
            
            results = query_obj.order_by(desc(Run.created_at)).limit(limit).all()
            
            # LoRAの重みも取得
            lora_weights = {}
            for run in results:
                run_lora = session.query(RunLora).filter(
                    and_(
                        RunLora.run_id == run.run_id,
                        RunLora.lora_id == lora_model.model_id
                    )
                ).first()
                if run_lora:
                    lora_weights[run.run_id] = run_lora.weight
            
            # セッションから切り離し
            for result in results:
                session.expunge(result)
        
        if not results:
            display_warning(f"LoRA '{lora_model.name}' を使用している実行履歴が見つかりません")
            return
        
        display_success(f"検索結果: {len(results)}件の実行履歴で '{lora_model.name}' が使用されています")
        
        if output == 'table':
            table_data = []
            for run in results:
                weight = lora_weights.get(run.run_id, 1.0)
                prompt_preview = run.prompt[:35] + '...' if len(run.prompt) > 35 else run.prompt
                
                table_data.append([
                    str(run.run_id),
                    run.title[:20] + '...' if len(run.title) > 20 else run.title,
                    prompt_preview,
                    format_status(run.status),
                    f"{weight:.2f}",
                    format_datetime(run.created_at)
                ])
            
            display_table(
                ['ID', 'タイトル', 'プロンプト', 'ステータス', '重み', '作成日時'],
                table_data,
                f'LoRA使用履歴: {lora_model.name}'
            )
        elif output == 'json':
            output_json(results)
        elif output == 'yaml':
            output_yaml(results)
            
    except Exception as e:
        handle_database_error(e)


@search_commands.command()
@click.option(
    '--date-from',
    type=click.DateTime(formats=['%Y-%m-%d', '%Y-%m-%d %H:%M:%S']),
    default=None,
    help='検索開始日時 (YYYY-MM-DD または YYYY-MM-DD HH:MM:SS)'
)
@click.option(
    '--date-to',
    type=click.DateTime(formats=['%Y-%m-%d', '%Y-%m-%d %H:%M:%S']),
    default=None,
    help='検索終了日時 (YYYY-MM-DD または YYYY-MM-DD HH:MM:SS)'
)
@click.option(
    '--status',
    type=click.Choice(['Purchased', 'Tried', 'Tuned', 'Final']),
    multiple=True,
    help='フィルタするステータス（複数指定可能）'
)
@click.option(
    '--cfg-min',
    type=float,
    default=None,
    help='CFGの最小値'
)
@click.option(
    '--cfg-max',
    type=float,
    default=None,
    help='CFGの最大値'
)
@click.option(
    '--steps-min',
    type=int,
    default=None,
    help='Stepsの最小値'
)
@click.option(
    '--steps-max',
    type=int,
    default=None,
    help='Stepsの最大値'
)
@click.option(
    '--sampler',
    default=None,
    help='サンプラーでフィルタ'
)
@click.option(
    '--limit',
    type=int,
    default=50,
    help='表示件数の制限'
)
@click.option(
    '--output', '-o',
    type=click.Choice(['table', 'json', 'yaml']),
    default='table',
    help='出力形式'
)
@click.pass_context
def advanced(
    ctx: click.Context,
    date_from: Optional[datetime],
    date_to: Optional[datetime],
    status: tuple,
    cfg_min: Optional[float],
    cfg_max: Optional[float],
    steps_min: Optional[int],
    steps_max: Optional[int],
    sampler: Optional[str],
    limit: int,
    output: str
) -> None:
    """高度な条件で実行履歴を検索します.
    
    日時範囲、パラメータ値、サンプラーなどの詳細条件で検索します。
    """
    state = CliState(ctx)
    
    try:
        db_manager = state.db_manager
        
        with db_manager.get_session() as session:
            query_obj = session.query(Run)
            
            # 日時フィルタ
            if date_from:
                query_obj = query_obj.filter(Run.created_at >= date_from)
            if date_to:
                query_obj = query_obj.filter(Run.created_at <= date_to)
            
            # ステータスフィルタ
            if status:
                query_obj = query_obj.filter(Run.status.in_(status))
            
            # CFGフィルタ
            if cfg_min is not None:
                query_obj = query_obj.filter(Run.cfg >= cfg_min)
            if cfg_max is not None:
                query_obj = query_obj.filter(Run.cfg <= cfg_max)
            
            # Stepsフィルタ
            if steps_min is not None:
                query_obj = query_obj.filter(Run.steps >= steps_min)
            if steps_max is not None:
                query_obj = query_obj.filter(Run.steps <= steps_max)
            
            # サンプラーフィルタ
            if sampler:
                query_obj = query_obj.filter(Run.sampler.contains(sampler))
            
            results = query_obj.order_by(desc(Run.created_at)).limit(limit).all()
            
            # セッションから切り離し
            for result in results:
                session.expunge(result)
        
        if not results:
            display_warning("指定された条件にマッチする実行履歴が見つかりません")
            return
        
        # 検索条件を表示
        conditions = []
        if date_from:
            conditions.append(f"開始日時: {date_from.strftime('%Y-%m-%d %H:%M:%S')}")
        if date_to:
            conditions.append(f"終了日時: {date_to.strftime('%Y-%m-%d %H:%M:%S')}")
        if status:
            conditions.append(f"ステータス: {', '.join(status)}")
        if cfg_min is not None or cfg_max is not None:
            cfg_range = f"CFG: {cfg_min or '−'}〜{cfg_max or '+'}"
            conditions.append(cfg_range)
        if steps_min is not None or steps_max is not None:
            steps_range = f"Steps: {steps_min or '−'}〜{steps_max or '+'}"
            conditions.append(steps_range)
        if sampler:
            conditions.append(f"サンプラー: {sampler}")
        
        if conditions:
            display_info("検索条件: " + " | ".join(conditions))
        
        display_success(f"検索結果: {len(results)}件")
        
        if output == 'table':
            table_data = []
            for run in results:
                table_data.append([
                    str(run.run_id),
                    run.title[:20] + '...' if len(run.title) > 20 else run.title,
                    format_status(run.status),
                    f"{run.cfg:.1f}",
                    str(run.steps),
                    run.sampler[:15] + '...' if len(run.sampler) > 15 else run.sampler,
                    format_datetime(run.created_at)
                ])
            
            display_table(
                ['ID', 'タイトル', 'ステータス', 'CFG', 'Steps', 'サンプラー', '作成日時'],
                table_data,
                '高度検索結果'
            )
        elif output == 'json':
            output_json(results)
        elif output == 'yaml':
            output_yaml(results)
            
    except Exception as e:
        handle_database_error(e)


@search_commands.command()
@click.option(
    '--output', '-o',
    type=click.Choice(['table', 'json', 'yaml']),
    default='table',
    help='出力形式'
)
@click.pass_context
def stats(ctx: click.Context, output: str) -> None:
    """検索統計情報を表示します.
    
    データベース内のデータの統計情報を表示します。
    """
    state = CliState(ctx)
    
    try:
        db_manager = state.db_manager
        
        with db_manager.get_session() as session:
            # ステータス別統計
            status_stats = []
            for status in ['Purchased', 'Tried', 'Tuned', 'Final']:
                count = session.query(Run).filter(Run.status == status).count()
                status_stats.append([status, str(count)])
            
            # モデルタイプ別統計
            model_stats = []
            for model_type in ['checkpoint', 'lora', 'vae', 'controlnet']:
                count = session.query(Model).filter(Model.type == model_type).count()
                model_stats.append([model_type, str(count)])
            
            # サンプラー別統計
            sampler_stats = session.query(
                Run.sampler, 
                func.count().label('count')
            ).group_by(Run.sampler).order_by(desc('count')).limit(10).all()
            
            # CFG統計
            cfg_stats = session.query(
                Run.cfg,
                func.count().label('count')
            ).group_by(Run.cfg).order_by(desc('count')).limit(10).all()
        
        if output == 'table':
            # ステータス別統計を表示
            display_table(
                ['ステータス', '件数'],
                status_stats,
                'ステータス別統計'
            )
            
            # モデルタイプ別統計を表示
            display_table(
                ['モデルタイプ', '件数'],
                model_stats,
                'モデルタイプ別統計'
            )
            
            # サンプラー別統計を表示（上位10位）
            if sampler_stats:
                sampler_data = [[s[0], str(s[1])] for s in sampler_stats]
                display_table(
                    ['サンプラー', '使用回数'],
                    sampler_data,
                    'サンプラー使用頻度 (上位10位)'
                )
            
            # CFG値別統計を表示（上位10位）
            if cfg_stats:
                cfg_data = [[str(c[0]), str(c[1])] for c in cfg_stats]
                display_table(
                    ['CFG値', '使用回数'],
                    cfg_data,
                    'CFG値使用頻度 (上位10位)'
                )
                
        elif output == 'json':
            stats_data = {
                'status_stats': {str(k): int(v) for k, v in status_stats},
                'model_stats': {str(k): int(v) for k, v in model_stats},
                'sampler_stats': {str(k): int(v) for k, v in sampler_stats},
                'cfg_stats': {str(k): int(v) for k, v in cfg_stats}
            }
            output_json(stats_data)
        elif output == 'yaml':
            stats_data = {
                'status_stats': {str(k): int(v) for k, v in status_stats},
                'model_stats': {str(k): int(v) for k, v in model_stats},
                'sampler_stats': {str(k): int(v) for k, v in sampler_stats},
                'cfg_stats': {str(k): int(v) for k, v in cfg_stats}
            }
            output_yaml(stats_data)
            
    except Exception as e:
        handle_database_error(e)