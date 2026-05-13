-- Migration: 003_blocks_and_topics
-- Version: 3
-- Name: blocks_and_topics
-- Description: Storage objects, manifests, artifacts, blocks, topics, name lineage, and pipeline runtime

CREATE TABLE storage_objects (
  object_id TEXT PRIMARY KEY,
  sha256 TEXT NOT NULL UNIQUE,
  storage_uri TEXT NOT NULL,
  byte_size INTEGER NOT NULL,
  mime_type TEXT,
  created_at TEXT NOT NULL,
  exists_verified_at TEXT
);

CREATE TABLE manifests (
  manifest_id TEXT PRIMARY KEY,
  subject_type TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  schema_name TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  object_id TEXT NOT NULL REFERENCES storage_objects(object_id),
  created_at TEXT NOT NULL
);

CREATE INDEX idx_manifests_subject
  ON manifests(subject_type, subject_id, created_at DESC);

CREATE TABLE artifacts (
  artifact_id TEXT PRIMARY KEY,
  content_id TEXT NOT NULL REFERENCES contents(content_id),
  stage TEXT NOT NULL,
  artifact_type TEXT NOT NULL,
  role TEXT NOT NULL,
  object_id TEXT NOT NULL REFERENCES storage_objects(object_id),
  manifest_id TEXT REFERENCES manifests(manifest_id),
  schema_name TEXT,
  schema_version TEXT,
  run_id TEXT,
  artifact_version INTEGER NOT NULL,
  is_canonical INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  metadata_json TEXT
);

CREATE TABLE artifact_edges (
  parent_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
  child_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
  relation TEXT NOT NULL,
  PRIMARY KEY (parent_artifact_id, child_artifact_id, relation)
);

CREATE INDEX idx_artifacts_content_stage
  ON artifacts(content_id, stage, is_canonical DESC, created_at DESC);

CREATE INDEX idx_artifacts_stage_type
  ON artifacts(stage, artifact_type, created_at DESC);

CREATE TABLE content_blocks (
  block_id TEXT PRIMARY KEY,
  content_id TEXT NOT NULL REFERENCES content_identities(content_id),
  content_version_id TEXT REFERENCES content_versions(content_version_id),
  artifact_id TEXT REFERENCES artifacts(artifact_id),
  stage TEXT NOT NULL,
  block_type TEXT NOT NULL,
  order_index INTEGER NOT NULL,
  parent_block_id TEXT REFERENCES content_blocks(block_id),
  text_object_id TEXT REFERENCES storage_objects(object_id),
  text_excerpt TEXT,
  start_offset INTEGER,
  end_offset INTEGER,
  metadata_json TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE topic_blocks (
  topic_block_id TEXT PRIMARY KEY,
  content_id TEXT NOT NULL REFERENCES content_identities(content_id),
  source_artifact_id TEXT REFERENCES artifacts(artifact_id),
  topic_title TEXT NOT NULL,
  topic_type TEXT NOT NULL,
  start_block_index INTEGER,
  end_block_index INTEGER,
  metadata_json TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE topic_block_members (
  topic_block_id TEXT NOT NULL REFERENCES topic_blocks(topic_block_id),
  block_id TEXT NOT NULL REFERENCES content_blocks(block_id),
  order_index INTEGER NOT NULL,
  PRIMARY KEY (topic_block_id, block_id)
);

CREATE INDEX idx_content_blocks_content_order
  ON content_blocks(content_id, stage, order_index);

CREATE INDEX idx_content_blocks_version
  ON content_blocks(content_version_id, order_index);

CREATE INDEX idx_topic_blocks_content
  ON topic_blocks(content_id, created_at DESC);

CREATE TABLE name_bindings (
  name_binding_id TEXT PRIMARY KEY,
  subject_type TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  stage TEXT,
  namespace TEXT NOT NULL,
  name_kind TEXT NOT NULL,
  display_value TEXT NOT NULL,
  normalized_value TEXT,
  path_safe_value TEXT,
  is_primary INTEGER NOT NULL DEFAULT 0,
  valid_from TEXT NOT NULL,
  valid_to TEXT
);

CREATE INDEX idx_name_bindings_subject
  ON name_bindings(subject_type, subject_id, namespace, name_kind);

CREATE INDEX idx_name_bindings_primary
  ON name_bindings(subject_type, subject_id, stage, is_primary);

CREATE TABLE pipeline_runs (
  run_id TEXT PRIMARY KEY,
  run_type TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  input_ref TEXT,
  summary_json TEXT
);

CREATE TABLE stage_status (
  content_id TEXT NOT NULL REFERENCES contents(content_id),
  stage TEXT NOT NULL,
  status TEXT NOT NULL,
  latest_artifact_id TEXT REFERENCES artifacts(artifact_id),
  error_code TEXT,
  error_message TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (content_id, stage)
);

CREATE INDEX idx_stage_status_stage
  ON stage_status(stage, status, updated_at DESC);

CREATE INDEX idx_pipeline_runs_status
  ON pipeline_runs(run_type, status, started_at DESC);
