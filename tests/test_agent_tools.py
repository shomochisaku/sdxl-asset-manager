"""LLMエージェントのテスト.

このモジュールはLLMエージェント機能のテストを提供します。
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.agent_tools.chat_agent import ChatAgent, LLMError
from src.models.database import Model, Run, Image, Tag, RunLora, RunTag
from src.utils.db_utils import DatabaseManager


class TestChatAgent:
    """ChatAgentクラスのテスト."""

    @pytest.fixture
    def mock_db_manager(self):
        """モックデータベースマネージャーを作成."""
        manager = Mock(spec=DatabaseManager)
        session = Mock()
        
        # Mock session context manager
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=None)
        manager.get_session.return_value = session
        
        return manager, session

    @pytest.fixture
    def mock_runs(self):
        """モック実行データを作成."""
        runs = []
        for i in range(5):
            run = Mock(spec=Run)
            run.run_id = i + 1
            run.title = f"Test Run {i + 1}"
            run.prompt = f"test prompt {i + 1}"
            run.negative = f"test negative {i + 1}"
            run.cfg = 7.5
            run.steps = 20
            run.sampler = "DPM++ 2M"
            run.scheduler = "karras"
            run.width = 1024
            run.height = 1024
            run.status = "Tried"
            run.created_at = datetime.now()
            run.model = Mock(spec=Model)
            run.model.name = f"model_{i + 1}"
            runs.append(run)
        return runs

    @pytest.fixture
    def mock_openai_client(self):
        """モックOpenAIクライアントを作成."""
        client = Mock()
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message.content = "Test AI response"
        client.chat.completions.create.return_value = response
        return client

    @pytest.fixture
    def mock_anthropic_client(self):
        """モックAnthropicクライアントを作成."""
        client = Mock()
        response = Mock()
        response.content = [Mock()]
        response.content[0].text = "Test AI response"
        client.messages.create.return_value = response
        return client

    def test_init_with_openai(self, mock_db_manager):
        """OpenAIプロバイダーでの初期化をテスト."""
        db_manager, _ = mock_db_manager
        
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            with patch('openai.OpenAI') as mock_openai:
                agent = ChatAgent(db_manager, api_provider="openai")
                assert agent.api_provider == "openai"
                mock_openai.assert_called_once_with(api_key='test_key')

    def test_init_with_anthropic(self, mock_db_manager):
        """Anthropicプロバイダーでの初期化をテスト."""
        db_manager, _ = mock_db_manager
        
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test_key'}):
            with patch('anthropic.Anthropic') as mock_anthropic:
                agent = ChatAgent(db_manager, api_provider="anthropic")
                assert agent.api_provider == "anthropic"
                mock_anthropic.assert_called_once_with(api_key='test_key')

    def test_init_missing_api_key(self, mock_db_manager):
        """APIキーが設定されていない場合のエラーをテスト."""
        db_manager, _ = mock_db_manager
        
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(LLMError, match="OPENAI_API_KEY environment variable is required"):
                ChatAgent(db_manager, api_provider="openai")

    def test_init_unsupported_provider(self, mock_db_manager):
        """サポートされていないプロバイダーのエラーをテスト."""
        db_manager, _ = mock_db_manager
        
        with pytest.raises(LLMError, match="Unsupported API provider"):
            ChatAgent(db_manager, api_provider="unsupported")

    def test_get_database_context(self, mock_db_manager, mock_runs):
        """データベースコンテキスト取得をテスト."""
        db_manager, session = mock_db_manager
        
        # Mock query results
        session.query.return_value.count.return_value = 10
        session.query.return_value.filter.return_value.count.return_value = 5
        session.query.return_value.order_by.return_value.limit.return_value.all.return_value = mock_runs
        session.query.return_value.join.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            with patch('openai.OpenAI'):
                agent = ChatAgent(db_manager, api_provider="openai")
                context = agent.get_database_context()
                
                assert 'models' in context
                assert 'runs' in context
                assert 'images' in context
                assert 'tags' in context
                assert 'recent_activity' in context

    def test_get_run_analysis(self, mock_db_manager, mock_runs):
        """実行データ分析をテスト."""
        db_manager, session = mock_db_manager
        
        # Mock query results
        session.query.return_value.order_by.return_value.limit.return_value.all.return_value = mock_runs
        
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            with patch('openai.OpenAI'):
                agent = ChatAgent(db_manager, api_provider="openai")
                analysis = agent.get_run_analysis()
                
                assert 'analyzed_runs' in analysis
                assert 'settings_analysis' in analysis
                assert analysis['analyzed_runs'] == 5

    def test_chat_with_openai(self, mock_db_manager, mock_openai_client):
        """OpenAIを使用したチャットをテスト."""
        db_manager, session = mock_db_manager
        
        # Mock database queries
        session.query.return_value.count.return_value = 10
        session.query.return_value.filter.return_value.count.return_value = 5
        session.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
        session.query.return_value.join.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            with patch('openai.OpenAI', return_value=mock_openai_client):
                agent = ChatAgent(db_manager, api_provider="openai")
                response = agent.chat("Test message")
                
                assert response == "Test AI response"
                mock_openai_client.chat.completions.create.assert_called_once()

    def test_chat_with_anthropic(self, mock_db_manager, mock_anthropic_client):
        """Anthropicを使用したチャットをテスト."""
        db_manager, session = mock_db_manager
        
        # Mock database queries
        session.query.return_value.count.return_value = 10
        session.query.return_value.filter.return_value.count.return_value = 5
        session.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
        session.query.return_value.join.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test_key'}):
            with patch('anthropic.Anthropic', return_value=mock_anthropic_client):
                agent = ChatAgent(db_manager, api_provider="anthropic")
                response = agent.chat("Test message")
                
                assert response == "Test AI response"
                mock_anthropic_client.messages.create.assert_called_once()

    def test_analyze_data(self, mock_db_manager, mock_openai_client, mock_runs):
        """データ分析をテスト."""
        db_manager, session = mock_db_manager
        
        # Mock database queries
        session.query.return_value.count.return_value = 10
        session.query.return_value.filter.return_value.count.return_value = 5
        session.query.return_value.order_by.return_value.limit.return_value.all.return_value = mock_runs
        session.query.return_value.join.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            with patch('openai.OpenAI', return_value=mock_openai_client):
                agent = ChatAgent(db_manager, api_provider="openai")
                result = agent.analyze_data("general")
                
                assert result == "Test AI response"
                mock_openai_client.chat.completions.create.assert_called_once()

    def test_recommend_optimization(self, mock_db_manager, mock_openai_client, mock_runs):
        """最適化推奨をテスト."""
        db_manager, session = mock_db_manager
        
        # Mock database queries
        session.query.return_value.count.return_value = 10
        session.query.return_value.filter.return_value.count.return_value = 5
        session.query.return_value.order_by.return_value.limit.return_value.all.return_value = mock_runs
        session.query.return_value.join.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            with patch('openai.OpenAI', return_value=mock_openai_client):
                agent = ChatAgent(db_manager, api_provider="openai")
                result = agent.recommend_optimization("general")
                
                assert result == "Test AI response"
                mock_openai_client.chat.completions.create.assert_called_once()

    def test_search_similar_runs(self, mock_db_manager, mock_runs):
        """類似実行検索をテスト."""
        db_manager, session = mock_db_manager
        
        # Mock query results
        session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_runs[:2]
        
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            with patch('openai.OpenAI'):
                agent = ChatAgent(db_manager, api_provider="openai")
                results = agent.search_similar_runs("test", limit=2)
                
                assert len(results) == 2
                assert results[0]['title'] == "Test Run 1"
                assert results[1]['title'] == "Test Run 2"

    def test_llm_api_error(self, mock_db_manager):
        """LLM API呼び出しエラーをテスト."""
        db_manager, session = mock_db_manager
        
        # Mock database queries
        session.query.return_value.count.return_value = 10
        session.query.return_value.filter.return_value.count.return_value = 5
        session.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
        session.query.return_value.join.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            with patch('openai.OpenAI') as mock_openai:
                # Mock API error
                mock_client = Mock()
                mock_client.chat.completions.create.side_effect = Exception("API Error")
                mock_openai.return_value = mock_client
                
                agent = ChatAgent(db_manager, api_provider="openai")
                
                with pytest.raises(LLMError, match="LLM API call failed"):
                    agent.chat("Test message")

    def test_conversation_history(self, mock_db_manager, mock_openai_client):
        """会話履歴付きチャットをテスト."""
        db_manager, session = mock_db_manager
        
        # Mock database queries
        session.query.return_value.count.return_value = 10
        session.query.return_value.filter.return_value.count.return_value = 5
        session.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
        session.query.return_value.join.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            with patch('openai.OpenAI', return_value=mock_openai_client):
                agent = ChatAgent(db_manager, api_provider="openai")
                
                history = [
                    {"role": "user", "content": "Previous message"},
                    {"role": "assistant", "content": "Previous response"}
                ]
                
                response = agent.chat("New message", history)
                
                assert response == "Test AI response"
                
                # Check that history was included in the call
                call_args = mock_openai_client.chat.completions.create.call_args
                messages = call_args[1]['messages']
                assert len(messages) == 4  # system + history + new message
                assert messages[1]['content'] == "Previous message"
                assert messages[2]['content'] == "Previous response"
                assert messages[3]['content'] == "New message"