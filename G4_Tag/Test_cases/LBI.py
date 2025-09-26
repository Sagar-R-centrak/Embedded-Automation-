from UDP_API.UDP_stream_validation_API import PacketCapture
from Arduino_API.Arduino_serial_API import SerialConnection
import time

class MainProcess:
    def __init__(self):
        self.serial_conn = SerialConnection(port="COM11", baud_rate=9600)
        self.packet_capture = PacketCapture()
        print("Initializing serial connection...")
        self.serial_conn.init_serial()

    def button_api(self, serial_message, expected_values):


        print(f"Sending command '{serial_message}' to Arduino...")
        self.serial_conn.send_command(serial_message)

        print("Capturing packets...")
        self.packet_capture.capture()

        print("Processing and validating captured packets...")
        is_valid = self.packet_capture.process_packets(expected_values)
        self.serial_conn.send_command('servo1.stop')

        return is_valid

if __name__ == "__main__":
    process = MainProcess()
    print("Executing LBI : To validate LBI by short press ")
    time.sleep(10)
    expected_values = {
    'Tag ID': 17684992,
    'Button 4': '0',
    'Button 3': '0',
    'Button 2': '0',
    'Button 1': '1',
    'LBI': 2871
    }

    result = process.button_api(serial_message="tag1skey1", expected_values=expected_values)
    if result:
        print("Packet validation successful.")

    else:
        print("Packet validation failed.")

    process.serial_conn.close()