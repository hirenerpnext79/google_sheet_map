# Copyright (c) 2026, Google Sheet Map and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import requests

class GoogleSheetMap(Document):
	pass

def get_doc_ranges(doc):
	return [row.cell for row in doc.get("google_sheet_cell_settings") if row.cell]

# ---------------------------------------------------------
# GOOGLE DRIVE API METHODS
# ---------------------------------------------------------
def get_google_access_token():
	try:
		return frappe.get_doc('Google Drive').get_access_token()
	except Exception as e:
		frappe.throw(f'Error fetching Google Access Token. Please check Google Drive integration: {str(e)}')

def get_google_headers():
	return {
		"Authorization": f"Bearer {get_google_access_token()}",
		"Accept": "application/json",
		"Content-Type": "application/json"
	}

def get_sheet_name(doc, headers):
	sheet_url = f"https://sheets.googleapis.com/v4/spreadsheets/{doc.google_sheet_id}"
	res = requests.get(sheet_url, headers=headers)
	
	if res.status_code != 200:
		frappe.throw(f"Error accessing Google Sheet: {res.text}")
		
	sheet_info = res.json()
	
	if not doc.google_sheet_tab_id:
		if sheet_info.get("sheets"):
			return sheet_info.get("sheets")[0].get("properties", {}).get("title")
		frappe.throw("No sheets found in the Google Document.")

	for sheet in sheet_info.get("sheets", []):
		if str(sheet.get("properties", {}).get("sheetId")) == str(doc.google_sheet_tab_id):
			return sheet.get("properties", {}).get("title")
			
	frappe.throw(f"Could not find Sheet with Tab ID {doc.google_sheet_tab_id}")

def fetch_google_sheet_data(doc, headers, sheet_name, ranges):
	query_params = [f"ranges={sheet_name}!{r}" for r in ranges]
	batch_get_url = f"https://sheets.googleapis.com/v4/spreadsheets/{doc.google_sheet_id}/values:batchGet?{'&'.join(query_params)}"
	
	res = requests.get(batch_get_url, headers=headers)
	if res.status_code != 200:
		frappe.throw(f"Error reading from Google Sheet: {res.text}")
		
	return res.json().get("valueRanges", [])

def map_data_to_doc(doc, value_ranges):
	range_value_map = {}
	for vr in value_ranges:
		range_name = vr.get("range", "").split("!")[-1]
		values = vr.get("values", [])
		range_value_map[range_name] = values[0][0] if values and values[0] else ""
			
	for row in doc.get("google_sheet_cell_settings"):
		if row.cell in range_value_map:
			row.value = range_value_map[row.cell]
			
	doc.save()

def build_update_payload(doc, sheet_name):
	data = [{"range": f"{sheet_name}!{row.cell}", "values": [[row.value]]} 
	        for row in doc.get("google_sheet_cell_settings") if row.cell and row.value]
	return data

def update_google_sheet_data(doc, headers, data):
	url = f"https://sheets.googleapis.com/v4/spreadsheets/{doc.google_sheet_id}/values:batchUpdate"
	payload = {"valueInputOption": "USER_ENTERED", "data": data}
	
	res = requests.post(url, headers=headers, json=payload)
	if res.status_code != 200:
		frappe.throw(f"Error writing to Google Sheet: {res.text}")

# ---------------------------------------------------------
# APPS SCRIPT WEB APP METHODS
# ---------------------------------------------------------
def read_via_web_app(doc, url, ranges):
	payload = {
		"action": "read",
		"sheet_id": doc.google_sheet_id,
		"tab_id": doc.google_sheet_tab_id,
		"ranges": ranges
	}
	
	try:
		res = requests.post(url, json=payload)
		res.raise_for_status()
	except Exception as e:
		frappe.throw(f"Error communicating with Google Web App: {str(e)}")
		
	response_data = res.json()
	if response_data.get("status") == "error":
		frappe.throw(f"Error from Google Web App: {response_data.get('message')}")
		
	data = response_data.get("data", {})
	
	for row in doc.get("google_sheet_cell_settings"):
		if row.cell in data:
			row.value = data[row.cell]
			
	doc.save()

def write_via_web_app(doc, url):
	data = [{"cell": row.cell, "value": row.value} 
	        for row in doc.get("google_sheet_cell_settings") if row.cell]
	        
	if not data:
		return
		
	payload = {
		"action": "write",
		"sheet_id": doc.google_sheet_id,
		"tab_id": doc.google_sheet_tab_id,
		"data": data
	}
	
	try:
		res = requests.post(url, json=payload, allow_redirects=True)
		res.raise_for_status()
	except Exception as e:
		frappe.throw(f"Error communicating with Google Web App: {str(e)}")
		
	response_data = res.json()
	if response_data.get("status") == "error":
		frappe.throw(f"Error from Google Web App: {response_data.get('message')}")

# ---------------------------------------------------------
# WHITELISTED ENTRY POINTS
# ---------------------------------------------------------
@frappe.whitelist()
def read_from_google_sheet(docname):
	doc = frappe.get_doc("Google Sheet Map", docname)
	ranges = get_doc_ranges(doc)

	if not ranges:
		return
		
	deployment_id = doc.get("app_script_deployment_id")
	
	if deployment_id:
		script_url = f"https://script.google.com/macros/s/{deployment_id}/exec"
		read_via_web_app(doc, script_url, ranges)
	else:
		headers = get_google_headers()
		sheet_name = get_sheet_name(doc, headers)
		value_ranges = fetch_google_sheet_data(doc, headers, sheet_name, ranges)
		map_data_to_doc(doc, value_ranges)
		
	return "Success"

@frappe.whitelist()
def write_to_google_sheet(docname):
	doc = frappe.get_doc("Google Sheet Map", docname)
	
	deployment_id = doc.get("app_script_deployment_id")
	
	if deployment_id:
		script_url = f"https://script.google.com/macros/s/{deployment_id}/exec"
		write_via_web_app(doc, script_url)
	else:
		headers = get_google_headers()
		sheet_name = get_sheet_name(doc, headers)
		data = build_update_payload(doc, sheet_name)
		if not data:
			return
		update_google_sheet_data(doc, headers, data)
		
	return "Success"
