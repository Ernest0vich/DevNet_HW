import netmiko
import os
from os import path
from datetime import datetime
import re
from ipaddress import ip_address

class Cisco:
    def __init__(self, username, password, ip_address, secret):
        param = {
            'ip': ip_address,
            'username': username,
            'password': password,
            'device_type': 'cisco_ios',
            'secret': secret
        }
        try:
            self.handler = netmiko.ConnectHandler(**param)
            self.hostname = self.handler.find_prompt()[:-1]
        except Exception as e:
            print(f"Can't init device handler: {e}")

    def get_hostname(self):
        return self.hostname

    def cli(self, command):
        try:
            response = self.handler.send_command(command)
        except Exception as e:
            print(f"Can't run command '{command}': {e}")
            return None
        return response
        
    def backup_configuration(self, output_dir):
        config = self.cli('show run')
        if config is None:
            return None
    
        if not path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except:
                print("Can't create selected directory for backup storing")
                return None

        else:
            if os.path.isfile(output_dir):
                print('File is passed as target directory')
                return None

        now = datetime.now()
        timestamp = now.strftime('%Y_%m_%d_%H_%M_%S')
        short_filename = f'{self.hostname}_{timestamp}'
        filename = path.join(output_dir, short_filename)

        try:
            with open(filename, 'w') as output_file:
                output_file.write(config)
        except Exception as e:
            print("Can't write to target file: {e}")

    def check_cdp(self):
        cdp_check = self.cli('show cdp neighbors')

        if cdp_check is None:
            return None
        
        if 'CDP is not enabled' in cdp_check:
            return 'CDP is OFF'

        else:
            cdp_neighbors = re.search(r'Total cdp entries displayed : (\d+)', cdp_check)[1]
            return f'CDP is ON, {cdp_neighbors} peers'

    def check_device(self):
        inventory_check = self.cli('show inventory')
        if inventory_check is None:
            return None
        
        device_pid = re.search('PID:\s+(.*?)\s', inventory_check)

        try:
            pid = device_pid[1]
            return pid
        except Exception as e:
            print(f"Can't parse PID from output: {e}")
            return None

    def check_software(self):
        software_check = self.cli('show version')
        if software_check is None:
            return None
        
        regexp_scan = re.search('Software\s*\((.*?)\),\s*Version\s*(.*?)[,\s]', software_check)
        software_version = None
        system_type = None

        try:
            software_version = regexp_scan[2]
        except Exception as e:
            print("Can't parse software version")

        try:
            software_type = regexp_scan[1].lower()
            if 'npe' in software_type:
                system_type = 'NPE'
            else:
                system_type = 'PE'
        except Exception as e:
            print("Can't parse software type")

        data = {
            'software_version': software_version,
            'system_type': system_type
            }

        return data

    def is_ip_valid(self, ip):
        try:
            tmp = ip_address(ip)
        except:
            print(f"IP address {ip} isn't valid")
            return False
        return True

    def configure_ntp(self, ntp_server):
        if not self.is_ip_valid(ntp_server):
            return None

        command_list = [f'ntp server {ntp_server}']

        try:
            self.handler.send_config_set(command_list)
        except Exception as e:
            print(f"Can't configure device: {e}")
        
    def is_available(self, ip):
        if not self.is_ip_valid(ip):
            return None
        
        ping_check = self.cli(f'ping {ip}')

        try:
            success_rate = int(re.search('Success rate is (\d+) percent', ping_check)[1])
        except Exception as e:
            print(f"Can't parse ping output: {e}")
            return None

        if success_rate > 0:
            return True
        return False
        
    def set_timezone(self, tz_name, hours_shift, minutes_shift):
        if int(hours_shift) < -23 or int(hours_shift) > 23:
            print('Invalid hours shift value')
            return None

        if int(minutes_shift) < 0 or int(minutes_shift) > 59:
            print('Invalid minutes shift value')
            return None
        
        command_list = [f'clock timezone {tz_name} {hours_shift} {minutes_shift}']

        try:
            self.handler.send_config_set(command_list)
        except Exception as e:
            print(f"Can't configure device: {e}")

    def verify_ntp_status(self):
        ntp_status = self.cli('show ntp status')
        if 'unsynchronized' in ntp_status:
            return 'Clock not in Sync'
        else:
            return 'Clock in Sync'

        
if __name__ == '__main__':
    pass


        
        
            

    

        
