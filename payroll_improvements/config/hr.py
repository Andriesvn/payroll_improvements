from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
        {
			"label": _("Attendance"),
			"items": [
				{
					"type": "doctype",
					"name": "Timesheet Period",
                    "label": _("Timesheet Period"),
					"hide_count": True,
					"dependencies": ["Salary Structure Assignment"]
				},
				{
					"type": "doctype",
					"name": "Monthly Timesheet",
                    "label": _("Monthly Timesheet"),
					"hide_count": True,
					"dependencies": ["Timesheet Period"]
				},
			]
		},
    ]