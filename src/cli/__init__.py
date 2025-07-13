"""Main CLI entry point for SDXL Asset Manager.

このモジュールはSDXL Asset Managerのメインコマンドラインインターフェースを提供します。
"""

import sys
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv

from .db import db_commands
from .run import run_commands
from .search import search_commands
from .yaml_cmd import yaml_commands


def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """ログレベルを設定します.

    Args:
        verbose: 詳細ログを有効にする
        quiet: 警告以上のみ表示
    """
    import logging

    if quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


@click.group()
@click.option(
    '--config',
    type=click.Path(exists=True),
    default=None,
    help='設定ファイルのパス (デフォルト: .env)'
)
@click.option(
    '--db',
    type=click.Path(),
    default=None,
    help='データベースファイルのパス (デフォルト: data/asset_manager.db)'
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='詳細ログを有効にする'
)
@click.option(
    '--quiet', '-q',
    is_flag=True,
    help='警告以上のメッセージのみ表示'
)
@click.pass_context
def cli(
    ctx: click.Context,
    config: Optional[str],
    db: Optional[str],
    verbose: bool,
    quiet: bool
) -> None:
    """SDXL Asset Manager - 画像生成ワークフロー統合管理システム.

    データベース操作、YAML処理、検索機能などの基本コマンドを提供します。
    """
    # ログ設定
    setup_logging(verbose, quiet)

    # コンテキストオブジェクトを初期化
    ctx.ensure_object(dict)

    # グローバル設定を保存
    ctx.obj['config_path'] = config
    ctx.obj['db_path'] = db
    ctx.obj['verbose'] = verbose
    ctx.obj['quiet'] = quiet

    # .envファイルを読み込み
    if config:
        load_dotenv(config)
    elif Path('.env').exists():
        load_dotenv()


def handle_error(error: Exception, exit_code: int = 1) -> None:
    """エラーを処理して適切な終了コードで終了します.

    Args:
        error: 処理するエラー
        exit_code: 終了コード
    """
    import logging

    logger = logging.getLogger(__name__)

    if isinstance(error, click.ClickException):
        # Clickエラーはそのまま表示
        error.show()
        sys.exit(error.exit_code)
    elif isinstance(error, FileNotFoundError):
        logger.error(f"ファイルが見つかりません: {error}")
        sys.exit(3)  # ファイルエラー
    else:
        logger.error(f"予期しないエラーが発生しました: {error}")

        # --verboseが有効な場合はスタックトレースを表示
        if '--verbose' in sys.argv or '-v' in sys.argv:
            import traceback
            logger.debug(traceback.format_exc())

        sys.exit(exit_code)


# サブコマンドグループを追加
cli.add_command(db_commands)
cli.add_command(yaml_commands)
cli.add_command(search_commands)
cli.add_command(run_commands)

__all__ = ["cli", "setup_logging", "handle_error", "db_commands", "yaml_commands", "search_commands", "run_commands"]
