"""CLI共通ユーティリティ機能.

このモジュールはCLIコマンド間で共有される共通機能を提供します。
"""

from typing import Any, List, Optional

import click
from sqlalchemy.exc import SQLAlchemyError

from src.utils.db_utils import DatabaseManager


def get_database_manager(ctx: click.Context) -> DatabaseManager:
    """コンテキストからDatabaseManagerインスタンスを取得します.

    Args:
        ctx: Click コンテキスト

    Returns:
        DatabaseManager インスタンス

    Raises:
        click.ClickException: データベース接続エラー
    """
    try:
        db_path = ctx.obj.get('db_path')
        return DatabaseManager(db_path)
    except Exception as e:
        raise click.ClickException(f"データベース接続エラー: {e}") from e


def confirm_dangerous_action(message: str, force: bool = False) -> bool:
    """危険な操作の確認プロンプトを表示します.

    Args:
        message: 確認メッセージ
        force: 強制実行フラグ

    Returns:
        実行を継続する場合True
    """
    if force:
        return True

    return click.confirm(
        click.style(f"⚠️  {message}", fg='yellow', bold=True),
        default=False
    )


def display_success(message: str) -> None:
    """成功メッセージを表示します.

    Args:
        message: 表示するメッセージ
    """
    click.echo(click.style(f"✅ {message}", fg='green', bold=True))


def display_error(message: str) -> None:
    """エラーメッセージを表示します.

    Args:
        message: 表示するメッセージ
    """
    click.echo(click.style(f"❌ {message}", fg='red', bold=True), err=True)


def display_warning(message: str) -> None:
    """警告メッセージを表示します.

    Args:
        message: 表示するメッセージ
    """
    click.echo(click.style(f"⚠️  {message}", fg='yellow', bold=True))


def display_info(message: str) -> None:
    """情報メッセージを表示します.

    Args:
        message: 表示するメッセージ
    """
    click.echo(click.style(f"ℹ️  {message}", fg='blue'))


def display_table(headers: List[str], rows: List[List[str]], title: Optional[str] = None) -> None:
    """テーブル形式でデータを表示します.

    Args:
        headers: ヘッダーのリスト
        rows: データ行のリスト
        title: テーブルのタイトル
    """
    if title:
        click.echo(click.style(f"\n{title}", fg='cyan', bold=True))
        click.echo(click.style("=" * len(title), fg='cyan'))

    if not rows:
        display_info("表示するデータがありません")
        return

    # カラム幅を計算
    col_widths = []
    for i, header in enumerate(headers):
        max_width = len(header)
        for row in rows:
            if i < len(row):
                max_width = max(max_width, len(str(row[i])))
        col_widths.append(max_width + 2)

    # ヘッダーを表示
    header_line = "".join(h.ljust(w) for h, w in zip(headers, col_widths, strict=False))
    click.echo(click.style(header_line, fg='white', bold=True))
    click.echo(click.style("-" * len(header_line), fg='white'))

    # データ行を表示
    for row in rows:
        row_data = []
        for i, cell in enumerate(row):
            if i < len(col_widths):
                row_data.append(str(cell).ljust(col_widths[i]))
        click.echo("".join(row_data))


def format_datetime(dt: Any) -> str:
    """日時を読みやすい形式でフォーマットします.

    Args:
        dt: datetime オブジェクト

    Returns:
        フォーマットされた日時文字列
    """
    if dt is None:
        return "N/A"

    try:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except AttributeError:
        return str(dt)


def format_status(status: str) -> str:
    """ステータスを色付きでフォーマットします.

    Args:
        status: ステータス文字列

    Returns:
        色付きステータス文字列
    """
    status_colors = {
        'Purchased': 'blue',
        'Tried': 'yellow',
        'Tuned': 'magenta',
        'Final': 'green'
    }

    color = status_colors.get(status, 'white')
    return click.style(status, fg=color, bold=True)


