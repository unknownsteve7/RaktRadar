-- GitHub is the source of truth: Snowflake reads this repo, never writes to it.
-- Run once as ACCOUNTADMIN after snowflake_setup.sql has created RAKTRADAR.
use role accountadmin;

-- Repo is public, so no authentication secret is needed for read-only access
create api integration if not exists GITHUB_API
    API_PROVIDER = git_https_api
    API_ALLOWED_PREFIXES = ('https://github.com/unknownsteve7')
    ENABLED = TRUE
    COMMENT = 'Read-only access to the RaktRadar GitHub repo';

create git repository if not exists RAKTRADAR.PUBLIC.RAKTRADAR_REPO
    API_INTEGRATION = GITHUB_API
    ORIGIN = 'https://github.com/unknownsteve7/RaktRadar.git';

-- ==============================================================================
-- Deploy: pull the latest commits, then run a script straight from main
-- ==============================================================================
alter git repository RAKTRADAR.PUBLIC.RAKTRADAR_REPO fetch;

-- List the files in the main branch
-- ls @RAKTRADAR.PUBLIC.RAKTRADAR_REPO/branches/main/;
-- execute immediate from @RAKTRADAR.PUBLIC.RAKTRADAR_REPO/branches/main/snowflake_setup.sql;

