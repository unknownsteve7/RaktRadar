import os
import time
import requests
import json
import logging
from datetime import datetime
import asyncio
# pyrefly: ignore [missing-import]
import aiohttp
import gzip
# pyrefly: ignore [missing-import]
import orjson
# pyrefly: ignore [missing-import]
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

logging.basicConfig(
    filename='eraktkosh_stock_log.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

MASTER_URL = "https://eraktkosh.mohfw.gov.in/eraktkoshPortal/eraktkosh/master/all"
STOCK_URL = "https://eraktkosh.mohfw.gov.in/eraktkoshPortal/eraktkosh/blood-availability"

COLLECTION_CONFIG = {
    "states": [],
    "districts": [],
}

def fetch_master_all():
    headers = {
        'Content-Type': 'application/json'
    }
    response = requests.post(MASTER_URL, json={"hospitalCode": 100}, headers=headers, timeout=15)
    response.raise_for_status()
    payload = response.json()
    
    state_dict = {}
    district_dict = {}
    
    for state in payload.get("statesWithDistricts", []):
        state_code = state["stateCode"]
        state_dict[state["stateName"]] = state_code
        district_dict[state_code] = {
            d["districtName"]: d["districtCode"] for d in state.get("districts", [])
        }
        
    blood_dict = {g["bloodGroupName"]: g["bloodGroupCode"] for g in payload.get("bloodGroups", [])}
    component_dict = {c["componentName"]: c["componentCode"] for c in payload.get("componentList", [])}
    
    return state_dict, district_dict, blood_dict, component_dict

def save_master_data(path="master_data.json"):
    state_dict, district_dict, blood_dict, component_dict = fetch_master_all()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "state_dict": state_dict,
                "district_dict": district_dict,
                "blood_dict": blood_dict,
                "component_dict": component_dict,
            },
            f, ensure_ascii=False, indent=2,
        )
    return state_dict, district_dict, blood_dict, component_dict

def load_master_data(path="master_data.json"):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["state_dict"], data["district_dict"], data["blood_dict"], data["component_dict"]

@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
)
async def fetch_district(state_code, district_code, session, sem):
    # Without componentId/bloodGroupId the API returns every component x blood group
    # per blood bank in one response (verified against the filtered calls)
    params = {"stateCode": state_code, "districtId": district_code}

    async with sem:
        async with session.get(STOCK_URL, params=params, timeout=30) as resp:
            resp.raise_for_status()
            data = await resp.json()

    fetched_at = datetime.now().isoformat(timespec="seconds")
    # Keep each blood bank entry as returned; parsing happens in dbt staging
    return [
        {"fetched_at": fetched_at, "state_code": state_code, "district_code": district_code, **entry}
        for entry in data or []
    ]

async def fetch_all(params_list, session, sem, f):
    tasks = [asyncio.create_task(fetch_district(sc, dc, session, sem)) for sc, dc in params_list]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    failed, total = [], 0
    for params, res in zip(params_list, results, strict=True):
        if isinstance(res, Exception):
            logging.error(f"District {params} failed after retries: {res!r}")
            failed.append(params)
            continue
        for row in res:
            f.write(orjson.dumps(row) + b'\n')
            total += 1
    return total, failed

async def run_collection(output_prefix="blood_data"):
    """
    Main entry point for running the asynchronous blood availability data collection.
    """
    master_file = "master_data.json"
    try:
        if os.path.exists(master_file):
            file_age_days = (time.time() - os.path.getmtime(master_file)) / (60 * 60 * 24)
            if file_age_days > 7:
                logging.info(f"Master data is {file_age_days:.1f} days old. Refreshing...")
                state_dict, district_dict, _, _ = save_master_data(master_file)
            else:
                state_dict, district_dict, _, _ = load_master_data(master_file)
                logging.info("Loaded master data from cache.")
        else:
            raise FileNotFoundError
    except FileNotFoundError:
        logging.info("Master data not found. Fetching and saving...")
        state_dict, district_dict, _, _ = save_master_data(master_file)

    states_to_fetch = COLLECTION_CONFIG.get("states") or list(state_dict.keys())
    districts_to_fetch = COLLECTION_CONFIG.get("districts")

    params_list = []
    for state_name in states_to_fetch:
        state_code = state_dict.get(state_name)
        if not state_code:
            continue

        for district_name, district_code in district_dict.get(state_code, {}).items():
            if districts_to_fetch and district_name not in districts_to_fetch:
                continue
            params_list.append((state_code, district_code))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"{output_prefix}_{timestamp}.ndjson.gz"

    # One call per district (~800), so a low limit is plenty and easy on the portal
    sem = asyncio.Semaphore(10)
    logging.info(f"Fetching {len(params_list)} districts...")

    async with aiohttp.ClientSession() as session:
        with gzip.open(output_file, 'wb') as f:
            total, failed = await fetch_all(params_list, session, sem, f)

            # Second pass for districts that failed all retries (usually transient timeouts)
            if failed:
                logging.info(f"Retrying {len(failed)} failed districts...")
                await asyncio.sleep(30)
                retry_total, failed = await fetch_all(failed, session, sem, f)
                total += retry_total

    if failed:
        logging.error(f"{len(failed)} districts still failed after second pass: {failed}")
    logging.info(f"Collection complete. Extracted {total} blood bank records from "
                 f"{len(params_list) - len(failed)}/{len(params_list)} districts to {output_file}.")

if __name__ == "__main__":
    asyncio.run(run_collection())
