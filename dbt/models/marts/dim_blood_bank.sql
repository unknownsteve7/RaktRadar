-- SCD2 blood bank dimension. Versions are bounded by run_id rather than dbt_valid_from:
-- the snapshot runs after the load, so its timestamps are later than the fetch they describe.

with versions as (

    select
        *,
        row_number() over (partition by hospital_code order by dbt_valid_from) as version_number
    from {{ ref('snap_blood_bank') }}

)

select
    dbt_scd_id                                  as blood_bank_sk,
    hospital_code,
    blood_bank_name,
    address,
    contact,
    hospital_category,
    bank_type,
    state_code,
    district_code,
    version_number,
    -- The first version also covers runs loaded before the snapshot existed
    case when version_number = 1 then '00000000_000000' else first_seen_run_id end as valid_from_run_id,
    lead(first_seen_run_id) over (partition by hospital_code order by dbt_valid_from) as valid_to_run_id,
    dbt_valid_from                              as valid_from,
    dbt_valid_to                                as valid_to,
    dbt_valid_to is null                        as is_current
from versions
