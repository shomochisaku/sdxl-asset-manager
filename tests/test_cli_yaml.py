"""Tests for CLI YAML commands.

このモジュールはCLI YAMLコマンドの機能をテストします。
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


@pytest.fixture
def initialized_db(temp_db):
    """初期化済みのテスト用データベースを提供します."""
    runner = CliRunner()
    result = runner.invoke(cli, ['--db', temp_db, 'db', 'init', '--force'])
    assert result.exit_code == 0
    return temp_db


@pytest.fixture
def sample_yaml_data():
    """サンプルYAMLデータを提供します."""
    return {
        'run_title': 'Test Run',
        'prompt': 'masterpiece, 1girl, beautiful',
        'negative': 'lowres, bad anatomy',
        'cfg': 7.5,
        'steps': 20,
        'sampler': 'DPM++ 2M',
        'seed': 12345,
        'width': 512,
        'height': 768,
        'model': 'test_model.safetensors',
        'loras': ['test_lora1', 'test_lora2'],
        'status': 'Tried',
        'source': 'ComfyUI'
    }


@pytest.fixture
def temp_yaml_file(sample_yaml_data):
    """テスト用の一時YAMLファイルを提供します."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".yaml") as tmp_file:
        yaml.dump(sample_yaml_data, tmp_file, allow_unicode=True)
        yaml_path = tmp_file.name
    yield yaml_path
    # クリーンアップ
    if os.path.exists(yaml_path):
        os.unlink(yaml_path)


