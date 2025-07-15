# SDXL Asset Manager

画像生成ワークフロー統合システム - Stable Diffusion XLの素材管理と生成ログを一元管理するツール

## 概要

本システムは以下の機能を提供します：

### ✅ 実装完了機能 (Phase 1-3)
- **購入素材の管理**: モデル/LoRA/プロンプト/パラメータのデータベース管理
- **生成ログの記録と検索**: 詳細な検索・統計機能
- **Notion DB同期**: 双方向同期・競合検出・解決
- **LLMエージェント**: 対話型AI相談・データ分析・プロンプト最適化
- **YAML インポート/エクスポート**: データの一括処理

### 🔄 今後の実装予定 (Phase 4)
- ComfyUIとの連携
- Web UI
- チーム機能・クラウド対応

## 必要要件

- Python 3.9+
- SQLite3
- Notion API トークン（Phase 2機能用）
- OpenAI API キー（LLMエージェント用）
- Anthropic API キー（LLMエージェント用）
- ComfyUI（オプション）

## セットアップ

### 🚀 新しい端末での開発環境構築

#### 1. 前提条件
- Python 3.9+ （必須）
- Git
- GitHub CLI (Claude GitHub App連携用)
- LLM API キー（OpenAI または Anthropic）

#### 2. リポジトリセットアップ
```bash
# リポジトリクローン
git clone https://github.com/shomochisaku/sdxl-asset-manager.git
cd sdxl-asset-manager

# 現在のブランチ確認
git branch -a
git checkout main
```

#### 3. Python環境セットアップ
```bash
# Python 3.9+確認
python3 --version

# 依存関係インストール
pip install -r requirements.txt

# 開発ツールインストール
pip install mypy pytest ruff
```

#### 4. 環境変数設定
```bash
# .envファイル作成
touch .env

# 必要に応じて以下を設定
echo "NOTION_API_KEY=your_notion_api_key" >> .env
echo "NOTION_DATABASE_ID=your_database_id" >> .env
echo "OPENAI_API_KEY=your_openai_api_key" >> .env
echo "ANTHROPIC_API_KEY=your_anthropic_api_key" >> .env
echo "COMFYUI_HOST=localhost:8188" >> .env
```

#### 5. 動作確認
```bash
# テスト実行
python3 -m pytest

# 型チェック
python3 -m mypy src/

# リンター（現在一時無効化中）
python3 -m ruff check src/

# YAMLローダーテスト
python3 -c "from src.yaml_loader import YAMLLoader; print('✅ YAML Loader OK')"
```

#### 6. GitHub CLI設定（Claude連携用）
```bash
# GitHub CLIインストール確認
gh --version

# GitHub認証（必要に応じて）
gh auth login

# Issueでの@claudeメンション使用可能
gh issue list
```

### 📁 プロジェクト構造
```
sdxl-asset-manager/
├── src/
│   ├── models/database.py      # SQLAlchemyモデル
│   ├── utils/db_*.py          # データベースユーティリティ
│   └── yaml_loader.py         # YAMLローダー
├── tests/                     # テストスイート
├── data/
│   └── yamls/                 # YAMLファイル格納
├── CLAUDE.md                  # 開発ガイド
└── requirements.txt           # 依存関係
```

## 使い方

### CLI コマンド ✅ 実装完了

CLIは以下の方法で実行できます：

#### 方法1: モジュールとして実行 (開発時)
```bash
# データベース初期化
python -m src db init

# YAMLファイルの処理
python -m src yaml load data/yamls/ --recursive

# データベース検索
python -m src search prompt "masterpiece 1girl" --limit 10

# 実行履歴表示
python -m src run list --status Final

# データベースステータス確認
python -m src db status

# Notion API連携 (Phase 2)
python -m src notion setup
python -m src notion sync --direction both

# LLMエージェント機能 (Phase 3)
python -m src agent chat           # 対話型AI相談
python -m src agent analyze        # データ分析
python -m src agent recommend      # 最適化提案
```

#### 方法2: インストール後のコマンド (本番運用)
```bash
# パッケージをインストール
pip install -e .

# コマンドとして実行
sdxl-asset-manager db init
sdxl-asset-manager yaml load data/yamls/ --recursive
sdxl-asset-manager search prompt "masterpiece 1girl" 
sdxl-asset-manager run list --status Final
sdxl-asset-manager db status

# Notion API連携とLLMエージェント
sdxl-asset-manager notion sync --direction both
sdxl-asset-manager agent chat
sdxl-asset-manager agent analyze
```

#### 方法3: 直接実行 (開発時)
```bash
# 直接Pythonファイルを実行
python src/cli.py --help
python src/cli.py db init
python src/cli.py yaml validate data/yamls/
```

**✅ CLI機能実装済み (PR #14)**

### データ構造

#### YAML形式（Notion管理）
```yaml
run_title: "作品タイトル"
model: "モデル名"
loras: ["LoRA名"]
prompt: "プロンプト"
negative: "ネガティブプロンプト"
cfg: 7.0
steps: 20
```

## 開発

### Claude GitHub App連携開発フロー

このプロジェクトは**Claude GitHub App**を使用した自動実装に対応しています。

#### Issue作成 → 自動実装フロー
1. **Issue作成**: 機能要望をGitHub Issueとして作成
2. **@claudeメンション**: Issue内で`@claude この Issue を実装してください`
3. **自動実装**: Claude GitHub Appが自動でコード実装・テスト作成
4. **PR確認**: 生成されたPull Requestをレビュー・マージ

#### 開発ツール確認
```bash
# テスト実行
python3 -m pytest

# 型チェック  
python3 -m mypy src/

# リンター（一時無効化中）
python3 -m ruff check src/
```

### 手動開発時の注意事項
- **CLAUDE.md**を必ず確認（プロジェクト固有のガイドライン）
- **既存モジュール**を活用（DatabaseManager, YAMLLoader）
- **テスト**は必須（pytest + mypy + ruff）

### トラブルシューティング

#### よくある問題
- **Python 3.12未満**: 型ヒント構文エラー
- **依存関係不足**: `pip install -r requirements.txt`で解決
- **import エラー**: `PYTHONPATH`設定または`python -m`使用

#### サポート
- **開発ガイド**: [CLAUDE.md](CLAUDE.md)参照
- **Issue**: GitHub Issueで質問・バグ報告
- **実装依頼**: @claudeメンションで自動実装

## ライセンス

MIT License