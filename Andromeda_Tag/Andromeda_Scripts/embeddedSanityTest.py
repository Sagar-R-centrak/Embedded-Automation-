import socket
import struct
import datetime
import time
import serial
import logging
import json
import os
import subprocess
from openpyxl import load_workbook
from Report_process import RateProcessor
from Profile import JSONMessageApp
from Tcp_command_1 import DevCommandSender
from Power_supply import KoradPowerSupply
import joulescope
import numpy as np
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import keyboard
from pyautogui import hotkey
import os, time
import subprocess
import keyboard
from pyautogui import hotkey
import pygetwindow as gw
import zipfile
import pandas as pd
import win32com.client
import re

url = "https://centrak-apps.sourcerepo.com/redmine/centrak/attachments/download/154073"
username = "Cheluva.GB"
password = "Infinite@1234"
username_field_id = "username"  # ID as per HTML
password_field_id = "password"  # ID as per HTML
login_button_id = "login-submit"  # ID as per HTML
downloads_path = os.path.join(os.path.expanduser("~"), "C:\\Users\\cheluvagb\\Downloads")
unzip_to_folder = "C:\\Users\\cheluvagb\\Downloads\\Firmwares\\SafetyBracelet"
timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
# Create a file using pathlib
file_path = Path(f"CurrentConsumption_{timestamp}.txt")

tag1_id = 17686527
server_ip = "192.168.1.16"
PS = KoradPowerSupply(config_file="config.json")
PS.connect()
PS.set_voltage(0)
PS.disconnect()
time.sleep(5)
PS.connect()
PS.set_voltage(3)
TCP = JSONMessageApp(server_ip)
Report_processor = RateProcessor()
sender = DevCommandSender()

def extract_urls(text):
    url_pattern = r'(https?://[^\s]+|www\.[^\s]+)'
    return re.findall(url_pattern, text)

def send_outlook_email(to_email, subject, body):
    outlook = win32com.client.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)  # 0: olMailItem
    mail.To = to_email
    mail.Subject = subject
    mail.Body = body
    mail.Send()
    print(f"Email sent to {to_email}")

def excel_to_html(excel_file, html_file):
    df = pd.read_csv(excel_file) if excel_file.endswith('.csv') else pd.read_excel(excel_file)
    html_content = df.to_html(index=False, border=1)
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    return html_file


def filter_failed_tests(excel_file):
    df = pd.read_csv(excel_file) if excel_file.endswith('.csv') else pd.read_excel(excel_file)
    result_col = next((col for col in df.columns if
                       'result' in col.lower() or 'status' in col.lower() or 'verdict' in col.lower() or 'pass' in col.lower() or 'fail' in col.lower()),
                      None)
    if result_col is None:
        for col in df.columns:
            values = df[col].astype(str).str.lower()
            if (values == 'fail').any():
                result_col = col
                break
    if result_col is None:
        raise ValueError('No pass/fail column found!')
    return df[df[result_col].astype(str).str.lower() == 'fail']


def send_failed_cases_email_html(df_failed, to_addr, html_file):
    outlook = win32com.client.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)
    mail.To = to_addr
    mail.Subject = "Sanity test results"

    if df_failed.empty:
        html_body = "<p>All test cases PASSED.</p>"
    else:
        html_table = df_failed.to_html(index=False, border=1)
        html_body = (
            "<p>Hello,<br><br>"
            "The following test cases FAILED in the latest sanity run:<br><br>"
            f"{html_table}<br><br>"
            "Regards,<br>Automation"
            "</p>"
        )
    mail.HTMLBody = html_body
    mail.Attachments.Add(html_file)
    mail.Send()
    print(f"HTML table email sent to {to_addr}")


def load_config():
    with open("config.json", "r") as file:
        return json.load(file)


# Read Arduino serial port from config
config = load_config()
Arduino_serial_port = config["Arduino_serial_port"]
host = config["host"]
port = config["port"]
timeout = config["timeout"]


def Report(test_id, f):
    STP = load_workbook('Andromeda_tag_Sanity_testcases.xlsx')
    sheet = STP.get_sheet_by_name('RF_900MHz')
    for x in range(2000):
        x += 1
        rn = 'D' + str(x)
        rs = 'F' + str(x)
        c = str(sheet[rn].value)
        if test_id in c:
            if f == 1:
                sheet[rs].value = "PASS"
                print(x)
            else:
                sheet[rs].value = "FAIL"
                print(x)
    STP.save('Andromeda_tag_Sanity_testcases.xlsx')


#

# Configure logging
LOG_FILE = "output.log"  # Predefined file name


def Output(data: str):
    """Writes data to a predefined file with a timestamp, each entry on a new line."""
    time_stamp = datetime.now()
    with open(LOG_FILE, "a") as file:  # Append mode to keep old data
        file.write(f"{time_stamp} - {data}\n")  # Write timestamp + data + newline


