import netmiko
import getpass
import csv
import os
import datetime
import re
import time
import concurrent.futures

DEVICE_LIST = r'\your\path\to\device\list.txt'
CONFIG_PATH = r'\your\path\to\configs'
NTP_SERVER = '192.168.1.30'
CONCURRENT_JOBS = 3

def scan_device(device):
    param = {
            'ip': device['ip'],
            'username': username,
            'password': password,
            'device_type': 'cisco_ios',
            'secret': secret
            }
    ssh_handler = netmiko.ConnectHandler(**param)
    ssh_handler.enable()
    
    # Сохраняем вывод show run
    print('Saving config')
    config = ssh_handler.send_command('show run')
    short_filename = "{}_{}.txt".format(device['hostname'], str(datetime.datetime.now()).replace(':', '-'))
    target_file = os.path.join(CONFIG_PATH, short_filename)
    with open(target_file, 'w') as output_file:
        output_file.write(config)
    
    # Проверяем CDP
    print('Checking CDP')
    cdp_check = ssh_handler.send_command('show cdp')
    if 'CDP is not enabled' in cdp_check:
        cdp = 'CDP is OFF'
    else:
        
        # Проверяем соседей (сразу делим вывод на секции по соседям)
        cdp_neighbors = ssh_handler.send_command('show cdp neighbors detail').split('\n')
        cdp_nei_num = 0
        for line in cdp_neighbors:
            if line == '-------------------------':
                cdp_nei_num += 1
        cdp = f'CDP is ON, {cdp_nei_num} peers'     

    # Проверяем модель устройства
    print('Cheking device model')
    model_check = ssh_handler.send_command('show inventory').split('\n')
    chassis = model_check[1].split(',')[0].split(':')[1].strip()

    # Проверяем версию софта
    print('Checking software')
    sw_check = ssh_handler.send_command('show version | i image').split(' ')[4].strip(r'"').split('.')
    # Если Install mode, вместо mage указывается conf файл, тогда ищем в заголовке версию ПО
    if sw_check[1] == 'conf':
        sw_check = ssh_handler.send_command('show version')
        reg_match = re.findall(r'(?<=Version\s).*?(?=\s)', sw_check)
        image_version = reg_match[0]
        reg_match = re.findall(r'(?<=\().*?(?=\))', sw_check)
        image_type = reg_match[0]
        
    else:
        # Отделяем носитель
        image_type = sw_check[0].split(':')[1]
        
        # Убираем / если есть
        image_type = image_type.strip(r'/')
        # Если Install mode, вместо mage указывается conf файл, тогда ищем в заголовке версию ПО
        if image_type == '':
            sw_check = ssh_handler.send_command('show version')
            reg_match = re.findall(r'(?<=Version\s).*?(?=\s)', sw_check)
        image_version = '.'.join(sw_check[1:-1])
    if 'npe' in image_type:
        image_type ='NPE'
    else:
        image_type = 'PE'
    
    # Настраиваем время
    # Проверяем доступность предполагаемого NTP
    print('Configuring NTP')
    ntp_check = ssh_handler.send_command(f'ping {NTP_SERVER}').split('\n')[-1]
    
    success_rate = int(ntp_check.split(' ')[3])
    if success_rate > 0:
        ntp_available = True
    else:
        ntp_available = False
    # Настраиваем часовой пояс и NTP
    
    command_list = [
        'clock timezone GMT 0 0',
        f'ntp server {NTP_SERVER}'
        ]
    ssh_handler.send_config_set(command_list)
    print('Waiting for NTP to sync...')
    time.sleep(30)
    
    # Проверяем NTP
    ntp_check = ssh_handler.send_command('show ntp status')
    if 'unsynchronized' in ntp_check:
        ntp_sync = 'Clock not in Sync'
    else:
        ntp_sync = 'Clock in Sync'


    
    output_string = f'{device["hostname"]}|{chassis}|{image_version}|{image_type}|{cdp}|{ntp_sync}'
    print(output_string)
    
    
        

if __name__ == '__main__':
    import logging
    logging.basicConfig(filename='test.log', level=logging.DEBUG)
    username = input('Username: ')
    password = getpass.getpass('Password: ')
    secret = getpass.getpass('Secret (leave blank if same as password): ')
    if secret == '':
        secret = password
    devices = []
    with open(DEVICE_LIST, 'r') as input_file:
        reader = csv.DictReader(input_file, delimiter=';')
        for line in reader:
            tmp = {
                'hostname': line['hostname'],
                'ip': line['ip']
                }
            devices.append(tmp)
    # Опрашиваем девайсы
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_JOBS) as executor:
        for i in executor.map(scan_device, devices):
            pass
        
