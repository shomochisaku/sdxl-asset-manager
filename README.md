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

```bash
# Notionからデータを同期
python -m src.cli sync

# YAMLファイルから画像生成
python -m src.cli gen path/to/prompt.yml

# データベース検索
python -m src.cli search "masterpiece 1girl"
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