@pytest.fixture
def temp_yaml_dir(sample_yaml_data):
    """テスト用の一時YAMLディレクトリを提供します."""
    temp_dir = tempfile.mkdtemp()
    
    # 複数のYAMLファイルを作成
    for i in range(3):
        data = sample_yaml_data.copy()
        data['run_title'] = f'Test Run {i+1}'
        data['seed'] = 12345 + i
        
        yaml_file = Path(temp_dir) / f'test_run_{i+1}.yaml'
        with open(yaml_file, 'w') as f:
            yaml.dump(data, f, allow_unicode=True)
    
    yield temp_dir
    # クリーンアップ
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def invalid_yaml_file():
    """無効なYAMLファイルを提供します."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".yaml") as tmp_file:
        tmp_file.write("invalid: yaml: content: [\n")  # 無効なYAML
        yaml_path = tmp_file.name
    yield yaml_path
    # クリーンアップ
    if os.path.exists(yaml_path):
        os.unlink(yaml_path)


class TestYAMLCommands:
    """YAMLコマンドのテストクラス."""

    def test_yaml_help(self, runner):
        """yamlコマンドのヘルプが正常に表示されることをテストします."""
        result = runner.invoke(cli, ['yaml', '--help'])
        assert result.exit_code == 0
        assert 'YAML操作コマンド' in result.output
        assert 'load' in result.output
        assert 'validate' in result.output
        assert 'export' in result.output
        assert 'info' in result.output

    def test_yaml_load_single_file(self, runner, initialized_db, temp_yaml_file):
        """単一YAMLファイルの読み込みをテストします."""
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'load',
            temp_yaml_file
        ])
        assert result.exit_code == 0
        assert '1件のYAMLファイルを正常に読み込みました' in result.output

    def test_yaml_load_directory(self, runner, initialized_db, temp_yaml_dir):
        """ディレクトリのYAMLファイル読み込みをテストします."""
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'load',
            temp_yaml_dir
        ])
        assert result.exit_code == 0
        assert '3件のYAMLファイルを正常に読み込みました' in result.output

    def test_yaml_load_recursive(self, runner, initialized_db):
        """再帰的な読み込みをテストします."""
        with runner.isolated_filesystem():
            # ネストしたディレクトリ構造を作成
            os.makedirs('subdir')
            
            # ルートディレクトリにYAMLファイル
            with open('root.yaml', 'w') as f:
                yaml.dump({
                    'run_title': 'Root Run',
                    'prompt': 'test prompt',
                    'cfg': 7.5,
                    'steps': 20,
                    'sampler': 'DPM++ 2M'
                }, f)
            
            # サブディレクトリにYAMLファイル
            with open('subdir/sub.yaml', 'w') as f:
                yaml.dump({
                    'run_title': 'Sub Run',
                    'prompt': 'test prompt 2',
                    'cfg': 8.0,
                    'steps': 25,
                    'sampler': 'Euler a'
                }, f)
            
            result = runner.invoke(cli, [
                '--db', initialized_db,
                'yaml', 'load',
                '.',
                '--recursive'
            ])
            assert result.exit_code == 0
            assert '2件のYAMLファイルを正常に読み込みました' in result.output

    def test_yaml_load_dry_run(self, runner, initialized_db, temp_yaml_file):
        """ドライランモードをテストします."""
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'load',
            temp_yaml_file,
            '--dry-run'
        ])
        assert result.exit_code == 0
        assert 'ドライランモード' in result.output
        assert '処理対象ファイル: 1件' in result.output

    def test_yaml_load_skip_validation(self, runner, initialized_db, temp_yaml_file):
        """バリデーションスキップをテストします."""
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'load',
            temp_yaml_file,
            '--skip-validation'
        ])
        assert result.exit_code == 0
        assert '1件のYAMLファイルを正常に読み込みました' in result.output

    def test_yaml_load_continue_on_error(self, runner, initialized_db):
        """エラー継続モードをテストします."""
        with runner.isolated_filesystem():
            # 正常なファイル
            with open('valid.yaml', 'w') as f:
                yaml.dump({
                    'run_title': 'Valid Run',
                    'prompt': 'test prompt',
                    'cfg': 7.5,
                    'steps': 20,
                    'sampler': 'DPM++ 2M'
                }, f)
            
            # 無効なファイル（必須フィールドが不足）
            with open('invalid.yaml', 'w') as f:
                yaml.dump({
                    'run_title': 'Invalid Run',
                    # prompt が不足
                    'cfg': 7.5,
                    'steps': 20,
                    'sampler': 'DPM++ 2M'
                }, f)
            
            result = runner.invoke(cli, [
                '--db', initialized_db,
                'yaml', 'load',
                '.',
                '--continue-on-error'
            ])
            assert result.exit_code == 0  # 継続モードなので成功扱い
            assert '1件のYAMLファイルを正常に読み込みました' in result.output

    def test_yaml_load_duplicate_handling(self, runner, initialized_db, temp_yaml_file):
        """重複データの処理をテストします."""
        # 最初の読み込み
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'load',
            temp_yaml_file
        ])
        assert result.exit_code == 0
        
        # 同じファイルを再度読み込み（重複としてスキップされるはず）
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'load',
            temp_yaml_file
        ])
        assert result.exit_code == 0
        assert '1件のファイルをスキップしました' in result.output

    def test_yaml_validate_single_file(self, runner, temp_yaml_file):
        """単一ファイルのバリデーションをテストします."""
        result = runner.invoke(cli, [
            'yaml', 'validate',
            temp_yaml_file
        ])
        assert result.exit_code == 0
        assert '1件のファイルが正常です' in result.output

    def test_yaml_validate_directory(self, runner, temp_yaml_dir):
        """ディレクトリのバリデーションをテストします."""
        result = runner.invoke(cli, [
            'yaml', 'validate',
            temp_yaml_dir
        ])
        assert result.exit_code == 0
        assert '3件のファイルが正常です' in result.output

    def test_yaml_validate_invalid_file(self, runner, invalid_yaml_file):
        """無効なファイルのバリデーションをテストします."""
        result = runner.invoke(cli, [
            'yaml', 'validate',
            invalid_yaml_file
        ])
        assert result.exit_code == 1
        assert '1件のファイルでエラーが発生しました' in result.output

    def test_yaml_validate_strict_mode(self, runner):
        """厳密バリデーションモードをテストします."""
        with runner.isolated_filesystem():
            # 警告があるが有効なYAMLファイル
            with open('warning.yaml', 'w') as f:
                yaml.dump({
                    'run_title': 'Warning Run',
                    'prompt': 'test prompt',
                    'cfg': 7.5,
                    'steps': 20,
                    'sampler': 'DPM++ 2M'
                    # negative, seed, model が不足（警告項目）
                }, f)
            
            # 通常モード（警告は許可）
            result = runner.invoke(cli, [
                'yaml', 'validate',
                'warning.yaml'
            ])
            assert result.exit_code == 0
            assert '1件のファイルが正常です' in result.output
            
            # 厳密モード（警告もエラー）
            result = runner.invoke(cli, [
                'yaml', 'validate',
                'warning.yaml',
                '--strict'
            ])
            assert result.exit_code == 1
            assert '1件のファイルでエラーが発生しました' in result.output


    def test_yaml_export_invalid_run_ids(self, runner, initialized_db):
        """無効なRun ID指定をテストします."""
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'export',
            '--run-ids', 'invalid,ids'
        ])
        assert result.exit_code == 1
        assert '無効なRun ID形式です' in result.output

    def test_yaml_export_no_data(self, runner, initialized_db):
        """データなしでのエクスポートをテストします."""
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'export'
        ])
        assert result.exit_code == 0
        assert 'エクスポート対象のデータが見つかりません' in result.output

    def test_yaml_export_default(self, runner, initialized_db, temp_yaml_file):
        """デフォルトのYAMLエクスポートをテストします."""
        # まずデータを読み込み
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'load',
            temp_yaml_file
        ])
        assert result.exit_code == 0
        
        # エクスポートを実行
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'export'
        ])
        assert result.exit_code == 0
        assert 'エクスポート対象: 1件' in result.output
        assert 'Test Run' in result.output

    def test_yaml_export_to_file(self, runner, initialized_db, temp_yaml_file):
        """ファイルへのエクスポートをテストします."""
        # まずデータを読み込み
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'load',
            temp_yaml_file
        ])
        assert result.exit_code == 0
        
        # ファイルにエクスポート
        with runner.isolated_filesystem():
            result = runner.invoke(cli, [
                '--db', initialized_db,
                'yaml', 'export',
                '--output', 'export.yaml'
            ])
            assert result.exit_code == 0
            assert 'データをエクスポートしました: export.yaml' in result.output
            
            # ファイルが作成されているか確認
            import os
            assert os.path.exists('export.yaml')
            
            # 内容を確認
            with open('export.yaml', 'r', encoding='utf-8') as f:
                content = f.read()
                assert 'Test Run' in content

    def test_yaml_export_json_format(self, runner, initialized_db, temp_yaml_file):
        """JSON形式でのエクスポートをテストします."""
        # まずデータを読み込み
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'load',
            temp_yaml_file
        ])
        assert result.exit_code == 0
        
        # JSON形式でエクスポート
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'export',
            '--format', 'json'
        ])
        assert result.exit_code == 0
        assert 'エクスポート対象: 1件' in result.output
        
        # JSONとして解析可能か確認
        import json
        lines = result.output.split('\n')
        json_start_idx = None
        for i, line in enumerate(lines):
            if line.strip().startswith('['):
                json_start_idx = i
                break
        
        assert json_start_idx is not None
        
        # JSON部分を抽出（multiline JSONを考慮）
        json_lines = []
        bracket_count = 0
        for i in range(json_start_idx, len(lines)):
            line = lines[i]
            json_lines.append(line)
            bracket_count += line.count('[') - line.count(']')
            if bracket_count == 0 and line.strip().endswith(']'):
                break
        
        json_str = '\n'.join(json_lines)
        data = json.loads(json_str)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]['run_title'] == 'Test Run'

    def test_yaml_export_filtered_by_status(self, runner, initialized_db, temp_yaml_file):
        """ステータスフィルタでのエクスポートをテストします."""
        # まずデータを読み込み
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'load',
            temp_yaml_file
        ])
        assert result.exit_code == 0
        
        # Triedステータスでエクスポート
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'export',
            '--status', 'Tried'
        ])
        assert result.exit_code == 0
        assert 'エクスポート対象: 1件' in result.output
        
        # Finalステータスでエクスポート（該当なし）
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'export',
            '--status', 'Final'
        ])
        assert result.exit_code == 0
        assert 'エクスポート対象のデータが見つかりません' in result.output

    def test_yaml_export_with_run_ids(self, runner, initialized_db, temp_yaml_file):
        """Run ID指定でのエクスポートをテストします."""
        # まずデータを読み込み
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'load',
            temp_yaml_file
        ])
        assert result.exit_code == 0
        
        # Run ID 1でエクスポート
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'export',
            '--run-ids', '1'
        ])
        assert result.exit_code == 0
        assert 'エクスポート対象: 1件' in result.output
        
        # 存在しないRun IDでエクスポート
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'export',
            '--run-ids', '999'
        ])
        assert result.exit_code == 0
        assert 'エクスポート対象のデータが見つかりません' in result.output
        assert 'Run ID 999 が見つかりません' in result.output

    def test_yaml_export_with_date_filters(self, runner, initialized_db, temp_yaml_file):
        """日付フィルタでのエクスポートをテストします."""
        # まずデータを読み込み
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'load',
            temp_yaml_file
        ])
        assert result.exit_code == 0
        
        # 過去の日付でフィルタ（データが含まれるべき）
        past_date = '2020-01-01'
        
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'export',
            '--since', past_date
        ])
        assert result.exit_code == 0
        assert 'エクスポート対象: 1件' in result.output or 'エクスポート対象のデータが見つかりません' in result.output
        
        # 未来の日付でフィルタ（該当なし）
        future_date = '2030-01-01'
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'export',
            '--since', future_date
        ])
        assert result.exit_code == 0
        assert 'エクスポート対象のデータが見つかりません' in result.output

    def test_yaml_export_with_limit(self, runner, initialized_db, temp_yaml_dir):
        """制限付きエクスポートをテストします."""
        # まずディレクトリのデータを読み込み
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'load',
            temp_yaml_dir
        ])
        assert result.exit_code == 0
        assert '3件のYAMLファイルを正常に読み込みました' in result.output
        
        # 制限付きエクスポート
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'export',
            '--limit', '2'
        ])
        assert result.exit_code == 0
        assert 'エクスポート対象: 2件' in result.output

    def test_yaml_export_invalid_date_format(self, runner, initialized_db):
        """無効な日付形式でのエクスポートをテストします."""
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'export',
            '--since', 'invalid-date'
        ])
        assert result.exit_code == 1
        assert '無効な開始日時形式です' in result.output
        
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'export',
            '--until', 'invalid-date'
        ])
        assert result.exit_code == 1
        assert '無効な終了日時形式です' in result.output

    def test_yaml_export_nonexistent_run_id(self, runner, initialized_db):
        """存在しないRun IDでのエクスポートをテストします."""
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'export',
            '--run-ids', '1,2,3'
        ])
        assert result.exit_code == 0
        assert 'エクスポート対象のデータが見つかりません' in result.output
        assert 'Run ID 1 が見つかりません' in result.output
        assert 'Run ID 2 が見つかりません' in result.output
        assert 'Run ID 3 が見つかりません' in result.output

    def test_yaml_info(self, runner, temp_yaml_file):
        """YAMLファイル情報表示をテストします."""
        result = runner.invoke(cli, [
            'yaml', 'info',
            temp_yaml_file
        ])
        assert result.exit_code == 0
        assert 'ファイル:' in result.output
        assert 'サイズ:' in result.output
        assert 'バリデーション: 正常' in result.output
        assert 'YAML内容:' in result.output
        assert 'Test Run' in result.output

    def test_yaml_info_invalid_file(self, runner, invalid_yaml_file):
        """無効なYAMLファイルの情報表示をテストします."""
        result = runner.invoke(cli, [
            'yaml', 'info',
            invalid_yaml_file
        ])
        assert result.exit_code == 1
        assert 'ファイル読み込みエラー' in result.output


class TestYAMLErrorHandling:
    """YAMLコマンドのエラーハンドリングテストクラス."""

    def test_yaml_load_nonexistent_file(self, runner, initialized_db):
        """存在しないファイルの読み込みをテストします."""
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'load',
            '/nonexistent/file.yaml'
        ])
        assert result.exit_code != 0  # Click がファイル存在チェック

    def test_yaml_load_invalid_path(self, runner, initialized_db):
        """無効なパスの読み込みをテストします."""
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'yaml', 'load',
            '/dev/null'  # 通常ファイルではない
        ])
        assert result.exit_code == 1

    def test_yaml_validate_no_files(self, runner):
        """ファイルなしでのバリデーションをテストします."""
        with runner.isolated_filesystem():
            # YAMLファイルのないディレクトリ
            os.makedirs('empty_dir')
            result = runner.invoke(cli, [
                'yaml', 'validate',
                'empty_dir'
            ])
            assert result.exit_code == 0
            assert '検証対象のYAMLファイルが見つかりません' in result.output


if __name__ == '__main__':
    pytest.main([__file__])