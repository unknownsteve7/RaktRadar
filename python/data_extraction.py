import requests
import json
from datetime import datetime

MASTER_URL = "https://eraktkosh.mohfw.gov.in/eraktkoshPortal/eraktkosh/master/all"
STOCK_URL = "https://eraktkosh.mohfw.gov.in/eraktkoshPortal/eraktkosh/blood-availability"


def fetch_master_all():
    headers = {
        'Content-Type': 'application/json'
    }
    response = requests.post(MASTER_URL, json={"hospitalCode": 100}, headers=headers)
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
    response = requests.get(STOCK_URL, params=params)
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


def run_collection():
    """
    Main entry point for running the blood availability data collection.
    """
    try:
        state_dict, district_dict, blood_dict, component_dict = load_master_data()
        print("Loaded master data from cache.")
    except FileNotFoundError:
        print("Master data not found. Fetching and saving...")
        state_dict, district_dict, blood_dict, component_dict = save_master_data()

    
    print("Ready to run collection pipeline.")


if __name__ == "__main__":
    run_collection()
