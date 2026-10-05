// Copyright (c) 2026, Google Sheet Map and contributors
// For license information, please see license.txt

frappe.ui.form.on("Google Sheet Map", {
	refresh(frm) {
		frm.add_custom_button(__("Read"), function() {
			frappe.call({
				method: "google_sheet_map.google_sheet_map.doctype.google_sheet_map.google_sheet_map.read_from_google_sheet",
				args: {
					docname: frm.doc.name
				},
				freeze: true,
				freeze_message: __("Reading from Google Sheet..."),
				callback: function(r) {
					if (!r.exc) {
						frm.reload_doc();
						frappe.show_alert({message: __("Data fetched successfully"), indicator: "green"});
					}
				}
			});
		});

		frm.add_custom_button(__("Write"), function() {
			frappe.call({
				method: "google_sheet_map.google_sheet_map.doctype.google_sheet_map.google_sheet_map.write_to_google_sheet",
				args: {
					docname: frm.doc.name
				},
				freeze: true,
				freeze_message: __("Writing to Google Sheet..."),
				callback: function(r) {
					if (!r.exc) {
						frappe.show_alert({message: __("Data written successfully"), indicator: "green"});
					}
				}
			});
		});

	},
});
