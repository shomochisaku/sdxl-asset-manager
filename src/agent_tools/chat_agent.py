"""LLMエージェントエンジン.

このモジュールは対話型AI相談、データ分析、プロンプト最適化機能を提供します。
"""

import json
import os
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, func

from src.models.database import Image, Model, Run, RunTag, Tag
from src.utils.db_utils import DatabaseManager


class LLMError(Exception):
    """LLM処理でのエラー."""
    pass


class ChatAgent:
    """対話型LLMエージェント.

    データベース内容に基づく相談・アドバイス機能を提供します。
    """

    def __init__(self, db_manager: DatabaseManager, api_provider: str = "openai"):
        """チャットエージェントを初期化します.

        Args:
            db_manager: データベースマネージャー
            api_provider: LLM API プロバイダー ('openai' または 'anthropic')
        """
        self.db_manager = db_manager
        self.api_provider = api_provider
        self._client: Optional[Any] = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """LLM APIクライアントを初期化します."""
        if self.api_provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise LLMError("OPENAI_API_KEY environment variable is required")

            try:
                import openai
                self._client = openai.OpenAI(api_key=api_key)
            except ImportError:
                raise LLMError("openai package is required. Run: pip install openai")

        elif self.api_provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise LLMError("ANTHROPIC_API_KEY environment variable is required")

            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=api_key)
            except ImportError:
                raise LLMError("anthropic package is required. Run: pip install anthropic")

        else:
            raise LLMError(f"Unsupported API provider: {self.api_provider}")

    def get_database_context(self) -> Dict[str, Any]:
        """データベースの現在の状態を取得します.

        Returns:
            データベース統計情報
        """
        with self.db_manager.get_session() as session:
            # モデル統計
            total_models = session.query(Model).count()
            checkpoint_count = session.query(Model).filter(Model.type == 'checkpoint').count()
            lora_count = session.query(Model).filter(Model.type == 'lora').count()

            # 実行統計
            total_runs = session.query(Run).count()
            status_counts = {}
            for status in ['Purchased', 'Tried', 'Tuned', 'Final']:
                count = session.query(Run).filter(Run.status == status).count()
                status_counts[status] = count

            # 画像統計
            total_images = session.query(Image).count()

            # タグ統計
            total_tags = session.query(Tag).count()

            # 最近のアクティビティ
            recent_runs = session.query(Run).order_by(desc(Run.created_at)).limit(5).all()
            recent_activity = []
            for run in recent_runs:
                recent_activity.append({
                    'id': run.run_id,
                    'title': run.title,
                    'status': run.status,
                    'created_at': run.created_at.isoformat() if run.created_at else None
                })

            # 人気のタグ
            popular_tags = session.query(
                Tag.name,
                func.count(RunTag.run_id).label('count')
            ).join(RunTag).group_by(Tag.name).order_by(desc('count')).limit(10).all()

            return {
                'models': {
                    'total': total_models,
                    'checkpoints': checkpoint_count,
                    'loras': lora_count
                },
                'runs': {
                    'total': total_runs,
                    'status_breakdown': status_counts
                },
                'images': {
                    'total': total_images
                },
                'tags': {
                    'total': total_tags,
                    'popular': [{'name': tag.name, 'count': tag.count} for tag in popular_tags]
                },
                'recent_activity': recent_activity
            }

    def get_run_analysis(self, limit: int = 20) -> Dict[str, Any]:
        """実行データの分析を取得します.

        Args:
            limit: 分析対象の最大実行数

        Returns:
            実行データ分析結果
        """
        with self.db_manager.get_session() as session:
            # 最近の実行を取得
            recent_runs = session.query(Run).order_by(desc(Run.created_at)).limit(limit).all()

            # CFGスケール分析
            cfg_values = [run.cfg for run in recent_runs]
            avg_cfg = sum(cfg_values) / len(cfg_values) if cfg_values else 0

            # ステップ数分析
            steps_values = [run.steps for run in recent_runs]
            avg_steps = sum(steps_values) / len(steps_values) if steps_values else 0

            # 解像度分析
            resolutions: Dict[str, int] = {}
            for run in recent_runs:
                res = f"{run.width}x{run.height}"
                resolutions[res] = resolutions.get(res, 0) + 1

            # サンプラー分析
            samplers: Dict[str, int] = {}
            for run in recent_runs:
                samplers[run.sampler] = samplers.get(run.sampler, 0) + 1

            # 最も使用されているモデル
            model_usage: Dict[str, int] = {}
            for run in recent_runs:
                if run.model:
                    model_usage[run.model.name] = model_usage.get(run.model.name, 0) + 1

            return {
                'analyzed_runs': len(recent_runs),
                'settings_analysis': {
                    'average_cfg': round(avg_cfg, 2),
                    'average_steps': round(avg_steps, 1),
                    'common_resolutions': dict(sorted(resolutions.items(), key=lambda x: x[1], reverse=True)),
                    'popular_samplers': dict(sorted(samplers.items(), key=lambda x: x[1], reverse=True)),
                    'popular_models': dict(sorted(model_usage.items(), key=lambda x: x[1], reverse=True))
                }
            }

    def _create_system_prompt(self, context: Dict[str, Any]) -> str:
        """システムプロンプトを作成します.

        Args:
            context: データベースコンテキスト

        Returns:
            システムプロンプト
        """
        return f"""あなたはSDXL Asset Managerの専門AIアシスタントです。
画像生成ワークフローの最適化とアドバイスを行います。

現在のデータベース状況:
- モデル: {context['models']['total']}件 (Checkpoint: {context['models']['checkpoints']}, LoRA: {context['models']['loras']})
- 実行履歴: {context['runs']['total']}件
- 画像: {context['images']['total']}件
- タグ: {context['tags']['total']}件

実行ステータス内訳:
{json.dumps(context['runs']['status_breakdown'], indent=2)}

人気のタグ:
{json.dumps(context['tags']['popular'], indent=2)}

最近のアクティビティ:
{json.dumps(context['recent_activity'], indent=2)}

あなたの役割:
1. 画像生成のテクニカルアドバイス
2. プロンプトの最適化提案
3. ワークフローの効率化提案
4. データベース内容に基づく統計分析
5. 設定パラメータの推奨値提案

回答は日本語で、具体的で実用的なアドバイスを提供してください。"""

    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """LLM APIを呼び出します.

        Args:
            messages: 会話メッセージ

        Returns:
            LLMの応答
        """
        if self._client is None:
            raise LLMError("LLM client is not initialized")

        try:
            if self.api_provider == "openai":
                response = self._client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    max_tokens=1500,
                    temperature=0.7
                )
                return response.choices[0].message.content

            elif self.api_provider == "anthropic":
                # Anthropic APIの場合、システムメッセージを分離
                system_msg = None
                conversation_msgs = []

                for msg in messages:
                    if msg['role'] == 'system':
                        system_msg = msg['content']
                    else:
                        conversation_msgs.append(msg)

                response = self._client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1500,
                    temperature=0.7,
                    system=system_msg,
                    messages=conversation_msgs
                )
                return response.content[0].text

        except Exception as e:
            raise LLMError(f"LLM API call failed: {e}")

        # This should never be reached, but mypy needs a return statement
        raise LLMError(f"Unknown API provider: {self.api_provider}")

    def chat(self, user_message: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> str:
        """対話型相談を行います.

        Args:
            user_message: ユーザーメッセージ
            conversation_history: 会話履歴 (オプション)

        Returns:
            AIの応答
        """
        # データベースコンテキストを取得
        context = self.get_database_context()

        # メッセージを構築
        messages = [
            {"role": "system", "content": self._create_system_prompt(context)}
        ]

        # 会話履歴を追加
        if conversation_history:
            messages.extend(conversation_history)

        # ユーザーメッセージを追加
        messages.append({"role": "user", "content": user_message})

        # LLMを呼び出し
        return self._call_llm(messages)

    def analyze_data(self, analysis_type: str = "general") -> str:
        """データベースの分析を行います.

        Args:
            analysis_type: 分析タイプ ('general', 'settings', 'trends')

        Returns:
            分析結果
        """
        context = self.get_database_context()
        run_analysis = self.get_run_analysis()

        analysis_prompt = f"""以下のデータに基づいて{analysis_type}分析を行ってください：

データベース概要:
{json.dumps(context, indent=2)}

実行データ分析:
{json.dumps(run_analysis, indent=2)}

分析タイプ: {analysis_type}

以下の観点で分析してください：
1. 現在の状況の要約
2. 傾向の分析
3. 最適化の提案
4. 改善すべき点の指摘
5. 次のステップの推奨

具体的で実用的な分析結果を日本語で提供してください。"""

        messages = [
            {"role": "system", "content": "あなたはSDXL画像生成の専門データアナリストです。"},
            {"role": "user", "content": analysis_prompt}
        ]

        return self._call_llm(messages)

    def recommend_optimization(self, target_area: str = "general") -> str:
        """プロンプトや設定の最適化を推奨します.

        Args:
            target_area: 最適化対象 ('general', 'prompts', 'settings', 'workflow')

        Returns:
            最適化推奨内容
        """
        context = self.get_database_context()
        run_analysis = self.get_run_analysis()

        # 最近の実行データを取得
        with self.db_manager.get_session() as session:
            recent_runs = session.query(Run).order_by(desc(Run.created_at)).limit(10).all()
            run_details = []
            for run in recent_runs:
                run_details.append({
                    'title': run.title,
                    'prompt': run.prompt[:200] + '...' if len(run.prompt) > 200 else run.prompt,
                    'negative': run.negative,
                    'cfg': run.cfg,
                    'steps': run.steps,
                    'sampler': run.sampler,
                    'status': run.status,
                    'resolution': f"{run.width}x{run.height}"
                })

        optimization_prompt = f"""以下のデータに基づいて{target_area}の最適化推奨を行ってください：

データベース概要:
{json.dumps(context, indent=2)}

実行データ分析:
{json.dumps(run_analysis, indent=2)}

最近の実行詳細:
{json.dumps(run_details, indent=2)}

最適化対象: {target_area}

以下の観点で最適化提案を提供してください：
1. 現在の問題点の特定
2. 具体的な改善提案
3. 推奨パラメータ値
4. プロンプトの改善例
5. ワークフローの効率化案

実践的で具体的な最適化提案を日本語で提供してください。"""

        messages = [
            {"role": "system", "content": "あなたはSDXL画像生成の最適化専門家です。"},
            {"role": "user", "content": optimization_prompt}
        ]

        return self._call_llm(messages)

    def search_similar_runs(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """類似の実行を検索します.

        Args:
            query: 検索クエリ
            limit: 返却する最大件数

        Returns:
            類似実行のリスト
        """
        with self.db_manager.get_session() as session:
            # プロンプトまたはタイトルに基づく検索
            runs = session.query(Run).filter(
                Run.prompt.contains(query) | Run.title.contains(query)
            ).order_by(desc(Run.created_at)).limit(limit).all()

            results = []
            for run in runs:
                results.append({
                    'id': run.run_id,
                    'title': run.title,
                    'prompt': run.prompt[:100] + '...' if len(run.prompt) > 100 else run.prompt,
                    'status': run.status,
                    'cfg': run.cfg,
                    'steps': run.steps,
                    'sampler': run.sampler,
                    'resolution': f"{run.width}x{run.height}",
                    'created_at': run.created_at.isoformat() if run.created_at else None
                })

            return results

