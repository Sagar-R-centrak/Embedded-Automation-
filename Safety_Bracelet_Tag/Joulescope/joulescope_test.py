# @pytest.fixture(scope="module")
# def main_process():
#     process = MainProcess()
#     # Add a test counter to the process for delay logic
#     process._test_counter = 0
#     yield process
#     process.serial_conn.close()
#
# # Fixture for PowerSupply, only if needed by a test
# @pytest.fixture(scope="module")
# def power_supply():
#     ps = PowerSupply()
#     yield ps
#     # If PowerSupply has a close method, call it here
#     if hasattr(ps, 'close'):
#         ps.close()
#
# @pytest.fixture(scope="module")
# def joulescope():
#     js = JoulescopeAPI()
#     yield js
#     js.close()

#
# def test_button_press_led_count(main_process):
#     main_process.send_command("motion")
#     time.sleep(1)
#     Inventory_Factory_sleep_using_GUI.send_inventory_sleep("192.168.1.17", "4296384")
#     time.sleep(30)
#     main_process.send_command("lpress")
#     time.sleep(30)
#     main_process.send_command("motion")
#     time.sleep(5)
#     main_process.send_command("spress")
#     time.sleep(1)
#     output = main_process.send_command_and_wait("ledcount", 15)
#     green_count = None
#     red_count = None
#     first_led = None
#     lines = [line.strip().lower().replace('_', ' ') for line in output.splitlines() if line.strip()]
#     for line in lines:
#         if "green led on count" in line and green_count is None:
#             try:
#                 green_count = int(line.split(':')[-1].strip())
#                 if first_led is None:
#                     first_led = 'green'
#             except Exception:
#                 pass
#         elif "red led on count" in line and red_count is None:
#             try:
#                 red_count = int(line.split(':')[-1].strip())
#                 if first_led is None:
#                     first_led = 'red'
#             except Exception:
#                 pass
#     result = (
#         green_count == 4 and
#         red_count == 0 and
#         first_led == 'green'
#     )
#     assert result, f"LED count check failed: green={green_count}, red={red_count}, first_led={first_led}"
#
import re
import openpyxl
from openpyxl import Workbook
import os

def extract_test_names(py_file):
    with open(py_file, 'r', encoding='utf-8') as f:
        content = f.read()
    return re.findall(r'def (test_[a-zA-Z0-9_]+)\s*\(', content)

def write_tests_to_excel(test_names, excel_path):
    if not os.path.exists(excel_path):
        wb = Workbook()
        ws = wb.active
        ws.append(['SL NO', 'Test Name'])
    else:
        wb = openpyxl.load_workbook(excel_path)
        ws = wb.active

    for idx, name in enumerate(test_names, start=1):
        ws.append([idx, name])
    wb.save(excel_path)

if __name__ == "__main__":
    py_file = '../testcase_execution.py'
    excel_path = '../safety_bracelet_test_results.xlsx'
    test_names = extract_test_names(py_file)
    write_tests_to_excel(test_names, excel_path)


# def test_current_during_active(main_process, joulescope):
#     main_process.send_command("motion")
#     output_current = joulescope.read_current(38)  # Read current for 5 seconds during sleep
#     if output_current <= 0.12:
#         print(f"Current during factory sleep is within expected range: {output_current}mA")
#     else:
#         print(f"Current during factory sleep is within expected range: {output_current}mA")
#     assert output_current <= 0.12, f"Current too high: {output_current}mA"
