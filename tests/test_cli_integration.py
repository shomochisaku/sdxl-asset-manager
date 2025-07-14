"""Integration tests for CLI functionality.

このモジュールはCLI機能の統合テストを実行します。
"""

import json
import os
import tempfile
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from src.cli import cli
from src.models.database import Model, Run
from src.utils.db_utils import DatabaseManager


@pytest.fixture
def temp_db():
    """テスト用の一時データベースファイルを提供します."""
    # ファイルを作成せず、パスだけを生成
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test.db")
    yield db_path
    # クリーンアップ
    if os.path.exists(temp_dir):
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def runner():
    """Click test runner を提供します."""
    return CliRunner()


class TestCLIIntegration:
    """CLI統合テストクラス."""

    def test_full_workflow(self, runner, temp_db):
        """完全なワークフローをテストします."""
        with runner.isolated_filesystem():
            # 1. データベース初期化
            result = runner.invoke(cli, ['--db', temp_db, 'db', 'init'])
            assert result.exit_code == 0
            assert 'データベースが正常に初期化されました' in result.output
            
            # 2. YAMLファイル作成
            yaml_data = {
                'run_title': 'Integration Test Run',
                'prompt': 'masterpiece, 1girl, integration test',
                'negative': 'lowres, bad anatomy',
                'cfg': 7.5,
                'steps': 20,
                'sampler': 'DPM++ 2M',
                'seed': 12345,
                'model': 'integration_test_model.safetensors',
                'loras': ['test_lora'],
                'status': 'Final'
            }
            
            with open('test_run.yaml', 'w') as f:
                yaml.dump(yaml_data, f, allow_unicode=True)
            
            # 3. YAMLバリデーション
            result = runner.invoke(cli, ['yaml', 'validate', 'test_run.yaml'])
            assert result.exit_code == 0
            assert '1件のファイルが正常です' in result.output
            
            # 4. YAML読み込み
            result = runner.invoke(cli, [
                '--db', temp_db,
                'yaml', 'load',
                'test_run.yaml'
            ])
            assert result.exit_code == 0
            assert '1件のYAMLファイルを正常に読み込みました' in result.output
            
            # 5. データベースステータス確認
            result = runner.invoke(cli, ['--db', temp_db, 'db', 'status'])
            assert result.exit_code == 0
            assert 'Integration Test Run' in result.output
            
            # 6. バックアップ作成
            result = runner.invoke(cli, [
                '--db', temp_db,
                'db', 'backup',
                '--output', 'backup.db'
            ])
            assert result.exit_code == 0
            assert Path('backup.db').exists()

    def test_error_handling_workflow(self, runner, temp_db):
        """エラーハンドリングワークフローをテストします."""
        with runner.isolated_filesystem():
            # 1. 初期化されていないDBでの操作
            result = runner.invoke(cli, ['--db', temp_db, 'db', 'status'])
            assert result.exit_code == 0  # 適切にハンドリングされて成功
            
            # 2. 無効なYAMLファイルの処理
            with open('invalid.yaml', 'w') as f:
                f.write('invalid: yaml: content: [\n')
            
            result = runner.invoke(cli, ['yaml', 'validate', 'invalid.yaml'])
            assert result.exit_code == 1
            
            # 3. 存在しないRun IDでの操作
            result = runner.invoke(cli, ['--db', temp_db, 'db', 'init'])
            assert result.exit_code == 0
            
            result = runner.invoke(cli, [
                '--db', temp_db,
                'run', 'show', '999'
            ])
            assert result.exit_code == 1
            assert 'Run ID 999 が見つかりません' in result.output

    def test_data_consistency_workflow(self, runner, temp_db):
        """データ整合性ワークフローをテストします."""
        with runner.isolated_filesystem():
            # データベース初期化
            result = runner.invoke(cli, ['--db', temp_db, 'db', 'init'])
            assert result.exit_code == 0
            
            # 複数のYAMLファイルを読み込み
            for i in range(3):
                yaml_data = {
                    'run_title': f'Test Run {i+1}',
                    'prompt': f'test prompt {i+1}',
                    'cfg': 7.0 + i * 0.5,
                    'steps': 20 + i * 5,
                    'sampler': 'DPM++ 2M',
                    'status': ['Purchased', 'Tried', 'Final'][i]
                }
                
                with open(f'run_{i+1}.yaml', 'w') as f:
                    yaml.dump(yaml_data, f, allow_unicode=True)
            
            # ディレクトリ全体を読み込み
            result = runner.invoke(cli, [
                '--db', temp_db,
                'yaml', 'load',
                '.'
            ])
            assert result.exit_code == 0
            assert '3件のYAMLファイルを正常に読み込みました' in result.output


    def test_concurrent_operations(self, runner, temp_db):
        """並行操作の安全性をテストします."""
        with runner.isolated_filesystem():
            # データベース初期化
            result = runner.invoke(cli, ['--db', temp_db, 'db', 'init'])
            assert result.exit_code == 0
            
            # データを追加
            yaml_data = {
                'run_title': 'Concurrent Test',
                'prompt': 'concurrent test',
                'cfg': 7.5,
                'steps': 20,
                'sampler': 'DPM++ 2M'
            }
            
            with open('concurrent.yaml', 'w') as f:
                yaml.dump(yaml_data, f, allow_unicode=True)
            
            result = runner.invoke(cli, [
                '--db', temp_db,
                'yaml', 'load',
                'concurrent.yaml'
            ])
            assert result.exit_code == 0
            
            # ステータス確認
            result1 = runner.invoke(cli, ['--db', temp_db, 'db', 'status'])
            assert result1.exit_code == 0
            
            # 再度ステータス確認（データ整合性確認）
            result2 = runner.invoke(cli, ['--db', temp_db, 'db', 'status'])
            assert result2.exit_code == 0

    def test_cleanup_and_maintenance(self, runner, temp_db):
        """クリーンアップとメンテナンスワークフローをテストします."""
        with runner.isolated_filesystem():
            # データベース初期化とデータ投入
            result = runner.invoke(cli, ['--db', temp_db, 'db', 'init'])
            assert result.exit_code == 0
            
            # 直接データベースに未使用モデルを作成
            db_manager = DatabaseManager(temp_db)
            unused_model = db_manager.create_record(
                Model,
                name='unused_model',
                type='checkpoint'
            )
            
            # クリーンアップのドライラン
            result = runner.invoke(cli, [
                '--db', temp_db,
                'db', 'cleanup',
                '--dry-run'
            ])
            assert result.exit_code == 0
            assert 'ドライランモード' in result.output
            
            # 実際のクリーンアップ
            result = runner.invoke(cli, [
                '--db', temp_db,
                'db', 'cleanup',
                '--force'
            ])
            assert result.exit_code == 0
            
            # バックアップ作成
            result = runner.invoke(cli, [
                '--db', temp_db,
                'db', 'backup',
                '--output', 'maintenance_backup.db'
            ])
            assert result.exit_code == 0
            assert Path('maintenance_backup.db').exists()


if __name__ == '__main__':
    pytest.main([__file__])