# SDXL Asset Manager - Claude Code 開発ガイド

## プロジェクト概要

本プロジェクトは画像生成ワークフローの統合管理システムです。
Stable Diffusion XLの購入素材と自作生成ログを一元管理し、最適化を支援します。

## 技術スタック

- Python 3.12
- SQLite（データベース）
- Notion API（外部データソース）
- ComfyUI API（画像生成）
- pytest（テスト）
- mypy（型チェック）
- ruff（リンター）

## 開発規約

### コーディング規約
- 型ヒントを必ず使用
- docstringはGoogle Style
- 日本語コメント歓迎
- エラーハンドリングを適切に実装
- セキュリティベストプラクティスに従う

### ブランチ戦略
- Git-flowを採用
- feature/ブランチで開発
- developブランチに統合
- mainブランチが安定版

### テスト
```bash
# 実行前に必ず以下を確認
pytest
mypy src/
ruff check src/
```

## Claude GitHub App セットアップ手順

### 🚨 重要：正しいセットアップ方法

Claude GitHub Appを使用するには、**リポジトリ個別でのインストール**が必要です。

#### 1. 前提条件
- ✅ Claude Pro (MAX) サブスクリプション
- ✅ GitHub CLI (`gh`) インストール済み
- ✅ Claude Code CLI 使用

#### 2. セットアップ手順
```bash
# 1. リポジトリ個別でClaude GitHub Appをインストール
/install-github-app

# 2. 設定画面で以下を選択
# - @Claude Code (Issue/PRメンション対応) ✅
# - Claude Code Review (PR自動レビュー) ✅  
# - Subscription (Maxプラン使用) ✅

# 3. ブラウザでClaude.ai認証
# - 権限許可
# - GitHub連携

# 4. 自動PRのマージ
# - .github/workflows/claude-code-review.yml
# - .github/workflows/claude.yml
```

#### 3. 使用方法
```bash
# Issueで@claudeメンション
@claude この Issue を実装してください

# 1分以内に反応開始
# - 自動ブランチ作成
# - 実装ファイル作成  
# - PR自動作成
```

#### ❌ 間違った方法（動作しない）
- GitHub Apps画面からの手動インストール
- 手動でのワークフロー作成
- APIキーのみでの設定

#### ✅ 正しい方法
- `/install-github-app` コマンド使用
- Claude.aiサブスクリプション連携
- 公式ワークフローの自動生成

## Issue対応ガイド

### Issue処理の流れ
1. Issueの内容を理解
2. `@claude` でメンション（自動でfeatureブランチ作成）
3. Claude GitHub Appが自動実装
4. 生成されたPRをレビュー・マージ

### 実装優先順位
1. **Phase 1**: 基本機能（DB、YAML loader、CLI）
2. **Phase 2**: Notion同期
3. **Phase 3**: ComfyUI連携
4. **Phase 4**: LLMエージェント

## モジュール構成

- `src/cli.py`: メインCLIインターフェース
- `src/notion_sync.py`: Notion API連携
- `src/yaml_loader.py`: YAML→DB変換
- `src/models/`: SQLAlchemyモデル定義
- `src/agent_tools/`: LLMツール実装

## 環境変数

`.env`ファイルで管理：
- `NOTION_API_KEY`: Notion APIトークン
- `NOTION_DATABASE_ID`: 対象データベースID
- `COMFYUI_HOST`: ComfyUI APIホスト（デフォルト: localhost:8188）

## デバッグ情報

- ログレベル: `logging.INFO`をデフォルト使用
- エラー時は詳細なスタックトレースを含める
- SQLクエリはパラメータ化して実行（SQLインジェクション対策）

## 注意事項

- 外部Webサービスは呼び出さない（Notion/ComfyUI APIを除く）
- 画像ファイルは`data/images/`に保存
- YAMLファイルは`data/yamls/`に保存
- データベースファイルは`.gitignore`に含める