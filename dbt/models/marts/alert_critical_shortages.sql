-- New red-cell shortages: district x blood group where every reporting (non-stale) blood bank
-- now has 0 units of Packed Red Blood Cells and Whole Blood, but those same banks had stock
-- in the previous run. Read by RAKTRADAR.ANALYTICS.SEND_SHORTAGE_EMAIL.

{{ config(materialized='view') }}

with runs as (

    select
        max(run_id) as latest_run_id,
        max(case when run_id < (select max(f.run_id) from {{ ref('fct_stock_snapshot') }} as f) then run_id end)
            as previous_run_id
    from {{ ref('fct_stock_snapshot') }}

),

bank_stock as (

    select
        f.run_id,
        f.hospital_code,
        f.state_code,
        f.district_code,
        f.blood_group,
        sum(f.units) as units,
        boolor_agg(f.is_stale) as is_stale
    from {{ ref('fct_stock_snapshot') }} as f
    inner join runs as r
        on f.run_id in (r.latest_run_id, r.previous_run_id)
    where f.component_name in ('Packed Red Blood Cells', 'Whole Blood')
    group by 1, 2, 3, 4, 5

),

district_change as (

    -- Only banks reporting now count, so a bank going silent never looks like a shortage
    select
        cur.state_code,
        cur.district_code,
        cur.blood_group,
        count(*) as reporting_banks,
        sum(cur.units) as current_units,
        sum(coalesce(prev.units, 0)) as previous_units
    from bank_stock as cur
    inner join runs as r
        on cur.run_id = r.latest_run_id
    left join bank_stock as prev
        on r.previous_run_id = prev.run_id
        and cur.hospital_code = prev.hospital_code
        and cur.blood_group = prev.blood_group
    where not cur.is_stale
    group by 1, 2, 3

)

select
    r.latest_run_id as run_id,
    r.previous_run_id,
    coalesce(d.state_name, c.state_code) as state_name,
    coalesce(d.district_name, c.district_code) as district_name,
    c.state_code,
    c.district_code,
    c.blood_group,
    c.reporting_banks,
    c.previous_units
from district_change as c
cross join runs as r
left join {{ ref('ref_districts') }} as d
    on c.district_code = d.district_code
where c.current_units = 0
    and c.previous_units > 0
