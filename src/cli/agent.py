"""LLMエージェントコマンド.

このモジュールはLLMエージェントを使用した対話型相談、データ分析、最適化提案機能を提供します。
"""

import json
import os
from typing import Dict, List

import click

from src.agent_tools.chat_agent import ChatAgent, LLMError

from .utils import (
    CliState,
    display_error,
    display_info,
    display_success,
    display_table,
    display_warning,
    handle_database_error,
    output_json,
    output_yaml,
)


@click.group(name='agent')
@click.pass_context
def agent_commands(ctx: click.Context) -> None:
    """LLMエージェント機能.

    データベース内容に基づく対話型相談、データ分析、最適化提案を提供します。
    """
    pass


@agent_commands.command()
@click.option(
    '--provider', '-p',
    type=click.Choice(['openai', 'anthropic']),
    default='openai',
    help='LLM APIプロバイダー'
)
@click.option(
    '--save-history',
    is_flag=True,
    help='会話履歴を保存する'
)
@click.pass_context
def chat(ctx: click.Context, provider: str, save_history: bool) -> None:
    """対話型AI相談モード.

    データベース内容に基づいてAIとの対話で相談やアドバイスを受けられます。
    """
    state = CliState(ctx)

    try:
        # ChatAgentを初期化
        agent = ChatAgent(state.db_manager, api_provider=provider)

        display_info(f"🤖 LLMエージェント ({provider}) を起動しました")
        display_info("画像生成ワークフローについて何でも質問してください")
        display_info("終了するには 'quit' または 'exit' を入力してください")

        conversation_history: List[Dict[str, str]] = []

        while True:
            try:
                # ユーザー入力を取得
                user_input = click.prompt(
                    click.style("\n🧑 あなた", fg='blue', bold=True),
                    type=str
                ).strip()

                # 終了コマンドチェック
                if user_input.lower() in ['quit', 'exit', 'q']:
                    display_info("会話を終了します")
                    break

                # 空入力チェック
                if not user_input:
                    display_warning("メッセージを入力してください")
                    continue

                # AIの応答を取得
                display_info("🤖 考え中...")
                response = agent.chat(user_input, conversation_history)

                # 応答を表示
                click.echo(click.style("\n🤖 AIアシスタント:", fg='green', bold=True))
                click.echo(response)

                # 会話履歴を保存
                if save_history:
                    conversation_history.append({"role": "user", "content": user_input})
                    conversation_history.append({"role": "assistant", "content": response})

                    # 履歴が長すぎる場合は古いものを削除
                    if len(conversation_history) > 20:
                        conversation_history = conversation_history[-20:]

            except KeyboardInterrupt:
                display_info("\n会話を終了します")
                break
            except Exception as e:
                display_error(f"エラーが発生しました: {e}")
                continue

    except LLMError as e:
        display_error(f"LLMエラー: {e}")
        ctx.exit(1)
    except Exception as e:
        handle_database_error(e)


@agent_commands.command()
@click.option(
    '--type', '-t',
    type=click.Choice(['general', 'settings', 'trends']),
    default='general',
    help='分析タイプ'
)
@click.option(
    '--output', '-o',
    type=click.Choice(['text', 'json', 'yaml']),
    default='text',
    help='出力形式'
)
@click.option(
    '--provider', '-p',
    type=click.Choice(['openai', 'anthropic']),
    default='openai',
    help='LLM APIプロバイダー'
)
@click.pass_context
def analyze(ctx: click.Context, type: str, output: str, provider: str) -> None:
    """データベースの分析を実行.

    データベース内容を分析し、統計情報、傾向、最適化提案を提供します。
    """
    state = CliState(ctx)

    try:
        # ChatAgentを初期化
        agent = ChatAgent(state.db_manager, api_provider=provider)

        display_info(f"🔍 データベース分析を実行中... (タイプ: {type})")

        # 分析を実行
        analysis_result = agent.analyze_data(type)

        if output == 'text':
            display_success("📊 分析結果:")
            click.echo(analysis_result)
        elif output == 'json':
            result_data = {
                'analysis_type': type,
                'timestamp': agent.get_database_context(),
                'result': analysis_result
            }
            output_json(result_data)
        elif output == 'yaml':
            result_data = {
                'analysis_type': type,
                'timestamp': agent.get_database_context(),
                'result': analysis_result
            }
            output_yaml(result_data)

    except LLMError as e:
        display_error(f"LLMエラー: {e}")
        ctx.exit(1)
    except Exception as e:
        handle_database_error(e)


