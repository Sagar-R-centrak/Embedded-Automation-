import socket
import struct
import datetime
import time
import serial
import logging
import json
from openpyxl import load_workbook
from Report_process import RateProcessor
from Profile import JSONMessageApp
from Tcp_command_1 import DevCommandSender
from Power_supply import KoradPowerSupply
tag1_id = 17686523

server_ip = "192.168.1.8"
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

def load_config():
    with open("config.json", "r") as file:
        return json.load(file)

# Read Arduino serial port from config
config = load_config()
Arduino_serial_port = config["Arduino_serial_port"]
host = config["host"]
port = config["port"]
timeout = config["timeout"]

def Report(test_id,f):
   STP = load_workbook('Andromeda_tag_testcases.xlsx')
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
   STP.save('Andromeda_tag_testcases.xlsx')
#

# Configure logging
LOG_FILE = "output.log"  # Predefined file name

def Output(data: str):
    """Writes data to a predefined file with a timestamp, each entry on a new line."""
    time_stamp = datetime.datetime.now()
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

        return data_length,data_checksum

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
    def decode_location_packet(packet,expected_checksum):
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
        readable_time = datetime.datetime.utcfromtimestamp(time_stamp).strftime('%Y-%m-%d %H:%M:%S')
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
    def __init__(self, host='127.0.0.1', port=7166, timeout=10):
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
                    data_length,checksum = PacketDecoder.decode_header(header)
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
                        decoded_packet = PacketDecoder.decode_location_packet(location_packet,checksum)

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
    print("Executing Version_01 : To validate tag FW version  ")
    logging.info("Executing Version_01 : To validate tag FW version \n  ")
    time.sleep(3)
    expected_values = {
        'Tag ID': tag1_id,
        'Version': 28
    }

    result = process.button_api(serial_message="tag1skey1", expected_values=expected_values)
    if result:
        print("Packet validation successful.")
        Report("Version_01", 1)
        Output(f"Iteration{i}: Version_01 Test PASS")
    else:
        print("Packet validation failed.")
        Report("Version_01", 0)
        Output(f"Iteration{i}: Version_01 Test FAIL")

    # ******************************************************************************************************************
    print("Executing packet validation for retransmission after POR")
    logging.info("Executing packet validation for retransmission after POR \n ")
    time.sleep(3)
    expected_values = {
        'Tag ID': tag11_id,
        'Motion Flag': '1',
        'Monitor ID': 8449603,

        'IR ID': 2,
        'LF Flag': 2
    }

    result = process.button_api(serial_message="servo1.start", expected_values=expected_values)
    process.serial_conn.send_command("servo1.stop")
    if result:
        print("Packet validation successful.")
        Report("Location_01", 1)
        Output(f"Iteration{i}: Location_01 Test PASS")
    else:
        print("Packet validation failed.")
        Report("Location_01", 0)
        Output(f"Iteration{i}: Location_01 Test FAIL")
    json_request = '''Setmonitorprofile
    {
    "deviceprofile": {
        "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
        "device_type": "2 - [Dual IR Monitor]",
        "monitor_type": "4",
        "monitor_id": "8465776",
        "ir_id": "2",
        "power_level": "0"

    }
    }
    '''
    TCP.send_message(json_request)

    # ******************************************************************************************************************
    
	print("Executing Button_01 : To validate button1 short press ")
    logging.info("Executing Button_01 : To validate button1 short press \n")
    time.sleep(3)
    # Example of calling the API function
    expected_values = {
        'Tag ID': tag1_id,
        'Button 4': '0',
        'Button 3': '0',
        'Button 2': '0',
        'Button 1': '1',
    }

    result = process.button_api(serial_message="tag1skey1", expected_values=expected_values)
    if result:
        print("Packet validation successful.")
        Report("Button_01", 1)
        Output(f"Iteration{i}: Button_01 Test PASS")
    else:
        print("Packet validation failed.")
        Report("Button_01", 0)
        Output(f"Iteration{i}: Button_01 Test FAIL")
    # ******************************************************************************************************************
    print("Executing current consumption : To validate current consumption   ")
    logging.info("Executing current consumption : To validate current consumption \n  ")

    time.sleep(3)
    expected_values = {
        'Tag ID': tag1_id,
        'LBI': 3000
    }
	measurecurrentConsumption()
    result = process.button_api(serial_message="tag1skey2", expected_values=expected_values)
    if result:
        print("Packet validation successful.")
        Report("Battery_01", 1)
        Output(f"Iteration{i}: Battery_01 Test PASS")
    else:
        print("Packet validation failed.")
        Report("Battery_01", 0)
        Output(f"Iteration{i}: Battery_01 Test FAIL")
