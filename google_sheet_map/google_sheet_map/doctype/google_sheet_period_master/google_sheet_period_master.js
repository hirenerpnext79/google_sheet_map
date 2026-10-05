// Copyright (c) 2026, Google Sheet Map and contributors
// For license information, please see license.txt

frappe.ui.form.on("Google Sheet Period Master", {
	refresh: function(frm) {
		frm.set_df_property('custom_label', 'reqd', frm.doc.keyword === 'Custom' ? 1 : 0);
	},
	keyword: function(frm) {
		if(!frm.doc.keyword) return;
		
		frm.set_df_property('custom_label', 'reqd', frm.doc.keyword === 'Custom' ? 1 : 0);
		
		if (frm.doc.keyword === 'Custom') {
			frm.set_value('from_date', '');
			frm.set_value('to_date', '');
			return;
		}

		let today = frappe.datetime.get_today();
		let from_date = "";
		let to_date = today;
		
		let m = moment();

		switch(frm.doc.keyword) {
			case "Last 365 days":
				from_date = frappe.datetime.add_days(today, -365);
				break;
			case "Last 90 days":
				from_date = frappe.datetime.add_days(today, -90);
				break;
			case "Last 30 days":
				from_date = frappe.datetime.add_days(today, -30);
				break;
			case "Last 7 days":
				from_date = frappe.datetime.add_days(today, -7);
				break;
			case "Previous Quarter":
				let pq_start = m.clone().subtract(1, 'quarter').startOf('quarter');
				let pq_end = m.clone().subtract(1, 'quarter').endOf('quarter');
				from_date = pq_start.format("YYYY-MM-DD");
				to_date = pq_end.format("YYYY-MM-DD");
				break;
			case "Current Quarter":
				let cq_start = m.clone().startOf('quarter');
				let cq_end = m.clone().endOf('quarter');
				from_date = cq_start.format("YYYY-MM-DD");
				to_date = cq_end.format("YYYY-MM-DD");
				break;
			case "Current Month":
				let cm_start = m.clone().startOf('month');
				let cm_end = m.clone().endOf('month');
				from_date = cm_start.format("YYYY-MM-DD");
				to_date = cm_end.format("YYYY-MM-DD");
				break;
			case "Today":
				from_date = today;
				to_date = today;
				break;
			case "Yesterday":
				let yesterday = frappe.datetime.add_days(today, -1);
				from_date = yesterday;
				to_date = yesterday;
				break;
			case "Previous Month":
				let pm_start = m.clone().subtract(1, 'month').startOf('month');
				let pm_end = m.clone().subtract(1, 'month').endOf('month');
				from_date = pm_start.format("YYYY-MM-DD");
				to_date = pm_end.format("YYYY-MM-DD");
				break;
			case "YTD":
				let ytd_start = m.clone().startOf('year');
				from_date = ytd_start.format("YYYY-MM-DD");
				to_date = today;
				break;
		}

		if (from_date && to_date) {
			frm.set_value("from_date", from_date);
			frm.set_value("to_date", to_date);
		}
	}
});
