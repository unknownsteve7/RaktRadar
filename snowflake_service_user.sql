-- Service user for the GitHub Actions loader (PUT + COPY INTO RAW.BLOOD_STOCK).
-- Run once as ACCOUNTADMIN after snowflake_setup.sql.
use role accountadmin;

-- TYPE = SERVICE: no password, no MFA prompts, key-pair auth only
create user if not exists RAKT_LOADER_SVC
    TYPE = SERVICE
    DEFAULT_ROLE = RAKT_LOADER
    DEFAULT_WAREHOUSE = RAKTRADAR_WH
    DEFAULT_NAMESPACE = RAKTRADAR.RAW
    COMMENT = 'GitHub Actions loader for RaktRadar';

grant role RAKT_LOADER to user RAKT_LOADER_SVC;

-- ==============================================================================
-- Attach the public key (run manually in a worksheet, not from the repo).
-- Paste the contents of rsa_key.pub without the BEGIN/END lines and newlines.
-- ==============================================================================
-- alter user RAKT_LOADER_SVC set RSA_PUBLIC_KEY = 'MIIBIjANBgkq...';
-- desc user RAKT_LOADER_SVC;  -- RSA_PUBLIC_KEY_FP should now be set

-- ==============================================================================
-- Service user for dbt (GitHub Actions), RAKT_TRANSFORMER: reads RAW, builds ANALYTICS
-- ==============================================================================
create user if not exists RAKT_TRANSFORMER_SVC
    TYPE = SERVICE
    DEFAULT_ROLE = RAKT_TRANSFORMER
    DEFAULT_WAREHOUSE = RAKTRADAR_WH
    DEFAULT_NAMESPACE = RAKTRADAR.ANALYTICS
    COMMENT = 'GitHub Actions dbt runner for RaktRadar';

grant role RAKT_TRANSFORMER to user RAKT_TRANSFORMER_SVC;

-- Same key pair as the loader, so CI needs no extra secret (run manually):
-- alter user RAKT_TRANSFORMER_SVC set RSA_PUBLIC_KEY = 'MIIBIjANBgkq...';
