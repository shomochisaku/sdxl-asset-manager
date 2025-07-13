# SDXL Asset Manager - セットアップガイド

## 🚀 クイックスタート

新しい端末でこのプロジェクトを開発するための完全ガイドです。

### 1. 前提条件確認

```bash
# Python 3.12+ 必須
python3 --version
# Python 3.12.x が表示されること

# Git確認
git --version

# GitHub CLI (Claude連携用)
gh --version
```

### 2. リポジトリクローン

```bash
# HTTPSクローン
git clone https://github.com/shomochisaku/sdxl-asset-manager.git
cd sdxl-asset-manager

# SSHクローン（推奨）
git clone git@github.com:shomochisaku/sdxl-asset-manager.git
cd sdxl-asset-manager

# ブランチ確認
git branch -a
git status
```

### 3. Python依存関係セットアップ

```bash
# 基本依存関係
pip install -r requirements.txt

# 開発ツール
pip install mypy pytest ruff

# インストール確認
pip list | grep -E "(sqlalchemy|click|pytest|mypy|ruff)"
```

### 4. 環境変数設定

```bash
# .envファイル作成
touch .env

# 基本設定（必要に応じて編集）
cat << 'EOF' > .env
# Notion API設定（Phase 2で使用）
NOTION_API_KEY=your_notion_api_key_here
NOTION_DATABASE_ID=your_database_id_here

# ComfyUI設定（Phase 3で使用）
COMFYUI_HOST=localhost:8188

# ログ設定
LOG_LEVEL=INFO
EOF

# 権限設定
chmod 600 .env
```

### 5. 動作確認テスト

```bash
# 1. 基本インポートテスト
python3 -c "
import sys
print(f'Python version: {sys.version}')
from src.models.database import Model, Run
from src.yaml_loader import YAMLLoader
from src.utils.db_init import init_database
print('✅ All core modules imported successfully')
"

# 2. テストスイート実行
python3 -m pytest tests/ -v

# 3. 型チェック
python3 -m mypy src/

# 4. YAMLローダーテスト
python3 -c "
from src.yaml_loader import YAMLLoader
import tempfile
print('✅ YAML Loader ready')
"
```

### 6. GitHub CLI設定

```bash
# GitHub認証状態確認
gh auth status

# 未認証の場合
gh auth login

# リポジトリ確認
gh repo view shomochisaku/sdxl-asset-manager

# Issue一覧確認
gh issue list
```

## 📁 プロジェクト構造理解

```
sdxl-asset-manager/
├── 📂 src/                    # メインソースコード
│   ├── 📂 models/             # データベースモデル
│   │   └── database.py        # SQLAlchemyモデル定義
│   ├── 📂 utils/              # ユーティリティ
│   │   ├── db_init.py         # DB初期化
│   │   └── db_utils.py        # CRUD操作
│   └── yaml_loader.py         # YAMLローダー
├── 📂 tests/                  # テストスイート
│   ├── test_database.py       # DBテスト
│   └── test_yaml_loader.py    # YAMLテスト
├── 📂 data/                   # データディレクトリ
│   └── 📂 yamls/              # YAMLファイル格納
│       └── sample_run.yaml    # サンプルファイル
├── 📄 CLAUDE.md               # 開発ガイド（重要）
├── 📄 README.md               # プロジェクト概要
└── 📄 requirements.txt        # Python依存関係
```

## 🔧 開発フロー

### Phase 1: 基本機能（現在）
- ✅ データベース基盤 (Issue #10)
- ✅ YAMLローダー (Issue #2)  
- 🔄 CLI実装 (Issue #13)

### Claude GitHub App使用
```bash
# 1. Issue作成
gh issue create --title "[FEATURE] 新機能" --body "詳細..."

# 2. @claudeメンション
gh issue comment 番号 --body "@claude この Issue を実装してください"

# 3. PR確認・マージ
gh pr list
gh pr view 番号
```

## ⚠️ トラブルシューティング

### よくある問題と解決法

#### Python importエラー
```bash
# PYTHONPATH設定
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# または python -m 使用
python -m src.yaml_loader
```

#### mypy型チェックエラー
```bash
# 現在の設定確認
cat pyproject.toml | grep -A 10 "\[tool.mypy\]"

# 一時的にstrict無効化済み
```

#### pytest実行エラー
```bash
# 詳細表示
python3 -m pytest tests/ -v -s

# 特定テスト実行
python3 -m pytest tests/test_yaml_loader.py::test_yaml_validation -v
```

#### ruffスタイルエラー
```bash
# 現在一時無効化中
echo "ruff check temporarily disabled in CI"

# 手動実行
python3 -m ruff check src/ --fix
```

## 🚀 新機能開発

### 手動開発の場合
1. **CLAUDE.md**確認（必須）
2. 既存モジュール活用
3. テスト作成
4. 型注釈追加

### Claude GitHub App使用の場合
1. Issue作成
2. @claudeメンション
3. PR確認
4. マージ

## 📞 サポート

- **開発ガイド**: [CLAUDE.md](CLAUDE.md)
- **プロジェクト概要**: [README.md](README.md)
- **Issue作成**: GitHub Issues
- **自動実装**: @claudeメンション

---

**このガイドで環境構築できない場合はIssueで質問してください！**