-- Each blood bank has exactly one current version
select hospital_code, count(*) as n
from {{ ref('dim_blood_bank') }}
where is_current
group by 1
having count(*) <> 1
