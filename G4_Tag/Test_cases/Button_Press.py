import json
import time
from UDP_Stream.UDP_Stream_validation_API.MainProcess import MainProcess
from UDP_Stream.UDP_Stream_validation_API.Report import Report
from UDP_Stream.UDP_Stream_validation_API.Output import Output
import logging

g4_tag1_id = 8457892
server_ip = "192.168.1.5"


process = MainProcess()
if __name__ == "__main__":


    print("Executing ButtonPress_05 : To validate tag Button Press")
    logging.info("Executing ButtonPress_05 : To validate tag Button Press \n  ")
    time.sleep(3)
    expected_values = {
        'Tag ID': g4_tag1_id,
        'Button 1': '1'
    }
    result = process.button_api(serial_message="t1lp", expected_values=expected_values)
    i = 1
    if result:
        print("Packet validation successful.")
        print(f"Iteration{i}: ButtonPress_05 Test PASS")
        Report("ButtonPress_05", 1)
        Output(f"Iteration{i}: ButtonPress_05 Test PASS")
    else:
        print("Packet validation failed.")
        print(f"Iteration{i}: ButtonPress_05 Test FAIL")
        Report("ButtonPress_05", 0)
        Output(f"Iteration{i}: ButtonPress_05 Test FAIL")