import json
import pysftp
from colorama import Fore, Style, init
import os
import logging
import ctypes  # Import ctypes for displaying a popup message

def get_config():
    # Load and return the configuration from config.json
    with open('config.json', 'r') as file:
        return json.load(file)

def backup_data(config):
    cnopts = pysftp.CnOpts()
    cnopts.hostkeys = None  # Be cautious with this line in a production environment
    
    for server in config['servers']:
        username = server['username']
        hostname = server['hostname']  # Assuming 'hostname' is a key in your server config
        if username.lower() == 'root':
            print(f"{Fore.RED}{Style.BRIGHT}WARNING: You are connecting as the 'root' user to {hostname}!{Style.RESET_ALL}")
        
        logging.info(f'Connecting to {hostname}')

        connection_params = {
            'host': server['ip'],
            'port': server['port'],
            'username': username,
            'private_key': server['ssh_key'],
            'cnopts': cnopts
        }

        if server.get('ssh_key_passphrase'):
            connection_params['private_key_pass'] = server['ssh_key_passphrase']

        # Establish a connection to the server
        with pysftp.Connection(**connection_params) as sftp:
            logging.info(f'Connected to {hostname}')
            
            remote_dir = server['backup_dir']
            # Check if the remote directory exists
            if sftp.exists(remote_dir):
                # Execute a command on the server to find the latest .gz file in the backup directory
                latest_file_bytes = sftp.execute(f"ls -t {remote_dir}/*.gz | head -n 1")[0]
                latest_file = latest_file_bytes.decode().strip()
                if latest_file:
                    logging.info(f'Latest file on {hostname}: {latest_file}')
                    
                    local_file_name = latest_file.split('/')[-1]  
                    local_file_path = os.path.join(config['local_backup_dir'], local_file_name)
                    
                    sftp.get(latest_file, localpath=local_file_path)
                    logging.info(f'File downloaded to {local_file_path}')
                    
                    # Check if the downloaded file has no size
                    if os.path.getsize(local_file_path) == 0:
                        print(f"{Fore.RED}{Style.BRIGHT}WARNING: Downloaded file {local_file_name} has no size!{Style.RESET_ALL}")
                else:
                    logging.warning(f'No .gz files found on {hostname}')
            else:
                error_message = f'Remote directory {remote_dir} does not exist on {hostname}'
                logging.error(f"{Fore.RED}{error_message}{Style.RESET_ALL}")
                # Display a popup warning message
                ctypes.windll.user32.MessageBoxW(0, error_message, "Warning", 0x40 | 0x1)

if __name__ == '__main__':
    init()  # Initialize colorama
    logging.basicConfig(level=logging.INFO)  # Set logging level to INFO for detailed output
    config = get_config()
    backup_data(config)
