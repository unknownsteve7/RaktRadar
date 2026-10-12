"""RaktRadar dashboard (Streamlit in Snowflake). Reads ANALYTICS models built by dbt.

The warehouse runtime ships an older Streamlit (< 1.23): no st.column_config or hide_index.
"""
from datetime import timedelta

import streamlit as st
from snowflake.snowpark.context import get_active_session

st.set_page_config(page_title="RaktRadar", layout="wide")
session = get_active_session()

DB = "RAKTRADAR.ANALYTICS"
GROUP_ORDER = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "OH+", "OH-"]


@st.cache_data(ttl=3600)
def query(sql, params=None):
    df = session.sql(sql, params=params).to_pandas()
    df.columns = df.columns.str.lower()
    return df


latest = query(f"select max(run_id) as run_id, max(fetched_at) as fetched_at from {DB}.AGG_DISTRICT_STOCK")
if latest.empty or latest.run_id.iloc[0] is None:
    st.warning("No data in AGG_DISTRICT_STOCK yet. Run the pipeline first.")
    st.stop()
run_id = latest.run_id.iloc[0]
fetched_ist = latest.fetched_at.iloc[0] + timedelta(hours=5, minutes=30)

# ---------------------------------------------------------------- sidebar filters
components = query(f"select distinct component_name from {DB}.AGG_DISTRICT_STOCK order by 1").component_name.tolist()
default_component = "Packed Red Blood Cells" if "Packed Red Blood Cells" in components else components[0]

with st.sidebar:
    st.header("Filters")
    component = st.selectbox("Component", components, index=components.index(default_component))
    groups = st.multiselect("Blood groups", GROUP_ORDER, default=GROUP_ORDER[:8])
    states = query(f"select distinct state_name from {DB}.AGG_DISTRICT_STOCK order by 1").state_name.tolist()
    state = st.selectbox("State", ["All India"] + states)
    st.caption("Units count only blood banks that updated in the last 7 days. "
               "Stale banks are excluded: their 'not available' usually means 'not reported'.")

stock = query(
    f"select * from {DB}.AGG_DISTRICT_STOCK where run_id = ? and component_name = ?",
    params=[run_id, component],
)
stock = stock[stock.blood_group.isin(groups)]
if state != "All India":
    stock = stock[stock.state_name == state]

# ---------------------------------------------------------------- header + KPIs
st.title("🩸 RaktRadar")
st.caption(f"Blood stock across India from eRaktKosh · latest run {run_id} · "
           f"fetched {fetched_ist:%d %b %Y, %H:%M} IST")

banks = query(
    f"""select count(distinct hospital_code) as total,
               count(distinct case when not is_stale then hospital_code end) as reporting
        from {DB}.FCT_STOCK_SNAPSHOT where run_id = ?""",
    params=[run_id],
)
reporting_cells = stock[stock.banks_reporting > 0]
zero_cells = reporting_cells[reporting_cells.units == 0]

c1, c2, c3, c4 = st.columns(4)
c1.metric(f"{component} units", f"{int(stock.units.sum()):,}")
c2.metric("Blood banks reporting", f"{int(banks.reporting.iloc[0]):,} / {int(banks.total.iloc[0]):,}")
c3.metric("District × group cells at 0", f"{len(zero_cells):,} / {len(reporting_cells):,}")
c4.metric("Districts with a group at 0", f"{zero_cells.district_code.nunique():,}")

tab_now, tab_trend, tab_alerts, tab_quality = st.tabs(["Current stock", "Trend", "New shortages", "Data quality"])

# ---------------------------------------------------------------- current stock
with tab_now:
    by_area = "district_name" if state != "All India" else "state_name"
    st.subheader(f"Units by {'district' if state != 'All India' else 'state'}")
    chart = stock.groupby(by_area).units.sum().sort_values(ascending=False)
    st.bar_chart(chart)

    st.subheader("District × blood group")
    st.caption("Lowest stock first. Blank = no reporting bank in that district.")
    grid = (
        reporting_cells.pivot_table(index=["state_name", "district_name"], columns="blood_group",
                                    values="units", aggfunc="sum")
        .reindex(columns=[g for g in GROUP_ORDER if g in groups])
    )
    # Int64 keeps blanks as <NA> without showing decimals (works on older Streamlit runtimes)
    grid = grid.loc[grid.min(axis=1).sort_values().index].astype("Int64")
    st.dataframe(grid, use_container_width=True)

# ---------------------------------------------------------------- trend
with tab_trend:
    st.subheader(f"{component}: daily units by blood group")
    state_filter = "and state_name = ?" if state != "All India" else ""
    params = [component] + ([state] if state != "All India" else [])
    trend = query(
        f"""select snapshot_date, blood_group, sum(units) as units
            from {DB}.AGG_DISTRICT_STOCK
            where component_name = ? {state_filter}
              and run_id in (select max(run_id) from {DB}.AGG_DISTRICT_STOCK group by snapshot_date)
            group by 1, 2 order by 1""",
        params=params,
    )
    trend = trend[trend.blood_group.isin(groups)]
    if trend.snapshot_date.nunique() < 2:
        st.info("Trend lines appear once there are at least two days of data.")
    st.line_chart(trend.pivot_table(index="snapshot_date", columns="blood_group", values="units"))

# ---------------------------------------------------------------- new shortages
with tab_alerts:
    st.subheader("New red-cell shortages")
    st.caption("Packed Red Blood Cells + Whole Blood: every reporting bank in the district is at 0 units "
               "for the group, after having stock in the previous run. Same list as the daily email.")
    alerts = query(f"select * from {DB}.ALERT_CRITICAL_SHORTAGES order by state_name, district_name, blood_group")
    if alerts.empty:
        st.success("No new shortages in the latest run.")
    else:
        st.dataframe(
            alerts[["state_name", "district_name", "blood_group", "previous_units", "reporting_banks"]]
            .set_index("state_name"),
            use_container_width=True,
        )

# ---------------------------------------------------------------- data quality
with tab_quality:
    st.subheader("Stale reporting by state")
    st.caption("Share of blood banks whose last update is more than 7 days old.")
    stale = query(
        f"""select coalesce(d.state_name, f.state_code) as state_name,
                   count(distinct f.hospital_code) as banks,
                   count(distinct case when f.is_stale then f.hospital_code end) as stale_banks
            from {DB}.FCT_STOCK_SNAPSHOT as f
            left join (select distinct state_code, state_name from {DB}.REF_DISTRICTS) as d
                on f.state_code = d.state_code
            where f.run_id = ?
            group by 1""",
        params=[run_id],
    )
    stale["stale_pct"] = (100 * stale.stale_banks / stale.banks).round(1)
    st.bar_chart(stale.set_index("state_name").stale_pct.sort_values(ascending=False))
    st.dataframe(stale.sort_values("stale_pct", ascending=False).set_index("state_name"), use_container_width=True)
