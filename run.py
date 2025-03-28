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

        try:
            with pysftp.Connection(**connection_params) as sftp:
                logging.info(
                    f"Connected to {hostname}, checking for startup commands if any defined"
                )

                if server.get("commands_on_connect"):
                    logging.info("Found startup commands, running")
                    for connect_command in server.get("commands_on_connect"):
                        try:
                            command_output = sftp.execute(connect_command)
                            logging.info(f"Command: {connect_command}: {command_output}")
                        except Exception as cmd_error:
                            logging.error(
                                f"Failed to execute command '{connect_command}' on {hostname}: {cmd_error}"
                            )

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

                        alphabet = string.ascii_letters + string.digits
                        nonce = "".join(secrets.choice(alphabet) for _ in range(10))

                        local_file_name = f"{hostname}_{latest_file.split('/')[-1].replace('.gz', f'_{nonce}.gz')}"
                        local_file_path = os.path.join(
                            config["local_backup_dir"], local_file_name
                        )

                        sftp.get(latest_file, localpath=local_file_path)
                        logging.info(f"File downloaded to {local_file_path}")

                    except FileNotFoundError as e:
                        logging.warning(e)
                    except Exception as e:
                        logging.error(
                            f"Unexpected error while processing {file_pattern} on {hostname}: {e}"
                        )
                        show_warning(
                            f"Unexpected error while processing {file_pattern} on {hostname}: {e}"
                        )

        except Exception as e:
            logging.error(f"Failed to connect to {hostname}: {e}")
            show_warning(f"Failed to connect to {hostname}: {e}")
            continue  # Move to the next server in the loop


if __name__ == "__main__":
    init()  # Initialize colorama
    logging.basicConfig(
        level=logging.INFO
    )  # Set logging level to INFO for detailed output
    config = get_config()
    backup_data(config)
    input("Press ENTER to exit...")