##***********************************************************************************************
	print("Executing Button_03 : To validate button3 short press ")
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
        Report("Button_03", 1)
        Output(f"Iteration{i}: Button_03 Test PASS")
    else:
        print("Packet validation failed.")
        Report("Button_03", 0)
        Output(f"Iteration{i}: Button_03 Test FAIL")
    # ******************************************************************************************************************
    print("Executing Button_02 : To validate button2 short press ")
    time.sleep(3)
    # Example of calling the API function
    expected_values = {
        'Tag ID': tag1_id,
        'Button 4': '0',
        'Button 3': '0',
        'Button 2': '1',
        'Button 1': '0',
    }

    result = process.button_api(serial_message="tag1skey2", expected_values=expected_values)
    if result:
        print("Packet validation successful.")
        Report("Button_02", 1)
        Output(f"Iteration{i}: Button_02 Test PASS")
    else:
        print("Packet validation failed.")
        Report("Button_02", 0)
        Output(f"Iteration{i}: Button_02 Test FAIL")

    # ******************************************************************************************************************
    
	print("Executing Button_04 : To validate button1 long press ")
    time.sleep(3)
    # Example of calling the API function
    expected_values = {
        'Tag ID': tag1_id,
        'Button 4': '0',
        'Button 3': '0',
        'Button 2': '0',
        'Button 1': '0',
        'EKEY': 9
    }

    result = process.button_api(serial_message="tag1lkey1", expected_values=expected_values)
    if result:
        print("Packet validation successful.")
        Report("Button_04", 1)
        Output(f"Iteration{i}: Button_04 Test PASS")
    else:
        print("Packet validation failed.")
        Report("Button_04", 0)
        Output(f"Iteration{i}: Button_04 Test FAIL")

    # ******************************************************************************************************************
    

    # ******************************************************************************************************************
    print("Executing Button_05 : To validate button2 long press ")
    time.sleep(3)
    # Example of calling the API function
    expected_values = {
        'Tag ID': tag1_id,
        'Button 4': '0',
        'Button 3': '0',
        'Button 2': '0',
        'Button 1': '0',
        'EKEY': 10
    }

    result = process.button_api(serial_message="tag1lkey2", expected_values=expected_values)
    if result:
        print("Packet validation successful.")
        Report("Button_05", 1)
        Output(f"Iteration{i}: Button_05 Test PASS")
    else:
        print("Packet validation failed.")
        Report("Button_05", 0)
        Output(f"Iteration{i}: Button_05 Test FAIL")

    # ******************************************************************************************************************
    print("Executing Button_06 : To validate button3 short press ")
    time.sleep(3)
    # Example of calling the API function
    expected_values = {
        'Tag ID': tag1_id,
        'Button 4': '0',
        'Button 3': '1',
        'Button 2': '0',
        'Button 1': '0',
        'EKEY': 4
    }

    result = process.button_api(serial_message="tag1lkey3", expected_values=expected_values)
    if result:
        print("Packet validation successful.")
        Report("Button_06", 1)
        Output(f"Iteration{i}: Button_06 Test PASS")
    else:
        print("Packet validation failed.")
        Report("Button_06", 0)
        Output(f"Iteration{i}: Button_06 Test FAIL")

    # ******************************************************************************************************************
    print("Executing Button_07 : To validate button1 Double press ")
    time.sleep(3)
    # Example of calling the API function
    expected_values = {
        'Tag ID': tag1_id,
        'Button 4': '0',
        'Button 3': '0',
        'Button 2': '0',
        'Button 1': '0',
        'EKEY': 13
    }

    result = process.button_api(serial_message="tag1dkey1", expected_values=expected_values)
    if result:
        print("Packet validation successful.")
        Report("Button_07", 1)
        Output(f"Iteration{i}: Button_07 Test PASS")

    else:
        print("Packet validation failed.")
        Report("Button_07", 0)
        Output(f"Iteration{i}: Button_07 Test FAIL")

    # ******************************************************************************************************************
    print("Executing Button_08 : To validate button2 Double press ")
    time.sleep(3)
    # Example of calling the API function
    expected_values = {
        'Tag ID': tag1_id,
        'Button 4': '0',
        'Button 3': '0',
        'Button 2': '0',
        'Button 1': '0',
        'EKEY': 14
    }

    result = process.button_api(serial_message="tag1dkey2", expected_values=expected_values)
    if result:
        print("Packet validation successful.")
        Report("Button_08", 1)
        Output(f"Iteration{i}: Button_08 Test PASS")
    else:
        print("Packet validation failed.")
        Report("Button_08", 0)
        Output(f"Iteration{i}: Button_08 Test FAIL")

    # ******************************************************************************************************************
    print("Executing Button_09 : To validate simultaneous short key press on 1,2  ")
    time.sleep(3)
    # Example of calling the API function
    expected_values = {
        'Tag ID': tag1_id,
        'Button 4': '0',
        'Button 3': '0',
        'Button 2': '1',
        'Button 1': '1',
        'EKEY': 3
    }

    result = process.button_api(serial_message="tag1multiskey1,2", expected_values=expected_values)
    if result:
        print("Packet validation successful.")
        Report("Button_09", 1)
        Output(f"Iteration{i}: Button_09 Test PASS")
    else:
        print("Packet validation failed.")
        Report("Button_09", 0)
        Output(f"Iteration{i}: Button_09 Test FAIL")

    # ******************************************************************************************************************
    print("Executing Button_10 : To validate simultaneous short key press on 1,3  ")
    logging.info("Executing Button_10 : To validate simultaneous short key press on 1,3  ")
    time.sleep(3)
    # Example of calling the API function
    expected_values = {
        'Tag ID': tag1_id,
        'Button 4': '0',
        'Button 3': '1',
        'Button 2': '0',
        'Button 1': '0',
        'EKEY': 4
    }

    result = process.button_api(serial_message="tag1multiskey1,3", expected_values=expected_values)
    if result:
        print("Packet validation successful.")
        Output(f"Iteration{i}: Button_10 Test PASS")
        Report("Button_10", 1)
    else:
        print("Packet validation failed.")
        Report("Button_10", 0)
        Output(f"Iteration{i}: Button_10 Test FAIL")

    # ******************************************************************************************************************

    print("Executing Motion_01 : To validate Resting state to Motion state  ")
    logging.info("Executing Motion_01 : To validate Resting state to Motion state  ")
    time.sleep(3)
    # Example of calling the API function
    expected_values = {
        'Tag ID': tag11_id
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
    if result:
        print(f"Iteration {i}: Test PASS")
        Output(f"Iteration{i}: Motion_01 Test PASS")
        Report("Motion_01", 1)
    else:
        print(f"Iteration {i}: Test FAIL")
        Output(f"Iteration {i}: Motion_01 Test FAIL")

        Report("Motion_01", 0)

    for i in range(1):
        user_message = '''settagprofile

                        {

                        deviceprofile:

                        {

                        "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                        "device_type":"1",
                              "device_category":"41 - [Andromeda Staff Tag]",
                              "profile_type":"1",
                              "tagcategory":"0",
                              "model_type":"2",
                              "tag_id":,
                              "profile":"0",
                              "ir_profile":"1",
                              "ir_report_time":"4",
                              "rf_report_time":"0",
                              "ir_rx_profile":"4"

                        }
                        }
                        '''
        TCP.send_message(user_message)
        time.sleep(5)
        process.serial_conn.send_command("servo1.start")
        time.sleep(2)
        process.serial_conn.send_command("servo1.stop")
        time.sleep(40)
        process.serial_conn.send_command("servo1.start")
        EXPECTED_VALUES = {
            'Tag ID': tag11_id,
            'Monitor ID': 0,
            'Button 4': '0',
            'Button 3': '0',
            'Button 2': '0',
            'Button 1': '0',
            'Motion Flag': '1',
            'Reserved': '0',
            'IR ID': 0,
            'Version': 28,
            'Astar ID': 40,
            'Retry Count': 1
        }


        expected_validation_count = 10
        expected_report_rate = 12
        Ctime = 125
        result = Report_processor.Intervals(Ctime, EXPECTED_VALUES, expected_validation_count, expected_report_rate)

        if result:
            print("Expected parameters matched!")
            Output(f"Iteration{i}: Report_01 Test PASS")
            Report("Report_01", 1)
        else:
            print("Expected parameters not matched.")
            Output(f"Iteration{i}: Report_01 Test FAIL")
            Report("Report_01", 0)
        process.serial_conn.send_command("servo1.stop")
        #******************************************************************************************************************

        user_message = '''settagprofile

                                {

                                deviceprofile:

                                {

                                "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                "device_type":"1",
                                      "device_category":"41 - [Andromeda Staff Tag]",
                                      "profile_type":"1",
                                      "tagcategory":"0",
                                      "model_type":"2",
                                      "tag_id":"17684982",
                                      "profile":"0",
                                      "ir_profile":"1",
                                      "ir_report_time":"4",
                                      "rf_report_time":"2",
                                      "ir_rx_profile":"4"

                                }
                                }
                                '''
        TCP.send_message(user_message)
        time.sleep(5)
        process.serial_conn.send_command("servo1.start")
        time.sleep(2)
        process.serial_conn.send_command("servo1.stop")
        time.sleep(40)
        process.serial_conn.send_command("servo1.start")
        time.sleep(5)
        EXPECTED_VALUES = {
            'Tag ID': tag11_id,
            'Monitor ID': 0,
            'Button 4': '0',
            'Button 3': '0',
            'Button 2': '0',
            'Button 1': '0',
            'Motion Flag': '1',
            'Reserved': '0',
            'IR ID': 0,
            'Version': 28,
            'Astar ID': 40,
            'Retry Count': 1
        }
        expected_validation_count = 10
        expected_report_rate = 24
        Ctime = 245
        result = Report_processor.Intervals(Ctime, EXPECTED_VALUES, expected_validation_count, expected_report_rate)

        if result:
            print("Expected parameters matched!")
            Output(f"Iteration{i}: Report_02 Test PASS")
            Report("Report_02", 1)
        else:
            print("Expected parameters not matched.")
            Output(f"Iteration{i}: Report_02 Test FAIL")
            Report("Report_02", 0)
        process.serial_conn.send_command("servo1.stop")
        time.sleep(75)
        #******************************************************************************************************************

        user_message = '''settagprofile

                                        {

                                        deviceprofile:

                                        {

                                        "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                        "device_type":"1",
                                              "device_category":"41 - [Andromeda Staff Tag]",
                                              "profile_type":"1",
                                              "tagcategory":"0",
                                              "model_type":"2",
                                              "tag_id":""17684982,
                                              "profile":"0",
                                              "ir_profile":"1",
                                              "ir_report_time":"4",
                                              "rf_report_time":"3",
                                              "ir_rx_profile":"4"

                                        }
                                        }
                                        '''
        TCP.send_message(user_message)
        time.sleep(5)
        process.serial_conn.send_command("servo1.start")
        time.sleep(2)
        process.serial_conn.send_command("servo1.stop")
        time.sleep(150)
        process.serial_conn.send_command("servo1.start")
        time.sleep(5)
        EXPECTED_VALUES = {
            'Tag ID': tag11_id,
            'Monitor ID': 0,
            'Button 4': '0',
            'Button 3': '0',
            'Button 2': '0',
            'Button 1': '0',
            'Motion Flag': '1',
            'Reserved': '0',
            'IR ID': 0,
            'Version': 28,
            'Astar ID': 40,
            'Retry Count': 1
        }
        expected_validation_count = 10
        expected_report_rate = 48
        Ctime = 485
        result = Report_processor.Intervals(Ctime, EXPECTED_VALUES, expected_validation_count, expected_report_rate)

        if result:
            print("Expected parameters matched!")
            Output(f"Iteration{i}: Report_03 Test PASS")
            Report("Report_03", 1)
        else:
            print("Expected parameters not matched.")
            Output(f"Iteration{i}: Report_03 Test FAIL")
            Report("Report_03", 0)
        process.serial_conn.send_command("servo1.stop")
        time.sleep(60)

        # ******************************************************************************************************************
        user_message = '''settagprofile

                                                {

                                                deviceprofile:

                                                {

                                                "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                "device_type":"1",
                                                      "device_category":"41 - [Andromeda Staff Tag]",
                                                      "profile_type":"1",
                                                      "tagcategory":"0",
                                                      "model_type":"2",
                                                      "tag_id":"17684982",
                                                      "profile":"0",
                                                      "ir_profile":"1",
                                                      "ir_report_time":"4",
                                                      "rf_report_time":"1",
                                                      "ir_rx_profile":"4"

                                                }
                                                }
                                                '''
        TCP.send_message(user_message)
        time.sleep(5)
        process.serial_conn.send_command("servo1.start")
        time.sleep(2)
        process.serial_conn.send_command("servo1.stop")
        time.sleep(150)
        process.serial_conn.send_command("servo1.start")
        time.sleep(5)
        EXPECTED_VALUES = {
            'Tag ID': tag11_id,
            'Monitor ID': 0,
            'Button 4': '0',
            'Button 3': '0',
            'Button 2': '0',
            'Button 1': '0',
            'Motion Flag': '1',
            'Reserved': '0',
            'IR ID': 0,
            'Version': 28,
            'Astar ID': 40,
            'Retry Count': 1
        }

        expected_validation_count = 10
        expected_report_rate = 6
        Ctime = 63
        result = Report_processor.Intervals(Ctime, EXPECTED_VALUES, expected_validation_count, expected_report_rate)

        if result:
            print("Expected parameters matched!")
            Output(f"Iteration{i}: Report_04 Test PASS")
            Report("Report_04", 1)
        else:
            print("Expected parameters not matched.")
            Output(f"Iteration{i}: Report_04 Test FAIL")
            Report("Report_04", 0)
        process.serial_conn.send_command("servo1.stop")
        time.sleep(60)

        json_request = '''Setmonitorprofile
        {
        "deviceprofile": {
            "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
            "device_type": "2 - [Dual IR Monitor]",
            "monitor_type": "4",
            "monitor_id": "8465776",
            "ir_id": "2",
            "power_level": "1"

        }
        }
        '''
        TCP.send_message(json_request)
        time.sleep(15)
        #******************************************************************************************************************
        user_message = '''settagprofile

                                                        {

                                                        deviceprofile:

                                                        {

                                                        "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                        "device_type":"1",
                                                              "device_category":"41 - [Andromeda Staff Tag]",
                                                              "profile_type":"1",
                                                              "tagcategory":"0",
                                                              "model_type":"2",
                                                              "tag_id":"17684982",
                                                              "profile":"0",
                                                              "ir_profile":"1",
                                                              "ir_report_time":"0",
                                                              "rf_report_time":"1",
                                                              "ir_rx_profile":"4"

                                                        }
                                                        }
                                                        '''
        TCP.send_message(user_message)
        time.sleep(5)
        process.serial_conn.send_command("servo1.start")
        time.sleep(2)
        process.serial_conn.send_command("servo1.stop")
        time.sleep(150)
        process.serial_conn.send_command("servo1.start")
        time.sleep(5)
        EXPECTED_VALUES = {
            'Tag ID': tag11_id,
            'Monitor ID': 8449603,
            'Button 4': '0',
            'Button 3': '0',
            'Button 2': '0',
            'Button 1': '0',
            'Motion Flag': '1',
            'Reserved': '0',
            'IR ID': 2,
            'Version': 28,
            'Astar ID': 40,
            'Retry Count': 1
        }
        expected_validation_count = 10
        expected_report_rate = 12
        Ctime = 125
        result = Report_processor.Intervals(Ctime, EXPECTED_VALUES, expected_validation_count, expected_report_rate)

        if result:
            print("Expected parameters matched!")
            Output(f"Iteration{i}: Report_05 Test PASS")
            Report("Report_05", 1)
        else:
            print("Expected parameters not matched.")
            Output(f"Iteration{i}: Report_05 Test FAIL")
            Report("Report_05", 0)
        process.serial_conn.send_command("servo1.stop")
        time.sleep(60)
        # ******************************************************************************************************************

        user_message = '''settagprofile

                                                                {

                                                                deviceprofile:

                                                                {

                                                                "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                                "device_type":"1",
                                                                      "device_category":"41 - [Andromeda Staff Tag]",
                                                                      "profile_type":"1",
                                                                      "tagcategory":"0",
                                                                      "model_type":"2",
                                                                      "tag_id":"17684982",
                                                                      "profile":"0",
                                                                      "ir_profile":"1",
                                                                      "ir_report_time":"1",
                                                                      "rf_report_time":"1",
                                                                      "ir_rx_profile":"4"

                                                                }
                                                                }
                                                                '''
        TCP.send_message(user_message)
        time.sleep(5)
        process.serial_conn.send_command("servo1.start")
        time.sleep(2)
        process.serial_conn.send_command("servo1.stop")
        time.sleep(40)

        process.serial_conn.send_command("servo1.start")
        time.sleep(5)
        EXPECTED_VALUES = {
            'Tag ID': tag11_id,
            'Monitor ID': 8449603,
            'Button 4': '0',
            'Button 3': '0',
            'Button 2': '0',
            'Button 1': '0',
            'Motion Flag': '1',
            'Reserved': '0',
            'IR ID': 2,
            'Version': 28,
            'Astar ID': 40,
            'Retry Count': 1
        }
        expected_validation_count = 10
        expected_report_rate = 48
        Ctime = 490
        result = Report_processor.Intervals(Ctime, EXPECTED_VALUES, expected_validation_count, expected_report_rate)

        if result:
            print("Expected parameters matched!")
            Output(f"Iteration{i}: Report_06 Test PASS")
            Report("Report_06", 1)
        else:
            print("Expected parameters not matched.")
            Output(f"Iteration{i}: Report_06 Test FAIL")
            Report("Report_06", 0)
        process.serial_conn.send_command("servo1.stop")
        time.sleep(60)

        # ******************************************************************************************************************
        user_message = '''settagprofile

                                                                        {

                                                                        deviceprofile:

                                                                        {

                                                                        "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                                        "device_type":"1",
                                                                              "device_category":"41 - [Andromeda Staff Tag]",
                                                                              "profile_type":"1",
                                                                              "tagcategory":"0",
                                                                              "model_type":"2",
                                                                              "tag_id":"17684982",
                                                                              "profile":"0",
                                                                              "ir_profile":"1",
                                                                              "ir_report_time":"2",
                                                                              "rf_report_time":"1",
                                                                              "ir_rx_profile":"4"

                                                                        }
                                                                        }
                                                                        '''
        TCP.send_message(user_message)
        time.sleep(5)
        process.serial_conn.send_command("servo1.start")
        time.sleep(2)
        process.serial_conn.send_command("servo1.stop")
        time.sleep(150)
        process.serial_conn.send_command("servo1.start")
        time.sleep(5)
        EXPECTED_VALUES = {
            'Tag ID': tag11_id,
            'Monitor ID': 8449603,
            'Button 4': '0',
            'Button 3': '0',
            'Button 2': '0',
            'Button 1': '0',
            'Motion Flag': '1',
            'Reserved': '0',
            'IR ID': 2,
            'Version': 28,
            'Astar ID': 40,
            'Retry Count': 1
        }
        expected_validation_count = 10
        expected_report_rate = 120
        Ctime = 1250
        result = Report_processor.Intervals(Ctime, EXPECTED_VALUES, expected_validation_count, expected_report_rate)

        if result:
            print("Expected parameters matched!")
            Output(f"Iteration{i}: Report_07 Test PASS")
            Report("Report_07", 1)
        else:
            print("Expected parameters not matched.")
            Output(f"Iteration{i}: Report_07 Test FAIL")
            Report("Report_07", 0)
        process.serial_conn.send_command("servo1.stop")
        time.sleep(60)

        #******************************************************************************************************************
        user_message = '''settagprofile

                                                                        {

                                                                        deviceprofile:

                                                                        {

                                                                        "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                                        "device_type":"1",
                                                                              "device_category":"41 - [Andromeda Staff Tag]",
                                                                              "profile_type":"1",
                                                                              "tagcategory":"0",
                                                                              "model_type":"2",
                                                                              "tag_id":"17684982",
                                                                              "profile":"0",
                                                                              "ir_profile":"1",
                                                                              "ir_report_time":"3",
                                                                              "rf_report_time":"1",
                                                                              "ir_rx_profile":"4"

                                                                        }
                                                                        }
                                                                        '''
        TCP.send_message(user_message)
        time.sleep(5)
        process.serial_conn.send_command("servo1.start")
        time.sleep(2)
        process.serial_conn.send_command("servo1.stop")
        time.sleep(365)
        process.serial_conn.send_command("servo1.start")
        time.sleep(5)
        EXPECTED_VALUES = {
            'Tag ID': tag11_id,
            'Monitor ID': 8449603,
            'Button 4': '0',
            'Button 3': '0',
            'Button 2': '0',
            'Button 1': '0',
            'Motion Flag': '1',
            'Reserved': '0',
            'IR ID': 2,
            'Version': 28,
            'Astar ID': 40,
            'Retry Count': 1
        }
        expected_validation_count = 10
        expected_report_rate = 300
        Ctime = 3050
        result = Report_processor.Intervals(Ctime, EXPECTED_VALUES, expected_validation_count, expected_report_rate)

        if result:
            print("Expected parameters matched!")
            Output(f"Iteration{i}: Report_08 Test PASS")
            Report("Report_08", 1)
        else:
            print("Expected parameters not matched.")
            Output(f"Iteration{i}: Report_08 Test FAIL")
            Report("Report_08", 0)
        process.serial_conn.send_command("servo1.stop")
        time.sleep(60)


    # ******************************************************************************************************************
    print("Executing Cmd_01 : To Validate Reset command ")
    time.sleep(75)
    sender.send_command(tag1_id, 0x1, 1)
    time.sleep(1)
    expected_values = {
        'Tag ID': tag1_id,
        'CMD3' : "840b07"

    }

    result = process.Command_api(serial_message="tag1skey1", expected_values=expected_values)
    process.serial_conn.send_command("servo1.stop")
    if result:
        print("Cmd_01 Test PASS")
        Report("Cmd_01", 1)
        Output(f"Iteration{i}: Cmd_01 Test PASS")
    else:
        print("Cmd_01 Test FAIL.")
        Report("Cmd_01", 0)
        Output(f"Iteration{i}: Cmd_01 Test FAIL")

    # ******************************************************************************************************************
    print("Executing Cmd_02 : To Validate Led on command ")
    time.sleep(75)
    sender.send_command(tag1_id, 0x2, 100)
    time.sleep(1)
    expected_values = {
        'Tag ID': tag1_id,
        'CMD3': "640002"

    }

    result = process.Command_api(serial_message="tag1skey1", expected_values=expected_values)
    process.serial_conn.send_command("servo1.stop")
    if result:
        print("Cmd_02 Test PASS")
        Report("Cmd_02", 1)
        Output(f"Iteration{i}: Cmd_02 Test PASS")
    else:
        print("Cmd_02 Test FAIL.")
        Report("Cmd_02", 0)
        Output(f"Iteration{i}: Cmd_02 Test FAIL")

    # ******************************************************************************************************************
    print("Executing Cmd_03 : To Validate Led off command ")
    time.sleep(75)
    sender.send_command(tag1_id, 0x3, 0)
    time.sleep(1)
    expected_values = {
        'Tag ID': tag1_id,
        'CMD3': "000003"

    }

    result = process.Command_api(serial_message="tag1skey1", expected_values=expected_values)
    process.serial_conn.send_command("servo1.stop")
    if result:
        print("Cmd_03 Test PASS")
        Report("Cmd_03", 1)
        Output(f"Iteration{i}: Cmd_03 Test PASS")
    else:
        print("Cmd_03 Test FAIL.")
        Report("Cmd_03", 0)
        Output(f"Iteration{i}: Cmd_03 Test FAIL")

    # ******************************************************************************************************************
    print("Executing Cmd_04 : To validate Get profile command ")
    time.sleep(75)
    sender.send_command(tag1_id, 0x5, 2)
    time.sleep(1)
    expected_values = {
        'Tag ID': tag1_id,
        'CMD3': "020005"

    }

    result = process.Command_api(serial_message="tag1skey1", expected_values=expected_values)
    process.serial_conn.send_command("servo1.stop")
    if result:
        print("Cmd_04 Test PASS")
        Report("Cmd_04", 1)
        Output(f"Iteration{i}: Cmd_04 Test PASS")
    else:
        print("Cmd_04 Test FAIL.")
        Report("Cmd_04", 0)
        Output(f"Iteration{i}: Cmd_04 Test FAIL")

    # ******************************************************************************************************************
    print("Executing Cmd_05 : To Validate Get Version Command ")
    time.sleep(75)
    sender.send_command(tag1_id, 0x6, 2)
    time.sleep(1)
    expected_values = {
        'Tag ID': tag1_id,
        'CMD3': "1b0006"

    }

    result = process.Command_api(serial_message="tag1skey1", expected_values=expected_values)
    process.serial_conn.send_command("servo1.stop")
    if result:
        print("Cmd_05 Test PASS")
        Report("Cmd_05", 1)
        Output(f"Iteration{i}: Cmd_05 Test PASS")
    else:
        print("Cmd_05 Test FAIL.")
        Report("Cmd_05", 0)
        Output(f"Iteration{i}: Cmd_05 Test FAIL")

    # ******************************************************************************************************************
    print("Executing Cmd_06 : To Validate Get Summary info Command ")
    time.sleep(75)
    sender.send_command(tag1_id, 0x20, 2)
    time.sleep(1)
    expected_values = {
        'Tag ID': tag1_id,
        'CMD3': "000020"

    }

    result = process.Command_api(serial_message="tag1skey1", expected_values=expected_values)
    process.serial_conn.send_command("servo1.stop")
    if result:
        print("Cmd_06 Test PASS")
        Report("Cmd_06", 1)
        Output(f"Iteration{i}: Cmd_06 Test PASS")
    else:
        print("Cmd_06 Test FAIL.")
        Report("Cmd_06", 0)
        Output(f"Iteration{i}: Cmd_06 Test FAIL")

    #******************************************************************************************************************
    print("Executing Cmd_07 : To Validate Clear Summary info Command ")
    time.sleep(75)
    sender.send_command(tag1_id, 0x22, 2)
    time.sleep(1)
    expected_values = {
        'Tag ID': tag1_id,
        'CMD3': "000022"

    }
	
	
	
	

    result = process.Command_api(serial_message="tag1skey1", expected_values=expected_values)
    process.serial_conn.send_command("servo1.stop")
    if result:
        print("Cmd_07 Test PASS")
        Report("Cmd_07", 1)
        Output(f"Iteration{i}: Cmd_07 Test PASS")
    else:
        print("Cmd_07 Test FAIL.")
        Report("Cmd_07", 0)
        Output(f"Iteration{i}: Cmd_07 Test FAIL")

    # ******************************************************************************************************************
    print("Executing Cmd_08 : To Validate Turn on Buzzer Command ")
    time.sleep(75)
    sender.send_command(tag1_id, 0x11, 1)
    time.sleep(1)
    expected_values = {
        'Tag ID': tag1_id,
        'CMD3': "010011"

    }

    result = process.Command_api(serial_message="tag1skey1", expected_values=expected_values)
    process.serial_conn.send_command("servo1.stop")
    if result:
        print("Cmd_08 Test PASS")
        Report("Cmd_08", 1)
        Output(f"Iteration{i}: Cmd_08 Test PASS")
    else:
        print("Cmd_08 Test FAIL.")
        Report("Cmd_08", 0)
        Output(f"Iteration{i}: Cmd_08 Test FAIL")

    # ******************************************************************************************************************
    print("Executing Cmd_09 : To Validate Turn off Buzzer Command ")
    time.sleep(75)
    sender.send_command(tag1_id, 0x12, 1)
    time.sleep(1)
    expected_values = {
        'Tag ID': tag1_id,
        'CMD3': "010012"

    }

    result = process.Command_api(serial_message="tag1skey1", expected_values=expected_values)
    process.serial_conn.send_command("servo1.stop")
    if result:
        print("Cmd_09 Test PASS")
        Report("Cmd_09", 1)
        Output(f"Iteration{i}: Cmd_09 Test PASS")
    else:
        print("Cmd_09 Test FAIL.")
        Report("Cmd_09", 0)
        Output(f"Iteration{i}: Cmd_09 Test FAIL")

    #******************************************************************************************************************
    print("Executing Profile_01 : To Validate Turning off Buzzer ack for keys")
    user_message = '''settagprofile

                                                            {

                                                            deviceprofile:

                                                            {

                                                            "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                            "device_type":"1",
                                                                  "device_category":"41 - [Andromeda Staff Tag]",
                                                                  "profile_type":"1",
                                                                  "tagcategory":"0",
                                                                  "model_type":"2",
                                                                  "tag_id":"17684982",
                                                                  "profile":"0",
                                                                  "ir_profile":"1",
                                                                  "ir_report_time":"1",
                                                                  "rf_report_time":"2",
                                                                  "buzzer_mode": "0"

                                                            }
                                                            }
                                                            '''
    TCP.send_message(user_message)
    time.sleep(5)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(5)
    sender.send_command(tag11_id, 0x5, 1)
    time.sleep(2)
    process.serial_conn.send_command("servo1.start")
    time.sleep(25)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(5)
    json_request = """gettagprofile
            {
                "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
                "tag_id": "17684982"
            }
            """
    expected_values = {
                "tag_id": "17684982",
                "buzzer_mode": "0"
        }

    a = TCP.validate_tag_profile(json_request,expected_values)
    b = get_tester_feedback("Does Buzzer Ack disabled for all keys ?")
    result = a & b

    if result:
        print("Profile_01 Test PASS")
        Output(f"Iteration{i}: Profile_01 Test PASS")
        Report("Profile_01", 1)
    else:
        print("Profile_01 Test FAIL.")
        Output(f"Iteration{i}: Profile_01 Test FAIL")
        Report("Profile_01", 0)


    # ******************************************************************************************************************
    print("Executing Profile_02 : To Validate Turning on Buzzer ack for all keys")
    user_message = '''settagprofile

                                                                {

                                                                deviceprofile:

                                                                {

                                                                "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                                "device_type":"1",
                                                                      "device_category":"41 - [Andromeda Staff Tag]",
                                                                      "profile_type":"1",
                                                                      "tagcategory":"0",
                                                                      "model_type":"2",
                                                                      "tag_id":"17684982",
                                                                      "profile":"0",
                                                                      "ir_profile":"1",
                                                                      "ir_report_time":"1",
                                                                      "rf_report_time":"2",
                                                                      "buzzer_mode": "1"

                                                                }
                                                                }
                                                                '''
    TCP.send_message(user_message)
    time.sleep(5)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(5)
    sender.send_command(tag11_id, 0x5, 1)
    time.sleep(2)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(25)
    json_request = """gettagprofile
                {
                    "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
                    "tag_id": "17684982"
                }
                """
    expected_values = {
        "tag_id": "17684982",
        "buzzer_mode": "1"
    }
    a = TCP.validate_tag_profile(json_request, expected_values)
    b = get_tester_feedback("Does Buzzer ack enabled for all keys ?")
    result = a & b

    if result:
        print("Profile_02 Test PASS")
        Output(f"Iteration{i}: Profile_02 Test PASS")
        Report("Profile_02", 1)
    else:
        print("Profile_02 Test FAIL.")
        Output(f"Iteration{i}: Profile_02 Test FAIL")
        Report("Profile_02", 0)


    # ******************************************************************************************************************
    print("Executing Profile_03 : To Validate Turning on Buzzer ack for Duress key only")
    user_message = '''settagprofile

                                                                    {

                                                                    deviceprofile:

                                                                    {

                                                                    "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                                    "device_type":"1",
                                                                          "device_category":"41 - [Andromeda Staff Tag]",
                                                                          "profile_type":"1",
                                                                          "tagcategory":"0",
                                                                          "model_type":"2",
                                                                          "tag_id":"17684982",
                                                                          "profile":"0",
                                                                          "ir_profile":"1",
                                                                          "ir_report_time":"1",
                                                                          "rf_report_time":"2",
                                                                          "buzzer_mode": "2"

                                                                    }
                                                                    }
                                                                    '''
    TCP.send_message(user_message)
    time.sleep(5)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(5)
    sender.send_command(tag11_id, 0x5, 1)
    time.sleep(2)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(25)
    json_request = """gettagprofile
                    {
                        "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
                        "tag_id": "17684982"
                    }
                    """
    expected_values = {
        "tag_id": "17684982",
        "buzzer_mode": "2"
    }

    a = TCP.validate_tag_profile(json_request, expected_values)



    b = get_tester_feedback("Does Buzzer Enabled only for duress key only ?")
    result = a & b

    if result:
        print("Profile_03 Test PASS")
        Output(f"Iteration{i}: Profile_03 Test PASS")
        Report("Profile_03", 1)
    else:
        print("Profile_03 Test FAIL.")
        Output(f"Iteration{i}: Profile_03 Test FAIL")
        Report("Profile_03", 0)
    print("Waiting for Keys validation")


    # ******************************************************************************************************************
    print("Executing Profile_04 : To Validate enabling Custom profile for Tag")
    user_message = '''settagprofile

                                                                        {

                                                                        deviceprofile:

                                                                        {

                                                                        "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                                        "device_type":"1",
                                                                              "device_category":"41 - [Andromeda Staff Tag]",
                                                                              "profile_type":"1",
                                                                              "tagcategory":"0",
                                                                              "model_type":"2",
                                                                              "tag_id":"17684982",
                                                                              "profile":"0",
                                                                              "ir_profile":"1",
                                                                              "ir_report_time":"1",
                                                                              "rf_report_time":"2",
                                                                              "profile_type": "1"

                                                                        }
                                                                        }
                                                                        '''
    TCP.send_message(user_message)
    time.sleep(3)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(5)
    sender.send_command(tag11_id, 0x5, 1)
    time.sleep(2)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(25)
    json_request = """gettagprofile
                        {
                            "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
                            "tag_id": "17684982"
                        }
                        """
    expected_values = {
        "tag_id": "17684982",
        "profile_type": "1"
    }
    a = TCP.validate_tag_profile(json_request, expected_values)
    b = get_tester_feedback("Does Tag configured with Custom profile option ?")
    result = a & b

    if result:
        print("Profile_04 Test PASS")
        Output(f"Iteration{i}: Profile_04 Test PASS")
        Report("Profile_04", 1)
    else:
        print("Profile_04 Test FAIL.")
        Output(f"Iteration{i}: Profile_04 Test FAIL")
        Report("Profile_04", 0)
    print("Please make sure Tag profile is selected as Custom profile")


    # ******************************************************************************************************************
    print("Executing Profile_05 : To Validate enabling Predefined tag profile")
    user_message = '''settagprofile

                                                                            {

                                                                            deviceprofile:

                                                                            {

                                                                            "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                                            "device_type":"1",
                                                                                  "device_category":"41 - [Andromeda Staff Tag]",
                                                                                  "profile_type":"1",
                                                                                  "tagcategory":"0",
                                                                                  "model_type":"2",
                                                                                  "tag_id":"17684982",
                                                                                  "profile":"0",
                                                                                  "ir_profile":"1",
                                                                                  "ir_report_time":"1",
                                                                                  "rf_report_time":"2",
                                                                                  "profile_type": "0"

                                                                            }
                                                                            }
                                                                            '''
    TCP.send_message(user_message)
    time.sleep(3)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(5)
    sender.send_command(tag11_id, 0x5, 1)
    time.sleep(2)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(25)
    json_request = """gettagprofile
                            {
                                "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
                                "tag_id": "17684982"
                            }
                            """
    expected_values = {
        "tag_id": "17684982",
        "profile_type": "0"
    }

    a = TCP.validate_tag_profile(json_request, expected_values)
    b = get_tester_feedback("Does Tag profile is selected as Predefined tag profile in Core Live ?")
    result = a&b

    if result:
        print("Profile_05 Test PASS")
        Output(f"Iteration{i}: Profile_05 Test PASS")
        Report("Profile_05", 1)
    else:
        print("Profile_05 Test FAIL.")
        Output(f"Iteration{i}: Profile_05 Test FAIL")
        Report("Profile_05", 0)
    print("Please make sure Tag profile is selected as Predefined tag profile in Core Live")

    # ******************************************************************************************************************
    print("Executing Profile_06 : To Validate Tag operating mode as UHF only mode")
    user_message = '''settagprofile

                                                                                {

                                                                                deviceprofile:

                                                                                {

                                                                                "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                                                "device_type":"1",
                                                                                      "device_category":"41 - [Andromeda Staff Tag]",
                                                                                      "profile_type":"1",
                                                                                      "tagcategory":"0",
                                                                                      "model_type":"2",
                                                                                      "tag_id":"17684982",
                                                                                      "profile":"0",
                                                                                      "ir_profile":"1",
                                                                                      "ir_report_time":"1",
                                                                                      "rf_report_time":"2",
                                                                                      "operating_mode": "0"

                                                                                }
                                                                                }
                                                                                '''
    TCP.send_message(user_message)
    time.sleep(3)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(5)
    sender.send_command(tag11_id, 0x5, 1)
    time.sleep(2)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(25)
    json_request = """gettagprofile
                                {
                                    "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
                                    "tag_id": "17684982"
                                }
                                """
    expected_values = {
        "tag_id": "17684982",
        "operating_mode": "0"
    }

    a = TCP.validate_tag_profile(json_request, expected_values)
    b = get_tester_feedback("Does Tag Operating mode is UHF only in Core Live ?")
    result = a & b

    if result:
        print("Profile_06 Test PASS")
        Output(f"Iteration{i}: Profile_06 Test PASS")
        Report("Profile_06", 1)
    else:
        print("Profile_06 Test FAIL.")
        Output(f"Iteration{i}: Profile_06 Test FAIL")
        Report("Profile_06", 0)

    # ******************************************************************************************************************
    print("Executing Profile_07 : To Validate Tag operating mode as UHF/BLE mode")
    user_message = '''settagprofile

                                                                                                {

                                                                                                deviceprofile:

                                                                                                {

                                                                                                "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                                                                "device_type":"1",
                                                                                                      "device_category":"41 - [Andromeda Staff Tag]",
                                                                                                      "profile_type":"1",
                                                                                                      "tagcategory":"0",
                                                                                                      "model_type":"2",
                                                                                                      "tag_id":"17684982",
                                                                                                      "profile":"0",
                                                                                                      "ir_profile":"1",
                                                                                                      "ir_report_time":"1",
                                                                                                      "rf_report_time":"2",
                                                                                                      "operating_mode": "1"

                                                                                                }
                                                                                                }
                                                                                                '''
    TCP.send_message(user_message)
    time.sleep(3)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(5)
    sender.send_command(tag11_id, 0x5, 1)
    time.sleep(2)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(25)
    json_request = """gettagprofile
                                                    {
                                                        "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
                                                        "tag_id": "17684982"
                                                    }
                                                    """
    expected_values = {
        "tag_id": "17684982",
        "operating_mode": "1"
    }

    a = TCP.validate_tag_profile(json_request, expected_values)
    b = get_tester_feedback("Does Tag Operating mode is BLE/UHF mode in Core Live ?")
    result = a & b

    if result:
        print("Profile_07 Test PASS")
        Output(f"Iteration{i}: Profile_07 Test PASS")
        Report("Profile_07", 1)
    else:
        print("Profile_07 Test FAIL.")
        Output(f"Iteration{i}: Profile_07 Test FAIL")
        Report("Profile_07", 0)


    # ******************************************************************************************************************
    print("Executing Profile_08 : To Validate Tag operating mode as BLE only mode")
    user_message = '''settagprofile

                                                                                                {

                                                                                                deviceprofile:

                                                                                                {

                                                                                                "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                                                                "device_type":"1",
                                                                                                      "device_category":"41 - [Andromeda Staff Tag]",
                                                                                                      "profile_type":"1",
                                                                                                      "tagcategory":"0",
                                                                                                      "model_type":"2",
                                                                                                      "tag_id":"17684982",
                                                                                                      "profile":"0",
                                                                                                      "ir_profile":"1",
                                                                                                      "ir_report_time":"1",
                                                                                                      "rf_report_time":"2",
                                                                                                      "operating_mode": "2"

                                                                                                }
                                                                                                }
                                                                                                '''
    TCP.send_message(user_message)
    time.sleep(3)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(5)
    sender.send_command(tag11_id, 0x5, 1)
    time.sleep(2)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(25)
    json_request = """gettagprofile
                                                    {
                                                        "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
                                                        "tag_id": "17684982"
                                                    }
                                                    """
    expected_values = {
        "tag_id": "17684982",
        "operating_mode": "2"
    }

    a = TCP.validate_tag_profile(json_request, expected_values)
    b = get_tester_feedback("Does Tag Operating mode is BLE only mode in Core Live ?")
    result = a & b

    if result:
        print("Profile_08 Test PASS")
        Output(f"Iteration{i}: Profile_08 Test PASS")
        Report("Profile_08", 1)
    else:
        print("Profile_08 Test FAIL.")
        Output(f"Iteration{i}: Profile_08 Test FAIL")
        Report("Profile_08", 0)

    user_message = '''settagprofile

                                                                                {

                                                                                deviceprofile:

                                                                                {

                                                                                "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                                                "device_type":"1",
                                                                                      "device_category":"41 - [Andromeda Staff Tag]",
                                                                                      "profile_type":"1",
                                                                                      "tagcategory":"0",
                                                                                      "model_type":"2",
                                                                                      "tag_id":"17684982",
                                                                                      "profile":"0",
                                                                                      "ir_profile":"1",
                                                                                      "ir_report_time":"1",
                                                                                      "rf_report_time":"2",
                                                                                      "operating_mode": "0"

                                                                                }
                                                                                }
                                                                                '''
    TCP.send_message(user_message)
    time.sleep(3)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(5)
    get_tester_feedback("Now tag switches to BLE mode only please connect to tag via Andromeda mobile app and set operating mode as UHF only to proceed with test")

    # ******************************************************************************************************************
    print("Executing Profile_09 : To Validate Tag IR RX profile '1' ")
    user_message = '''settagprofile

                                                                                {

                                                                                deviceprofile:

                                                                                {

                                                                                "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                                                "device_type":"1",
                                                                                      "device_category":"41 - [Andromeda Staff Tag]",
                                                                                      "profile_type":"1",
                                                                                      "tagcategory":"0",
                                                                                      "model_type":"2",
                                                                                      "tag_id":"17684982",
                                                                                      "profile":"0",
                                                                                      "ir_profile":"1",
                                                                                      "ir_report_time":"1",
                                                                                      "rf_report_time":"2",
                                                                                      "ir_rx_profile": "1"

                                                                                }
                                                                                }
                                                                                '''
    TCP.send_message(user_message)
    time.sleep(3)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(5)
    sender.send_command(tag11_id, 0x5, 1)
    time.sleep(2)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(25)
    json_request = """gettagprofile
                                {
                                    "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
                                    "tag_id": "17684982"
                                }
                                """
    expected_values = {
        "tag_id": "17684982",
        "ir_rx_profile": "1"
    }

    a = TCP.validate_tag_profile(json_request, expected_values)
    b = get_tester_feedback("Does Tag conifgured with IR Rx profile as 1 in Core Live ?")
    result = a & b

    if result:
        print("Profile_09 Test PASS")
        Output(f"Iteration{i}: Profile_09 Test PASS")
        Report("Profile_09", 1)
    else:
        print("Profile_09 Test FAIL.")
        Output(f"Iteration{i}: Profile_09 Test FAIL")
        Report("Profile_09", 0)

    # ******************************************************************************************************************
    print("Executing Profile_10 : To Validate configuring Tag Active paging rate 12.5 sec  ")
    user_message = '''settagprofile

                                                                                {

                                                                                deviceprofile:

                                                                                {

                                                                                "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                                                "device_type":"1",
                                                                                      "device_category":"41 - [Andromeda Staff Tag]",
                                                                                      "profile_type":"1",
                                                                                      "tagcategory":"0",
                                                                                      "model_type":"2",
                                                                                      "tag_id":"17684982",
                                                                                      "profile":"0",
                                                                                      "ir_profile":"1",
                                                                                      "ir_report_time":"1",
                                                                                      "rf_report_time":"2",
                                                                                      "paging_profile": "0"

                                                                                }
                                                                                }
                                                                                '''
    TCP.send_message(user_message)
    time.sleep(3)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(5)
    sender.send_command(tag11_id, 0x5, 1)
    time.sleep(2)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(25)
    json_request = """gettagprofile
                                {
                                    "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
                                    "tag_id": "17684982"
                                }
                                """
    expected_values = {
        "tag_id": "17684982",
        "paging_profile": "0"
    }

    a = TCP.validate_tag_profile(json_request, expected_values)
    b = get_tester_feedback("Does Tag conifgured with Active paging rate as  in Core Live 12.5 sec ?")
    result = a & b

    if result:
        print("Profile_10 Test PASS")
        Output(f"Iteration{i}: Profile_10 Test PASS")
        Report("Profile_10", 1)
    else:
        print("Profile_10 Test FAIL.")
        Output(f"Iteration{i}: Profile_10 Test FAIL")
        Report("Profile_10", 0)


    # ******************************************************************************************************************
    print("Executing Profile_11 : To Validate configuring Tag Active paging rate 9.5 sec  ")
    user_message = '''settagprofile

                                                                                {

                                                                                deviceprofile:

                                                                                {

                                                                                "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                                                "device_type":"1",
                                                                                      "device_category":"41 - [Andromeda Staff Tag]",
                                                                                      "profile_type":"1",
                                                                                      "tagcategory":"0",
                                                                                      "model_type":"2",
                                                                                      "tag_id":"17684982",
                                                                                      "profile":"0",
                                                                                      "ir_profile":"1",
                                                                                      "ir_report_time":"1",
                                                                                      "rf_report_time":"2",
                                                                                      "paging_profile": "1"

                                                                                }
                                                                                }
                                                                                '''
    TCP.send_message(user_message)
    time.sleep(3)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(5)
    sender.send_command(tag11_id, 0x5, 1)
    time.sleep(2)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(25)
    json_request = """gettagprofile
                                {
                                    "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
                                    "tag_id": "17684982"
                                }
                                """
    expected_values = {
        "tag_id": "17684982",
        "paging_profile": "1"
    }

    a = TCP.validate_tag_profile(json_request, expected_values)
    b = get_tester_feedback("Does Tag conifgured with Active paging rate as  in Core Live 9.5 sec ?")
    result = a & b

    if result:
        print("Profile_11 Test PASS")
        Output(f"Iteration{i}: Profile_11 Test PASS")
        Report("Profile_11", 1)
    else:
        print("Profile_11 Test FAIL.")
        Output(f"Iteration{i}: Profile_11 Test FAIL")
        Report("Profile_11", 0)

    # ******************************************************************************************************************
    print("Executing Profile_12 : To Validate configuring Tag Active paging rate 6.5 sec  ")
    user_message = '''settagprofile

                                                                                {

                                                                                deviceprofile:

                                                                                {

                                                                                "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                                                "device_type":"1",
                                                                                      "device_category":"41 - [Andromeda Staff Tag]",
                                                                                      "profile_type":"1",
                                                                                      "tagcategory":"0",
                                                                                      "model_type":"2",
                                                                                      "tag_id":"17684982",
                                                                                      "profile":"0",
                                                                                      "ir_profile":"1",
                                                                                      "ir_report_time":"1",
                                                                                      "rf_report_time":"2",
                                                                                      "paging_profile": "2"

                                                                                }
                                                                                }
                                                                                '''
    TCP.send_message(user_message)
    time.sleep(3)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(5)
    sender.send_command(tag11_id, 0x5, 1)
    time.sleep(2)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(25)
    json_request = """gettagprofile
                                {
                                    "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
                                    "tag_id": "17684982"
                                }
                                """
    expected_values = {
        "tag_id": "17684982",
        "paging_profile": "2"
    }

    a = TCP.validate_tag_profile(json_request, expected_values)
    b = get_tester_feedback("Does Tag conifgured with Active paging rate as  in Core Live 6.5 sec ?")
    result = a & b

    if result:
        print("Profile_12 Test PASS")
        Output(f"Iteration{i}: Profile_12 Test PASS")
        Report("Profile_12", 1)
    else:
        print("Profile_12 Test FAIL.")
        Output(f"Iteration{i}: Profile_12 Test FAIL")
        Report("Profile_12", 0)

    # ******************************************************************************************************************
    print("Executing Profile_13 : To Validate configuring Tag Active paging rate 24.5 sec  ")
    user_message = '''settagprofile

                                                                                {

                                                                                deviceprofile:

                                                                                {

                                                                                "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                                                "device_type":"1",
                                                                                      "device_category":"41 - [Andromeda Staff Tag]",
                                                                                      "profile_type":"1",
                                                                                      "tagcategory":"0",
                                                                                      "model_type":"2",
                                                                                      "tag_id":"17684982",
                                                                                      "profile":"0",
                                                                                      "ir_profile":"1",
                                                                                      "ir_report_time":"1",
                                                                                      "rf_report_time":"2",
                                                                                      "paging_profile": "3"

                                                                                }
                                                                                }
                                                                                '''
    TCP.send_message(user_message)
    time.sleep(3)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(5)
    sender.send_command(tag11_id, 0x5, 1)
    time.sleep(2)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(25)
    json_request = """gettagprofile
                                {
                                    "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
                                    "tag_id": "17684982"
                                }
                                """
    expected_values = {
        "tag_id": "17684982",
        "paging_profile": "3"
    }

    a = TCP.validate_tag_profile(json_request, expected_values)
    b = get_tester_feedback("Does Tag conifgured with Active paging rate as  in Core Live 24.5 sec ?")
    result = a & b

    if result:
        print("Profile_13 Test PASS")
        Output(f"Iteration{i}: Profile_13 Test PASS")
        Report("Profile_13", 1)
    else:
        print("Profile_13 Test FAIL.")
        Output(f"Iteration{i}: Profile_13 Test FAIL")
        Report("Profile_13", 0)


    # ******************************************************************************************************************
    print("Executing Profile_14 : To Validate disabling tag LF RX  ")
    user_message = '''settagprofile

                                                                                {

                                                                                deviceprofile:

                                                                                {

                                                                                "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                                                "device_type":"1",
                                                                                      "device_category":"41 - [Andromeda Staff Tag]",
                                                                                      "profile_type":"1",
                                                                                      "tagcategory":"0",
                                                                                      "model_type":"2",
                                                                                      "tag_id":"17684982",
                                                                                      "profile":"0",
                                                                                      "ir_profile":"1",
                                                                                      "ir_report_time":"1",
                                                                                      "rf_report_time":"2",
                                                                                      "enable_lf": "0"

                                                                                }
                                                                                }
                                                                                '''
    TCP.send_message(user_message)
    time.sleep(3)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(5)
    sender.send_command(tag11_id, 0x5, 1)
    time.sleep(2)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(25)
    json_request = """gettagprofile
                                {
                                    "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
                                    "tag_id": "17684982"
                                }
                                """
    expected_values = {
        "tag_id": "17684982",
        "enable_lf": "0"
    }

    a = TCP.validate_tag_profile(json_request, expected_values)
    b = get_tester_feedback("Does Tag LF RX disabled in Core Live ?")
    result = a & b

    if result:
        print("Profile_14 Test PASS")
        Output(f"Iteration{i}: Profile_14 Test PASS")
        Report("Profile_14", 1)
    else:
        print("Profile_14 Test FAIL.")
        Output(f"Iteration{i}: Profile_14 Test FAIL")
        Report("Profile_14", 0)

    # ******************************************************************************************************************
    print("Executing Profile_15 : To Validate enabling tag LF RX  ")
    user_message = '''settagprofile

                                                                                {

                                                                                deviceprofile:

                                                                                {

                                                                                "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                                                "device_type":"1",
                                                                                      "device_category":"41 - [Andromeda Staff Tag]",
                                                                                      "profile_type":"1",
                                                                                      "tagcategory":"0",
                                                                                      "model_type":"2",
                                                                                      "tag_id":"17684982",
                                                                                      "profile":"0",
                                                                                      "ir_profile":"1",
                                                                                      "ir_report_time":"1",
                                                                                      "rf_report_time":"2",
                                                                                      "enable_lf": "1"

                                                                                }
                                                                                }
                                                                                '''
    TCP.send_message(user_message)
    time.sleep(3)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(5)
    sender.send_command(tag11_id, 0x5, 1)
    time.sleep(2)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(25)
    json_request = """gettagprofile
                                {
                                    "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
                                    "tag_id": "17684982"
                                }
                                """
    expected_values = {
        "tag_id": "17684982",
        "enable_lf": "1"
    }

    a = TCP.validate_tag_profile(json_request, expected_values)
    b = get_tester_feedback("Does Tag LF RX Enabled in Core Live  ?")
    result = a & b

    if result:
        print("Profile_15 Test PASS")
        Output(f"Iteration{i}: Profile_15 Test PASS")
        Report("Profile_15", 1)
    else:
        print("Profile_15 Test FAIL.")
        Output(f"Iteration{i}: Profile_15 Test FAIL")
        Report("Profile_15", 0)

    # ******************************************************************************************************************
    print("Executing Profile_16 : To Validate Enabling LF Exciter alert  ")
    user_message = '''settagprofile

                                                                                {

                                                                                deviceprofile:

                                                                                {

                                                                                "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                                                "device_type":"1",
                                                                                      "device_category":"41 - [Andromeda Staff Tag]",
                                                                                      "profile_type":"1",
                                                                                      "tagcategory":"0",
                                                                                      "model_type":"2",
                                                                                      "tag_id":"17684982",
                                                                                      "profile":"0",
                                                                                      "ir_profile":"1",
                                                                                      "ir_report_time":"1",
                                                                                      "rf_report_time":"2",
                                                                                      "enable_lf_exciter_alert": "1"

                                                                                }
                                                                                }
                                                                                '''
    TCP.send_message(user_message)
    time.sleep(3)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(5)
    sender.send_command(tag11_id, 0x5, 1)
    time.sleep(2)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(25)
    json_request = """gettagprofile
                                {
                                    "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
                                    "tag_id": "17684982"
                                }
                                """
    expected_values = {
        "tag_id": "17684982",
        "enable_lf_exciter_alert": "1"
    }

    a = TCP.validate_tag_profile(json_request, expected_values)
    b = get_tester_feedback("Does Tag LF Exciter alert enabled Core Live ?")
    result = a & b

    if result:
        print("Profile_16 Test PASS")
        Output(f"Iteration{i}: Profile_16 Test PASS")
        Report("Profile_16", 1)
    else:
        print("Profile_16 Test FAIL.")
        Output(f"Iteration{i}: Profile_16 Test FAIL")
        Report("Profile_16", 0)

    # ******************************************************************************************************************
    print("Executing Profile_17 : To Validate disabling LF Exciter alert  ")
    user_message = '''settagprofile

                                                                                {

                                                                                deviceprofile:

                                                                                {

                                                                                "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                                                "device_type":"1",
                                                                                      "device_category":"41 - [Andromeda Staff Tag]",
                                                                                      "profile_type":"1",
                                                                                      "tagcategory":"0",
                                                                                      "model_type":"2",
                                                                                      "tag_id":"17684982",
                                                                                      "profile":"0",
                                                                                      "ir_profile":"1",
                                                                                      "ir_report_time":"1",
                                                                                      "rf_report_time":"2",
                                                                                      "enable_lf_exciter_alert": "0"

                                                                                }
                                                                                }
                                                                                '''
    TCP.send_message(user_message)
    time.sleep(3)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(5)
    sender.send_command(tag11_id, 0x5, 1)
    time.sleep(2)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(25)
    json_request = """gettagprofile
                                {
                                    "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
                                    "tag_id": "17684982"
                                }
                                """
    expected_values = {
        "tag_id": "17684982",
        "enable_lf_exciter_alert": "0"
    }

    a = TCP.validate_tag_profile(json_request, expected_values)
    b = get_tester_feedback("Does LF Exciter alert disabled in Core Live  ?")
    result = a & b

    if result:
        print("Profile_17 Test PASS")
        Output(f"Iteration{i}: Profile_17 Test PASS")
        Report("Profile_17", 1)
    else:
        print("Profile_17 Test FAIL.")
        Output(f"Iteration{i}: Profile_17 Test FAIL")
        Report("Profile_17", 0)

    # ******************************************************************************************************************
    print("Executing Profile_18 : To Validate Enabling LF alert  ")
    user_message = '''settagprofile

                                                                                {

                                                                                deviceprofile:

                                                                                {

                                                                                "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                                                "device_type":"1",
                                                                                      "device_category":"41 - [Andromeda Staff Tag]",
                                                                                      "profile_type":"1",
                                                                                      "tagcategory":"0",
                                                                                      "model_type":"2",
                                                                                      "tag_id":"17684982",
                                                                                      "profile":"0",
                                                                                      "ir_profile":"1",
                                                                                      "ir_report_time":"1",
                                                                                      "rf_report_time":"2",
                                                                                      "enable_lf_alert": "1"

                                                                                }
                                                                                }
                                                                                '''
    TCP.send_message(user_message)
    time.sleep(3)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(5)
    sender.send_command(tag11_id, 0x5, 1)
    time.sleep(2)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(25)
    json_request = """gettagprofile
                                {
                                    "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
                                    "tag_id": "17684982"
                                }
                                """
    expected_values = {
        "tag_id": "17684982",
        "enable_lf_alert": "1"
    }

    a = TCP.validate_tag_profile(json_request, expected_values)
    b = get_tester_feedback("Does Tag LF alert enabled Core Live ?")
    result = a & b

    if result:
        print("Profile_18 Test PASS")
        Output(f"Iteration{i}: Profile_18 Test PASS")
        Report("Profile_18", 1)
    else:
        print("Profile_18 Test FAIL.")
        Output(f"Iteration{i}: Profile_18 Test FAIL")
        Report("Profile_18", 0)

    # ******************************************************************************************************************
    print("Executing Profile_19 : To Validate disabling LF alert  ")
    user_message = '''settagprofile

                                                                                {

                                                                                deviceprofile:

                                                                                {

                                                                                "centrak_guid":"9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",

                                                                                "device_type":"1",
                                                                                      "device_category":"41 - [Andromeda Staff Tag]",
                                                                                      "profile_type":"1",
                                                                                      "tagcategory":"0",
                                                                                      "model_type":"2",
                                                                                      "tag_id":"17684982",
                                                                                      "profile":"0",
                                                                                      "ir_profile":"1",
                                                                                      "ir_report_time":"1",
                                                                                      "rf_report_time":"2",
                                                                                      "enable_lf_alert": "0"

                                                                                }
                                                                                }
                                                                                '''
    TCP.send_message(user_message)
    time.sleep(3)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(5)
    sender.send_command(tag11_id, 0x5, 1)
    time.sleep(2)
    process.serial_conn.send_command("servo1.start")
    time.sleep(2)
    process.serial_conn.send_command("servo1.stop")
    time.sleep(25)
    json_request = """gettagprofile
                                {
                                    "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
                                    "tag_id": "17684982"
                                }
                                """
    expected_values = {
        "tag_id": "17684982",
        "enable_lf_alert": "0"
    }

    a = TCP.validate_tag_profile(json_request, expected_values)
    b = get_tester_feedback("Does LF alert disabled in Core Live  ?")
    result = a & b

    if result:
        print("Profile_19 Test PASS")
        Output(f"Iteration{i}: Profile_19 Test PASS")
        Report("Profile_19", 1)
    else:
        print("Profile_19 Test FAIL.")
        Output(f"Iteration{i}: Profile_19 Test FAIL")
        Report("Profile_19", 0)

    # ******************************************************************************************************************
    print("Executing Fsleep_01 : To Validate tag factory sleep entry through Long key press.  ")

    print("Please make sure Tag has been flashed before executing this test case  ")

    time.sleep(3)
    process.serial_conn.send_command("tag1akey1")
    time.sleep((10))

    # Example of calling the API function
    expected_values = {
        'Tag ID': tag1_id,
        'Button 4': '0',
        'Button 3': '0',
        'Button 2': '0',
        'Button 1': '1'
    }

    result = process.button_api(serial_message="tag1skey1", expected_values=expected_values)
    if result:
        print("Packet validation successful.")
        Report("Fsleep_01", 0)
        Output(f"Iteration{i}: Fsleep_01 Test FAIL")
    else:
        print("Packet validation failed.")
        Report("Fsleep_01", 1)
        Output(f"Iteration{i}: Fsleep_01 Test PASS")


    # ******************************************************************************************************************
    print("Executing Fsleep_02 : To Validate tag factory sleep EXIT through Long key press.  ")

    print("Please make sure Tag has been put in factory sleep before executing this test case  ")

    time.sleep(3)
    process.serial_conn.send_command("tag1akey1")
    time.sleep((10))

    # Example of calling the API function
    expected_values = {
        'Tag ID': tag1_id,
        'Button 4': '0',
        'Button 3': '0',
        'Button 2': '0',
        'Button 1': '1'
    }

    result = process.button_api(serial_message="tag1skey1", expected_values=expected_values)
    if result:
        print("Packet validation successful.")
        Report("Fsleep_02", 1)
        Output(f"Iteration{i}: Fsleep_02 Test PASS")
    else:
        print("Packet validation failed.")
        Report("Fsleep_02", 0)
        Output(f"Iteration{i}: Fsleep_02 Test FAIL")



    # ******************************************************************************************************************
    print("Executing Fsleep_03 : To Validate tag not enters into factory once it exits factory sleep through Long key press.  ")

    print("Please make sure Tag exited factory sleep before executing this test case  ")


    time.sleep((10))

    # Example of calling the API function
    expected_values = {
        'Tag ID': tag1_id,
        'Button 4': '0',
        'Button 3': '0',
        'Button 2': '0',
        'Button 1': '0',
        'EKEY': 9

    }

    result = process.button_api(serial_message="tag1akey1", expected_values=expected_values)
    if result:
        print("Packet validation successful.")
        Report("Fsleep_03", 1)
        Output(f"Iteration{i}: Fsleep_03 Test PASS")
    else:
        print("Packet validation failed.")
        Report("Fsleep_03", 0)
        Output(f"Iteration{i}: Fsleep_03 Test FAIL")


    # ******************************************************************************************************************
    print("Executing Fsleep_04 : To Validate tag factory sleep entry through LFID 430.  ")

    # We setup LF ID to 10 to avoid tags accidental entry into factory sleep
    json_request = '''setmonitorprofile
        {
        deviceprofile:
         {

        "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
        "monitor_id":"2624252",
        "device_type":"2 - [LF Exciter]",
        "monitor_type":"6",
        "lf_id":"10"


    }
    }
    '''
    TCP.send_message(json_request)
    get_tester_feedback("Please make sure Tag has been flashed before executing this test case yes/no ")
    time.sleep(15)
    json_request = '''setmonitorprofile
        {
        deviceprofile:
         {

        "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
        "monitor_id":"2624252",
        "device_type":"2 - [LF Exciter]",
        "monitor_type":"6",
        "lf_id":"430"


    }
    }
    '''
    TCP.send_message(json_request)
    time.sleep(180)
    expected_values = {
    'Tag ID': tag1_id,
    'Button 4': '0',
    'Button 3': '0',
    'Button 2': '0',
    'Button 1': '1'
    }

    result = process.button_api(serial_message="tag1skey1", expected_values=expected_values)
    if result:
        print("Packet validation successful.")
        Report("Fsleep_04", 0)
        Output(f"Iteration{i}: Fsleep_04 Test FAIL")
    else:
        print("Packet validation failed.")
        Report("Fsleep_04", 1)
        Output(f"Iteration{i}: Fsleep_04 Test PASS")
    json_request = '''setmonitorprofile
            {
            deviceprofile:
             {

            "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
            "monitor_id":"2624252",
            "device_type":"2 - [LF Exciter]",
            "monitor_type":"6",
            "lf_id":"10"


        }
        }
        '''
    TCP.send_message(json_request)

    # ******************************************************************************************************************
    print("Executing Fsleep_05 : To Validate tag factory sleep exit through LFID 1111.  ")
    json_request = '''setmonitorprofile
            {
            deviceprofile:
             {

            "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
            "monitor_id":"2624252",
            "device_type":"2 - [LF Exciter]",
            "monitor_type":"6",
            "lf_id":"1111"


        }
        }
        '''
    TCP.send_message(json_request)
    print("Waiting for Tag to exit Factory sleep mode by LFID 1111")
    time.sleep(150)
    result = process.button_api(serial_message="tag1skey1", expected_values=expected_values)
    if result:
        print("Packet validation successful.")
        Report("Fsleep_05", 1)
        Output(f"Iteration{i}: Fsleep_05 Test PASS")
    else:
        print("Packet validation failed.")
        Report("Fsleep_05", 0)
        Output(f"Iteration{i}: Fsleep_05 Test FAIL")

    json_request = '''setmonitorprofile
            {
            deviceprofile:
             {

            "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
            "monitor_id":"2624252",
            "device_type":"2 - [LF Exciter]",
            "monitor_type":"6",
            "lf_id":"11"


        }
        }
        '''
    TCP.send_message(json_request)

    # ******************************************************************************************************************
    print("Executing Isleep_01 : To Validate tag Inventory sleep sleep EXIT through Long key press.  ")

    get_tester_feedback("Please make sure Tag has been put in Inventory sleep before executing this test case yes/no ")

    time.sleep(3)
    process.serial_conn.send_command("tag1akey1")
    time.sleep((15))

    # Example of calling the API function
    expected_values = {
        'Tag ID': tag1_id,
        'Button 4': '0',
        'Button 3': '0',
        'Button 2': '0',
        'Button 1': '1'
    }

    result = process.button_api(serial_message="tag1skey1", expected_values=expected_values)
    if result:
        print("Packet validation successful.")
        Report("Isleep_02", 1)
        Output(f"Iteration{i}: Isleep_02 Test PASS")
    else:
        print("Packet validation failed.")
        Report("Isleep_02", 0)
        Output(f"Iteration{i}: Isleep_02 Test FAIL")

    # ******************************************************************************************************************
    print("Executing Isleep_02 : To Validate tag Inventory sleep exit through LFID 1111.  ")
    json_request = '''setmonitorprofile
            {
            deviceprofile:
             {

            "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
            "monitor_id":"2624252",
            "device_type":"2 - [LF Exciter]",
            "monitor_type":"6",
            "lf_id":"1111"


        }
        }
        '''
    TCP.send_message(json_request)
    print("Waiting for Tag to exit Inventory sleep mode by LFID 1111")
    time.sleep(150)
    expected_values = {
    'Tag ID': tag1_id,
    'Button 4': '0',
    'Button 3': '0',
    'Button 2': '0',
    'Button 1': '1'
    }
    result = process.button_api(serial_message="tag1skey1", expected_values=expected_values)
    if result:
        print("Packet validation successful.")
        Report("Isleep_02", 1)
        Output(f"Iteration{i}: Isleep_02 Test PASS")
    else:
        print("Packet validation failed.")
        Report("Isleep_02", 0)
        Output(f"Iteration{i}: Isleep_02 Test FAIL")

    json_request = '''setmonitorprofile
            {
            deviceprofile:
             {

            "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
            "monitor_id":"2624252",
            "device_type":"2 - [LF Exciter]",
            "monitor_type":"6",
            "lf_id":"11"


        }
        }
        '''
    TCP.send_message(json_request)

    json_request = '''Setmonitorprofile
    {
    "deviceprofile": {
        "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
        "device_type": "2 - [Dual IR Monitor]",
        "monitor_type": "4",
        "monitor_id": "8465776",
        "ir_id": "5",
        "power_level": "1"

    }
    }
    '''
    TCP.send_message(json_request)
    time.sleep(5)
    json_request = '''Setmonitorprofile
    {
    "deviceprofile": {
        "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
        "device_type": "2 - [Dual IR Monitor]",
        "monitor_type": "4",
        "monitor_id": "8463991",
        "ir_id": "20",
        "power_level": "0"

    }
    }
    '''
    TCP.send_message(json_request)
    time.sleep(20)
    # ******************************************************************************************************************
    print("Executing Location_01 : To validate Location packet ")
    logging.info("Executing Location_01 : To validate Location packet \n ")
    time.sleep(3)
    expected_values = {
        'Tag ID': tag11_id,
        'Motion Flag': '1',
        'Monitor ID': 8449603,

        'IR ID': 5,
        'LF Flag': 2
    }

    a  = process.Location_api(serial_message="servo1.start", expected_values=expected_values)
    process.serial_conn.send_command("servo1.stop")
    json_request = '''Setmonitorprofile
        {
        "deviceprofile": {
            "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
            "device_type": "2 - [Dual IR Monitor]",
            "monitor_type": "4",
            "monitor_id": "8465776",
            "ir_id": "6",
            "power_level": "1"

        }
        }
        '''
    TCP.send_message(json_request)
    time.sleep(20)
    expected_values = {
        'Tag ID': tag11_id,
        'Motion Flag': '1',
        'Monitor ID': 8449603,

        'IR ID': 6,
        'LF Flag': 2
    }
    b = process.Location_api(serial_message="servo1.start", expected_values=expected_values)
    process.serial_conn.send_command("servo1.stop")
    result = a & b
    if result:
        print("Packet validation successful.")
        Report("Location_01", 1)
        Output(f"Iteration{i}: Location_01 Test PASS")
    else:
        print("Packet validation failed.")
        Report("Location_01", 0)
        Output(f"Iteration{i}: Location_01 Test FAIL")
    json_request = '''Setmonitorprofile
        {
        "deviceprofile": {
            "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
            "device_type": "2 - [Dual IR Monitor]",
            "monitor_type": "4",
            "monitor_id": "8465776",
            "ir_id": "10",
            "power_level": "0"

        }
        }
        '''
    TCP.send_message(json_request)
    time.sleep(5)
    json_request = '''Setmonitorprofile
        {
        "deviceprofile": {
            "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
            "device_type": "2 - [Dual IR Monitor]",
            "monitor_type": "4",
            "monitor_id": "8463991",
            "ir_id": "20",
            "power_level": "1"

        }
        }
        '''
    TCP.send_message(json_request)
    time.sleep(20)
    # ******************************************************************************************************************
    print("Executing Location_02 : To validate Location change from Room1 to Room 2 packet ")
    logging.info("Executing Location_02 : To validate change from IR1 to IR2 \n ")
    time.sleep(3)
    expected_values = {
        'Tag ID': tag11_id,
        'Motion Flag': '1',
        'Monitor ID': 8449603,

        'IR ID': 20,
        'LF Flag': 2
    }

    a  = process.Location_api(serial_message="servo1.start", expected_values=expected_values)
    process.serial_conn.send_command("servo1.stop")
    json_request = '''Setmonitorprofile
        {
        "deviceprofile": {
            "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
            "device_type": "2 - [Dual IR Monitor]",
            "monitor_type": "4",
            "monitor_id": "8465776",
            "ir_id": "10",
            "power_level": "1"

        }
        }
        '''
    TCP.send_message(json_request)
    time.sleep(5)
    json_request = '''Setmonitorprofile
        {
        "deviceprofile": {
            "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
            "device_type": "2 - [Dual IR Monitor]",
            "monitor_type": "4",
            "monitor_id": "8463991",
            "ir_id": "20",
            "power_level": "0"

        }
        }
        '''
    TCP.send_message(json_request)
    time.sleep(20)
    expected_values = {
        'Tag ID': tag11_id,
        'Motion Flag': '1',
        'Monitor ID': 8449603,

        'IR ID': 10,
        'LF Flag': 2
    }
    b = process.Location_api(serial_message="servo1.start", expected_values=expected_values)
    process.serial_conn.send_command("servo1.stop")
    result = a & b
    if result:
        print("Packet validation successful.")
        Report("Location_02", 1)
        Output(f"Iteration{i}: Location_02 Test PASS")
    else:
        print("Packet validation failed.")
        Report("Location_02", 0)
        Output(f"Iteration{i}: Location_02 Test FAIL")

    TCP.send_message(json_request)
    time.sleep(5)
    json_request = '''Setmonitorprofile
        {
        "deviceprofile": {
            "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
            "device_type": "2 - [Dual IR Monitor]",
            "monitor_type": "4",
            "monitor_id": "8465776",
            "ir_id": "10",
            "power_level": "0"

        }
        }
        '''
    TCP.send_message(json_request)
    time.sleep(36)
    # ******************************************************************************************************************
    print("Executing Location_03 : To validate IR to No IR ")
    logging.info("Executing Location_03 : To validate IR to No IR \n ")
    time.sleep(3)
    expected_values = {
        'Tag ID': tag11_id,
        'Motion Flag': '1',
        'Monitor ID': 0,

        'IR ID': 0,
        'LF Flag': 2
    }

    result  = process.Location_api(serial_message="servo1.start", expected_values=expected_values)
    process.serial_conn.send_command("servo1.stop")
    if result:
        print("Packet validation successful.")
        Report("Location_03", 1)
        Output(f"Iteration{i}: Location_03 Test PASS")
    else:
        print("Packet validation failed.")
        Report("Location_03", 0)
        Output(f"Iteration{i}: Location_03 Test FAIL")


    json_request = '''Setmonitorprofile
    {
    "deviceprofile": {
        "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
        "device_type": "2 - [Dual IR Monitor]",
        "monitor_type": "4",
        "monitor_id": "8465776",
        "ir_id": "5",
        "power_level": "1"

    }
    }
    '''
    TCP.send_message(json_request)
    time.sleep(5)
    json_request = '''Setmonitorprofile
    {
    "deviceprofile": {
        "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
        "device_type": "2 - [Dual IR Monitor]",
        "monitor_type": "4",
        "monitor_id": "8463991",
        "ir_id": "20",
        "power_level": "0"

    }
    }
    '''
    TCP.send_message(json_request)
    time.sleep(20)
    # ******************************************************************************************************************
    print("Executing Location_04 : To validate IR to LF ")
    logging.info("Executing Location_04 : To validate IR to LF \n ")
    time.sleep(3)
    expected_values = {
        'Tag ID': tag11_id,
        'Motion Flag': '1',
        'Monitor ID': 8449603,

        'IR ID': 5,
        'LF Flag': 2
    }

    a  = process.Location_api(serial_message="servo1.start", expected_values=expected_values)
    process.serial_conn.send_command("servo1.stop")
    json_request = '''Setmonitorprofile
        {
        "deviceprofile": {
            "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
            "device_type": "2 - [Dual IR Monitor]",
            "monitor_type": "4",
            "monitor_id": "8465776",
            "ir_id": "5",
            "power_level": "0"

        }
        }
        '''
    TCP.send_message(json_request)
    time.sleep(32)
    process.serial_conn.send_command("lf1.on")
    time.sleep(30)
    expected_values = {
        'Tag ID': tag11_id,
        'Motion Flag': '1',
        'Monitor ID': 8449603,

        'IR ID': 11,
        'LF Flag': 3
    }
    b = process.Location_api(serial_message="servo1.start", expected_values=expected_values)
    process.serial_conn.send_command("servo1.stop")
    result = a & b
    if result:
        print("Packet validation successful.")
        Report("Location_04", 1)
        Output(f"Iteration{i}: Location_04 Test PASS")
    else:
        print("Packet validation failed.")
        Report("Location_04", 0)
        Output(f"Iteration{i}: Location_04 Test FAIL")

    process.serial_conn.send_command("lf1.off")
    time.sleep(32)
    json_request = '''Setmonitorprofile
        {
        "deviceprofile": {
            "centrak_guid": "9ab3e119-f7d2-42d1-9153-b2a6cb17ae5c",
            "device_type": "2 - [Dual IR Monitor]",
            "monitor_type": "4",
            "monitor_id": "8463991",
            "ir_id": "20",
            "power_level": "1"

        }
        }
        '''
    TCP.send_message(json_request)
    time.sleep(20)

    process.serial_conn.send_command("servo1.start")
    time.sleep(5)
    EXPECTED_VALUES = {
            'Tag ID': tag11_id,
            'Monitor ID': 8449603,
            'Button 4': '0',
            'Button 3': '0',
            'Button 2': '0',
            'Button 1': '0',
            'Motion Flag': '1',
            'Reserved': '0',
            'IR ID': 20,
            'Version': 28
        }
    expected_validation_count = 10
    expected_report_rate = 12
    Ctime = 130
    result = Report_processor.Intervals(Ctime, EXPECTED_VALUES, expected_validation_count, expected_report_rate)

    if result:
            print("Expected parameters matched!")
            Output(f"Iteration{i}: Location_05 Test PASS")
            Report("Location_05", 1)
    else:
            print("Expected parameters not matched.")
            Output(f"Iteration{i}: Location_05 Test FAIL")
            Report("Location_05", 0)
    process.serial_conn.send_command("servo1.stop")

