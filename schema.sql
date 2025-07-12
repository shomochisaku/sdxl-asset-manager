-- SDXL Asset Manager Database Schema
-- SQLite3

-- モデル情報テーブル
CREATE TABLE IF NOT EXISTS models (
    model_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    type TEXT DEFAULT 'checkpoint', -- checkpoint, lora, vae, controlnet
    filename TEXT,
    source TEXT, -- 購入元URL/作者名
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 実行履歴テーブル
CREATE TABLE IF NOT EXISTS runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER,
    title TEXT NOT NULL,
    prompt TEXT NOT NULL,
    negative TEXT,
    cfg REAL DEFAULT 7.0,
    steps INTEGER DEFAULT 20,
    sampler TEXT DEFAULT 'DPM++ 2M',
    scheduler TEXT,
    seed INTEGER,
    width INTEGER DEFAULT 1024,
    height INTEGER DEFAULT 1024,
    batch_size INTEGER DEFAULT 1,
    status TEXT DEFAULT 'Tried', -- Purchased, Tried, Tuned, Final
    source TEXT, -- 参考元
    notion_page_id TEXT, -- Notion連携用
    comfyui_workflow_id TEXT, -- ComfyUI連携用
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_id) REFERENCES models(model_id) ON DELETE SET NULL
);

-- LoRA関連付けテーブル（多対多）
CREATE TABLE IF NOT EXISTS run_loras (
    run_id INTEGER,
    lora_id INTEGER,
    weight REAL DEFAULT 1.0,
    PRIMARY KEY (run_id, lora_id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (lora_id) REFERENCES models(model_id) ON DELETE CASCADE
);

-- 生成画像テーブル
CREATE TABLE IF NOT EXISTS images (
    image_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    width INTEGER,
    height INTEGER,
    file_size INTEGER, -- bytes
    hash TEXT, -- ファイルハッシュ（重複検出用）
    metadata TEXT, -- JSON形式の追加メタデータ
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

-- タグテーブル（将来の拡張用）
CREATE TABLE IF NOT EXISTS tags (
    tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    category TEXT, -- style, character, quality, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 実行履歴とタグの関連付け（多対多）
CREATE TABLE IF NOT EXISTS run_tags (
    run_id INTEGER,
    tag_id INTEGER,
    PRIMARY KEY (run_id, tag_id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(tag_id) ON DELETE CASCADE
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at);
CREATE INDEX IF NOT EXISTS idx_models_type ON models(type);
CREATE INDEX IF NOT EXISTS idx_images_run_id ON images(run_id);
CREATE INDEX IF NOT EXISTS idx_images_hash ON images(hash);

-- トリガー: updated_atの自動更新
CREATE TRIGGER IF NOT EXISTS update_models_timestamp 
AFTER UPDATE ON models
BEGIN
    UPDATE models SET updated_at = CURRENT_TIMESTAMP WHERE model_id = NEW.model_id;
END;

CREATE TRIGGER IF NOT EXISTS update_runs_timestamp 
AFTER UPDATE ON runs
BEGIN
    UPDATE runs SET updated_at = CURRENT_TIMESTAMP WHERE run_id = NEW.run_id;
END;