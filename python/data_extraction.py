import os
import csv
import time
import requests
import json
import logging
from datetime import datetime

logging.basicConfig(
    filename='eraktkosh_stock_log.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

MASTER_URL = "https://eraktkosh.mohfw.gov.in/eraktkoshPortal/eraktkosh/master/all"
STOCK_URL = "https://eraktkosh.mohfw.gov.in/eraktkoshPortal/eraktkosh/blood-availability"

COLLECTION_CONFIG = {
    "states": ["Andhra Pradesh"],
    "districts" : ["Alluri Sitharama Raju", "East Godavari"],
    "blood_groups": ['A+Ve', 'A-Ve', 'B+Ve', 'B-Ve'],
    "components": ['Packed Red Blood Cells', '']
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


def fetch_blood_data(state_code, district_code, blood_group_code, component_code, component_name):
    params = {
        "stateCode": state_code,
        "districtId": district_code,
        "componentId": component_code,
        "bloodGroupId": blood_group_code,
    }
    response = requests.get(STOCK_URL, params=params, timeout=15)
    response.raise_for_status()
    entries = response.json()
    fetched_at = datetime.now().isoformat(timespec="seconds")
    
    cleaned = []
    for entry in entries:
        comp_info = entry.get("components", {}).get(component_name, {})
        cleaned.append({
            "fetched_at": fetched_at,
            "state_code": state_code,
            "district_code": district_code,
            "blood_group": blood_group_code,
            "blood_component": component_code,
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
    return cleaned


def run_collection(output_file="blood_data.csv"):
    """
    Main entry point for running the blood availability data collection.
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

    headers = [
        "fetched_at", "state_code", "district_code", "blood_group", 
        "blood_component", "blood_bank", "hospital_code", "address", 
        "contact", "category", "available", "not_available", 
        "last_updated", "bank_type"
    ]
    
    file_exists = os.path.isfile(output_file)
    with open(output_file, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        if not file_exists:
            writer.writeheader()

        total_fetched = 0
        
        states_to_fetch = COLLECTION_CONFIG.get("states") or list(state_dict.keys())
        bgs_to_fetch = COLLECTION_CONFIG.get("blood_groups") or list(blood_dict.keys())
        comps_to_fetch = COLLECTION_CONFIG.get("components") or list(component_dict.keys())
        districts_to_fetch = COLLECTION_CONFIG.get("districts")
        
        for state_name in states_to_fetch:
            state_code = state_dict.get(state_name)
            if not state_code:
                logging.warning(f"State '{state_name}' not found.")
                continue
                
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
                            
                        logging.info(f"Fetching: {state_name} - {district_name} | {bg_name} | {comp_name}")
                        try:
                            results = fetch_blood_data(state_code, district_code, bg_code, comp_code, comp_name)
                            if results:
                                writer.writerows(results)
                                csvfile.flush() 
                                total_fetched += len(results)
                                logging.info(f"Saved {len(results)} rows.")
                            else:
                                logging.info("No data found.")
                        except Exception as e:
                            logging.error(f"Failed to fetch {state_name} - {district_name} | {bg_name} | {comp_name}: {e}")
    logging.info(f"Collection complete. Fetched {total_fetched} total records to {output_file}.")


if __name__ == "__main__":
    run_collection()
