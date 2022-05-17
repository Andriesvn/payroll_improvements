from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils.data import formatdate
from frappe.utils import cint
import pymysql
import pymysql.cursors

def insert_employee_clockings_from_zk_based_on_employee_field(employee_name,start_date,end_date, employee_fieldname='attendance_device_id'):
    employee = frappe.db.get_values("Employee", {'name': employee_name}, ["name", "employee_name", 'employee_number', employee_fieldname], as_dict=True)
    if employee:
        employee = employee[0]
    else:
        frappe.throw(_("Employee not found. 'name': {}").format(employee_name))
    
    pid = employee.get(employee_fieldname)
    if pid == None or pid.strip() == "":
        if employee.employee_number == None or employee.employee_number.strip() == "":
          frappe.throw(_("Employee {} does not have an {} or an Employee Number assigned.").format(employee_name, employee_fieldname))
        else:
          pid = employee.employee_number
    
     
    clockings = get_employees_clockings_from_zk([pid], start_date,end_date)
    insert_employee_checkins(clockings)

def get_employee_clockings_from_zk(pid,start_date,end_date):
    clockings = get_employees_clockings_from_zk([pid], start_date,end_date)
    return clockings

def insert_employee_checkins(clockings, update_last_sync=False, last_sync_id=0):
    max_sync_id = 0
    #make sure last sync is a number not a string
    if last_sync_id != None and isinstance(last_sync_id, str):
        if last_sync_id.isnumeric():
           try:
               last_sync_id = int(last_sync_id)
           except:
               last_sync_id = 0
        else:
            last_sync_id = 0
    

    for clocking in clockings:
        if clocking['id'] > max_sync_id:
            max_sync_id = clocking['id']
        #extra bit of protection to try to prevent duplicates
        if clocking['id'] > last_sync_id:
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
    if update_last_sync and max_sync_id > last_sync_id:
        frappe.db.set_single_value('HR Settings', 'last_sync_id', max_sync_id)


def get_employees_clockings_from_zk(pids,start_date,end_date):
    hr_settings = frappe.get_single('HR Settings')
    strPassword = hr_settings.get_password('zk_password')
    zkdb = pymysql.connect(host=hr_settings.zk_host,user=hr_settings.zk_user,password=strPassword,database=hr_settings.zk_database, cursorclass=pymysql.cursors.DictCursor)
    cursor = zkdb.cursor()

    sql = "select id, emp_code `pin`, punch_time `checktime`, punch_state `checktype`, terminal_sn `sn_name` From iclock_transaction\
           where emp_code in (%s) and punch_time>='%s' and punch_time<='%s'\
           order by punch_time" \
            % (','.join(pids), formatdate(start_date, 'yyyy-mm-dd'),formatdate(end_date, 'yyyy-mm-dd'))
    results = None
    try:
        cursor.execute(sql)
        # Fetch all the rows in a list of lists.
        results = cursor.fetchall()
    except:
        frappe.msgprint(_("Unable to fetch data from Zk database. Server ran into a problem."), title=_('Zk Server Problem'))
    
    finally:
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
                'id': row['id'],
                'employee': pin,
                'checktime': clocking_value,
                'log_type' : check_type,
                'device' : row['sn_name']
            }
        )
    return normalized_clockings

def fix_zk_pin(pin):
    return pin.lstrip('0')

def import_employee_clockings_since_last_sync():
    # Get a list of employees 
    employees = get_list_of_employee_pins()
    if employees == None or len(employees) == 0:
        return
    clockings ,last_sync_id = get_employees_clockings_from_zk_since_last_sync(employees)
    if clockings == None or len(clockings) == 0:
        return
    insert_employee_checkins(clockings, update_last_sync=True, last_sync_id=last_sync_id)



def get_list_of_employee_pins():
    employees = []
    employee_list = frappe.get_all('Employee', 'attendance_device_id', {'status': 'Active','attendance_device_id':("!=", "")}, as_list=True) 
    for employee in employee_list:
        employees.append(employee[0])
    return employees

