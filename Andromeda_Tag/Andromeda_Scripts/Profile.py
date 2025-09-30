import socket
import time
from datetime import datetime

class JSONMessageApp:
    def __init__(self, server_ip, server_port=8185):
        self.server_ip = server_ip
        self.server_port = server_port
        self.sock = None

    def connect_streaming_server(self):
        """Establish a connection to the streaming server."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.server_ip, self.server_port))
        except socket.error as e:
            print(f"Error connecting to server: {e}")
            self.sock = None

    def send_message(self, json_message):
        """Send a JSON message to the server and print the response."""
        if not self.sock:
            print("Socket not connected. Attempting to reconnect...")
            self.connect_streaming_server()

        if not self.sock:
            print("Failed to connect to the server.")
            return

        try:
            # Send the JSON message
            self.sock.sendall(json_message.encode())
            print(f"Sent: {json_message}")

            # Wait for acknowledgment
            ack_received = False
            retry_count = 0
            while retry_count < 20:
                self.sock.settimeout(1.0)
                try:
                    ack_message = self.sock.recv(2080).decode()
                    ack_received = True
                    break
                except socket.timeout:
                    retry_count += 1
                    print(f"Retrying... ({retry_count}/20)")

            if ack_received:
                print(f"Response: {ack_message}")
                self.log_request_response(json_message, ack_message)
            else:
                print("Acknowledgment not received within retry limit.")

        except socket.error as e:
            print(f"Error during communication: {e}")
        finally:
            self.close_connection()

    def close_connection(self):
        """Close the socket connection."""
        if self.sock:
            self.sock.close()
            self.sock = None

    def log_request_response(self, request, response):
        """Log the request and response to a file."""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{current_time} Request:\n{request}\nResponse:\n{response}\n\n"
        print(log_entry)

        # Write to a log file
        with open("ProfileSummary.txt", "a") as log_file:
            log_file.write(log_entry)


# Example usage
if __name__ == "__main__":
    server_ip = "192.168.1.10"  # Replace with your server IP
    #To set tag profile
    user_message ='''settagprofile

{

deviceprofile:

{ 

"centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

"device_type":"1",
      "device_category":"41 - [Andromeda Staff Tag]",
      "profile_type":"1",
      "tagcategory":"0",
      "model_type":"2",
      "tag_id":"17684931",
      "profile":"0",
      "ir_profile":"1",
      "ir_report_time":"1",
      "rf_report_time":"1",
      "ir_rx_profile":"4",
      "enable_fpb":"0",
      "operating_mode":"0",
      "ir_rx_slot":"1",
      "paging_profile":"3",
      "enable_lf":"0",
      "enable_lf_exciter_alert":"1",
      "enable_lf_alert":"1",
      "repeaterack":"0",
      "repeatermode":"0",
      "irrx":"1",
      "time_delay":"4",
      "tac_alert_delay":"4",
      "vwo_alert_delay":"4",
      "vwi_alert_delay":"4",
      "beep_cycle":"2",
      "beep_repeat":"1",
      "motion_sensor_logic":"0",
      "ble_irrx":"0",
      "pewbletxpower":"14",
      "ble_num_pings":"5",
      "ble_reportrate_active":"0",
      "ble_reportrate_sleep":"0",
      "ble_in900mhz":"1",
      "ble_pingrate":"1",
      "ble_duress_rate":"2",
      "ble_duress_timeout":"1",
      "model_number":"0",
      "tag_name":",""buzzer_mode"":"3",""fast_reporting_interval"":"1"\"
}
}
'''
# TO
    app = JSONMessageApp(server_ip)
    app.send_message(user_message)
json_request = """gettagprofile
{
    "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
    "tag_id": "17630048"
}
"""
