--In the latest run, which districts in Andhra Pradesh 
--have 0 units of O- Packed Red Blood Cells even though 
--at least 1 bank is reporting?

select
    district_name,
    units,
    banks_reporting,
    banks_stale,
    snapshot_date
from analytics.agg_district_stock
where run_id = (select max(run_id) from analytics.agg_district_stock)
  and state_name = 'Andhra Pradesh'
  and blood_group = 'O-'
  and component_name = 'Packed Red Blood Cells'
  and units = 0
  and banks_reporting >= 1
order by banks_reporting desc
limit 10;

--Which states have more than 10,000 total Packed Red Blood Cells 
--units on hand in the latest run, sorted highest to lowest?

SELECT 
STATE_NAME,SUM(UNITS) as total_units
from ANALYTICS.AGG_DISTRICT_STOCK
WHERE COMPONENT_NAME = 'Packed Red Blood Cells' and RUN_ID = (select max(RUN_ID)
from ANALYTICS.AGG_DISTRICT_STOCK)
GROUP BY STATE_NAME
HAVING total_units > 10000 
ORDER BY total_units DESC  ;


-- Categorize every blood bank in fct_stock_snapshot as 'Fresh'
-- (days_since_update <= 7), 'Stale' (> 7), or 'Missing' 
--(last_updated_at IS NULL), and count how many banks fall into each bucket.

WITH bank_status as
(
    SELECT
    CASE 
        WHEN DAYS_SINCE_UPDATE <= 7 THEN 'Fresh'
        WHEN DAYS_SINCE_UPDATE > 7 THEN 'Stale'
        ELSE  'Missing'
    END as status
    FROM FCT_STOCK_SNAPSHOT
)
SELECT status, count(*) FROM bank_status
group by status ORDER BY count(*) desc;



-- For the latest run, show the top 
--10 blood banks by total Whole 
--Blood units, including their 
--blood_bank_name, hospital_category,
-- and district_name
select b.blood_bank_name,b.hospital_code,b.hospital_category, d.district_name, f.blood_group, sum(f.units) as Total_whole_blood_units from analytics.dim_blood_bank b left join analytics.ref_districts d on b.district_code = d.district_code
left join analytics.fct_stock_snapshot f 
on b.hospital_code = f.hospital_code 
where b.bank_type = 'Blood Bank' and f.component_name = 'Whole Blood' and f.run_id = (select max(run_id) from analytics.fct_stock_snapshot)
group by b.blood_bank_name,b.hospital_category,b.hospital_code, d.district_name, f.blood_group order by Total_whole_blood_units desc limit 10;