-- Migration: 001_initial_project_memory
-- Version: 1
-- Name: initial_project_memory
-- Description: Project registry, metadata, and schema migration ledger

CREATE TABLE projects (
  project_id TEXT PRIMARY KEY,
  project_instance_id TEXT NOT NULL UNIQUE,
  project_name TEXT NOT NULL,
  project_root TEXT NOT NULL,
  storage_root TEXT NOT NULL,
  status TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE project_memory_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  checksum TEXT NOT NULL,
  applied_at TEXT NOT NULL,
  applied_by TEXT,
  execution_ms INTEGER NOT NULL
);
