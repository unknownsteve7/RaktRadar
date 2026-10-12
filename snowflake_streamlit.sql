-- RaktRadar dashboard: Streamlit in Snowflake, deployed from this repo's streamlit/ folder.
-- Owned by the read-only RAKT_REPORTER role. Re-run after pushing app changes
-- (alter git repository ... fetch first): the app copies its files only at CREATE time.
use role accountadmin;

grant usage on schema RAKTRADAR.PUBLIC to role RAKT_REPORTER;
grant read on git repository RAKTRADAR.PUBLIC.RAKTRADAR_REPO to role RAKT_REPORTER;
grant create streamlit on schema RAKTRADAR.ANALYTICS to role RAKT_REPORTER;

use role RAKT_REPORTER;
use warehouse RAKTRADAR_WH;

create or replace streamlit RAKTRADAR.ANALYTICS.RAKTRADAR_DASHBOARD
    from @RAKTRADAR.PUBLIC.RAKTRADAR_REPO/branches/main/streamlit/
    main_file = 'streamlit_app.py'
    query_warehouse = RAKTRADAR_WH
    title = 'RaktRadar'
    comment = 'Blood stock dashboard over RAKTRADAR.ANALYTICS';

alter streamlit RAKTRADAR.ANALYTICS.RAKTRADAR_DASHBOARD add live version from last;

-- Open it: Snowsight > Projects > Streamlit > RaktRadar
