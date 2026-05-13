-- Migration: 004_asset_fts
-- Version: 4
-- Name: asset_fts
-- Description: Frontend asset index and FTS5 search

CREATE TABLE asset_index (
  asset_id TEXT PRIMARY KEY,
  content_id TEXT NOT NULL REFERENCES contents(content_id),
  stage TEXT NOT NULL,
  display_name TEXT NOT NULL,
  subtitle TEXT,
  source_platform TEXT,
  source_type TEXT,
  content_type TEXT,
  source_group_id TEXT,
  latest_artifact_id TEXT REFERENCES artifacts(artifact_id),
  manifest_id TEXT REFERENCES manifests(manifest_id),
  status TEXT NOT NULL,
  sort_key TEXT,
  updated_at TEXT NOT NULL,
  search_text TEXT,
  metadata_json TEXT
);

CREATE INDEX idx_asset_index_stage
  ON asset_index(stage, status, sort_key DESC);

CREATE INDEX idx_asset_index_content
  ON asset_index(content_id, stage);

CREATE INDEX idx_asset_index_source_group
  ON asset_index(source_group_id, stage);

CREATE VIRTUAL TABLE asset_index_fts USING fts5(
  asset_id UNINDEXED,
  display_name,
  subtitle,
  search_text,
  content='asset_index',
  content_rowid='rowid'
);
