# Copyright (c) 2026, Google Sheet Map and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json
import requests

class GoogleSheetMap(Document):
	def before_save(self):
		for row in self.get("google_sheet_cell_settings"):
			if row.query:
				query = row.query
				if row.period and row.date_field:
					period_doc = frappe.get_doc("Google Sheet Period Master", row.period)
					if period_doc.from_date and period_doc.to_date:
						if "where" in query.lower():
							query += f" AND {row.date_field} BETWEEN '{period_doc.from_date}' AND '{period_doc.to_date}'"
						else:
							query += f" WHERE {row.date_field} BETWEEN '{period_doc.from_date}' AND '{period_doc.to_date}'"
				try:
					row.final_query = query
					result = frappe.db.sql(query, as_dict=True)
					if result:
						if row.output_type == 'Number':
							if len(result) == 1 and len(result[0]) == 1:
								val = list(result[0].values())[0]
								row.value = val if val is not None else ""
							else:
								row.value = json.dumps(result, default=str)
							row.value_list = ""
						elif row.output_type == 'List':
							row.value_list = json.dumps(result, default=str)
							row.value = ""
						else:
							# Default behavior just in case
							row.value = json.dumps(result, default=str)
					else:
						row.value = ""
						row.value_list = ""
				except Exception as e:
					frappe.throw(f"Error executing query in row {row.idx}: {str(e)}")

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

def handle_google_api_error(res, action_message):
	if res.status_code != 200:
		error_msg = res.text
		try:
			error_data = res.json()
			if "error" in error_data and "message" in error_data["error"]:
				error_msg = error_data["error"]["message"]
				if error_data["error"].get("status") == "PERMISSION_DENIED":
					error_msg = f"Permission Denied: Service account does not have permission to access this sheet. ({error_msg})"
		except Exception:
			pass
		frappe.throw(f"{error_msg}", title="Google Sheet Sync Error")

def get_sheet_name(doc, headers):
	sheet_url = f"https://sheets.googleapis.com/v4/spreadsheets/{doc.google_sheet_id}"
	res = requests.get(sheet_url, headers=headers)
	
	handle_google_api_error(res, "Error accessing Google Sheet")
		
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
	handle_google_api_error(res, "Error reading from Google Sheet")
		
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

def get_values_for_row(row):
	if row.output_type == 'List' and row.value_list:
		try:
			list_data = json.loads(row.value_list)
			if list_data and isinstance(list_data, list) and len(list_data) > 0:
				headers = list(list_data[0].keys())
				if row.list_type == 'Vertical':
					values = [headers]
					for item in list_data:
						values.append([item.get(h, '') for h in headers])
					return values
				elif row.list_type == 'Horizontal':
					values = []
					for h in headers:
						row_vals = [h]
						for item in list_data:
							row_vals.append(item.get(h, ''))
						values.append(row_vals)
					return values
		except Exception:
			pass
	return [[row.value]] if row.value else []

def build_update_payload(doc, sheet_name):
	data = []
	for row in doc.get("google_sheet_cell_settings"):
		if not row.cell:
			continue
		values = get_values_for_row(row)
		if values:
			data.append({"range": f"{sheet_name}!{row.cell}", "values": values})
	return data

def update_google_sheet_data(doc, headers, data):
	url = f"https://sheets.googleapis.com/v4/spreadsheets/{doc.google_sheet_id}/values:batchUpdate"
	payload = {"valueInputOption": "USER_ENTERED", "data": data}
	
	res = requests.post(url, headers=headers, json=payload)
	handle_google_api_error(res, "Error writing to Google Sheet")

# ---------------------------------------------------------
# WHITELISTED ENTRY POINTS
# ---------------------------------------------------------
@frappe.whitelist()
def read_from_google_sheet(docname):
	doc = frappe.get_doc("Google Sheet Map", docname)
	ranges = get_doc_ranges(doc)

	if not ranges:
		return
		
	headers = get_google_headers()
	sheet_name = get_sheet_name(doc, headers)
	value_ranges = fetch_google_sheet_data(doc, headers, sheet_name, ranges)
	map_data_to_doc(doc, value_ranges)
		
	return "Success"

@frappe.whitelist()
def write_to_google_sheet(docname):
	doc = frappe.get_doc("Google Sheet Map", docname)
	
	headers = get_google_headers()
	sheet_name = get_sheet_name(doc, headers)
	data = build_update_payload(doc, sheet_name)
	if not data:
		return
	update_google_sheet_data(doc, headers, data)
		
	return "Success"
