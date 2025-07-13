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

### 🚨 重要：CI/型チェック互換性
**Python 3.9+互換性の維持が必須**です。以下の型注釈は避けてください：

#### ❌ 使用禁止（Python 3.10+でのみ利用可能）
```python
# Union type syntax (Python 3.10+)
def func() -> str | None:  # ❌ NG
def func() -> dict[str, Any]:  # ❌ NG  
def func() -> list[Model]:  # ❌ NG
def func() -> type[Model]:  # ❌ NG
```

#### ✅ 推奨（Python 3.9+互換）
```python
from typing import Dict, List, Optional, Type, Union

def func() -> Optional[str]:  # ✅ OK
def func() -> Dict[str, Any]:  # ✅ OK
def func() -> List[Model]:  # ✅ OK
def func() -> Type[Model]:  # ✅ OK
def func() -> Union[str, int]:  # ✅ OK
```

#### よくあるCIエラーと対処法
- **mypy Error**: `unsupported operand type(s) for |`
  → `str | None` を `Optional[str]` に変更
- **mypy Error**: `'type' object is not subscriptable`
  → `dict[str, Any]` を `Dict[str, Any]` に変更
- **ImportError**: `types-PyYAML` 関連
  → `# type: ignore[import-untyped]` で対応

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

## 開発進捗 (2025-07-13)

### ✅ 完了済み

#### プロジェクト基盤
- ✅ GitHubリポジトリ作成・初期セットアップ
- ✅ プロジェクト構造設計 (src/, tests/, docs/, data/)
- ✅ 依存関係管理 (requirements.txt, pyproject.toml)
- ✅ Git-flowブランチ戦略の採用
- ✅ Claude GitHub App連携設定完了

#### CI/CD & 品質管理
- ✅ GitHub Actions CI設定 (pytest, mypy, ruff)
- ✅ ブランチ保護ルール設定 (Pull Request必須)
- ✅ Claude Code Review自動レビュー
- ✅ テストカバレッジ設定

#### Phase 1: 基本機能実装
1. **データベース基盤 (Issue #10) ✅ 完了**
   - SQLAlchemyモデル設計・実装 (6テーブル)
   - データベース初期化機能
   - CRUD操作ユーティリティ
   - 包括的テストスイート (21テスト)
   - PR #11でマージ済み

2. **YAMLローダー (Issue #2) ✅ 完了**
   - YAMLファイル読み込み・バリデーション
   - SQLAlchemyモデルへの変換
   - データベース挿入機能
   - LoRA・モデル関係管理
   - 包括的テストスイート (47テスト)
   - PR #12でマージ済み

#### 技術的解決事項
- ✅ SQLAlchemy 2.0+ 対応
- ✅ DetachedInstanceError対策 (session.expunge)
- ✅ 型注釈対応 (mypy strict mode)
- ✅ Claude GitHub App運用フロー確立
- ✅ ブランチ保護ルール運用経験

### 🔄 進行中

#### Issue #13 - CLI基本機能実装
- **状況**: Claude GitHub App実装中
- **内容**: click使用のモダンCLI
- **コマンド**: db, yaml, search, run
- **優先度**: Phase 1最終タスク

### 📋 次のステップ

#### 1. Phase 1完了後の即座対応
- [ ] CLI実装完了・テスト (Issue #13)
- [ ] データベースマイグレーション機能
- [ ] ruff style問題修正 (別Issue/PR)
- [ ] Phase 1統合テスト実施

#### 2. Phase 2: 外部連携機能
- [ ] Notion API同期機能 (Issue #4)
- [ ] ComfyUI API連携 (Issue #5)
- [ ] バッチ処理・自動化

#### 3. Phase 3以降
- [ ] LLMエージェント機能
- [ ] Web UI実装
- [ ] 高度な検索・分析機能

### 🚨 既知の課題

1. **ruffスタイルエラー (120+件)**
   - ~~型注釈の現代化 (`Optional[T]` → `T | None`)~~ **注意**: これは実施しない（CI互換性のため）
   - 未使用インポートの削除
   - 空白行の修正
   - **対応**: 別途Issue作成して修正予定

2. **datetime.utcnow() 非推奨警告**
   - SQLAlchemyモデルで使用中
   - **対応**: `datetime.now(datetime.UTC)` への移行必要

3. **型注釈互換性問題（解決済み）**
   - Python 3.10+型注釈を使用するとCI失敗
   - **対策**: Python 3.9+互換の`Optional[T]`, `Dict[str, Any]`等を使用

### 💡 学習事項

1. **Claude GitHub App運用**
   - 自動実装は成功、手動PR作成・マージが必要
   - CI失敗時のトラブルシューティング経験蓄積
   - @claudeメンションで効率的な実装指示

2. **SQLAlchemy 2.0移行**
   - session管理のベストプラクティス習得
   - 型安全性の重要性確認
   - DetachedInstanceError対策の実装

3. **CI/CD最適化**
   - 段階的品質チェック (tests → types → style)
   - 一時的無効化による開発速度とクオリティのバランス
   - ブランチ保護ルールの柔軟な運用

4. **開発フロー最適化**
   - Claude Code CLI: 設計・調査・指示
   - Claude GitHub App: 実装・テスト作成
   - 役割分担による効率的な開発

## 注意事項

- 外部Webサービスは呼び出さない（Notion/ComfyUI APIを除く）
- 画像ファイルは`data/images/`に保存
- YAMLファイルは`data/yamls/`に保存
- データベースファイルは`.gitignore`に含める