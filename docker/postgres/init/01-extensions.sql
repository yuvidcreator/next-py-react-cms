-- =============================================================================
-- PyPress — PostgreSQL Initialization
-- =============================================================================
-- This script runs ONCE when the PostgreSQL container is first created.
-- It enables recommended extensions for a CMS workload.
--
-- WordPress equivalent: The initial MySQL database creation step.
-- Actual table creation (pp_posts, pp_users, etc.) is handled by Alembic
-- migrations in the backend, not here.
-- =============================================================================

-- Full-text search support (used by the built-in search, Elasticsearch plugin
-- is optional and additive)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- UUID generation for primary keys
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Case-insensitive text type (useful for usernames, slugs)
CREATE EXTENSION IF NOT EXISTS citext;

-- Unaccented text search (so searching "café" finds "cafe" and vice versa)
CREATE EXTENSION IF NOT EXISTS unaccent;
