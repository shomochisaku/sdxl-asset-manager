"""Tests for CLI database commands.

このモジュールはCLIデータベースコマンドの機能をテストします。
"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
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
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_backup_dir():
    """テスト用の一時バックアップディレクトリを提供します."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # クリーンアップ
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


class TestDBCommands:
    """データベースコマンドのテストクラス."""

    def test_db_help(self, runner):
        """dbコマンドのヘルプが正常に表示されることをテストします."""
        result = runner.invoke(cli, ['db', '--help'])
        assert result.exit_code == 0
        assert 'データベース管理コマンド' in result.output
        assert 'init' in result.output
        assert 'status' in result.output
        assert 'backup' in result.output
        assert 'restore' in result.output
        assert 'cleanup' in result.output

    def test_db_init_new_database(self, runner, temp_db):
        """新しいデータベースの初期化をテストします."""
        result = runner.invoke(cli, ['--db', temp_db, 'db', 'init'])
        assert result.exit_code == 0
        assert 'データベースが正常に初期化されました' in result.output
        assert Path(temp_db).exists()

    def test_db_init_existing_database_with_force(self, runner, temp_db):
        """既存データベースの強制初期化をテストします."""
        # 最初にデータベースを作成
        result = runner.invoke(cli, ['--db', temp_db, 'db', 'init'])
        assert result.exit_code == 0
        
        # 強制初期化
        result = runner.invoke(cli, ['--db', temp_db, 'db', 'init', '--force'])
        assert result.exit_code == 0
        assert 'データベースが正常に初期化されました' in result.output

    def test_db_init_existing_database_without_force(self, runner, temp_db):
        """既存データベースの初期化（確認なし）をテストします."""
        # 最初にデータベースを作成
        result = runner.invoke(cli, ['--db', temp_db, 'db', 'init'])
        assert result.exit_code == 0
        
        # 確認なしで初期化（'n'で拒否）
        result = runner.invoke(cli, ['--db', temp_db, 'db', 'init'], input='n\n')
        assert result.exit_code == 0
        assert 'データベース初期化をキャンセルしました' in result.output

    def test_db_init_directory_creation(self, runner):
        """データベースディレクトリの自動作成をテストします."""
        with runner.isolated_filesystem():
            db_path = 'nested/dir/test.db'
            result = runner.invoke(cli, ['--db', db_path, 'db', 'init'])
            assert result.exit_code == 0
            assert Path(db_path).exists()
            assert Path(db_path).parent.exists()

    def test_db_status_existing_database(self, runner, initialized_db):
        """既存データベースのステータス表示をテストします."""
        result = runner.invoke(cli, ['--db', initialized_db, 'db', 'status'])
        assert result.exit_code == 0
        assert 'データベース統計' in result.output
        assert 'Models' in result.output
        assert 'Runs' in result.output
        assert 'Images' in result.output
        assert 'Tags' in result.output

    def test_db_status_nonexistent_database(self, runner):
        """存在しないデータベースのステータス表示をテストします."""
        result = runner.invoke(cli, ['--db', '/nonexistent/db.sqlite', 'db', 'status'])
        assert result.exit_code == 1  # データベースエラー
        assert 'データベース接続エラー' in result.output

    def test_db_backup_default_name(self, runner, initialized_db):
        """デフォルト名でのバックアップ作成をテストします."""
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ['--db', initialized_db, 'db', 'backup'])
            assert result.exit_code == 0
            assert 'バックアップが正常に作成されました' in result.output
            
            # バックアップファイルが作成されたことを確認
            backup_files = list(Path('.').glob('*_backup_*.db'))
            assert len(backup_files) > 0

    def test_db_backup_custom_name(self, runner, initialized_db, temp_backup_dir):
        """カスタム名でのバックアップ作成をテストします."""
        backup_path = Path(temp_backup_dir) / 'custom_backup.db'
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'db', 'backup',
            '--output', str(backup_path)
        ])
        assert result.exit_code == 0
        assert backup_path.exists()
        assert 'バックアップが正常に作成されました' in result.output

    def test_db_backup_existing_file_confirmation(self, runner, initialized_db, temp_backup_dir):
        """既存ファイルへのバックアップ確認をテストします."""
        backup_path = Path(temp_backup_dir) / 'existing_backup.db'
        backup_path.touch()  # 既存ファイルを作成
        
        # 確認で拒否
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'db', 'backup',
            '--output', str(backup_path)
        ], input='n\n')
        assert result.exit_code == 0
        assert 'バックアップをキャンセルしました' in result.output

    def test_db_backup_nonexistent_source(self, runner):
        """存在しないデータベースのバックアップをテストします."""
        result = runner.invoke(cli, [
            '--db', '/nonexistent/db.sqlite',
            'db', 'backup'
        ])
        assert result.exit_code == 1  # データベースエラー
        assert 'データベースファイルが見つかりません' in result.output

    def test_db_restore(self, runner, initialized_db, temp_backup_dir):
        """バックアップからの復元をテストします."""
        # まずバックアップを作成
        backup_path = Path(temp_backup_dir) / 'restore_test.db'
        shutil.copy2(initialized_db, backup_path)
        
        # 新しいDBパスで復元
        new_db_path = Path(temp_backup_dir) / 'restored.db'
        result = runner.invoke(cli, [
            '--db', str(new_db_path),
            'db', 'restore',
            str(backup_path),
            '--force'
        ])
        assert result.exit_code == 0
        assert 'データベースが正常に復元されました' in result.output
        assert new_db_path.exists()

    def test_db_restore_with_confirmation(self, runner, initialized_db, temp_backup_dir):
        """確認付きの復元をテストします."""
        # バックアップを作成
        backup_path = Path(temp_backup_dir) / 'restore_confirm_test.db'
        shutil.copy2(initialized_db, backup_path)
        
        # 確認で拒否
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'db', 'restore',
            str(backup_path)
        ], input='n\n')
        assert result.exit_code == 0
        assert '復元をキャンセルしました' in result.output

    def test_db_restore_nonexistent_backup(self, runner, temp_db):
        """存在しないバックアップファイルの復元をテストします."""
        result = runner.invoke(cli, [
            '--db', temp_db,
            'db', 'restore',
            '/nonexistent/backup.db'
        ])
        assert result.exit_code != 0  # Click がファイル存在チェックでエラー

    def test_db_cleanup_dry_run(self, runner, initialized_db):
        """ドライランモードでのクリーンアップをテストします."""
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'db', 'cleanup',
            '--dry-run'
        ])
        assert result.exit_code == 0
        assert 'ドライランモード' in result.output

    def test_db_cleanup_models(self, runner, initialized_db):
        """モデルのクリーンアップをテストします."""
        # テストデータを準備（未使用モデルを作成）
        db_manager = DatabaseManager(initialized_db)
        db_manager.create_record(Model, name='unused_model', type='checkpoint')
        
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'db', 'cleanup',
            '--table', 'models',
            '--force'
        ])
        assert result.exit_code == 0

    def test_db_cleanup_images(self, runner, initialized_db):
        """画像のクリーンアップをテストします."""
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'db', 'cleanup',
            '--table', 'images',
            '--force'
        ])
        assert result.exit_code == 0

    def test_db_cleanup_all(self, runner, initialized_db):
        """全テーブルのクリーンアップをテストします."""
        result = runner.invoke(cli, [
            '--db', initialized_db,
            'db', 'cleanup',
            '--table', 'all',
            '--force'
        ])
        assert result.exit_code == 0


