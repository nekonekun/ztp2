from netmiko.linux import LinuxSSH


def generate_option_125(firmware_filename: str):
    dlink_id = '00:00:00:AB'
    suboption_length = hex(1 + 1 + len(firmware_filename))[2:].upper().zfill(2)
    suboption_code = '01'
    filename_length = hex(len(firmware_filename))[2:].upper().zfill(2)
    hex_filename = ':'.join(
        [hex(ord(letter))[2:].upper().zfill(2)
         for letter in firmware_filename])
    answer = dlink_id
    answer += ':'
    answer += suboption_length
    answer += ':'
    answer += suboption_code
    answer += ':'
    answer += filename_length
    answer += ':'
    answer += hex_filename
    return answer


def create_entry(ztp_id: int, mac_address: str, ftp_host: str,
                 config_filename: str, firmware_filename: str,
                 dhcp_config_filepath: str, session: LinuxSSH):
    cmd = f"cat {dhcp_config_filepath} | " \
          f"grep -Fn 'hardware ethernet {mac_address}' | " \
          f"cut --delimiter=':' --fields=1"
    possible_mac_duplicate = session.send_command(cmd)
    if possible_mac_duplicate:
        line_number = int(possible_mac_duplicate)
        cmd = f"sudo sed -i '{line_number - 5},{line_number + 1}d' " \
              f"{dhcp_config_filepath}"
        session.send_command(cmd)
    lines = [
        'group {',
        f'option tftp-server-name "{ftp_host}";',
        f'option bootfile-name "{config_filename}";',
        f'option option125 {generate_option_125(firmware_filename)};',
        f'option option150 {ftp_host};',
        f'host entry_{ztp_id} {{ hardware ethernet {mac_address}; }}',
        '}'
    ]
    for line in lines:
        session.send_command(f'echo \'{line}\' >> {dhcp_config_filepath}')
    session.send_command('sudo /etc/init.d/isc-dhcp-server restart')


def change_mac_address(ztp_id: int,
                       new_mac: str,
                       dhcp_config_filepath: str,
                       session: LinuxSSH):
    line_number = session.send_command(
        f"cat {dhcp_config_filepath} | "
        f"grep -Fn 'entry_{ztp_id}' | "
        f"cut --delimiter=':' --fields=1")
    if not line_number:
        return
    cmd = f"sudo sed -i -E " \
        f"'{line_number}s/(hardware ethernet ).+?(;)/\\1{new_mac}\\2/' " \
        f"{dhcp_config_filepath}"
    session.send_command(cmd)


def change_ip_address(ztp_id: int,
                      new_ip: str,
                      dhcp_config_filepath: str,
                      session: LinuxSSH):
    line_number = session.send_command(
        f"cat {dhcp_config_filepath} | "
        f"grep -Fn 'entry_{ztp_id}' | "
        f"cut --delimiter=':' --fields=1")
    if not line_number:
        return
    bootfile_line = int(line_number) - 3
    cmd = f"sudo sed -i -E " \
          f"'{bootfile_line}s/(initial\\/).+?(\\.cfg)/\\1{new_ip}\\2/' " \
          f"{dhcp_config_filepath}"
    session.send_command(cmd)


def delete_entry(ztp_id: int,
                 dhcp_config_filepath: str,
                 session: LinuxSSH):
    line_number = session.send_command(
        f"cat {dhcp_config_filepath} | "
        f"grep -Fn 'entry_{ztp_id}' | "
        f"cut --delimiter=':' --fields=1")
    if not line_number:
        return
    line_number = int(line_number)
    cmd = f"sudo sed -i '{line_number-5},{line_number+1}d' " \
          f"{dhcp_config_filepath}"
    session.send_command(cmd)
