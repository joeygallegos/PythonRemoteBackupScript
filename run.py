import json
import pysftp
from colorama import Fore, Style, init
import os
import logging
import ctypes  # Import ctypes for displaying a popup message
import secrets
import string


def get_config():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    with open(config_path, "r") as file:
        return json.load(file)


def show_warning(message):
    try:
        ctypes.windll.user32.MessageBoxW(0, str(message), "Warning", 0x40 | 0x1)
    except Exception as e:
        print(f"Failed to show warning: {e}")


def backup_data(config):
    cnopts = pysftp.CnOpts()
    cnopts.hostkeys = None  # Be cautious with this line in a production environment

    for server in config["servers"]:
        if not server.get("active"):
            continue

        username = server["username"]
        hostname = server["hostname"]
        if username.lower() == "root":
            print(
                f"{Fore.RED}{Style.BRIGHT}WARNING: You are connecting as the 'root' user to {hostname}!{Style.RESET_ALL}"
            )

        logging.info(f"Connecting to {hostname}")

        connection_params = {
            "host": server["ip"],
            "port": server["port"],
            "username": username,
            "private_key": server["ssh_key"],
            "cnopts": cnopts,
        }

        if server.get("ssh_key_passphrase"):
            connection_params["private_key_pass"] = server.get("ssh_key_passphrase")

        with pysftp.Connection(**connection_params) as sftp:
            logging.info(
                f"Connected to {hostname}, checking for startup commands if any defined"
            )

            # If there are startup commands, run them once connected
            if server.get("commands_on_connect"):
                logging.info(f"Found startup commands, running")
                for connect_command in server.get("commands_on_connect"):
                    command_output = sftp.execute(connect_command)
                    logging.info(f"Command: {connect_command}: {command_output}")

            remote_dir = server.get("backup_dir")
            if not sftp.exists(remote_dir):
                error_message = (
                    f"Remote directory {remote_dir} does not exist on {hostname}"
                )
                logging.error(f"{Fore.RED}{error_message}{Style.RESET_ALL}")
                show_warning(error_message)
                continue  # Skip to the next server

            files_to_backup = server.get("files", [])
            for file_pattern in files_to_backup:
                try:
                    latest_file_output = sftp.execute(
                        f"ls -t {remote_dir}/{file_pattern} | head -n 1"
                    )
                    if not latest_file_output:
                        show_warning(
                            f"No files matching {file_pattern} found on {hostname}"
                        )
                        raise FileNotFoundError(
                            f"No files matching {file_pattern} found on {hostname}"
                        )

                    latest_file = latest_file_output[0].decode().strip()
                    logging.info(
                        f"Latest file matching {file_pattern} on {hostname}: {latest_file}"
                    )

                    # Generate a 10-character nonce
                    alphabet = string.ascii_letters + string.digits
                    nonce = "".join(secrets.choice(alphabet) for _ in range(10))

                    local_file_name = f"{hostname}_{latest_file.split('/')[-1].replace('.gz', f'_{nonce}.gz')}"
                    local_file_path = os.path.join(
                        config["local_backup_dir"], local_file_name
                    )

                    sftp.get(latest_file, localpath=local_file_path)
                    logging.info(f"File downloaded to {local_file_path}")

                    latest_file_size = os.path.getsize(local_file_path)
                    size_threshold = latest_file_size * 0.75

                    # Check the sizes of the last 5 files
                    previous_files_output = sftp.execute(
                        f"ls -t {remote_dir}/{file_pattern} | head -n 6 | tail -n 5"
                    )
                    previous_files = [
                        f.decode().strip() for f in previous_files_output if f
                    ]

                    smaller_file_found = any(
                        sftp.stat(os.path.join(remote_dir, file)).st_size
                        < size_threshold
                        for file in previous_files
                    )

                    if smaller_file_found:
                        error_message = f"Some recent files matching {file_pattern} on {hostname} are at least 25% smaller in size than the latest file. Please verify the downloaded file."
                        print(
                            f"{Fore.RED}{Style.BRIGHT}WARNING: {error_message}{Style.RESET_ALL}"
                        )
                        show_warning(error_message)

                except FileNotFoundError as e:
                    logging.warning(e)
                except Exception as e:
                    logging.error(
                        f"Unexpected error while processing {file_pattern} on {hostname}: {e}"
                    )
                    show_warning(
                        f"Unexpected error while processing {file_pattern} on {hostname}: {e}"
                    )


if __name__ == "__main__":
    init()  # Initialize colorama
    logging.basicConfig(
        level=logging.INFO
    )  # Set logging level to INFO for detailed output
    config = get_config()
    backup_data(config)
