-- Daily shortage email: a Snowflake alert at 08:00 UTC calls SEND_SHORTAGE_EMAIL, which emails
-- either the new shortages (ANALYTICS.ALERT_CRITICAL_SHORTAGES) or a "no data today" warning.
-- Run after dbt has built the ANALYTICS models.

-- ==============================================================================
-- 1. Email integration (run manually once, as ACCOUNTADMIN, with your own address).
--    The address must belong to a Snowflake user in this account and be verified
--    (Snowsight > your profile > Email > Verify). Kept out of the repo on purpose.
-- ==============================================================================
-- use role accountadmin;
-- create notification integration if not exists RAKT_EMAIL
--     TYPE = EMAIL
--     ENABLED = TRUE
--     ALLOWED_RECIPIENTS = ('you@example.com')
--     DEFAULT_RECIPIENTS = ('you@example.com')
--     DEFAULT_SUBJECT = 'RaktRadar daily shortage alert';

-- ==============================================================================
-- 2. Privileges for the transformer role, which owns the procedure and the alert
-- ==============================================================================
use role accountadmin;

grant usage on integration RAKT_EMAIL to role RAKT_TRANSFORMER;
grant execute alert on account to role RAKT_TRANSFORMER;
grant create procedure, create alert on schema RAKTRADAR.ANALYTICS to role RAKT_TRANSFORMER;

-- ==============================================================================
-- 3. Procedure + alert
-- ==============================================================================
use role RAKT_TRANSFORMER;
use warehouse RAKTRADAR_WH;
use schema RAKTRADAR.ANALYTICS;

create or replace procedure SEND_SHORTAGE_EMAIL()
returns string
language sql
execute as owner
as
$$
declare
    latest_run string;
    shortage_count integer;
    table_rows string;
    html string;
begin
    select max(run_id) into :latest_run from RAKTRADAR.ANALYTICS.FCT_STOCK_SNAPSHOT;

    -- run_id is the UTC start time of the run (YYYYMMDD_HHMMSS)
    if (latest_run is null or left(latest_run, 8) < to_char(convert_timezone('UTC', current_timestamp()), 'YYYYMMDD')) then
        html := '<h2>RaktRadar: no data loaded today</h2>'
             || '<p>The latest run in Snowflake is <b>' || coalesce(latest_run, 'none') || '</b>. '
             || 'Check the <a href="https://github.com/unknownsteve7/RaktRadar/actions">GitHub Actions pipeline</a>.</p>';
        call SYSTEM$SEND_SNOWFLAKE_NOTIFICATION(
            SNOWFLAKE.NOTIFICATION.TEXT_HTML(:html),
            SNOWFLAKE.NOTIFICATION.INTEGRATION('RAKT_EMAIL'));
        return 'no data today: warning sent';
    end if;

    select
        count(*),
        listagg(
            '<tr><td>' || replace(state_name, '&', '&amp;')
            || '</td><td>' || replace(district_name, '&', '&amp;')
            || '</td><td><b>' || blood_group
            || '</b></td><td align="right">' || previous_units
            || '</td><td align="right">' || reporting_banks || '</td></tr>', '')
            within group (order by state_name, district_name, blood_group)
    into :shortage_count, :table_rows
    from RAKTRADAR.ANALYTICS.ALERT_CRITICAL_SHORTAGES;

    if (shortage_count = 0) then
        return 'no new shortages';
    end if;

    html := '<h2>RaktRadar: ' || shortage_count || ' new red-cell shortage(s)</h2>'
         || '<p>Every reporting blood bank in these districts now has <b>0 units</b> of Packed Red Blood Cells '
         || 'and Whole Blood for the blood group, after having stock in the previous run. '
         || 'Banks that have not updated in 7+ days are excluded. Run ' || latest_run || '.</p>'
         || '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse">'
         || '<tr><th>State</th><th>District</th><th>Group</th><th>Units before</th><th>Banks reporting</th></tr>'
         || table_rows || '</table>';

    call SYSTEM$SEND_SNOWFLAKE_NOTIFICATION(
        SNOWFLAKE.NOTIFICATION.TEXT_HTML(:html),
        SNOWFLAKE.NOTIFICATION.INTEGRATION('RAKT_EMAIL'));
    return shortage_count || ' shortage(s) emailed';
end;
$$;

-- 08:00 UTC (13:30 IST): the pipeline is scheduled at 06:00 UTC, but GitHub cron can lag by up to an hour
create or replace alert SHORTAGE_ALERT
    warehouse = RAKTRADAR_WH
    schedule = 'USING CRON 0 8 * * * UTC'
    if (exists (
        select 1 from RAKTRADAR.ANALYTICS.ALERT_CRITICAL_SHORTAGES
        union all
        select 1
        from (select max(run_id) as latest_run from RAKTRADAR.ANALYTICS.FCT_STOCK_SNAPSHOT)
        where latest_run is null
            or left(latest_run, 8) < to_char(convert_timezone('UTC', current_timestamp()), 'YYYYMMDD')
    ))
    then
        call RAKTRADAR.ANALYTICS.SEND_SHORTAGE_EMAIL();

-- New and replaced alerts start suspended
alter alert SHORTAGE_ALERT resume;

-- ==============================================================================
-- Testing (manual)
-- ==============================================================================
-- select * from RAKTRADAR.ANALYTICS.ALERT_CRITICAL_SHORTAGES;      -- what would be emailed
-- call RAKTRADAR.ANALYTICS.SEND_SHORTAGE_EMAIL();                   -- send now
-- select * from table(information_schema.alert_history()) order by scheduled_time desc;
