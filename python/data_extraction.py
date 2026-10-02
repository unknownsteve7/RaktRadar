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
    "blood_groups": [],
    "components": []
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
async def fetch_blood_data(state_code, district_code, bg_code, comp_code, comp_name, session, sem):
    url = STOCK_URL
    params = {
        "stateCode": state_code,
        "districtId": district_code,
        "componentId": comp_code,
        "bloodGroupId": bg_code,
    }
    
    async with sem:
        async with session.get(url, params=params, timeout=15) as resp:
            resp.raise_for_status()
            data = await resp.json()

    fetched_at = datetime.now().isoformat(timespec="seconds")
    out = []

    for entry in data or []:
        comp_info = entry.get("components", {}).get(comp_name, {})
        out.append({
            "fetched_at": fetched_at,
            "state_code": state_code,
            "district_code": district_code,
            "blood_group": bg_code,
            "blood_component": comp_code,
            "blood_bank": entry.get("hospitalname"),
            "hospital_code": entry.get("hospitalCode"),
            "address": entry.get("hospitaladd"),
            "contact": entry.get("hospitalcontact"),
            "category": entry.get("hospitalType"),
            "available": comp_info.get("available_WithQty", ""),
            "not_available": comp_info.get("not_available_WithQty", ""),
            "last_updated": entry.get("entrydate"),
            "bank_type": entry.get("type"),
        })
    return out

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
                state_dict, district_dict, blood_dict, component_dict = save_master_data(master_file)
            else:
                state_dict, district_dict, blood_dict, component_dict = load_master_data(master_file)
                logging.info("Loaded master data from cache.")
        else:
            raise FileNotFoundError
    except FileNotFoundError:
        logging.info("Master data not found. Fetching and saving...")
        state_dict, district_dict, blood_dict, component_dict = save_master_data(master_file)
        
    states_to_fetch = COLLECTION_CONFIG.get("states") or list(state_dict.keys())
    bgs_to_fetch = COLLECTION_CONFIG.get("blood_groups") or list(blood_dict.keys())
    comps_to_fetch = COLLECTION_CONFIG.get("components") or list(component_dict.keys())
    districts_to_fetch = COLLECTION_CONFIG.get("districts")
    
    # Generate the cartesian product of all API calls needed
    tasks_params = []
    for state_name in states_to_fetch:
        state_code = state_dict.get(state_name)
        if not state_code: continue
        
        districts = district_dict.get(state_code, {})
        for district_name, district_code in districts.items():
            if districts_to_fetch and district_name not in districts_to_fetch:
                continue
            for bg_name in bgs_to_fetch:
                bg_code = blood_dict.get(bg_name)
                if not bg_code: continue
                    
                for comp_name in comps_to_fetch:
                    comp_code = component_dict.get(comp_name)
                    if not comp_code: continue
                    
                    tasks_params.append((state_code, district_code, bg_code, comp_code, comp_name))
                    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"{output_prefix}_{timestamp}.ndjson.gz"
    
    total_fetched = 0
    # Restrict to 50 concurrent connections
    sem = asyncio.Semaphore(50)
    
    logging.info(f"Generated {len(tasks_params)} API call parameters. Starting async fetch...")
    
    # Process in chunks of 1000 to prevent overwhelming memory with asyncio tasks
    chunk_size = 1000
    
    async with aiohttp.ClientSession() as session:
        # Write to GZIP compressed NDJSON file
        with gzip.open(output_file, 'wb') as f:
            for i in range(0, len(tasks_params), chunk_size):
                chunk = tasks_params[i:i+chunk_size]
                
                tasks = [
                    asyncio.create_task(
                        fetch_blood_data(sc, dc, bgc, cc, cn, session, sem)
                    ) for sc, dc, bgc, cc, cn in chunk
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for res in results:
                    if isinstance(res, Exception):
                        logging.error(f"Task failed with exception after retries: {res}")
                        continue
                        
                    for row in res:
                        # Serialize dict to JSON bytes and write newline
                        f.write(orjson.dumps(row) + b'\n')
                        total_fetched += 1
                        
                logging.info(f"Processed {min(i+chunk_size, len(tasks_params))} / {len(tasks_params)} tasks. Total records extracted: {total_fetched}")

    logging.info(f"Collection complete. Safely extracted {total_fetched} total records to {output_file}.")

if __name__ == "__main__":
    asyncio.run(run_collection())