class TestDBCommandsWithData:
    """データ入りデータベースでのコマンドテストクラス."""

    @pytest.fixture
    def db_with_data(self, initialized_db):
        """テストデータを含むデータベースを提供します."""
        db_manager = DatabaseManager(initialized_db)
        
        # テストデータを作成
        model = db_manager.create_record(
            Model,
            name='test_model',
            type='checkpoint'
        )
        
        run = db_manager.create_record(
            Run,
            title='Test Run',
            prompt='test prompt',
            cfg=7.5,
            steps=20,
            sampler='DPM++ 2M',
            status='Tried',
            model_id=model.model_id
        )
        
        return initialized_db

    def test_db_status_with_data(self, runner, db_with_data):
        """データありでのステータス表示をテストします."""
        result = runner.invoke(cli, ['--db', db_with_data, 'db', 'status'])
        assert result.exit_code == 0
        assert 'データベース統計' in result.output
        assert '最近のアクティビティ' in result.output
        assert 'Test Run' in result.output

    def test_db_backup_with_data(self, runner, db_with_data, temp_backup_dir):
        """データありでのバックアップをテストします."""
        backup_path = Path(temp_backup_dir) / 'data_backup.db'
        result = runner.invoke(cli, [
            '--db', db_with_data,
            'db', 'backup',
            '--output', str(backup_path)
        ])
        assert result.exit_code == 0
        assert backup_path.exists()
        
        # バックアップファイルのサイズが適切であることを確認
        original_size = Path(db_with_data).stat().st_size
        backup_size = backup_path.stat().st_size
        assert backup_size == original_size


class TestDBErrorHandling:
    """データベースコマンドのエラーハンドリングテストクラス."""

    def test_db_init_permission_error(self, runner):
        """権限エラーでの初期化をテストします."""
        # 権限のないディレクトリに初期化を試行
        if os.name != 'nt':  # Windows以外でテスト
            result = runner.invoke(cli, [
                '--db', '/root/test.db',
                'db', 'init'
            ])
            # 権限エラーまたは適切なエラーハンドリングを確認
            assert result.exit_code != 0

    def test_db_backup_permission_error(self, runner, initialized_db):
        """権限エラーでのバックアップをテストします."""
        if os.name != 'nt':  # Windows以外でテスト
            result = runner.invoke(cli, [
                '--db', initialized_db,
                'db', 'backup',
                '--output', '/root/backup.db'
            ])
            # 権限エラーまたは適切なエラーハンドリングを確認
            assert result.exit_code != 0

    def test_db_restore_corrupted_backup(self, runner, temp_db, temp_backup_dir):
        """破損したバックアップファイルの復元をテストします."""
        # 破損したバックアップファイルを作成
        corrupted_backup = Path(temp_backup_dir) / 'corrupted.db'
        with open(corrupted_backup, 'w') as f:
            f.write('this is not a valid database file')
        
        result = runner.invoke(cli, [
            '--db', temp_db,
            'db', 'restore',
            str(corrupted_backup),
            '--force'
        ])
        assert result.exit_code == 1  # データベースエラー
        assert 'データベース検証エラー' in result.output or 'の検証に失敗しました' in result.output or 'データベース接続エラー' in result.output


if __name__ == '__main__':
    pytest.main([__file__])