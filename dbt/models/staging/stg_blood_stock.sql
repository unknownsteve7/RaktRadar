-- Grain: one row per run x blood bank x component x blood group.
-- The API packs each component's stock into strings like "A-Ve : 5, AB+Ve : 20";
-- this splits them into rows and parses the unit counts.

with src as (

    select raw_variant as v, _run_id, _loaded_at
    from {{ source('raw', 'blood_stock') }}
    -- Skip rows in the pre-PR #4 shape (one row per group x component)
    where raw_variant:components is not null

),

components as (

    select src.*, c.key::string as component_name, c.value as stock
    from src, lateral flatten(input => v:components) c

),

cells as (

    select components.*, true as is_available, s.value::string as cell
    from components,
        lateral flatten(input => split(coalesce(stock:available_WithQty::string, ''), ',')) s

    union all

    select components.*, false as is_available, s.value::string as cell
    from components,
        lateral flatten(input => split(coalesce(stock:not_available_WithQty::string, ''), ',')) s

),

parsed as (

    select
        _run_id                                    as run_id,
        v:fetched_at::timestamp_ntz                as fetched_at,
        v:state_code::string                       as state_code,
        v:district_code::string                    as district_code,
        v:hospitalCode::string                     as hospital_code,
        trim(v:hospitalname::string)               as blood_bank_name,
        trim(v:hospitalType::string)               as hospital_category,
        trim(v:type::string)                       as bank_type,
        component_name,
        -- Labels vary ("A-Ve", "A -ve", "Oh+VE"), so normalise to A-, AB+, OH-, ...
        replace(upper(replace(split_part(cell, ':', 1), ' ', '')), 'VE', '') as blood_group,
        is_available,
        try_to_number(trim(split_part(cell, ':', 2))) as units,
        try_to_timestamp_ntz(v:entrydate::string)  as last_updated_at,
        _loaded_at
    from cells
    where trim(cell) <> ''

)

-- The portal sometimes lists a group twice for the same component (label variants or
-- separate stock entries with different counts), so sum them into one cell
select
    run_id,
    fetched_at,
    state_code,
    district_code,
    hospital_code,
    blood_bank_name,
    hospital_category,
    bank_type,
    component_name,
    blood_group,
    boolor_agg(is_available)                    as is_available,
    sum(units)                                  as units,
    count(*)                                    as source_entries,
    last_updated_at,
    datediff('day', last_updated_at, fetched_at) as days_since_update,
    -- Stale or missing entrydate: "not available" likely means unreported, not empty
    coalesce(datediff('day', last_updated_at, fetched_at) > {{ var('stale_after_days') }}, true) as is_stale,
    max(_loaded_at)                             as _loaded_at
from parsed
where blood_group <> 'NULL'
group by
    run_id, fetched_at, state_code, district_code, hospital_code, blood_bank_name,
    hospital_category, bank_type, component_name, blood_group, last_updated_at
