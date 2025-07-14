"""
Notion CLI commands for SDXL Asset Manager.

This module provides CLI commands for Notion API integration including
setup, sync, status, and conflict resolution.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

import click
from tabulate import tabulate

from ..notion_client import NotionClient
from ..notion_sync import NotionSyncManager

# Configure logging
logger = logging.getLogger(__name__)


@click.group()
def notion():
    """Notion API連携機能。"""
    pass


@notion.command()
@click.option('--api-key', prompt='Notion API Key', help='Notion API キー')
@click.option('--database-id', prompt='Database ID', help='NotionデータベースID')
@click.option('--test-connection', is_flag=True, help='設定後に接続テストを実行')
def setup(api_key: str, database_id: str, test_connection: bool):
    """
    Notion API の設定を行う。

    APIキーとデータベースIDを.envファイルに保存し、
    オプションで接続テストを実行します。
    """
    try:
        # .envファイルのパスを取得
        env_path = os.path.join(os.getcwd(), '.env')

        # 既存の.envファイルを読み込む
        env_lines = []
        if os.path.exists(env_path):
            with open(env_path, encoding='utf-8') as f:
                env_lines = f.readlines()

        # 新しい設定を追加または更新
        new_env_lines = []
        api_key_updated = False
        database_id_updated = False

        for line in env_lines:
            if line.startswith('NOTION_API_KEY='):
                new_env_lines.append(f'NOTION_API_KEY={api_key}\n')
                api_key_updated = True
            elif line.startswith('NOTION_DATABASE_ID='):
                new_env_lines.append(f'NOTION_DATABASE_ID={database_id}\n')
                database_id_updated = True
            else:
                new_env_lines.append(line)

        # 新しい設定を追加
        if not api_key_updated:
            new_env_lines.append(f'NOTION_API_KEY={api_key}\n')
        if not database_id_updated:
            new_env_lines.append(f'NOTION_DATABASE_ID={database_id}\n')

        # .envファイルに保存
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(new_env_lines)

        click.echo("✅ Notion API設定が保存されました。")
        click.echo(f"📁 設定ファイル: {env_path}")

        # 環境変数を更新
        os.environ['NOTION_API_KEY'] = api_key
        os.environ['NOTION_DATABASE_ID'] = database_id

        # 接続テスト
        if test_connection:
            click.echo("\n🔄 接続テストを実行しています...")
            result = asyncio.run(_test_connection_async(api_key, database_id))

            if result["success"]:
                click.echo("✅ 接続テスト成功!")
                click.echo(f"📊 データベース: {result.get('database_title', 'Unknown')}")
            else:
                click.echo("❌ 接続テスト失敗:")
                click.echo(f"エラー: {result.get('error', 'Unknown error')}")

    except Exception as e:
        click.echo(f"❌ 設定の保存に失敗しました: {e}")
        logger.error(f"Setup failed: {e}")


@notion.command()
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']),
              default='table', help='出力形式')
def status(output_format: str):
    """
    Notion API の接続状況と設定を確認する。

    現在の設定と接続状況を表示します。
    """
    try:
        # 環境変数を取得
        api_key = os.getenv('NOTION_API_KEY')
        database_id = os.getenv('NOTION_DATABASE_ID')

        status_data = {
            "api_key_configured": bool(api_key),
            "database_id_configured": bool(database_id),
            "api_key_preview": f"{api_key[:8]}..." if api_key else None,
            "database_id": database_id,
            "connection_status": "未テスト"
        }

        if api_key and database_id:
            # 接続テスト
            result = asyncio.run(_test_connection_async(api_key, database_id))
            status_data.update({
                "connection_status": "成功" if result["success"] else "失敗",
                "database_title": result.get("database_title"),
                "error": result.get("error")
            })

        # 出力
        if output_format == 'json':
            click.echo(json.dumps(status_data, ensure_ascii=False, indent=2))
        else:
            _print_status_table(status_data)

    except Exception as e:
        click.echo(f"❌ ステータス確認に失敗しました: {e}")
        logger.error(f"Status check failed: {e}")


@notion.command()
@click.option('--direction', type=click.Choice(['from', 'to', 'both']),
              default='both', help='同期方向')
@click.option('--dry-run', is_flag=True, help='実際の変更を行わず、変更内容をプレビュー')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']),
              default='table', help='出力形式')
def sync(direction: str, dry_run: bool, output_format: str):
    """
    Notion と ローカルデータベースを同期する。

    --direction from: Notion → Local
    --direction to: Local → Notion
    --direction both: 双方向同期
    """
    try:
        # 設定を取得
        api_key = os.getenv('NOTION_API_KEY')
        database_id = os.getenv('NOTION_DATABASE_ID')

        if not api_key or not database_id:
            click.echo("❌ Notion API設定が見つかりません。")
            click.echo("'notion setup' コマンドで設定を行ってください。")
            return

        # 同期実行
        if dry_run:
            click.echo("🔍 ドライランモード: 実際の変更は行いません")

        click.echo(f"🔄 同期を開始しています... (方向: {direction})")

        result = asyncio.run(_sync_async(api_key, database_id, direction, dry_run))

        # 結果を表示
        if output_format == 'json':
            click.echo(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            _print_sync_results(result, direction, dry_run)

    except Exception as e:
        click.echo(f"❌ 同期に失敗しました: {e}")
        logger.error(f"Sync failed: {e}")


@notion.command()
@click.option('--resolve', type=click.Choice(['auto', 'manual']),
              help='競合解決方法')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']),
              default='table', help='出力形式')
def conflicts(resolve: Optional[str], output_format: str):
    """
    競合を検出・解決する。

    NotionとローカルDBの間の競合を検出し、オプションで解決します。
    """
    try:
        # 設定を取得
        api_key = os.getenv('NOTION_API_KEY')
        database_id = os.getenv('NOTION_DATABASE_ID')

        if not api_key or not database_id:
            click.echo("❌ Notion API設定が見つかりません。")
            click.echo("'notion setup' コマンドで設定を行ってください。")
            return

        click.echo("🔍 競合を検出しています...")

        conflicts_data = asyncio.run(_detect_conflicts_async(api_key, database_id))

        if not conflicts_data:
            click.echo("✅ 競合は見つかりませんでした。")
            return

        # 競合を表示
        if output_format == 'json':
            click.echo(json.dumps(conflicts_data, ensure_ascii=False, indent=2))
        else:
            _print_conflicts_table(conflicts_data)

        # 自動解決
        if resolve == 'auto':
            click.echo("\n🔄 自動解決を実行しています...")
            # 最新の更新時刻を優先して解決
            result = asyncio.run(_resolve_conflicts_auto(api_key, database_id))
            click.echo(f"✅ {result['resolved']} 件の競合を解決しました。")

        elif resolve == 'manual':
            click.echo("\n⚠️ 手動解決は現在実装されていません。")
            click.echo("auto解決を使用するか、手動で Notion または Local DB を更新してください。")

    except Exception as e:
        click.echo(f"❌ 競合検出に失敗しました: {e}")
        logger.error(f"Conflict detection failed: {e}")


@notion.command()
@click.option('--confirm', is_flag=True, help='確認なしで実行')
def init_database(confirm: bool):
    """
    Notion データベースを初期化する。

    必要なプロパティを持つNotionデータベースを作成します。
    """
    if not confirm:
        click.echo("⚠️ この機能は現在実装されていません。")
        click.echo("Notionで手動でデータベースを作成し、以下のプロパティを追加してください:")
        click.echo("")

        properties = [
            ("Title", "title", "タイトル"),
            ("Prompt", "rich_text", "プロンプト"),
            ("Negative", "rich_text", "ネガティブプロンプト"),
            ("CFG", "number", "CFG値"),
            ("Steps", "number", "ステップ数"),
            ("Sampler", "select", "サンプラー"),
            ("Seed", "number", "シード値"),
            ("Width", "number", "幅"),
            ("Height", "number", "高さ"),
            ("Model", "select", "モデル"),
            ("LoRAs", "multi_select", "LoRA"),
            ("Tags", "multi_select", "タグ"),
            ("Status", "select", "ステータス"),
            ("Image_Path", "url", "画像パス"),
            ("Notes", "rich_text", "メモ")
        ]

        headers = ["プロパティ名", "タイプ", "説明"]
        table_data = [(prop[0], prop[1], prop[2]) for prop in properties]

        click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))
        click.echo("")
        click.echo("データベース作成後、'notion setup' コマンドで設定を行ってください。")


# Helper functions

async def _test_connection_async(api_key: str, database_id: str) -> Dict[str, Any]:
    """Test Notion API connection asynchronously."""
    try:
        client = NotionClient(api_key, database_id)
        return await client.test_connection()
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "接続失敗"
        }


async def _sync_async(
    api_key: str,
    database_id: str,
    direction: str,
    dry_run: bool
) -> Dict[str, Any]:
    """Perform sync operation asynchronously."""
    try:
        client = NotionClient(api_key, database_id)
        sync_manager = NotionSyncManager(client, dry_run=dry_run)

        if direction == 'from':
            stats = await sync_manager.sync_from_notion()
        elif direction == 'to':
            stats = await sync_manager.sync_to_notion()
        elif direction == 'both':
            stats = await sync_manager.sync_bidirectional()

        return {
            "success": True,
            "direction": direction,
            "dry_run": dry_run,
            "stats": {
                "total_notion_pages": stats.total_notion_pages,
                "total_local_runs": stats.total_local_runs,
                "created_local": stats.created_local,
                "updated_local": stats.updated_local,
                "created_notion": stats.created_notion,
                "updated_notion": stats.updated_notion,
                "skipped": stats.skipped,
                "conflicts": stats.conflicts,
                "errors": stats.errors
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "同期失敗"
        }


async def _detect_conflicts_async(api_key: str, database_id: str) -> List[Dict[str, Any]]:
    """Detect conflicts asynchronously."""
    try:
        client = NotionClient(api_key, database_id)
        sync_manager = NotionSyncManager(client)

        return await sync_manager.detect_conflicts()
    except Exception as e:
        logger.error(f"Conflict detection failed: {e}")
        return []


async def _resolve_conflicts_auto(api_key: str, database_id: str) -> Dict[str, Any]:
    """Resolve conflicts automatically (latest wins)."""
    try:
        client = NotionClient(api_key, database_id)
        sync_manager = NotionSyncManager(client)

        # 双方向同期を実行（競合解決含む）
        stats = await sync_manager.sync_bidirectional()

        return {
            "success": True,
            "resolved": stats.updated_local + stats.updated_notion,
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Auto conflict resolution failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "resolved": 0
        }


def _print_status_table(status_data: Dict[str, Any]) -> None:
    """Print status in table format."""
    click.echo("📊 Notion API Status")
    click.echo("=" * 50)

    table_data = [
        ["API Key", "✅ 設定済み" if status_data["api_key_configured"] else "❌ 未設定"],
        ["Database ID", "✅ 設定済み" if status_data["database_id_configured"] else "❌ 未設定"],
        ["接続状況", _get_connection_status_emoji(status_data["connection_status"])],
    ]

    if status_data.get("database_title"):
        table_data.append(["データベース名", status_data["database_title"]])

    if status_data.get("error"):
        table_data.append(["エラー", status_data["error"]])

    click.echo(tabulate(table_data, headers=["項目", "状態"], tablefmt="grid"))


def _print_sync_results(result: Dict[str, Any], direction: str, dry_run: bool) -> None:
    """Print sync results in table format."""
    if not result["success"]:
        click.echo(f"❌ 同期失敗: {result.get('error', 'Unknown error')}")
        return

    stats = result["stats"]

    click.echo(f"✅ 同期完了 {'(ドライラン)' if dry_run else ''}")
    click.echo(f"📊 同期方向: {direction}")
    click.echo("=" * 50)

    table_data = [
        ["Notion総ページ数", stats["total_notion_pages"]],
        ["Local総実行数", stats["total_local_runs"]],
        ["Local作成", stats["created_local"]],
        ["Local更新", stats["updated_local"]],
        ["Notion作成", stats["created_notion"]],
        ["Notion更新", stats["updated_notion"]],
        ["スキップ", stats["skipped"]],
        ["競合", stats["conflicts"]],
        ["エラー", stats["errors"]]
    ]

    click.echo(tabulate(table_data, headers=["項目", "件数"], tablefmt="grid"))


def _print_conflicts_table(conflicts_data: List[Dict[str, Any]]) -> None:
    """Print conflicts in table format."""
    click.echo(f"⚠️ {len(conflicts_data)} 件の競合が見つかりました")
    click.echo("=" * 80)

    table_data = []
    for conflict in conflicts_data:
        table_data.append([
            conflict["run_id"],
            conflict["local_title"][:30] + "..." if len(conflict["local_title"]) > 30 else conflict["local_title"],
            conflict["notion_title"][:30] + "..." if len(conflict["notion_title"]) > 30 else conflict["notion_title"],
            conflict["local_modified"].strftime("%Y-%m-%d %H:%M") if conflict["local_modified"] else "N/A",
            conflict["notion_modified"].strftime("%Y-%m-%d %H:%M") if conflict["notion_modified"] else "N/A",
            conflict["conflict_type"]
        ])

    headers = ["Run ID", "Local Title", "Notion Title", "Local Modified", "Notion Modified", "Type"]
    click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))


def _get_connection_status_emoji(status: str) -> str:
    """Get emoji for connection status."""
    if status == "成功":
        return "✅ 成功"
    elif status == "失敗":
        return "❌ 失敗"
    else:
        return "⏳ 未テスト"


if __name__ == "__main__":
    notion()
