-- Daily stock history. Grain: run x blood bank x component x blood group.
-- Incremental on _loaded_at, so late backfills of older runs are still picked up.

{{ config(
    materialized='incremental',
    unique_key=['run_id', 'hospital_code', 'component_name', 'blood_group'],
    on_schema_change='append_new_columns'
) }}

with stock as (

    select * from {{ ref('stg_blood_stock') }}
    {% if is_incremental() %}
    where _loaded_at > (select max(_loaded_at) from {{ this }})
    {% endif %}

)

select
    s.run_id,
    s.fetched_at::date                          as snapshot_date,
    s.fetched_at,
    d.blood_bank_sk,
    s.hospital_code,
    s.state_code,
    s.district_code,
    s.component_name,
    s.blood_group,
    s.is_available,
    s.units,
    s.source_entries,
    s.last_updated_at,
    s.days_since_update,
    s.is_stale,
    s._loaded_at
from stock s
left join {{ ref('dim_blood_bank') }} d
    on  d.hospital_code = s.hospital_code
    and s.run_id >= d.valid_from_run_id
    and (d.valid_to_run_id is null or s.run_id < d.valid_to_run_id)
