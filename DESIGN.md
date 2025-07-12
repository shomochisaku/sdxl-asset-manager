# SDXL Asset Manager 設計仕様書

## 1. 目的・ゴール

1. **購入素材（モデル／LoRA／プロンプト／パラメータ）** と **自作生成ログ** を一元管理し、検索・再利用・最適化を容易にする
2. ChatGPT で発案 → Claude Code で実装し、最終的には **Vibe Coding** で拡張・保守可能なコードベースを構築する
3. 個人運用が前提だが、将来的なチーム共有にも耐えうるスキーマ・モジュール分割を行う

## 2. システム構成図

```
┌──────────────────┐         ┌───────────────┐
│  Notion DB       │─API───▶│  Sync Script  │────────┐
│  (YAML＋画像)    │        │  (Python)     │        │
└──────────────────┘        └───────────────┘        │
        ▲                                           ▼
   手動入力①                              ┌────────────────┐
   /Drag&Drop                              │  SQL DB (SQLite) │
                                           │  tables: models │
                                           │          runs   │
                                           │          images │
                                           └────────────────┘
                                                       ▲
                                                       │
                                       ┌───────────────┴──────────────┐
                                       │  Vector Store (optional)     │
                                       │  Supabase / Chroma / Weaviate│
                                       └───────────────┬──────────────┘
                                                       │
                          ┌──────────────┐             │
                          │  LLM Agents  │◀────────────┘
                          │ ChatGPT / Claude etc.      │
                          └──────────────┘
```

## 3. データ構造

### 3.1 YAML テンプレート（購入・生成共通）

```yaml
run_title: "Cute Girl Turbo"
model: "SDXL-Turbo-0.9"
loras: ["animeSharp_v1"]
vae: "sdxl_vae.safetensors"
prompt: |-
  masterpiece, 1girl, ***, best quality
negative: |-
  lowres, bad anatomy, ***, watermark
cfg: 4
steps: 25
sampler: DPM++ 2M
seed: 123456
source: "作者名 / URL"
status: Purchased   # ↔ Tried / Tuned / Final
```

### 3.2 データベース設計

詳細は `schema.sql` を参照。主要テーブル：

- **models**: モデル/LoRA/VAE情報
- **runs**: 実行履歴（プロンプト、パラメータ）
- **images**: 生成画像メタデータ
- **run_loras**: LoRAとRunの多対多関係
- **tags**: タグ管理（将来拡張用）

## 4. モジュール設計

| モジュール                         | 役割                                              | 主要ライブラリ                                |
| ----------------------------- | ----------------------------------------------- | -------------------------------------- |
| **notion\_sync.py**           | Notion → YAML 抽出＋画像DL／週1 差分同期                   | `notion-client`, `PyYAML`, `requests`  |
| **yaml\_loader.py**           | YAML → SQLite INSERT／更新                         | `sqlite3`, `PyYAML`                    |
| **embed\_runner.py** (任意)     | 新規・更新 `run_id` をベクター化し Upsert                   | `langchain`, `supabase` or `chromadb`  |
| **agent\_tools.sql\_tool**    | `run_sql(query)` を LLM へ公開                      | `sqlite3`                              |
| **agent\_tools.vector\_tool** | `vector_search(text, filter)`                   | 〃                                      |
| **cli.py**                    | `python cli.py gen "prompt.yml"` → ComfyUI 呼び出し | `subprocess`, `requests` (ComfyUI API) |

## 5. 主要フロー

| # | フェーズ        | 入出力 & 処理                                                   |
| - | ----------- | ---------------------------------------------------------- |
| 1 | **購入**      | 手動で Notion に YAML ＋ 参考画像を貼付                                |
| 2 | **同期**      | `notion_sync.py` が YAML DL → `yaml_loader.py` で DB 反映      |
| 3 | **試行**      | `cli.py gen <yml>` で ComfyUI 生成 → JSON/画像を Notion へ添付      |
| 4 | **改善**      | ChatGPT / Claude に `<LOG>…</LOG>` 送信 → **Agent** が DB検索＋提案 |
| 5 | **調整**      | プロンプト修正、cfg/steps 変更→再生成 (#3 ループ)                          |
| 6 | **完成**      | `status` を Final、Notion ページ先頭に要約を貼付                        |
| 7 | **ポートフォリオ** | `SELECT * WHERE status='Final'` → CSV → 外部公開など             |

## 6. 非機能要件

| 項目     | 要件値                              |
| ------ | -------------------------------- |
| 同期頻度   | 手動 or CRON 週1                    |
| 同期遅延   | 10 分以内                           |
| 検索応答   | SQL < 500 ms, Vector < 1 s       |
| データ量想定 | 画像 1 万枚 / YAML 3 千件 / DB 〜200 MB |
| バックアップ | SQLite と画像フォルダを週1 圧縮 & 外部ドライブ    |

## 7. 開発フェーズ

### Phase 1: 基本機能（Issue #1-3）
- SQLAlchemyモデル・DB初期化
- YAMLローダー・バリデーション
- 基本的なCLI構造

### Phase 2: Notion連携
- Notion API同期機能
- 差分同期ロジック
- 画像ダウンロード

### Phase 3: ComfyUI連携
- ComfyUI API統合
- ワークフロー生成・実行

### Phase 4: LLM Agent
- SQL検索ツール
- ベクトル検索（オプション）
- プロンプト最適化エージェント

## 8. セキュリティ・プライバシー

- **機密データ保護**: すべての購入素材情報、生成画像は `.gitignore` で除外
- **API キー管理**: 環境変数（.env）で管理
- **ローカル運用**: 個人データはローカルに保存

## 9. 今後の拡張性

- **チーム共有**: データベースをPostgreSQLに移行
- **Web UI**: Streamlit/FastAPI でWeb インターフェース
- **クラウド対応**: AWS/GCP でのホスティング
- **AI機能強化**: より高度な最適化・推奨機能