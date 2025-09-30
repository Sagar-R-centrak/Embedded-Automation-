import socket
import struct
import datetime
import time
import serial
# Set the serial port and baud rate
SERIAL_PORT = 'COM13'  # Replace with the correct port e.g., 'COM3'
BAUD_RATE = 9600      # Match this to the baud rate in the Arduino sketch
TIMEOUT = 1           # Timeout for reading from the serial port

LOG_FILE = "packet_intervals.log"
TOLERANCE_SECONDS = 5
EXPECTED_INTERVAL_SECONDS = 180

# Log intervals and timestamps
def log_intervals(timestamps, intervals):
    with open(LOG_FILE, "w") as log:
        log.write("Timestamp (UTC), Interval (seconds)\n")
        for i, timestamp in enumerate(timestamps[1:]):
            log.write(f"{timestamps[i+1]} UTC, {intervals[i]} seconds\n")
        print(f"Log written to {LOG_FILE}")
# Initialize the serial connection
def init_serial():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=TIMEOUT)
        if ser.isOpen():
            print(f"Connected to {SERIAL_PORT}")
        # Wait for Arduino to initialize
        time.sleep(2)
        return ser
    except serial.SerialException as e:
        print(f"Error opening serial port: {e}")
        return None

# Send command to Arduino
def send_command(ser, command):
    try:
        # Send the command
        ser.write(f"{command}\n".encode())  # Encode the string to bytes and send with newline
        print(f"Sent: {command}")

        # Read and display the response from Arduino
        time.sleep(1)  # Wait for response
        if ser.in_waiting > 0:
            response = ser.read(ser.in_waiting).decode('utf-8').strip()
            print(f"Arduino: {response}")
    except serial.SerialException as e:
        print(f"Error communicating with Arduino: {e}")

# Close serial connection
def close_serial(ser):
    if ser and ser.isOpen():
        ser.close()
        print("Serial connection closed.")
# Expected values for validation


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
    # Extract the timestamp from the packet
    time_stamp = int.from_bytes(packet[24:28], byteorder='little')
    # Convert to a timezone-aware UTC datetime
    readable_time = datetime.datetime.fromtimestamp(time_stamp, datetime.UTC)

    # Print decoded values
    print(f"Device Type: {'Tag' if device_type == 0x01 else 'Monitor'}")
    print(f"Tag ID: {tag_id}")
    print(f"RSSI: {rssi:.2f} dBm")
    print(f"Monitor ID: {monitor_id}")
    print(f"CMD: {cmd}")
    status_fields = decode_status_byte(status_byte)
    print(f"IR ID: {ir_id}")
    print(f"Version: {version}")
    print(f"Astar ID: {astar_id}")
    print(f"LBI: {lbi}")
    print(f"CMD3: {cmd3}")
    print(f"Timestamp: {readable_time}")

    return {
        'Tag ID': tag_id,
        'RSSI': rssi,
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
        'Timestamp': readable_time
    }

def validate_packet(decoded_packet):
    for key, expected_value in EXPECTED_VALUES.items():
        if decoded_packet.get(key) != expected_value:
            return 0
    return 1

def capture_packets():
    captured_packets = []
    timestamps = []
    intervals = []
    validation_count = 0

    start_time = time.time()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1', 7166))
        s.settimeout(30)  # Set a smaller timeout for individual receive attempts

        while time.time() - start_time < 21800:  # Capture for 1 hour (3600 seconds)
            try:
                packet, addr = s.recvfrom(1024)  # Receive packet
                print(f"Packet from {addr}")
                print(f"Raw Data: {packet.hex()}")
                captured_packets.append(packet)
            except socket.timeout:
                # Continue capturing after timeout without exiting the loop
                print("No packet received in the last 10 seconds, continuing capture...")

    for i in range(0, len(captured_packets) - 1, 2):  # Process packets in pairs
        combined_packet = captured_packets[i] + captured_packets[i + 1]
        if len(combined_packet) > 13:
            header = combined_packet[:13]
            data_length = decode_header(header)
            num_location_packets = data_length // 28

            for j in range(num_location_packets):
                start_idx = 13 + j * 28
                end_idx = start_idx + 28
                location_packet = combined_packet[start_idx:end_idx]

                decoded_packet = decode_location_packet(location_packet)

                if validate_packet(decoded_packet) == 1:
                    validation_count += 1
                    timestamps.append(decoded_packet['Timestamp'])  # Append UTC datetime

    # Calculate intervals between timestamps
    for k in range(1, len(timestamps)):
        interval = abs((timestamps[k] - timestamps[k - 1]).total_seconds())
        intervals.append(interval)

    # Log timestamps and intervals
    log_intervals(timestamps, intervals)
    report_rate = sum(intervals)/len(intervals)

    # Check if intervals are within tolerance
    for interval in intervals:
        if not (EXPECTED_INTERVAL_SECONDS - TOLERANCE_SECONDS <= interval <= EXPECTED_INTERVAL_SECONDS + TOLERANCE_SECONDS):
            print(f"Unexpected interval detected: {interval} seconds")
        else:
            print(f"Interval within tolerance: {interval} seconds")

    print(f"Validation count: {validation_count}")
    return validation_count,report_rate



EXPECTED_VALUES = {
                'Tag ID': 17686300,
                'Monitor ID': 8466264,
                'Button 4': '0',
                'Button 3': '0',
                'Button 2': '0',
                'Button 1': '0',
                'Motion Flag': '0',
                'Reserved': '0',
                'IR ID': 3,
                'Version': 15,
                'Astar ID': 40

            }
def main():
    for i in range(1):
        print("Iteration:",i+1)
        serial_conn = init_serial()

        if serial_conn:
            # Send commands to control the servos

            time.sleep(1)
            send_command(serial_conn, "key3")
            time.sleep(1)  # Allow time for the servo to move

            # Close the serial connection

        cnt,rate = capture_packets()
        print(cnt,rate)

        if (cnt == 73) & (rate == 300):
            print("Expected parameters matched!")
        else:
            print("Expected parameters not matched.")
        close_serial(serial_conn)
        print("Serial port closed")

if __name__ == "__main__":
    main()
