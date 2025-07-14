"""CLI agentコマンドのテスト.

このモジュールはCLI agentコマンドのテストを提供します。
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner

from src.cli.agent import agent_commands
from src.agent_tools.chat_agent import ChatAgent, LLMError


class TestAgentCommands:
    """Agent CLI コマンドのテスト."""

    @pytest.fixture
    def runner(self):
        """ClickのCliRunnerを作成."""
        return CliRunner()

    @pytest.fixture
    def mock_chat_agent(self):
        """モックChatAgentを作成."""
        agent = Mock(spec=ChatAgent)
        agent.chat.return_value = "Test AI response"
        agent.analyze_data.return_value = "Test analysis result"
        agent.recommend_optimization.return_value = "Test recommendation"
        agent.search_similar_runs.return_value = [
            {
                'id': 1,
                'title': 'Test Run 1',
                'prompt': 'test prompt',
                'status': 'Tried',
                'cfg': 7.5,
                'steps': 20,
                'sampler': 'DPM++ 2M',
                'resolution': '1024x1024',
                'created_at': '2024-01-01T00:00:00'
            }
        ]
        agent.get_database_context.return_value = {
            'models': {'total': 10},
            'runs': {'total': 50},
            'images': {'total': 100},
            'tags': {'total': 20}
        }
        return agent

    def test_agent_commands_help(self, runner):
        """agentコマンドグループのヘルプをテスト."""
        result = runner.invoke(agent_commands, ['--help'])
        assert result.exit_code == 0
        assert 'LLMエージェント機能' in result.output

    def test_chat_help(self, runner):
        """chatコマンドのヘルプをテスト."""
        result = runner.invoke(agent_commands, ['chat', '--help'])
        assert result.exit_code == 0
        assert '対話型AI相談モード' in result.output

    def test_analyze_help(self, runner):
        """analyzeコマンドのヘルプをテスト."""
        result = runner.invoke(agent_commands, ['analyze', '--help'])
        assert result.exit_code == 0
        assert 'データベースの分析を実行' in result.output

    def test_recommend_help(self, runner):
        """recommendコマンドのヘルプをテスト."""
        result = runner.invoke(agent_commands, ['recommend', '--help'])
        assert result.exit_code == 0
        assert '最適化提案を生成' in result.output

    def test_search_help(self, runner):
        """searchコマンドのヘルプをテスト."""
        result = runner.invoke(agent_commands, ['search', '--help'])
        assert result.exit_code == 0
        assert '類似実行の検索' in result.output

    def test_status_help(self, runner):
        """statusコマンドのヘルプをテスト."""
        result = runner.invoke(agent_commands, ['status', '--help'])
        assert result.exit_code == 0
        assert 'エージェントの状態を確認' in result.output

    def test_demo_help(self, runner):
        """demoコマンドのヘルプをテスト."""
        result = runner.invoke(agent_commands, ['demo', '--help'])
        assert result.exit_code == 0
        assert 'デモ実行' in result.output

    @patch('src.cli.agent.ChatAgent')
    def test_analyze_text_output(self, mock_chat_agent_class, runner, mock_chat_agent):
        """analyzeコマンドのテキスト出力をテスト."""
        mock_chat_agent_class.return_value = mock_chat_agent
        
        with patch('src.cli.agent.CliState') as mock_state:
            mock_state.return_value.db_manager = Mock()
            
            result = runner.invoke(agent_commands, ['analyze', '--type', 'general', '--output', 'text'])
            
            assert result.exit_code == 0
            assert 'データベース分析を実行中' in result.output
            assert 'Test analysis result' in result.output

    @patch('src.cli.agent.ChatAgent')
    def test_analyze_json_output(self, mock_chat_agent_class, runner, mock_chat_agent):
        """analyzeコマンドのJSON出力をテスト."""
        mock_chat_agent_class.return_value = mock_chat_agent
        
        with patch('src.cli.agent.CliState') as mock_state:
            mock_state.return_value.db_manager = Mock()
            
            result = runner.invoke(agent_commands, ['analyze', '--type', 'general', '--output', 'json'])
            
            assert result.exit_code == 0
            assert '"analysis_type": "general"' in result.output

    @patch('src.cli.agent.ChatAgent')
    def test_recommend_text_output(self, mock_chat_agent_class, runner, mock_chat_agent):
        """recommendコマンドのテキスト出力をテスト."""
        mock_chat_agent_class.return_value = mock_chat_agent
        
        with patch('src.cli.agent.CliState') as mock_state:
            mock_state.return_value.db_manager = Mock()
            
            result = runner.invoke(agent_commands, ['recommend', '--target', 'general', '--output', 'text'])
            
            assert result.exit_code == 0
            assert '最適化提案を生成中' in result.output
            assert 'Test recommendation' in result.output

    @patch('src.cli.agent.ChatAgent')
    def test_search_basic(self, mock_chat_agent_class, runner, mock_chat_agent):
        """searchコマンドの基本機能をテスト."""
        mock_chat_agent_class.return_value = mock_chat_agent
        
        with patch('src.cli.agent.CliState') as mock_state:
            mock_state.return_value.db_manager = Mock()
            
            result = runner.invoke(agent_commands, ['search', 'test query'])
            
            assert result.exit_code == 0
            assert "検索中: 'test query'" in result.output
            assert 'Test Run 1' in result.output

    @patch('src.cli.agent.ChatAgent')
    def test_search_with_analysis(self, mock_chat_agent_class, runner, mock_chat_agent):
        """searchコマンドのAI分析付きをテスト."""
        mock_chat_agent_class.return_value = mock_chat_agent
        mock_chat_agent._call_llm.return_value = "Test analysis response"
        
        with patch('src.cli.agent.CliState') as mock_state:
            mock_state.return_value.db_manager = Mock()
            
            result = runner.invoke(agent_commands, ['search', 'test query', '--with-analysis'])
            
            assert result.exit_code == 0
            assert "検索中: 'test query'" in result.output
            assert 'Test Run 1' in result.output
            assert 'AI分析を実行中' in result.output
            assert 'Test analysis response' in result.output

    @patch('src.cli.agent.ChatAgent')
    def test_search_no_results(self, mock_chat_agent_class, runner, mock_chat_agent):
        """searchコマンドで結果がない場合をテスト."""
        mock_chat_agent_class.return_value = mock_chat_agent
        mock_chat_agent.search_similar_runs.return_value = []
        
        with patch('src.cli.agent.CliState') as mock_state:
            mock_state.return_value.db_manager = Mock()
            
            result = runner.invoke(agent_commands, ['search', 'nonexistent'])
            
            assert result.exit_code == 0
            assert '検索結果が見つかりませんでした' in result.output

    def test_status_with_api_keys(self, runner):
        """statusコマンドでAPIキーが設定されている場合をテスト."""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key', 'ANTHROPIC_API_KEY': 'test_key'}):
            with patch('src.cli.agent.CliState') as mock_state:
                mock_state.return_value.db_manager = Mock()
                
                with patch('src.cli.agent.ChatAgent') as mock_chat_agent_class:
                    mock_agent = Mock()
                    mock_agent.get_database_context.return_value = {
                        'models': {'total': 10},
                        'runs': {'total': 50}
                    }
                    mock_chat_agent_class.return_value = mock_agent
                    
                    result = runner.invoke(agent_commands, ['status'])
                    
                    assert result.exit_code == 0
                    assert '✅ 設定済み' in result.output

    def test_status_without_api_keys(self, runner):
        """statusコマンドでAPIキーが設定されていない場合をテスト."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('src.cli.agent.CliState') as mock_state:
                mock_state.return_value.db_manager = Mock()
                
                result = runner.invoke(agent_commands, ['status'])
                
                assert result.exit_code == 0
                assert '❌ 未設定' in result.output
                assert 'APIキーが設定されていません' in result.output

    def test_demo_without_api_keys(self, runner):
        """demoコマンドでAPIキーが設定されていない場合をテスト."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('src.cli.agent.CliState') as mock_state:
                mock_state.return_value.db_manager = Mock()
                
                result = runner.invoke(agent_commands, ['demo'])
                
                assert result.exit_code == 1
                assert 'APIキーが設定されていません' in result.output

    @patch('src.cli.agent.ChatAgent')
    def test_demo_with_api_key(self, mock_chat_agent_class, runner, mock_chat_agent):
        """demoコマンドでAPIキーが設定されている場合をテスト."""
        mock_chat_agent_class.return_value = mock_chat_agent
        
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            with patch('src.cli.agent.CliState') as mock_state:
                mock_state.return_value.db_manager = Mock()
                
                result = runner.invoke(agent_commands, ['demo'])
                
                assert result.exit_code == 0
                assert 'LLMエージェントデモを開始します' in result.output
                assert 'デモ完了!' in result.output

    @patch('src.cli.agent.ChatAgent')
    def test_llm_error_handling(self, mock_chat_agent_class, runner):
        """LLMエラーの処理をテスト."""
        mock_chat_agent_class.side_effect = LLMError("Test LLM error")
        
        with patch('src.cli.agent.CliState') as mock_state:
            mock_state.return_value.db_manager = Mock()
            
            result = runner.invoke(agent_commands, ['analyze'])
            
            assert result.exit_code == 1
            assert 'LLMエラー: Test LLM error' in result.output

    @patch('src.cli.agent.ChatAgent')
    def test_different_providers(self, mock_chat_agent_class, runner, mock_chat_agent):
        """異なるプロバイダーのテスト."""
        mock_chat_agent_class.return_value = mock_chat_agent
        
        with patch('src.cli.agent.CliState') as mock_state:
            mock_state.return_value.db_manager = Mock()
            
            # OpenAI
            result = runner.invoke(agent_commands, ['analyze', '--provider', 'openai'])
            assert result.exit_code == 0
            mock_chat_agent_class.assert_called_with(mock_state.return_value.db_manager, api_provider='openai')
            
            # Anthropic
            result = runner.invoke(agent_commands, ['analyze', '--provider', 'anthropic'])
            assert result.exit_code == 0
            mock_chat_agent_class.assert_called_with(mock_state.return_value.db_manager, api_provider='anthropic')

    def test_chat_interactive_mode_simulation(self, runner):
        """chatコマンドの対話モードのシミュレーション."""
        # Note: 実際の対話モードのテストは複雑なので、基本的なコマンド実行のみテスト
        with patch('src.cli.agent.CliState') as mock_state:
            mock_state.return_value.db_manager = Mock()
            
            with patch('src.cli.agent.ChatAgent') as mock_chat_agent_class:
                mock_agent = Mock()
                mock_chat_agent_class.return_value = mock_agent
                
                with patch('click.prompt', side_effect=['quit']):  # 即座に終了
                    result = runner.invoke(agent_commands, ['chat'])
                    
                    assert result.exit_code == 0
                    assert 'LLMエージェント (openai) を起動しました' in result.output
                    assert '会話を終了します' in result.output

    @patch('src.cli.agent.ChatAgent')
    def test_output_formats(self, mock_chat_agent_class, runner, mock_chat_agent):
        """異なる出力形式のテスト."""
        mock_chat_agent_class.return_value = mock_chat_agent
        
        with patch('src.cli.agent.CliState') as mock_state:
            mock_state.return_value.db_manager = Mock()
            
            # YAML output
            result = runner.invoke(agent_commands, ['analyze', '--output', 'yaml'])
            assert result.exit_code == 0
            
            # JSON output
            result = runner.invoke(agent_commands, ['recommend', '--output', 'json'])
            assert result.exit_code == 0