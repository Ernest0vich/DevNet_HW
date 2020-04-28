import yaml
import time
import concurrent.futures
import configparser
from os import path
import sys
from cisco_handler import Cisco

def is_list_valid(to_check):
    for i in to_check:
        if 'ip' not in i.keys() or 'username' not in i.keys() or \
           'password' not in i.keys() or 'secret' not in i.keys():
            return False
    return True

def scan_device(param):
    device_handler = Cisco(
        param['username'],
        param['password'],
        param['ip'],
        param['secret'])

    hostname = device_handler.get_hostname()

    device_handler.backup_configuration(param['backup'])

    cdp = device_handler.check_cdp()

    hw = device_handler.check_device()

    sw_data = device_handler.check_software()
    sw_ver = sw_data['software_version']
    sys_type = sw_data['system_type']

    device_handler.set_timezone(param['tz'], param['h_shift'], param['m_shift'])

    if device_handler.is_available(param['ntp']):
        device_handler.configure_ntp(param['ntp'])
        time.sleep(30)

    ntp_sync = device_handler.verify_ntp_status()
        
    print(f'{hostname}|{hw}|{sw_ver}|{sys_type}|{cdp}|{ntp_sync}')


if __name__ == '__main__':
    config = configparser.ConfigParser()

    try:
        config.read('default.conf')
        devices_file = config.get('PATH', 'devices_file', fallback = None)
        backup_dir = config.get('PATH', 'backup_dir', fallback = None)
        ntp_server = config.get('PARAMETERS', 'ntp_server', fallback = None)
        timezone = config.get('PARAMETERS', 'timezone_name', fallback = 'UTC')
        hours_shift = config.get('PARAMETERS', 'hours_shift', fallback = '0')
        minutes_shift = config.get('PARAMETERS', 'minutes_shift', fallback = '0')
        concurrent_jobs = int(config.get(
            'PARAMETERS', 'concurrent_jobs', fallback = 1))
    except Exception as e:
        print(f"Can't load configuration: {e}")

    if devices_file is None:
        print('No device file is configured')
        sys.exit(1)
    try:
        devices = []

        with open(devices_file, 'r') as file:
            devices = yaml.safe_load(file)
        print(devices)
        if not is_list_valid(devices):
            print('Devices list file is not valid')
            sys.exit(1)
    except Exception as e:
        print(f"Can't read devices file: {e}")

    for i in devices:
        i['backup'] = backup_dir
        i['ntp'] = ntp_server
        i['tz'] = timezone
        i['h_shift'] = hours_shift
        i['m_shift'] = minutes_shift
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_jobs) as executor:
        for i in executor.map(scan_device, devices):
            pass
        
    

