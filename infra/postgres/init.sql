-- ============================================================
-- Hotel ABC Platform — PostgreSQL Init Script
-- Crea database superset separato e estensioni necessarie
-- ============================================================

-- Estensioni
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- ricerca fuzzy sui nomi

-- Database separato per Superset BI
CREATE DATABASE hotel_abc_superset
    WITH OWNER hotel_user
    ENCODING 'UTF8'
    LC_COLLATE 'it_IT.UTF-8'
    LC_CTYPE 'it_IT.UTF-8'
    TEMPLATE template0;

-- Schema applicativo
CREATE SCHEMA IF NOT EXISTS abc;

-- Imposta timezone
SET timezone = 'Europe/Rome';
