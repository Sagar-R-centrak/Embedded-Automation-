import socket
import struct
import time
import datetime
import logging
import subprocess
import pandas as pd
import openpyxl
from Arduino_API.Arduino_serial_API import SerialConnection
from GUI_API.TI_Packet_Sniffer import PacketSnifferApp
from GUI_API.BLE_Packet_Sniffer import BleSnifferApp

class MainProcess:
    def __init__(self):
        self.serial_conn = SerialConnection(port="COM11", baud_rate=9600)
        print("Initializing serial connection...")
        self.serial_conn.init_serial()

    def send_cmd(self, serial_message):
        print(f"Sending command '{serial_message}' to Arduino...")
        self.serial_conn.send_command(serial_message)

TAG_FILTER = 17684992
MAC_FILTER = None  # Allow all MACs
EXPECTED_MONITOR_ID = 8508965
EXPECTED_IR_ID = 55
EXPECTED_ASTAR_ID = 900
EXPECTED_VERSION = 119
EXPECTED_LBI = 2452

timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
LOG_FILE = f"tag_{TAG_FILTER}_{timestamp}.txt"
EXCEL_FILE = f"validation_{TAG_FILTER}_{timestamp}.xlsx"
DEFAULT_DURATION = 125

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
    def __init__(self, host='', port=7171, timeout=1.0):  # Listen on all interfaces
        self.host = host
        self.port = port
        self.timeout = timeout
        self._buffer = bytearray()
        self.validation_results = []

    def _format_log_line(self, rx_utc, header, pkt):
        return (
            f"{rx_utc} | Cycle={header['Cycle Counter']} | StarMAC={header['Star MAC Id']} | "
            f"TagID={pkt['Tag ID']} | RSSI={pkt['RSSI']} | MonID={pkt['Monitor ID']}| "
            f"IR={pkt['IR ID']} | Ver={pkt['Version']} | Astar={pkt['Astar ID']} | LBI={pkt['LBI']} | "
            f"LF={pkt['LF Flag']} \r\n "
        )

    def _validate_fields(self, header, pkt):
        return {
            'Timestamp': pkt['Timestamp'],
            'Tag ID': 'Pass' if pkt['Tag ID'] == TAG_FILTER else 'Fail',
            'MAC ID': 'Pass' if MAC_FILTER is None or header['Star MAC Id'] == MAC_FILTER else 'Fail',
            'Monitor ID': 'Pass' if pkt['Monitor ID'] == EXPECTED_MONITOR_ID else 'Fail',
            'IR ID': 'Pass' if pkt['IR ID'] == EXPECTED_IR_ID else 'Fail',
            'Astar ID': 'Pass' if pkt['Astar ID'] == EXPECTED_ASTAR_ID else 'Fail',
            'Version': 'Pass' if pkt['Version'] == EXPECTED_VERSION else 'Fail',
            'LBI': 'Pass' if pkt['LBI'] == EXPECTED_LBI else 'Fail'
        }

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
                        (MAC_FILTER is None or header['Star MAC Id'] == MAC_FILTER) and
                        not (
                            pkt['CMD3'] == "190014" and
                            pkt['EKEY'] == 0 and
                            pkt['Status Byte'] == "00000000"
                        )
                    ):
                        rx_utc = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                        log_fp.write(self._format_log_line(rx_utc, header, pkt))
                        log_fp.flush()
                        logging.info(f"Logged Tag {TAG_FILTER}")
                        validation = self._validate_fields(header, pkt)
                        self.validation_results.append(validation)
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
        pd.DataFrame(self.validation_results).to_excel(EXCEL_FILE, index=False)
        logging.info(f"Validation results saved to {EXCEL_FILE}")

if __name__ == "__main__":
    process = MainProcess()
    ble_pakc = BleSnifferApp()
    ti_pack = PacketSnifferApp()

    try:
        ble_pakc.start()
        ble_pakc.open_settings()
        ble_pakc.write_streaming_ip("192.168.1.24")
        ble_pakc.save()
        ble_pakc.start_sniffer()
        ble_pakc.close_settings()
    except Exception as e:
        logging.error(f"BLE Sniffer failed to start: {e}")

    try:
        ti_pack.start()
        ti_pack.select_ble()
        ti_pack.start_ble()
        ti_pack.main_start()
    except Exception as e:
        logging.error(f"TI Packet Sniffer failed to start: {e}")

    process.send_cmd("tag1multiskey1,2\n")
    capt = PacketCapture()
    capt.listen_and_log()
    process.serial_conn.close()