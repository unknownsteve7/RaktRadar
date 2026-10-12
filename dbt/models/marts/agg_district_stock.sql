-- Dashboard-ready rollup. Grain: run x district x component x blood group.
-- Units count only banks that are reporting (not stale); stale banks are counted separately.

{{ config(
    materialized='incremental',
    unique_key=['run_id', 'district_code', 'component_name', 'blood_group'],
    on_schema_change='append_new_columns'
) }}

select
    f.run_id,
    f.snapshot_date,
    max(f.fetched_at) as fetched_at,
    f.state_code,
    coalesce(d.state_name, f.state_code) as state_name,
    f.district_code,
    coalesce(d.district_name, f.district_code) as district_name,
    f.component_name,
    f.blood_group,
    sum(case when not f.is_stale then f.units else 0 end) as units,
    count(distinct case when not f.is_stale then f.hospital_code end) as banks_reporting,
    count(distinct case when not f.is_stale and f.units > 0 then f.hospital_code end) as banks_with_stock,
    count(distinct case when f.is_stale then f.hospital_code end) as banks_stale,
    max(f._loaded_at) as _loaded_at
from {{ ref('fct_stock_snapshot') }} as f
left join {{ ref('ref_districts') }} as d
    on f.district_code = d.district_code
{% if is_incremental() %}
where f._loaded_at > (select max(existing._loaded_at) from {{ this }} as existing)
{% endif %}
group by f.run_id, f.snapshot_date, f.state_code, d.state_name, f.district_code, d.district_name,
    f.component_name, f.blood_group
