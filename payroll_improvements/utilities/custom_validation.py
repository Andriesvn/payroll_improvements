from __future__ import unicode_literals
import frappe
from frappe import _

def validate_shift_type(doc, method=None):
    validate_shift_type_break_times(doc)


def validate_shift_type_break_times(doc):
    if doc.break_times != None and len(doc.break_times) > 0:
        for break_time in doc.break_times:
            if break_time.end_time <= break_time.start_time:
                frappe.throw(_("Break Start Time cannot be more than End Time"))
            #Validate Not Overlap
            if len(doc.break_times) > 1:
                validate_overlapping_times(break_time,doc.break_times)

def validate_overlapping_times(break_time, break_times_list):
    for cur_break_time in break_times_list:
        if cur_break_time.name != break_time.name:
            if (cur_break_time.start_time >= break_time.start_time and cur_break_time.start_time < break_time.end_time) or \
               (cur_break_time.end_time > break_time.start_time and cur_break_time.end_time <= break_time.end_time):
               frappe.throw(_("Break times overlap"))