@agent_commands.command()
@click.option(
    '--target', '-t',
    type=click.Choice(['general', 'prompts', 'settings', 'workflow']),
    default='general',
    help='最適化対象'
)
@click.option(
    '--output', '-o',
    type=click.Choice(['text', 'json', 'yaml']),
    default='text',
    help='出力形式'
)
@click.option(
    '--provider', '-p',
    type=click.Choice(['openai', 'anthropic']),
    default='openai',
    help='LLM APIプロバイダー'
)
@click.pass_context
def recommend(ctx: click.Context, target: str, output: str, provider: str) -> None:
    """最適化提案を生成.

    現在のデータに基づいて、プロンプトや設定の最適化提案を生成します。
    """
    state = CliState(ctx)

    try:
        # ChatAgentを初期化
        agent = ChatAgent(state.db_manager, api_provider=provider)

        display_info(f"💡 最適化提案を生成中... (対象: {target})")

        # 最適化提案を生成
        recommendation = agent.recommend_optimization(target)

        if output == 'text':
            display_success("🎯 最適化提案:")
            click.echo(recommendation)
        elif output == 'json':
            result_data = {
                'target': target,
                'timestamp': agent.get_database_context(),
                'recommendation': recommendation
            }
            output_json(result_data)
        elif output == 'yaml':
            result_data = {
                'target': target,
                'timestamp': agent.get_database_context(),
                'recommendation': recommendation
            }
            output_yaml(result_data)

    except LLMError as e:
        display_error(f"LLMエラー: {e}")
        ctx.exit(1)
    except Exception as e:
        handle_database_error(e)


@agent_commands.command()
@click.argument('query', type=str)
@click.option(
    '--limit', '-l',
    type=int,
    default=5,
    help='表示する最大件数'
)
@click.option(
    '--with-analysis',
    is_flag=True,
    help='検索結果をAIに分析させる'
)
@click.option(
    '--provider', '-p',
    type=click.Choice(['openai', 'anthropic']),
    default='openai',
    help='LLM APIプロバイダー (--with-analysis使用時)'
)
@click.pass_context
def search(ctx: click.Context, query: str, limit: int, with_analysis: bool, provider: str) -> None:
    """類似実行の検索.

    プロンプトやタイトルに基づいて類似の実行を検索します。
    """
    state = CliState(ctx)

    try:
        # ChatAgentを初期化
        agent = ChatAgent(state.db_manager, api_provider=provider)

        display_info(f"🔍 検索中: '{query}'")

        # 類似実行を検索
        similar_runs = agent.search_similar_runs(query, limit)

        if not similar_runs:
            display_warning("検索結果が見つかりませんでした")
            return

        # 結果を表示
        display_success(f"📝 検索結果 ({len(similar_runs)}件):")

        table_data = []
        for run in similar_runs:
            table_data.append([
                str(run['id']),
                run['title'][:25] + '...' if len(run['title']) > 25 else run['title'],
                run['status'],
                f"{run['cfg']:.1f}",
                str(run['steps']),
                run['sampler'][:15] + '...' if len(run['sampler']) > 15 else run['sampler'],
                run['resolution']
            ])

        display_table(
            ['ID', 'タイトル', 'ステータス', 'CFG', 'Steps', 'サンプラー', '解像度'],
            table_data
        )

        # AI分析を実行
        if with_analysis:
            display_info("🤖 AI分析を実行中...")

            analysis_prompt = f"""以下の検索結果を分析してください:

検索クエリ: {query}
検索結果: {json.dumps(similar_runs, indent=2)}

分析観点:
1. 検索結果の特徴
2. 共通点と相違点
3. 設定の傾向
4. 改善提案

日本語で分析結果を提供してください。"""

            try:
                analysis = agent._call_llm([
                    {"role": "system", "content": "あなたは画像生成データの分析専門家です。"},
                    {"role": "user", "content": analysis_prompt}
                ])

                display_success("🎯 AI分析結果:")
                click.echo(analysis)

            except Exception as e:
                display_error(f"AI分析エラー: {e}")

    except LLMError as e:
        display_error(f"LLMエラー: {e}")
        ctx.exit(1)
    except Exception as e:
        handle_database_error(e)


