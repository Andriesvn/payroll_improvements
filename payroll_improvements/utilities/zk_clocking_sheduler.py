from __future__ import unicode_literals
from locale import normalize
import frappe
from frappe import _
from frappe.utils.data import formatdate
import pymysql
import pymysql.cursors
from erpnext.hr.doctype.employee_checkin.employee_checkin import (
	add_log_based_on_employee_field
)

def insert_employee_clockings_from_zk_based_on_employee_field(employee_name,start_date,end_date, employee_fieldname='attendance_device_id'):
    employee = frappe.db.get_values("Employee", {'name': employee_name}, ["name", "employee_name", 'employee_number', employee_fieldname], as_dict=True)
    if employee:
        employee = employee[0]
    else:
        frappe.throw(_("Employee not found. 'name': {}").format(employee_name))
    
    #print('Employee Found:', employee)
    pid = employee.get(employee_fieldname)
    if pid == None or pid.strip() == "":
        if employee.employee_number == None or employee.employee_number.strip() == "":
          frappe.throw(_("Employee {} does not have an {} or an Employee Number assigned.").format(employee_name, employee_fieldname))
        else:
          pid = employee.employee_number
    
     
    clockings = get_employees_clockings_from_zk([pid], start_date,end_date)
    #print('Employee Clockings:',clockings)
    insert_employee_checkins(clockings)

def get_employee_clockings_from_zk(pid,start_date,end_date):
    clockings = get_employees_clockings_from_zk([pid], start_date,end_date)
    #print('Employee Clockings:',clockings)
    return clockings

def insert_employee_checkins(clockings):
    for clocking in clockings:
        #print('Adding Clocking for ', clocking['employee'])
        try:
            add_log_based_on_employee_field(
                clocking['employee'],
                clocking['checktime'],
                clocking['device'],
                clocking['log_type'],
                skip_auto_attendance=0
            )
        except:
            pass

    


def get_employees_clockings_from_zk(pids,start_date,end_date):
    hr_settings = frappe.get_single('HR Settings')
    strPassword = hr_settings.get_password('zk_password')
    #print('password=',strPassword)
    zkdb = pymysql.connect(host=hr_settings.zk_host,user=hr_settings.zk_user,password=strPassword,database=hr_settings.zk_database, cursorclass=pymysql.cursors.DictCursor)
    cursor = zkdb.cursor()

    sql = "select pin, checktime, checktype, sn_name\
            from checkinout\
            where pin in (%s) and checktime>='%s' and checktime<='%s'\
            order by checktime" \
            % (','.join(pids), formatdate(start_date, 'yyyy-mm-dd'),formatdate(end_date, 'yyyy-mm-dd'))
    #print(sql)
    results = None
    try:
        cursor.execute(sql)
        # Fetch all the rows in a list of lists.
        results = cursor.fetchall()
    except:
        frappe.msgprint(_("Unable to fetch data from Zk database. Server ran into a problem."), title=_('Zk Server Problem'))
    # disconnect from server
    zkdb.close()
    if (results != None):
        return normalize_zkdb_clockings(results)
    else:
        return None

def normalize_zkdb_clockings(rows):
    normalized_clockings = []
    for row in rows:
        pin = fix_zk_pin(row['pin'])
        clocking_value = row['checktime']
        check_type = ''
        if row['checktype'] == '0' or row['checktype'] == '2' or row['checktype'] == '4' or row['checktype'] == 'I':
           check_type = 'IN'
        else:
            if row['checktype'] == '1' or row['checktype'] == '3' or row['checktype'] == '5' or row['checktype'] == 'O':
               check_type = 'OUT'
        normalized_clockings.append(
            {
                'employee': pin,
                'checktime': clocking_value,
                'log_type' : check_type,
                'device' : row['sn_name']
            }
        )
    return normalized_clockings

def fix_zk_pin(pin):
    return pin.lstrip('0')

        
