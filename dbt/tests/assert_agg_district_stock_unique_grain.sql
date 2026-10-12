-- One row per run x district x component x blood group
select run_id, district_code, component_name, blood_group, count(*) as n
from {{ ref('agg_district_stock') }}
group by 1, 2, 3, 4
having count(*) > 1