@agent_commands.command()
@click.option(
    '--provider', '-p',
    type=click.Choice(['openai', 'anthropic']),
    default='openai',
    help='LLM APIプロバイダー'
)
@click.pass_context
def status(ctx: click.Context, provider: str) -> None:
    """エージェントの状態を確認.

    LLMエージェントの設定状況とAPIキー設定を確認します。
    """
    state = CliState(ctx)

    try:
        # API キーの確認
        status_info = []

        # OpenAI設定確認
        openai_key = os.getenv("OPENAI_API_KEY")
        openai_status = "✅ 設定済み" if openai_key else "❌ 未設定"
        status_info.append(["OpenAI API Key", openai_status])

        # Anthropic設定確認
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        anthropic_status = "✅ 設定済み" if anthropic_key else "❌ 未設定"
        status_info.append(["Anthropic API Key", anthropic_status])

        # 現在のプロバイダー
        status_info.append(["現在のプロバイダー", provider])

        # パッケージの確認
        try:
            import openai
            openai_version = openai.__version__
            status_info.append(["OpenAI Package", f"✅ {openai_version}"])
        except ImportError:
            status_info.append(["OpenAI Package", "❌ 未インストール"])

        try:
            import anthropic
            anthropic_version = anthropic.__version__
            status_info.append(["Anthropic Package", f"✅ {anthropic_version}"])
        except ImportError:
            status_info.append(["Anthropic Package", "❌ 未インストール"])

        # データベース統計
        try:
            agent = ChatAgent(state.db_manager, api_provider=provider)
            db_context = agent.get_database_context()

            status_info.append(["データベース", "✅ 接続成功"])
            status_info.append(["総実行数", str(db_context['runs']['total'])])
            status_info.append(["総モデル数", str(db_context['models']['total'])])

        except Exception as e:
            status_info.append(["データベース", f"❌ エラー: {e}"])

        # 状態テーブルを表示
        display_table(
            ['項目', '状態'],
            status_info,
            'LLMエージェント状態'
        )

        # 設定ガイド
        if not openai_key and not anthropic_key:
            display_warning("APIキーが設定されていません")
            display_info("設定方法:")
            display_info("  OpenAI: export OPENAI_API_KEY=your_key_here")
            display_info("  Anthropic: export ANTHROPIC_API_KEY=your_key_here")

    except Exception as e:
        handle_database_error(e)


@agent_commands.command()
@click.pass_context
def demo(ctx: click.Context) -> None:
    """デモ実行.

    LLMエージェントの機能デモを実行します。
    """
    state = CliState(ctx)

    try:
        display_info("🎬 LLMエージェントデモを開始します")

        # API キーの確認
        openai_key = os.getenv("OPENAI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")

        if not openai_key and not anthropic_key:
            display_error("APIキーが設定されていません")
            display_info("デモを実行するには、OpenAIまたはAnthropicのAPIキーが必要です")
            display_info("設定方法:")
            display_info("  export OPENAI_API_KEY=your_key_here")
            display_info("  export ANTHROPIC_API_KEY=your_key_here")
            ctx.exit(1)

        # プロバイダーを決定
        provider = "openai" if openai_key else "anthropic"

        # ChatAgentを初期化
        agent = ChatAgent(state.db_manager, api_provider=provider)

        # デモ質問
        demo_questions = [
            "現在のデータベースの状況を教えて",
            "プロンプトの最適化について教えて",
            "CFGスケールの推奨値は？"
        ]

        for i, question in enumerate(demo_questions, 1):
            display_info(f"\n{i}. デモ質問: {question}")

            try:
                response = agent.chat(question)
                click.echo(click.style("🤖 応答:", fg='green', bold=True))
                click.echo(response)
            except Exception as e:
                display_error(f"質問{i}でエラー: {e}")

        display_success("🎉 デモ完了!")
        display_info("詳細な機能は以下のコマンドで利用できます:")
        display_info("  python -m src agent chat      # 対話モード")
        display_info("  python -m src agent analyze   # データ分析")
        display_info("  python -m src agent recommend # 最適化提案")

    except LLMError as e:
        display_error(f"LLMエラー: {e}")
        ctx.exit(1)
    except Exception as e:
        handle_database_error(e)
