# SDXL Asset Manager

画像生成ワークフロー統合システム - Stable Diffusion XLの素材管理と生成ログを一元管理するツール

## 概要

本システムは以下の機能を提供します：
- 購入素材（モデル/LoRA/プロンプト/パラメータ）の管理
- 自作生成ログの記録と検索
- Notion DBとの同期
- ComfyUIとの連携
- LLMエージェントによる最適化提案

## 必要要件

- Python 3.12+
- SQLite3
- Notion API トークン
- ComfyUI（オプション）

## インストール

```bash
# リポジトリのクローン
git clone https://github.com/yourusername/sdxl-asset-manager.git
cd sdxl-asset-manager

# 仮想環境の作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係のインストール
pip install -r requirements.txt

# 環境変数の設定
cp .env.example .env
# .envファイルを編集してNotion APIトークンを設定
```

## 使い方

### CLI コマンド

CLIは以下の方法で実行できます：

#### 方法1: モジュールとして実行 (開発時)
```bash
# データベース初期化
python -m src db init

# YAMLファイルの処理
python -m src yaml load path/to/prompt.yml

# データベース検索
python -m src search "masterpiece 1girl"

# データベースステータス確認
python -m src db status
```

#### 方法2: インストール後のコマンド (本番運用)
```bash
# パッケージをインストール
pip install -e .

# コマンドとして実行
sdxl-asset-manager db init
sdxl-asset-manager yaml load path/to/prompt.yml
sdxl-asset-manager search "masterpiece 1girl"
sdxl-asset-manager db status
```

#### 方法3: 直接実行 (開発時)
```bash
# 直接Pythonファイルを実行
python src/cli.py --help
python src/cli.py db init
```

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

### テスト実行
```bash
pytest
mypy src/
ruff check src/
```

### Issueの作成
GitHub Issuesを使用して機能要望やバグ報告を管理しています。
Claude GitHub Appが自動的にIssueを処理します。

## ライセンス

MIT License