logging.basicConfig(
    filename='Debug_log.log',  # Log file name
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def get_tester_feedback(message):
    while True:
        print(message)
        feedback = input("Please type 'yes' or 'no': ").strip().lower()
        if feedback == 'yes':
            return True
        elif feedback == 'no':
            return False
        else:
            print("Invalid input. Try again.\n")


class SerialConnection:
    def __init__(self, port, baud_rate, timeout=1):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.ser = None

    def init_serial(self):
        try:
            self.ser = serial.Serial(self.port, self.baud_rate, timeout=self.timeout)
            if self.ser.isOpen():
                print(f"Connected to {self.port}")
            # Wait for Arduino to initialize
            time.sleep(2)
        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")

    def send_command(self, command):
        try:
            if self.ser:
                # Send the command
                self.ser.write(f"{command}\n".encode())  # Encode the string to bytes and send with newline
                logging.info(command)
                print(f"Sent: {command}")
                # Wait for response
                time.sleep(1)  # Wait for response
                if self.ser.in_waiting > 0:
                    response = self.ser.read(self.ser.in_waiting).decode('utf-8').strip()
                    print(f"Arduino: {response}")
        except serial.SerialException as e:
            print(f"Error communicating with Arduino: {e}")

    def close(self):
        if self.ser and self.ser.isOpen():
            self.ser.close()
            print("Serial connection closed.")


class PacketDecoder:
    @staticmethod
    def calculate_checksum(data):
        """
        Calculates the checksum by summing all bytes in the data.
        """
        return sum(data) & 0xFFFF  # Ensure it is a 2-byte value

    @staticmethod
    def decode_header(header):
        if len(header) < 13:
            print(f"Error: Header too short (length {len(header)})")
            return None  # Return None to indicate an invalid packet

        cycle_counter = header[0]
        star_mac_id = ':'.join(f'{b:02X}' for b in header[1:7])
        data_length = struct.unpack('<H', header[7:9])[0]  # Little-endian
        data_checksum = struct.unpack('<H', header[9:11])[0]  # Little-endian
        header_checksum = struct.unpack('<H', header[11:13])[0]  # Little-endian

        print(f"Cycle Counter: {cycle_counter}")
        print(f"Star MAC Id: {star_mac_id}")
        print(f"Data Length: {data_length}")
        print(f"Data Checksum: {data_checksum}")
        print(f"Header Checksum: {header_checksum}")

        return data_length, data_checksum

    @staticmethod
    def decode_status_byte(status_byte):
        if not isinstance(status_byte, int) or status_byte > 255:
            print(f"Error: Invalid status byte {status_byte}")
            return None  # Return None if the byte is invalid
        bit_fields = f'{status_byte:08b}'
        print(f"Status Byte: {bit_fields}")
        print(f"  Button 4: {bit_fields[0]}")
        print(f"  Button 3: {bit_fields[1]}")
        print(f"  Button 2: {bit_fields[2]}")
        print(f"  Button 1: {bit_fields[3]}")
        print(f"  Motion Flag: {bit_fields[4]}")
        print(f"  Retry Count: {int(bit_fields[5:7], 2)}")  # Convert bits 5 and 6 to decimal
        print(f"  Reserved: {bit_fields[7]}")
        return {
            'Status Byte': bit_fields,
            'Button 4': bit_fields[0],
            'Button 3': bit_fields[1],
            'Button 2': bit_fields[2],
            'Button 1': bit_fields[3],
            'Motion Flag': bit_fields[4],
            'Retry Count': int(bit_fields[5:7], 2),
            'Reserved': bit_fields[7]
        }

    @staticmethod
    def decode_location_packet(packet, expected_checksum):
        if len(packet) < 30:
            print(f"Error: Location packet too short! Length: {len(packet)}")
            return None  # Return None if the packet is too short

        computed_checksum = PacketDecoder.calculate_checksum(packet)
        if computed_checksum != expected_checksum:
            print(
                f"Error: Data Checksum Mismatch! Computed: {computed_checksum:04X}, Expected: {expected_checksum:04X}")

        else:
            print(f"Data Checksum Matched: {computed_checksum:04X}")

        device_type = packet[0]
        tag_id_raw = int.from_bytes(packet[1:5], byteorder='little')
        tag_id = tag_id_raw & 0x0FFFFFFF  # Remove the MSB nibble
        raw_rssi = packet[8]
        rssi = (raw_rssi - 256) / 2.0 - 78 if raw_rssi >= 128 else raw_rssi / 2.0 - 78
        monitor_id = int.from_bytes(packet[9:12], byteorder='little')
        cmd = packet[12]
        status_byte = packet[13]
        # Decode status byte safely
        status_fields = PacketDecoder.decode_status_byte(status_byte)
        if status_fields is None:
            print("Error: Failed to decode status byte.")
            return None
        ir_id = struct.unpack('<H', packet[14:16])[0]
        version = packet[16]
        astar_id = struct.unpack('<H', packet[17:19])[0]
        lbi = struct.unpack('<H', packet[19:21])[0]
        cmd3 = packet[21:24].hex()
        time_stamp = int.from_bytes(packet[24:28], byteorder='little')
        readable_time = datetime.utcfromtimestamp(time_stamp).strftime('%Y-%m-%d %H:%M:%S')
        ekey = packet[28]
        lf_flag = packet[29]

        # Decode status byte
        status_fields = PacketDecoder.decode_status_byte(status_byte)

        # Prepare the decoded data
        decoded_data = {
            'Device Type': 'Tag' if device_type == 0x01 else 'Monitor',
            'Tag ID': tag_id,
            'RSSI': f"{rssi:.2f} dBm",
            'Monitor ID': monitor_id,
            'CMD': cmd,
            'Status Byte': status_fields['Status Byte'],
            'Button 4': status_fields['Button 4'],
            'Button 3': status_fields['Button 3'],
            'Button 2': status_fields['Button 2'],
            'Button 1': status_fields['Button 1'],
            'Motion Flag': status_fields['Motion Flag'],
            'Retry Count': status_fields['Retry Count'],
            'Reserved': status_fields['Reserved'],
            'IR ID': ir_id,
            'Version': version,
            'Astar ID': astar_id,
            'LBI': lbi,
            'CMD3': cmd3,
            'Timestamp': readable_time,
            'EKEY': ekey,
            'LF Flag': lf_flag
        }

        # Log the decoded data in a single line
        logging.info(json.dumps(decoded_data))

        # Print decoded values (optional)
        for key, value in decoded_data.items():
            print(f"{key}: {value}")

        return decoded_data


class PacketCapture:
    def __init__(self, host='127.0.0.1', port=7167, timeout=10):
        self.host = host
        self.port = port
        self.timeout = timeout

    def capture(self, timeout_type="short"):
        self.captured_packets = []
        start_time = time.time()

        # Define timeout values based on input type
        timeouts = {
            "short": 5,  # Short timeout: 5 seconds
            "medium": 15,  # Medium timeout: 10 seconds
            "long": 72  # Long timeout: 60 seconds
        }

        # Get the timeout value based on the input argument, default to "short"
        self.timeout = timeouts.get(timeout_type, 2)

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind((self.host, self.port))
            s.settimeout(self.timeout)

            while time.time() - start_time < self.timeout:
                try:
                    packet, addr = s.recvfrom(1024)  # Buffer size is 1024 bytes
                    print(f"Packet from {addr}")
                    print(f"Raw Data: {packet.hex()}")
                    self.captured_packets.append(packet)
                except socket.timeout:
                    print("Socket timed out, ending capture.")
                    break

    def validate_packet(self, decoded_packet, expected_values):
        """
        Validates if all key-value pairs in expected_values match those in decoded_packet.
        Adds a tolerance of 100 for 'LBI' and logs debug information to a file.

        Args:
            decoded_packet (dict): The actual decoded packet data.
            expected_values (dict): The expected key-value pairs to validate.

        Returns:
            bool: True if all expected values match (within tolerance for LBI), False otherwise.
        """

        mismatches = {}

        for key, expected_value in expected_values.items():
            actual_value = decoded_packet.get(key, None)

            if key == "LBI":
                # Apply tolerance of 100 for 'LBI'
                if actual_value is None or not (expected_value - 100 <= actual_value <= expected_value + 100):
                    mismatches[key] = {
                        "expected": f"{expected_value} ± 100",
                        "actual": actual_value
                    }
                    logging.debug(f"LBI mismatch: Expected {expected_value} ± 100, Got {actual_value}")
            else:
                # Exact match for other keys
                if actual_value != expected_value:
                    mismatches[key] = {
                        "expected": expected_value,
                        "actual": actual_value
                    }
                    logging.info(f"Mismatch for '{key}': Expected {expected_value}, Got {actual_value}")

        if mismatches:
            # Log all mismatches for debugging
            logging.info("Validation failed with mismatches:")
            print("Validation failed with mismatches:")
            for key, mismatch in mismatches.items():
                logging.info(f"Key: {key}, Expected: {mismatch['expected']}, Actual: {mismatch['actual']}")
                print(f"Key: {key}, Expected: {mismatch['expected']}, Actual: {mismatch['actual']}")
            return False

        logging.info("Validation successful!")
        return True

    def process_packets(self, expected_values):
        validation_result = False

        i = 0
        while i < len(self.captured_packets):
            if i + 1 < len(self.captured_packets):
                combined_packet = self.captured_packets[i] + self.captured_packets[i + 1]
                print("\nCombined Packet:")
                print(combined_packet.hex())

                if len(combined_packet) >= 13:  # Ensure at least header length
                    header = combined_packet[:13]
                    data_length, checksum = PacketDecoder.decode_header(header)
                    if data_length is None:
                        print("Skipping packet due to header decode failure.")
                        i += 2
                        continue

                    num_location_packets = data_length // 30
                    print(f"\nNumber of Location Packets: {num_location_packets}")

                    for j in range(num_location_packets):
                        start_idx = 13 + j * 30
                        end_idx = start_idx + 30
                        if end_idx > len(combined_packet):
                            print(f"Skipping incomplete location packet {j + 1}")
                            break

                        location_packet = combined_packet[start_idx:end_idx]
                        print(f"\nLocation Packet {j + 1}:")
                        decoded_packet = PacketDecoder.decode_location_packet(location_packet, checksum)

                        if decoded_packet is None:
                            print("Skipping invalid location packet.")
                            continue

                        validation_result = self.validate_packet(decoded_packet, expected_values)
                        if validation_result:
                            print("Expected parameters matched in this location packet!")
                            return True
                else:
                    print("Combined packet does not contain enough data for header.")
            i += 2

        return validation_result


class MainProcess:
    def __init__(self):
        self.serial_conn = SerialConnection(port=Arduino_serial_port, baud_rate=9600)
        self.packet_capture = PacketCapture()
        print("Initializing serial connection...")
        self.serial_conn.init_serial()

    def button_api(self, serial_message, expected_values):
        print(f"Sending command '{serial_message}' to Arduino...")
        self.serial_conn.send_command(serial_message)
        time.sleep(0.5)
        print("Capturing packets...")
        self.packet_capture.capture("short")

        print("Processing and validating captured packets...")
        is_valid = self.packet_capture.process_packets(expected_values)

        return is_valid

    def Location_api(self, serial_message, expected_values):
        print(f"Sending command '{serial_message}' to Arduino...")
        self.serial_conn.send_command(serial_message)
        time.sleep(0.5)
        print("Capturing packets...")
        self.packet_capture.capture("medium")

        print("Processing and validating captured packets...")
        is_valid = self.packet_capture.process_packets(expected_values)

        return is_valid

    def Command_api(self, serial_message, expected_values):
        print(f"Sending command '{serial_message}' to Arduino...")
        self.serial_conn.send_command(serial_message)
        time.sleep(0.5)
        print("Capturing packets...")
        self.packet_capture.capture("long")

        print("Processing and validating captured packets...")
        is_valid = self.packet_capture.process_packets(expected_values)

        return is_valid


if __name__ == "__main__":
    process = MainProcess()

for i in range(1):
    # ******************************************************************************************************************
    #
    # Test 1 ******************************************************************************************************************

    outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    inbox = outlook.GetDefaultFolder(6)  # 6 = Inbox

    # Find folder named "Satheesh"
    target_folder = None
    for subfolder in inbox.Folders:
        if subfolder.Name == "Satheesh":
            target_folder = subfolder
            break



    messages = target_folder.Items
    messages.Sort("[ReceivedTime]", True)  # Sort newest first

    if messages.Count > 0:
        latest_email = messages.GetFirst()
        print(f"Subject: {latest_email.Subject}\n")
        print("Body:\n")
        print(latest_email.Body)

        urls_1 = extract_urls(latest_email.Body)
        if urls_1:
            print("\nURLs Found in Email:")
            for url_1 in urls_1:
                print(url_1)


        else:
            print("No URLs found in email.")
    else:
        print("No emails found in Satheesh folder.")

    # Open product folder & login
    driver = webdriver.Chrome()  # or webdriver.Firefox() etc.
    driver.get(url)
    time.sleep(2)  # Wait for page to load (adjust as needed)
    driver.find_element(By.ID, username_field_id).send_keys(username)
    driver.find_element(By.ID, password_field_id).send_keys(password)
    driver.find_element(By.ID, login_button_id).click()
    time.sleep(10)  # Wait for login & download to complete

    # STEP 2: Find latest file in Downloads
    files = [os.path.join(downloads_path, f) for f in os.listdir(downloads_path)]
    files = [f for f in files if os.path.isfile(f)]
    latest_file = max(files, key=os.path.getctime)

    # STEP 3: Check if ZIP and unzip
    if latest_file.endswith('.zip'):
        with zipfile.ZipFile(latest_file, 'r') as zip_ref:
            zip_ref.extractall(unzip_to_folder)
        print(f"Extracted {latest_file} to {unzip_to_folder}")
    else:
        print("Latest file is not a ZIP file:", latest_file)

    driver.quit()

    file_path = "C:\\EmbeddedTestingAutomation\\Scripts\\Settings.ini"
    with open(file_path, 'r', encoding='utf-8') as file:
        filedata = file.read()
    newdata = filedata.replace('TAG_ID=17686528', 'TAG_ID=17686527')
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(newdata)

    subprocess.Popen("C:\\EmbeddedTestingAutomation\\Scripts\\ProductionTool")

    time.sleep(30)

    window = gw.getWindowsWithTitle("Production Tool")  # Replace with your window title

    print(window)

    if window:
        window[0].close()  # Close the first matching window
    else:
        print("Window not found!")

    print("Closing the window of production tool")
    time.sleep(10)

    with open("C:\\EmbeddedTestingAutomation\\Scripts\\Production.txt", "r") as file:
        lines = file.readlines()
        last_line = lines[-3].strip()  # Remove any trailing newline or spaces
        print(last_line)
        if "load process completed" in last_line:
            print("Test pass")
            Report("Flashing Test", 1)
            Output(f"Iteration{i}: Flashing Test PASS")
        elif "Firmware loading process failed" in last_line:
            print("test Fail")
            Report("Flashing Test", 0)
            Output(f"Iteration{i}: Flashing Test FAIL")

    # Test 2 ******************************************************************************************************************
    print("Executing current consumption after Flashing")
    time.sleep(3)
    with joulescope.scan_require_one(config='auto') as js:
        data = js.read(contiguous_duration=0.25)
    current, voltage = np.mean(data, axis=0, dtype=np.float64)
    current_mA = current * 1000
    stringAmp = str(current_mA)
    stringvolt = str(voltage)
    # print("Printing original current value")
    # print(f'{current} A, {voltage} V')
    print("Current consumption value")
    print(f'{current_mA} mA, {voltage} V')

    formatted_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Open a file in write mode (creates the file if it doesn't exist)
    with open(file_path, "a") as file:
        if current_mA >= 12.00:
            with open(file_path, "a") as file:
                print("Consuming high current")
                file.write("Consuming high sleep current\n")
                file.write(f" {formatted_timestamp} Current={stringAmp} mA     Voltage={stringvolt} V\n")
        else:
            file.write(f" {formatted_timestamp} Current={stringAmp} mA     Voltage={stringvolt} V\n")
        if current_mA < 0.09:
            print("Normal current consumption 0.85mA")
            Report("Current after Flashing", 1)
            Output(f"Iteration{i}: Current after Flashing Test PASS")
        elif current_mA > 0.09:
            print("Current consumption is high", current_mA)
            print("Current consumption validation failed.")
            Report("Current after Flashing", 0)
            Output(f"Iteration{i}: Current after Flashing Test FAIL")
    # Test 3 ******************************************************************************************************************
    print("Executing Version_01 : To validate tag FW version  ")
    logging.info("Executing Version : To validate tag FW version \n  ")
    time.sleep(3)
    expected_values = {
        'Tag ID': tag1_id,
        'Version': 107
    }

    result = process.button_api(serial_message="tag1skey1", expected_values=expected_values)
    if result:
        print("Packet validation successful.")
        Report("Version", 1)
        Output(f"Iteration{i}: Version Test PASS")
    else:
        print("Packet validation failed.")
        Report("Version", 0)
        Output(f"Iteration{i}: Version Test FAIL")
    """
    # Test 4 ******************************************************************************************************************
    print("Executing button1 Long press : To validate Factory sleep entry  ")
    logging.info("Executing button1 Long press : To validate Factory sleep entry  \n  ")
    time.sleep(3)
    expected_values = {
        'Tag ID': tag1_id,
        'Version': 28
    }

    result = process.button_api(serial_message="tag1Longkey1", expected_values=expected_values)
    time.sleep(20)
    result = process.button_api(serial_message="tag1skey1", expected_values=expected_values)
    if not result:
        print("Packet validation successful.")
        Report("FactorySleep", 1)
        Output(f"Iteration{i}: Entry to Factory sleep Test PASS")
    else:
        print("Packet validation failed.")
        Report("FactorySleep", 0)
        Output(f"Iteration{i}: Entry to Factory sleep Test FAIL")

    # Test 5 ******************************************************************************************************************
    print("Executing current consumption after factory Sleep")
    time.sleep(3)
    with joulescope.scan_require_one(config='auto') as js:
        data = js.read(contiguous_duration=0.25)
    current, voltage = np.mean(data, axis=0, dtype=np.float64)
    current_mA = current * 1000
    stringAmp = str(current_mA)
    stringvolt = str(voltage)
    # print("Printing original current value")
    # print(f'{current} A, {voltage} V')
    print("Current consumption value")
    print(f'{current_mA} mA, {voltage} V')

    formatted_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Open a file in write mode (creates the file if it doesn't exist)
    with open(file_path, "a") as file:
        if current_mA >= 12.00:
            with open(file_path, "a") as file:
                print("Consuming high current")
                file.write("Consuming high sleep current\n")
                file.write(f" {formatted_timestamp} Current={stringAmp} mA     Voltage={stringvolt} V\n")
        else:
            file.write(f" {formatted_timestamp} Current={stringAmp} mA     Voltage={stringvolt} V\n")
        if current_mA < 0.09:
            print("Normal current consumption", current_mA, "mA")
            Report("Factory sleep current", 1)
            Output(f"Iteration{i}: Factory sleep current Test PASS")
        elif current_mA > 0.09:
            print("Current consumption is high", current_mA)
            print("Current consumption validation failed.")
            Report("Factory sleep current", 0)
            Output(f"Iteration{i}: Factory sleep current Test FAIL")

    # Test 6 ******************************************************************************************************************
    print("Executing button1 Long press : To validate Factory sleep exit  ")
    logging.info("Executing button1 Long press : To validate Factory sleep entry  \n  ")
    time.sleep(3)
    expected_values = {
        'Tag ID': tag1_id,
        'Button 4': '0',
        'Button 3': '0',
        'Button 2': '0',
        'Button 1': '1',
    }

    result = process.button_api(serial_message="tag1Longkey1", expected_values=expected_values)
    time.sleep(30)
    result = process.button_api(serial_message="tag1skey1", expected_values=expected_values)
    if result:
        print("Packet validation successful.")
        Report("FactorySleep exit", 1)
        Output(f"Iteration{i}: Exit from Factory sleep Test PASS")
        if current_mA < 11.99:
            print("Normal current consumption", current_mA, "mA")
            Report("Current consumption after factory sleep test", 1)
            Output(f"Iteration{i}: Current consumption after factory sleep test")
        elif current_mA > 11.99:
            print("Current consumption is high", current_mA)
            print("Current consumption validation failed.")
            Report("Current consumption after factory sleep test", 0)
            Output(f"Iteration{i}: Current consumption after factory sleep test FAIL")
    else:
        print("Packet validation failed.")
        Report("FactorySleep exit", 0)
        Output(f"Iteration{i}: Exit from Factory sleep Test FAIL")
    """
    # Test 7******************************************************************************************************************
    print("Executing Button_Press : To validate button3 short press ")
    time.sleep(3)
    # Example of calling the API function
    expected_values = {
        'Tag ID': tag1_id,
        'Button 4': '0',
        'Button 3': '1',
        'Button 2': '0',
        'Button 1': '0',
    }

    result = process.button_api(serial_message="tag1skey3", expected_values=expected_values)
    if result:

        print("Packet validation successful.")
        Report("Button_3", 1)
        Output(f"Iteration{i}: Button_3 Test PASS")
    else:
        print("Packet validation failed.")
        Report("Button_3", 0)
        Output(f"Iteration{i}: Button_3 Test FAIL")
    # Test 8 ******************************************************************************************************************
    print("Executing Button_Press : To validate current consumption after button3 short press ")
    time.sleep(3)
    # Example of calling the API function
    expected_values = {
        'Tag ID': tag1_id,
        'Button 4': '0',
        'Button 3': '1',
        'Button 2': '0',
        'Button 1': '0',
    }

    result = process.button_api(serial_message="tag1skey3", expected_values=expected_values)
    with joulescope.scan_require_one(config='auto') as js:
        data = js.read(contiguous_duration=0.25)
    current, voltage = np.mean(data, axis=0, dtype=np.float64)
    current_mA = current * 1000
    stringAmp = str(current_mA)
    stringvolt = str(voltage)
    # print("Printing original current value")
    # print(f'{current} A, {voltage} V')
    print("Current consumption value")
    print(f'{current_mA} mA, {voltage} V')

    formatted_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Open a file in write mode (creates the file if it doesn't exist)
    with open(file_path, "a") as file:
        if current_mA >= 12.00:
            with open(file_path, "a") as file:
                print("Consuming high current")
                file.write("Consuming high sleep current\n")
                file.write(f" {formatted_timestamp} Current={stringAmp} mA     Voltage={stringvolt} V\n")
        else:
            file.write(f" {formatted_timestamp} Current={stringAmp} mA     Voltage={stringvolt} V\n")

    if result:

        print("Packet validation successful.")
        Report("Current consumption short press button 3", 1)
        Output(f"Iteration{i}: Current consumption short press Test PASS")

        if current_mA < 11.99:
            if current_mA <= 0.00:
                print("Current consumption validation failed.")
                Report("Current consumption short press button 3", 0)
                Output(f"Iteration{i}: Button_03 current consumption Test FAIL")
            else:
                print("Normal current consumption",current_mA)
        elif current_mA > 11.99:
            print("Current consumption is high", current_mA)
            print("Current consumption validation failed.")
            Report("Current consumption short press button 3", 0)
            Output(f"Iteration{i}: Button_03 current consumption Test FAIL")
    else:
        print("Packet validation failed.")
        Report("Current consumption short press button 3", 0)
        Output(f"Iteration{i}: Current consumption short press Test FAIL")

    # Test 9 ******************************************************************************************************************

    print("Executing Long Button_Press : To validate current consumption after button3 Long press ")
    time.sleep(3)
    # Example of calling the API function
    expected_values = {
        'Tag ID': tag1_id,
        'Button 4': '0',
        'Button 3': '1',
        'Button 2': '0',
        'Button 1': '0',
    }

    result = process.button_api(serial_message="tag1lkey3", expected_values=expected_values)
    with joulescope.scan_require_one(config='auto') as js:
        data = js.read(contiguous_duration=0.25)
    current, voltage = np.mean(data, axis=0, dtype=np.float64)
    current_mA = current * 1000
    stringAmp = str(current_mA)
    stringvolt = str(voltage)
    # print("Printing original current value")
    # print(f'{current} A, {voltage} V')
    print("Current consumption value")
    print(f'{current_mA} mA, {voltage} V')

    formatted_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Open a file in write mode (creates the file if it doesn't exist)
    with open(file_path, "a") as file:
        if current_mA >= 12.00:
            with open(file_path, "a") as file:
                print("Consuming high current")
                file.write("Consuming high sleep current\n")
                file.write(f" {formatted_timestamp} Current={stringAmp} mA     Voltage={stringvolt} V\n")
        else:
            file.write(f" {formatted_timestamp} Current={stringAmp} mA     Voltage={stringvolt} V\n")

    if result:

        print("Packet validation successful.")
        Report("Current consumption long press", 1)
        Output(f"Iteration{i}: Current consumption long press Test PASS")

        if current_mA < 11.99:
            print("Normal current consumption 0.64mA")
        elif current_mA > 11.99:
            print("Current consumption is high", current_mA)
            print("Current consumption validation failed.")
            Report("Button_03", 0)
            Output(f"Iteration{i}: Button_03 current consumption Test FAIL")
    else:
        print("Packet validation failed.")
        Report("Current consumption long press", 0)
        Output(f"Iteration{i}: Current consumption long press Test FAIL")
    """
    # Test 8 ******************************************************************************************************************
    print("Executing Sleep test after Button_Press : To validate current consumption after 5 min sleep time")
    time.sleep(3)
    # Example of calling the API function
    expected_values = {
        'Tag ID': tag1_id,
        'Button 4': '0',
        'Button 3': '1',
        'Button 2': '0',
        'Button 1': '0',
    }

    result = process.button_api(serial_message="tag1skey3", expected_values=expected_values)
    time.sleep(310)
    with joulescope.scan_require_one(config='auto') as js:
        data = js.read(contiguous_duration=0.25)
    current, voltage = np.mean(data, axis=0, dtype=np.float64)
    current_mA = current * 1000
    stringAmp = str(current_mA)
    stringvolt = str(voltage)
    # print("Printing original current value")
    # print(f'{current} A, {voltage} V')
    print("Current consumption value")
    print(f'{current_mA} mA, {voltage} V')

    formatted_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Open a file in write mode (creates the file if it doesn't exist)
    with open(file_path, "a") as file:
        if current_mA >= 12.00:
            with open(file_path, "a") as file:
                print("Consuming high current")
                file.write("Consuming high sleep current\n")
                file.write(f" {formatted_timestamp} Current={stringAmp} mA     Voltage={stringvolt} V\n")
        else:
            file.write(f" {formatted_timestamp} Current={stringAmp} mA     Voltage={stringvolt} V\n")
        if current_mA < 11.99:
            print("Normal current consumption", current_mA, "mA")
            Report("5 min sleep current", 1)
            Output(f"Iteration{i}: 5 min sleep current")
        elif current_mA > 11.99:
            print("Current consumption is high", current_mA)
            print("Current consumption validation failed.")
            Report("5 min sleep current", 0)
            Output(f"Iteration{i}: 5 min sleep current Test FAIL")
    """
    # Test 10 ******************************************************************************************************************
    print("Executing current consumption after POR Sleep")
    PS.disconnect()
    time.sleep(3)
    PS.connect()
    PS.set_voltage(0)
    time.sleep(5)
    PS.disconnect()
    time.sleep(10)
    PS.connect()
    PS.set_voltage(3)
    time.sleep(10)
    with joulescope.scan_require_one(config='auto') as js:
        data = js.read(contiguous_duration=0.25)
    current, voltage = np.mean(data, axis=0, dtype=np.float64)
    current_mA = current * 1000
    stringAmp = str(current_mA)
    stringvolt = str(voltage)
    # print("Printing original current value")
    # print(f'{current} A, {voltage} V')
    print("Current consumption value")
    print(f'{current_mA} mA, {voltage} V')

    formatted_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Open a file in write mode (creates the file if it doesn't exist)
    with open(file_path, "a") as file:
        if current_mA >= 12.00:
            with open(file_path, "a") as file:
                print("Consuming high current")
                file.write("Consuming high sleep current\n")
                file.write(f" {formatted_timestamp} Current={stringAmp} mA     Voltage={stringvolt} V\n")
        else:
            file.write(f" {formatted_timestamp} Current={stringAmp} mA     Voltage={stringvolt} V\n")
        if current_mA < 11.00:
            if current_mA <= 0.00:
                print("Current consumption validation failed.")
                Report("Current consumption POR sleep current", 0)
                Output(f"Iteration{i}: POR sleep current Test FAIL")
            else:
                print("Normal current consumption", current_mA)
        elif current_mA > 11.00:
            print("Current consumption is high", current_mA)
            print("Current consumption validation failed.")
            Report("POR sleep current", 0)
            Output(f"Iteration{i}: POR sleep current Test FAIL")

    # Test11-----------------------------------------------------------------------------------
    print("Executing Battery voltage : To validate tag LBI value ")
    logging.info("Executing Battery test case : To validate tag LBI value \n  ")
    time.sleep(3)
    time.sleep(3)
    expected_values = {
        'Tag ID': tag1_id,
        'LBI': 3200
    }
    result = process.button_api(serial_message="tag1skey2", expected_values=expected_values)
    if result:
        print("Packet validation successful.")
        Report("Battery", 1)
        Output(f"Iteration{i}: Battery Test PASS")
    else:
        print("Packet validation failed.")
        Report("Battery", 0)
        Output(f"Iteration{i}: Battery Test FAIL")

    # Test12 ******************************************************************************************************************
    print("Executing Location : To validate Location packet ")
    logging.info("Executing Location : To validate Location packet \n ")
    time.sleep(3)
    expected_values = {
        'Tag ID': tag1_id,
        'Motion Flag': '1',
        'Monitor ID': 2615964,

        'IR ID': 2,
        'LF Flag': 2
    }

    result = process.button_api(serial_message="servo1.start", expected_values=expected_values)
    process.serial_conn.send_command("servo1.stop")
    if result:
        print("Packet validation successful.")
        Report("Location", 1)
        Output(f"Iteration{i}: Location Test PASS")
    else:
        print("Packet validation failed.")
        Report("Location", 0)
        Output(f"Iteration{i}: Location Test FAIL")
    json_request = '''Setmonitorprofile
    {
    "deviceprofile": {
        "centrak_guid": "8de9fd77-e7c5-4eb3-a661-265055222cac",
        "device_type": "2 - [Dual IR Monitor]",
        "monitor_type": "4",
        "monitor_id": "2615964",
        "ir_id": "2",
        "power_level": "0"

    }
    }
    '''
    TCP.send_message(json_request)

    # Test 13 ******************************************************************************************************************
    #
    print("Executing Motion : To validate Motion flag  ")
    logging.info("Executing Motion : To validate Motion flag ")
    time.sleep(3)
    # Example of calling the API function
    expected_values = {
        'Tag ID': tag1_id
        ,
        'Button 4': '0',
        'Button 3': '0',
        'Button 2': '0',
        'Button 1': '0',
        'EKEY': 0,
        'LF Flag': 2,
        'Motion Flag': '1'

    }

    result = process.button_api(serial_message="servo1.start", expected_values=expected_values)
    process.serial_conn.send_command("servo1.stop")
    if not result:
        print(f"Iteration {i}: Test PASS")
        Output(f"Iteration{i}: Motion Test PASS")
        Report("Motion", 1)
    else:
        print(f"Iteration {i}: Test FAIL")
        Output(f"Iteration {i}: Motion Test FAIL")

        Report("Motion", 0)
releaseVersion = "Test Release - V41.1.107"
excel_file = "C:\\Users\\cheluvagb\\Downloads\\SanityTestsSampleUpload.xlsx"
html_file = "C:\\Users\\cheluvagb\\Downloads\\SanityResults.html"
excel_to_html(excel_file, html_file)
failed = filter_failed_tests(excel_file)

send_failed_cases_email_html(failed, "cheluvagb@centrak.com ", html_file)
send_failed_cases_email_html(failed, "psharma@centrak.com ", html_file)

filename = "C:\\EmbeddedTestingAutomation\\Scripts\\executed_builds.txt"

text = releaseVersion

with open(filename, 'a', encoding='utf-8') as f:
    f.write(text + '\n')