-- ==============================================================================
-- 1. DATABASE & SCHEMA SETUP
-- ==============================================================================
-- We create one main database and separate schemas for Raw data vs Clean data
CREATE DATABASE IF NOT EXISTS RAKTRADAR_DB;

USE DATABASE RAKTRADAR_DB;
CREATE SCHEMA IF NOT EXISTS RAW;        -- Where Python dumps data
CREATE SCHEMA IF NOT EXISTS ANALYTICS;  -- Where dbt builds clean tables

-- ==============================================================================
-- 2. CREATE ROLES
-- ==============================================================================
-- rakt_loader: Used by Python/Airflow to upload NDJSON and COPY INTO raw tables
CREATE ROLE IF NOT EXISTS rakt_loader;

-- rakt_transformer: Used by dbt to read raw data and build clean models
CREATE ROLE IF NOT EXISTS rakt_transformer;

-- rakt_reporter: Used by Streamlit/Metabase to read final dashboards (Read Only)
CREATE ROLE IF NOT EXISTS rakt_reporter;

-- (Optional) Grant roles to SYSADMIN so you can manage them easily in the UI
GRANT ROLE rakt_loader TO ROLE SYSADMIN;
GRANT ROLE rakt_transformer TO ROLE SYSADMIN;
GRANT ROLE rakt_reporter TO ROLE SYSADMIN;

-- ==============================================================================
-- 3. GRANT WAREHOUSE ACCESS
-- ==============================================================================
-- Assuming you named your warehouse RAKTRADAR_WH
GRANT USAGE ON WAREHOUSE RAKTRADAR_WH TO ROLE rakt_loader;
GRANT USAGE ON WAREHOUSE RAKTRADAR_WH TO ROLE rakt_transformer;
GRANT USAGE ON WAREHOUSE RAKTRADAR_WH TO ROLE rakt_reporter;

-- ==============================================================================
-- 4. GRANT DATABASE & SCHEMA ACCESS
-- ==============================================================================
-- Loader needs full control over RAW schema to create stages and tables
GRANT USAGE ON DATABASE RAKTRADAR_DB TO ROLE rakt_loader;
GRANT USAGE, CREATE STAGE, CREATE TABLE ON SCHEMA RAKTRADAR_DB.RAW TO ROLE rakt_loader;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA RAKTRADAR_DB.RAW TO ROLE rakt_loader;
GRANT ALL PRIVILEGES ON FUTURE TABLES IN SCHEMA RAKTRADAR_DB.RAW TO ROLE rakt_loader;

-- Transformer needs to READ from RAW, and FULL CONTROL over ANALYTICS
GRANT USAGE ON DATABASE RAKTRADAR_DB TO ROLE rakt_transformer;
GRANT USAGE ON SCHEMA RAKTRADAR_DB.RAW TO ROLE rakt_transformer;
GRANT SELECT ON ALL TABLES IN SCHEMA RAKTRADAR_DB.RAW TO ROLE rakt_transformer;
GRANT SELECT ON FUTURE TABLES IN SCHEMA RAKTRADAR_DB.RAW TO ROLE rakt_transformer;

GRANT USAGE, CREATE TABLE, CREATE VIEW ON SCHEMA RAKTRADAR_DB.ANALYTICS TO ROLE rakt_transformer;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA RAKTRADAR_DB.ANALYTICS TO ROLE rakt_transformer;
GRANT ALL PRIVILEGES ON ALL VIEWS IN SCHEMA RAKTRADAR_DB.ANALYTICS TO ROLE rakt_transformer;
GRANT ALL PRIVILEGES ON FUTURE TABLES IN SCHEMA RAKTRADAR_DB.ANALYTICS TO ROLE rakt_transformer;
GRANT ALL PRIVILEGES ON FUTURE VIEWS IN SCHEMA RAKTRADAR_DB.ANALYTICS TO ROLE rakt_transformer;

-- Reporter only needs to READ from ANALYTICS
GRANT USAGE ON DATABASE RAKTRADAR_DB TO ROLE rakt_reporter;
GRANT USAGE ON SCHEMA RAKTRADAR_DB.ANALYTICS TO ROLE rakt_reporter;
GRANT SELECT ON ALL TABLES IN SCHEMA RAKTRADAR_DB.ANALYTICS TO ROLE rakt_reporter;
GRANT SELECT ON ALL VIEWS IN SCHEMA RAKTRADAR_DB.ANALYTICS TO ROLE rakt_reporter;
GRANT SELECT ON FUTURE TABLES IN SCHEMA RAKTRADAR_DB.ANALYTICS TO ROLE rakt_reporter;
GRANT SELECT ON FUTURE VIEWS IN SCHEMA RAKTRADAR_DB.ANALYTICS TO ROLE rakt_reporter;

-- ==============================================================================
-- 5. CREATE INTERNAL STAGE & RAW TABLE (As rakt_loader)
-- ==============================================================================
USE ROLE rakt_loader;
USE SCHEMA RAKTRADAR_DB.RAW;

-- Create the Internal Stage where Python will upload the NDJSON.gz files
CREATE STAGE IF NOT EXISTS rakt_stage 
    FILE_FORMAT = (TYPE = JSON COMPRESSION = GZIP);

-- Create the RAW table that will receive the JSON payloads
CREATE TABLE IF NOT EXISTS BLOOD_STOCK (
    raw_variant VARIANT,
    _run_id STRING,
    _source_file STRING,
    _loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
