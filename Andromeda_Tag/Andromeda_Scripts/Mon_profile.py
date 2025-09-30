import socket
import json

# Load configuration from config.json
with open("config.json", "r") as config_file:
    config = json.load(config_file)

# Read server details from config.json
SERVER_IP = config.get("SERVER_IP", "127.0.0.1")  # Default to localhost if not found
PORT_PROFILE = config.get("Port_profile", 8185)  # Default to 8185 if not found


def send_json_message(json_message):
    """
    Sends a JSON message to the configured server and receives the response.

    Parameters:
        json_message (str): The JSON message to send.
    """
    try:
        # Create a socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            print("Connecting to the server...")

            # Connect to the server using global variables
            s.connect((SERVER_IP, PORT_PROFILE))
            print(f"Connected to {SERVER_IP}:{PORT_PROFILE}")

            # Send the JSON message
            message = json_message.encode('utf-8')
            s.sendall(message)
            print("Message sent:")
            print(json_message)

            # Wait for the server's response
            retries = 20
            timeout = 1
            s.settimeout(timeout)

            response = ""
            for attempt in range(retries):
                try:
                    # Receive data from the server
                    data = s.recv(2048)
                    response += data.decode('utf-8')
                    if data:
                        break
                except socket.timeout:
                    print(f"Retrying... ({attempt + 1}/{retries})")

            if response:
                print("Response received:")
                print(response)
            else:
                print("No response received after retries.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    # Example JSON message
    json_request = '''Setmonitorprofile
{
"deviceprofile": { 
    "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
    "device_type": "2 - [Dual IR Monitor]",
    "monitor_type": "4",
    "monitor_id": "479279",
    "enable_dual_irvw": "0",
    "ir_id": "12",
    "ir_idb": "0",
    "ir_powerlevel1": "51",
    "ir_powerlevel2": "0",
    "ir_profile": "1",
    "enable_primary_secondary": "0",
    "monitor_report_rate": "3",
    "noise_level": "0",
    "noise_levelb": "0",
    "operating_mode": "3",
    "paging_profile": "0",
    "power_level": "1",
    "power_levelb": "0",
    "profile": "0",
    "profileb": "0",
    "rssi_power_level1": "51",
    "rssi_power_level2": "0",
    "enable_self_noise": "0",
    "enable_self_noiseb": "0",
    "star_group": "0",
    "enable_super_sync": "0",
    "super_sync_range_offreq": "0",
    "wlan_channel_mask": "1057",
    "wlan_profile": "32",
    "zone_id": "0",
    "enable_contaminated": "0",
    "w2d_is_secondary": "0",
    "w2d_supersync_slot": "1",
    "w2d_primary_monitorid": "0",
    "w2d_timepull_counter": "5",
    "w2d_profilepull_counter": "5",
    "w2d_timeserver_ip": "255.255.255.255",
    "w2d_blnsupt": "0",
    "enable_sbfreq": "0",
    "aruba": "0",
    "is_3_1device": "1",
    "monitor_name": "",
    "dwell_monitor": "0",
    "enable_ble": "1",
    "parent_monitor": "1",
    "ethernet_type": "1",
    "stream_id": "0"
}
}
'''
    # Send JSON message to the server
    send_json_message(json_request)
