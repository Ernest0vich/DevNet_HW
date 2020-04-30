from nornir import InitNornir
from nornir.plugins.tasks import networking
from nornir.plugins.functions.text import print_result
import re


def find_interface(mac_table):
    r = re.search('.*?\s+(\d+).*((Eth|Fa|Gi|Te|Fo|Hu)\d+(/\d+)+)', mac_table)
    if r is None:
        return None, None
    vlan = r[1]
    interface = r[2]
    return vlan, interface


def is_access(int_config):
    if 'switchport mode trunk' not in int_config:
        return True
    return False


def find_int_mac(int):
    r = re.search('(([0-9a-f]{4}\.){2}[0-9a-f]{4})', int)
    if r is None:
        return None
    return r[0]


def get_svi(int_br):
    r = re.findall('Vlan\d+', int_br)
    if r is None:
        return None
    return r


if __name__ == '__main__':
    vlan = None
    host_interface = None
    host_switch = None
    is_found = False

    mac = input('Enter MAC to search: ')
    nr = InitNornir(config_file="config.yaml")
    hosts = nr.filter(type='switch')

    result = hosts.run(task=networking.netmiko_send_command,
                       command_string=f'show mac address-table address {mac}')

    for device, response in result.items():
        print(f'Checking results at {device}')
        tmp_vlan, interface = find_interface(response[0].result)
        # Сохраняем номер vlan где светится мак на случай если это svi
        if tmp_vlan is not None:
            print(f'Vlan id {tmp_vlan}')
            vlan = tmp_vlan
        if interface is None:
            print(f'MAC was not found at {device}')
            continue

        target = nr.filter(filter_func=lambda h: h.name == device)
        interface_result = target.run(task=networking.netmiko_send_command,
                                      command_string=f'show run int {interface}')
        if is_access(interface_result[device][0].result):
            host_interface = interface
            host_switch = device
            is_found = True
            break

    # Если мак хоть где-то засветился, мы знаем Vlan и ищем на SVI
    if not is_found and vlan is not None:
        for device, _ in result.items():
            target = nr.filter(filter_func=lambda h: h.name == device)
            check_interfaces = target.run(task=networking.netmiko_send_command,
                                          command_string=f'show int vlan {vlan}')
            print_result(check_interfaces)
            int_mac = find_int_mac(check_interfaces[device][0].result)

            if int_mac is None:
                continue

            if int_mac == mac:
                is_found = True
                host_switch = device
                host_interface = f'Vlan{vlan}'
                break

    # Если мак не светился и номер vlan ам неизвестен, начинаем обходить все svi на всех коммутаторах
    elif not is_found and vlan is None:
        print('Checking all SVI at every switch')
        ip_int = hosts.run(task=networking.netmiko_send_command,
                           command_string='show ip int br | i Vlan')
        print_result(ip_int)
        for device, response in ip_int.items():

            target = nr.filter(filter_func=lambda h: h.name == device)

            svi_list = get_svi(response[0].result)
            print(svi_list)

            for svi in svi_list:
                print(f'Checking {svi} at {device}')
                check_svi = target.run(task=networking.netmiko_send_command,
                                       command_string=f'show int {svi}')
                print_result(check_svi)
                int_mac = find_int_mac(check_svi[device][0].result)
                if int_mac is None:
                    continue
                if int_mac == mac:
                    is_found = True
                    host_switch = device
                    host_interface = svi
                    break

    if is_found:
        print('MAC was found')
        print(f'{host_switch} interface {host_interface}')
    else:
        print('MAC was not found')
