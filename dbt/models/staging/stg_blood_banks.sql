-- One row per blood bank, as of the latest run. Feeds the snap_blood_bank snapshot.

select
    raw_variant:hospitalCode::string           as hospital_code,
    trim(raw_variant:hospitalname::string)     as blood_bank_name,
    trim(raw_variant:hospitaladd::string)      as address,
    trim(raw_variant:hospitalcontact::string)  as contact,
    trim(raw_variant:hospitalType::string)     as hospital_category,
    trim(raw_variant:type::string)             as bank_type,
    raw_variant:state_code::string             as state_code,
    raw_variant:district_code::string          as district_code,
    -- Not a check column, so the snapshot keeps the run where each version first appeared
    _run_id                                    as first_seen_run_id
from {{ source('raw', 'blood_stock') }}
where raw_variant:components is not null
qualify row_number() over (partition by hospital_code order by _loaded_at desc) = 1
