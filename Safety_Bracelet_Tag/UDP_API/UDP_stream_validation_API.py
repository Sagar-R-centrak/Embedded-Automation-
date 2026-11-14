import socket
import struct
import datetime
import time
import logging
import json

class PacketDecoder:
    @staticmethod
    def decode_header(header):
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

        return data_length

    @staticmethod
    def decode_status_byte(status_byte):
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
    def decode_location_packet(packet):
        device_type = packet[0]
        tag_id_raw = int.from_bytes(packet[1:5], byteorder='little')
        tag_id = tag_id_raw & 0x0FFFFFFF  # Remove the MSB nibble
        raw_rssi = packet[8]
        rssi = (raw_rssi - 256) / 2.0 - 78 if raw_rssi >= 128 else raw_rssi / 2.0 - 78
        monitor_id = int.from_bytes(packet[9:12], byteorder='little')
        cmd = packet[12]
        status_byte = packet[13]
        ir_id = struct.unpack('<H', packet[14:16])[0]
        version = packet[16]
        astar_id = struct.unpack('<H', packet[17:19])[0]
        lbi = struct.unpack('<H', packet[19:21])[0]
        cmd3 = packet[21:24].hex()
        time_stamp = int.from_bytes(packet[24:28], byteorder='little')
        readable_time = datetime.datetime.fromtimestamp(time_stamp, datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
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
    def __init__(self, host='127.0.0.1', port=7171, timeout=10):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.captured_packets = []

    def capture(self):
        start_time = time.time()

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

                if len(combined_packet) > 13:  # Ensure there is enough data for header
                    header = combined_packet[:13]
                    data_length = PacketDecoder.decode_header(header)

                    num_location_packets = data_length // 30
                    print(f"\nNumber of Location Packets: {num_location_packets}")

                    for j in range(num_location_packets):
                        start_idx = 13 + j * 30
                        end_idx = start_idx + 30
                        location_packet = combined_packet[start_idx:end_idx]

                        print(f"\nLocation Packet {j + 1}:")
                        decoded_packet = PacketDecoder.decode_location_packet(location_packet)

                        # Validate packet
                        validation_result = self.validate_packet(decoded_packet, expected_values)
                        if validation_result:
                            print("Expected parameters matched in this location packet!")
                            break
                    if validation_result:
                        break
                else:
                    print("Combined packet does not contain enough data for header and location packets.")
            i += 2

        return validation_result

#main code
class MainProcess:
    def __init__(self):
        self.packet_capture = PacketCapture()
        print("Initializing serial connection...")


    def button_api(self,expected_values):
        print("Capturing packets...")
        self.packet_capture.capture()

        print("Processing and validating captured packets...")
        is_valid = self.packet_capture.process_packets(expected_values)

        return is_valid