def validate_output_format(output_format: str) -> str:
    """出力形式を検証します.

    Args:
        output_format: 出力形式

    Returns:
        検証済み出力形式

    Raises:
        click.BadParameter: 無効な出力形式
    """
    valid_formats = ['table', 'json', 'yaml']
    if output_format not in valid_formats:
        raise click.BadParameter(
            f"無効な出力形式: {output_format}。有効な形式: {', '.join(valid_formats)}"
        )
    return output_format


def output_json(data: Any) -> None:
    """JSON形式でデータを出力します.

    Args:
        data: 出力するデータ
    """
    import json

    def default_serializer(obj):
        """JSON serialization用のデフォルトシリアライザ."""
        if hasattr(obj, '__dict__'):
            # SQLAlchemyモデルの場合
            result = {}
            for key, value in obj.__dict__.items():
                if not key.startswith('_'):
                    if hasattr(value, 'isoformat'):  # datetime
                        result[key] = value.isoformat()
                    else:
                        result[key] = value
            return result
        elif hasattr(obj, 'isoformat'):  # datetime
            return obj.isoformat()
        return str(obj)

    click.echo(json.dumps(data, default=default_serializer, indent=2, ensure_ascii=False))


def output_yaml(data: Any) -> None:
    """YAML形式でデータを出力します.

    Args:
        data: 出力するデータ
    """
    import yaml

    # SQLAlchemyオブジェクトを辞書に変換
    def convert_to_dict(obj):
        if hasattr(obj, '__dict__'):
            result = {}
            for key, value in obj.__dict__.items():
                if not key.startswith('_'):
                    if hasattr(value, 'isoformat'):  # datetime
                        result[key] = value.isoformat()
                    elif hasattr(value, '__dict__'):
                        result[key] = convert_to_dict(value)
                    elif isinstance(value, list):
                        result[key] = [convert_to_dict(item) if hasattr(item, '__dict__') else item for item in value]
                    else:
                        result[key] = value
            return result
        return obj

    if isinstance(data, list):
        converted_data = [convert_to_dict(item) for item in data]
    else:
        converted_data = convert_to_dict(data)

    click.echo(yaml.dump(converted_data, allow_unicode=True, default_flow_style=False))


def handle_database_error(error: Exception) -> None:
    """データベースエラーを処理します.

    Args:
        error: 処理するエラー

    Raises:
        click.ClickException: 適切なエラーメッセージ付き
    """
    if isinstance(error, SQLAlchemyError):
        raise click.ClickException(f"データベースエラー: {error}")
    else:
        raise click.ClickException(f"予期しないエラー: {error}")


def progress_bar(items, label: str = "処理中"):
    """プログレスバーを表示します.

    Args:
        items: 処理するアイテムのイテラブル
        label: プログレスバーのラベル

    Yields:
        各アイテム
    """
    with click.progressbar(items, label=label) as bar:  # type: ignore[var-annotated]
        yield from bar


class CliState:
    """CLI実行状態を管理するクラス."""

    def __init__(self, ctx: click.Context):
        """CLI状態を初期化します.

        Args:
            ctx: Click コンテキスト
        """
        self.ctx = ctx
        self._db_manager: DatabaseManager | None = None

    @property
    def db_manager(self) -> DatabaseManager:
        """DatabaseManager インスタンスを取得します."""
        if self._db_manager is None:
            self._db_manager = get_database_manager(self.ctx)
        assert self._db_manager is not None
        return self._db_manager

    @property
    def config_path(self) -> Optional[str]:
        """設定ファイルパスを取得します."""
        return self.ctx.obj.get('config_path')

    @property
    def db_path(self) -> Optional[str]:
        """データベースファイルパスを取得します."""
        return self.ctx.obj.get('db_path')

    @property
    def verbose(self) -> bool:
        """詳細ログフラグを取得します."""
        return self.ctx.obj.get('verbose', False)

    @property
    def quiet(self) -> bool:
        """静寂モードフラグを取得します."""
        return self.ctx.obj.get('quiet', False)
