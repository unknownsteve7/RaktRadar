1. Beginner SQL (Foundations)

Commands to master: SELECT, DISTINCT, FROM, WHERE, AND / OR / IN / BETWEEN, IS NULL / IS NOT NULL, ORDER BY, LIMIT, COUNT, SUM, AVG, MIN, MAX, GROUP BY, HAVING, COALESCE, CASE WHEN.

Business Questions (RaktRadar)

DA — Filtering & Sorting: "In the latest run, which districts in Andhra Pradesh have 0 units of O- Packed Red Blood Cells even though at least 1 bank is reporting?"

Table: agg_district_stock
SQL skills: WHERE, AND, ORDER BY, LIMIT

DA — Aggregation & HAVING: "Which states have more than 10,000 total Packed Red Blood Cells units on hand in the latest run, sorted highest to lowest?"

Table: agg_district_stock
SQL skills: SUM(), GROUP BY, HAVING, ORDER BY

DA/DE — CASE WHEN & COALESCE: "Categorize every blood bank in fct_stock_snapshot as 'Fresh' (days_since_update <= 7), 'Stale' (> 7), or 'Missing' (last_updated_at IS NULL), and count how many banks fall into each bucket."

Table: fct_stock_snapshot
SQL skills: CASE WHEN, IS NULL, COUNT(DISTINCT ...)
2. Intermediate SQL (Multi-Table & Time-Series)

Commands to master: INNER JOIN, LEFT JOIN, UNION / UNION ALL, WITH (CTEs), subqueries, string functions (TRIM, UPPER, SPLIT_PART, REPLACE), date functions (DATE_TRUNC, DATEDIFF, DAYOFWEEK), QUALIFY (Snowflake).

Business Questions (RaktRadar)

DA — Joins & Grain Awareness: "For the latest run, show the top 10 blood banks by total Whole Blood units, including their blood_bank_name, hospital_category, and district_name."

Tables: fct_stock_snapshot + dim_blood_bank (join on blood_bank_sk) + ref_districts
SQL skills: INNER JOIN / LEFT JOIN, avoiding duplicate rows via blood_bank_sk

DA — CTEs & Conditional Aggregation: "For each state in the latest run, calculate the stale-reporting percentage (banks_stale / total_banks * 100) and rank states from worst to best."

Table: fct_stock_snapshot + ref_districts
SQL skills: WITH CTE, COUNT(DISTINCT CASE WHEN ... END), ROUND()

DA — Weekday / Diagnostic Analysis (Roadmap Item): "Does total national Packed Red Blood Cells stock drop on weekends vs. weekdays?"

Table: agg_district_stock
SQL skills: DAYOFWEEK(snapshot_date), CASE WHEN, AVG() across daily totals

DE — Semi-Structured JSON Parsing (Snowflake): "Take a raw VARIANT row from RAW.BLOOD_STOCK and flatten raw_variant:components into one row per component and blood group."

Table: RAW.BLOOD_STOCK
SQL skills: LATERAL FLATTEN, SPLIT_PART, UNION ALL, TRY_TO_NUMBER (this is literally stg_blood_stock.sql)
3. Advanced SQL (Window Functions, SCD2 & Warehouse Ops)

Commands to master:

Window Functions: ROW_NUMBER(), RANK(), DENSE_RANK(), LAG(), LEAD(), SUM() OVER (PARTITION BY ... ORDER BY ... ROWS BETWEEN ...)
DE Patterns: MERGE INTO, incremental watermarks, SCD Type 2 range joins, COPY INTO, CREATE STAGE / FILE FORMAT / TABLE / VIEW, CREATE ROLE / GRANT, CREATE PROCEDURE / ALERT, EXPLAIN / query profiling.
Business Questions (RaktRadar)

DA — LAG() for Day-over-Day Changes: "For each district and blood group, calculate today's Packed Red Blood Cells units, yesterday's units, and the net change (today - yesterday). Surface the 20 biggest single-day drops."

Table: agg_district_stock
SQL skills: LAG(units) OVER (PARTITION BY district_code, blood_group ORDER BY snapshot_date)

DA — Rolling Averages & Chronic Shortages (Roadmap Item): "Compute a 7-day rolling average of O+ Packed Red Blood Cells per district, and flag districts that stayed at 0 units for 7 consecutive runs."

Table: agg_district_stock
SQL skills: AVG(units) OVER (... ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), SUM(CASE WHEN units = 0 THEN 1 ELSE 0 END) OVER (...)

DE — SCD Type 2 & Range Joins: "Given snap_blood_bank (which has dbt_valid_from and dbt_valid_to), assign version_number and valid_to_run_id per hospital_code, and join fct_stock_snapshot to the exact bank version active at that run_id."

Tables: snap_blood_bank, dim_blood_bank, fct_stock_snapshot
SQL skills: ROW_NUMBER() OVER (...), LEAD(...) OVER (...), inequality range join (see dim_blood_bank.sql & fct_stock_snapshot.sql)

DE — Incremental Upserts (MERGE) & Data Quality Tests: "Write a MERGE statement that updates existing (run_id, hospital_code, component_name, blood_group) rows and inserts new ones, plus a SQL test that returns 0 rows only if every grain key is unique."

Tables: fct_stock_snapshot, dbt/tests/
SQL skills: MERGE INTO ... WHEN MATCHED / WHEN NOT MATCHED, GROUP BY ... HAVING COUNT(*) > 1

DE — Warehouse Security, Loading & Alerting: "Set up least-privilege RBAC (RAKT_LOADER, RAKT_TRANSFORMER, RAKT_REPORTER), load gzipped NDJSON from @RAKT_STAGE with COPY INTO, and schedule a Snowflake ALERT that emails only when alert_critical_shortages has rows."

Files: snowflake_setup.sql, snowflake_alerts.sql
SQL skills: GRANT, PUT, COPY INTO, CREATE PROCEDURE, CREATE ALERT