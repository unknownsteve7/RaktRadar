-- One row per run x blood bank x component x blood group
select run_id, hospital_code, component_name, blood_group, count(*) as n
from {{ ref('stg_blood_stock') }}
group by 1, 2, 3, 4
having count(*) > 1