def get_employees_clockings_from_zk_since_last_sync(pids):
    hr_settings = frappe.get_single('HR Settings')
    
    # Return if no settings defined
    if hr_settings.zk_host == None or hr_settings.zk_host.strip() == "" \
        or hr_settings.zk_database == None or hr_settings.zk_database.strip() == "" \
        or hr_settings.zk_user == None or hr_settings.zk_user.strip() == "":
        return None, None

    strPassword = hr_settings.get_password('zk_password')
    if strPassword == None or strPassword.strip() == "":
         frappe.throw(_("ZK Password not Set"))

    if hr_settings.last_sync_id == None or hr_settings.last_sync_id.strip() == "" or hr_settings.last_sync_id.strip() == "0" or hr_settings.last_sync_id == 0:
        hr_settings.last_sync_id = get_lowest_sync_id_from_date(hr_settings, strPassword)
        if hr_settings.last_sync_id == None:
            frappe.throw(_("Could not Determine the Sync ID to use"))
    
    zkdb = pymysql.connect(host=hr_settings.zk_host,user=hr_settings.zk_user,password=strPassword,database=hr_settings.zk_database, cursorclass=pymysql.cursors.DictCursor)
    cursor = zkdb.cursor()

    sql = "select id, emp_code `pin`, punch_time `checktime`, punch_state `checktype`, terminal_sn `sn_name` From iclock_transaction\
           where id > %s and emp_code in (%s)\
           order by punch_time" \
           % (hr_settings.last_sync_id,','.join(pids),)
    results = None
    try:
        cursor.execute(sql)
        # Fetch all the rows in a list of lists.
        results = cursor.fetchall()
    except:
        frappe.msgprint(_("Unable to fetch data from Zk database. Server ran into a problem."), title=_('Zk Server Problem'))
    
    finally:
        # disconnect from server
        zkdb.close()
    
    if (results != None):
        return normalize_zkdb_clockings(results), hr_settings.last_sync_id
    else:
        return None, None

def get_lowest_sync_id_from_date(hr_settings, strPassword):
    zkdb = pymysql.connect(host=hr_settings.zk_host,user=hr_settings.zk_user,password=strPassword,database=hr_settings.zk_database, cursorclass=pymysql.cursors.DictCursor)
    cursor = zkdb.cursor()

    sql = "select Max(id)\
            from iclock_transaction\
            where punch_time < '%s' \
            " \
            % (formatdate(hr_settings.import_after_date, 'yyyy-mm-dd'))
    results = None
    try:
        cursor.execute(sql)
        # Fetch all the rows in a list of lists.
        results = cursor.fetchall()
    except:
        frappe.msgprint(_("Unable to fetch data from Zk database. Server ran into a problem."), title=_('Zk Server Problem'))
    
    finally:
        # disconnect from server
        zkdb.close()
    if (results != None):
        return results[0]['Max(id)']
    else:
        return None
# Moved Here To Rework Manual Clockings
def add_log_based_on_employee_field(employee_field_value, timestamp, device_id=None, log_type=None, skip_auto_attendance=0, employee_fieldname='attendance_device_id'):
	"""Finds the relevant Employee using the employee field value and creates a Employee Checkin.

	:param employee_field_value: The value to look for in employee field.
	:param timestamp: The timestamp of the Log. Currently expected in the following format as string: '2019-05-08 10:48:08.000000'
	:param device_id: (optional)Location / Device ID. A short string is expected.
	:param log_type: (optional)Direction of the Punch if available (IN/OUT).
	:param skip_auto_attendance: (optional)Skip auto attendance field will be set for this log(0/1).
	:param employee_fieldname: (Default: attendance_device_id)Name of the field in Employee DocType based on which employee lookup will happen.
	"""

	if not employee_field_value or not timestamp:
		frappe.throw(_("'employee_field_value' and 'timestamp' are required."))

	employee = frappe.db.get_values("Employee", {employee_fieldname: employee_field_value}, ["name", "employee_name", employee_fieldname], as_dict=True)
	if employee:
		employee = employee[0]
	else:
		frappe.throw(_("No Employee found for the given employee field value. '{}': {}").format(employee_fieldname,employee_field_value))

	doc = frappe.new_doc("Employee Checkin")
	doc.employee = employee.name
	doc.employee_name = employee.employee_name
	doc.is_manual = 0
	doc.time = timestamp
	doc.device_id = device_id
	doc.log_type = log_type

	if cint(skip_auto_attendance) == 1: doc.skip_auto_attendance = '1'
	doc.insert()

	return doc



        
