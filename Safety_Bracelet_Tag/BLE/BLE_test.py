import socket
import struct
import time
import datetime
import logging
import subprocess
from Arduino_API.Arduino_serial_API import SerialConnection

class MainProcess:
    def __init__(self):
        self.serial_conn = SerialConnection(port="COM11", baud_rate=9600)
        print("Initializing serial connection...")
        self.serial_conn.init_serial()

    def send_cmd(self, serial_message):
        print(f"Sending command '{serial_message}' to Arduino...")
        self.serial_conn.send_command(serial_message)

TAG_FILTER = 17684992
MAC_FILTER = "00:00:00:00:00:00"
LOG_FILE = f"tag_{TAG_FILTER}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
DEFAULT_DURATION = 125  # Default duration in seconds

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class PacketDecoder:
    @staticmethod
    def decode_header(header: bytes):
        cycle_counter = header[0]
        star_mac_id = ':'.join(f'{b:02X}' for b in header[1:7])
        data_length = struct.unpack('<H', header[7:9])[0]
        data_checksum = struct.unpack('<H', header[9:11])[0]
        header_checksum = struct.unpack('<H', header[11:13])[0]
        return {
            "Cycle Counter": cycle_counter,
            "Star MAC Id": star_mac_id,
            "Data Length": data_length,
            "Data Checksum": data_checksum,
            "Header Checksum": header_checksum,
        }

    @staticmethod
    def _rssi_from_raw(raw_rssi: int) -> float:
        return (raw_rssi - 256) / 2.0 - 78 if raw_rssi >= 128 else raw_rssi / 2.0 - 78

    @staticmethod
    def decode_status_byte(status_byte: int):
        bits = f'{status_byte:08b}'
        return {
            'Status Byte': bits,
            'Button 4': bits[0],
            'Button 3': bits[1],
            'Button 2': bits[2],
            'Button 1': bits[3],
            'Motion Flag': bits[4],
            'Retry Count': int(bits[5:7], 2),
            'Reserved': bits[7]
        }

    @staticmethod
    def decode_location_packet(packet: bytes):
        device_type = packet[0]
        tag_id_raw = int.from_bytes(packet[1:5], 'little')
        tag_id = tag_id_raw & 0x0FFFFFFF
        raw_rssi = packet[8]
        rssi = PacketDecoder._rssi_from_raw(raw_rssi)
        monitor_id = int.from_bytes(packet[9:12], 'little')
        cmd = packet[12]
        status_byte = packet[13]
        ir_id = struct.unpack('<H', packet[14:16])[0]
        version = packet[16]
        astar_id = struct.unpack('<H', packet[17:19])[0]
        lbi = struct.unpack('<H', packet[19:21])[0]
        cmd3 = packet[21:24].hex()
        ts = int.from_bytes(packet[24:28], 'little')
        readable_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ekey = packet[28]
        lf_flag = packet[29]
        status_fields = PacketDecoder.decode_status_byte(status_byte)
        return {
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
            'IR ID': ir_id,
            'Version': version,
            'Astar ID': astar_id,
            'LBI': lbi,
            'CMD3': cmd3,
            'Timestamp': readable_time,
            'EKEY': ekey,
            'LF Flag': lf_flag
        }

HEADER_LEN = 13
LOCATION_PKT_LEN = 30

class PacketCapture:
    def __init__(self, host='127.0.0.1', port=7177, timeout=1.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._buffer = bytearray()

    def _format_log_line(self, rx_utc, header, pkt):
        return (
            f"{rx_utc} | Cycle={header['Cycle Counter']} | StarMAC={header['Star MAC Id']} | "
            f"TagID={pkt['Tag ID']} | RSSI={pkt['RSSI']} | MonID={pkt['Monitor ID']}| "
            f"IR={pkt['IR ID']} | Ver={pkt['Version']} | Astar={pkt['Astar ID']} | LBI={pkt['LBI']} | "
            f"LF={pkt['LF Flag']} \r\n "
        )

    def _try_parse_frames(self, log_fp):
        while True:
            if len(self._buffer) < HEADER_LEN:
                break
            header_bytes = self._buffer[:HEADER_LEN]
            try:
                header = PacketDecoder.decode_header(header_bytes)
            except Exception:
                self._buffer.pop(0)
                continue
            data_length = header['Data Length']
            total_len = HEADER_LEN + data_length
            if len(self._buffer) < total_len:
                break
            frame = bytes(self._buffer[:total_len])
            del self._buffer[:total_len]
            payload = frame[HEADER_LEN:]
            for i in range(data_length // LOCATION_PKT_LEN):
                try:
                    pkt = PacketDecoder.decode_location_packet(payload[i*LOCATION_PKT_LEN:(i+1)*LOCATION_PKT_LEN])
                    if (
                        pkt['Tag ID'] == TAG_FILTER and
                        header['Star MAC Id'] == MAC_FILTER and
                        not (
                            pkt['CMD3'] == "190014" and
                            pkt['EKEY'] == 0 and
                            pkt['Status Byte'] == "00000000"
                        )
                    ):
                        rx_utc = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                        log_fp.write(self._format_log_line(rx_utc, header, pkt))
                        log_fp.flush()
                        logging.info(f"Logged Tag {TAG_FILTER} from MAC {MAC_FILTER}")
                except Exception as e:
                    logging.warning(f"Failed to decode packet: {e}")

    def listen_and_log(self, duration_sec=DEFAULT_DURATION):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock, open(LOG_FILE, 'a', newline='') as log_fp:
            sock.bind((self.host, self.port))
            sock.settimeout(self.timeout)
            logging.info(f"Listening for Tag ID {TAG_FILTER} from MAC {MAC_FILTER} for {duration_sec} seconds...")
            start = time.time()
            while time.time() - start < duration_sec:
                try:
                    data, _ = sock.recvfrom(2048)
                    self._buffer.extend(data)
                    self._try_parse_frames(log_fp)
                except socket.timeout:
                    continue
        logging.info(f"Capture complete. Log saved to {LOG_FILE}")
        try:
            subprocess.Popen(['notepad.exe', LOG_FILE])
        except Exception as e:
            logging.error(f"Could not open Notepad: {e}")

# Main execution block
if __name__ == "__main__":
    process = MainProcess()
    process.send_cmd("tag1multiskey1,2\n")
    capt = PacketCapture()
    capt.listen_and_log()  # Uses DEFAULT_DURATION
    process.serial_conn.close()
