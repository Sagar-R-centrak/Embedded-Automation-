import os,time
import subprocess
import keyboard
from pyautogui import hotkey
import pygetwindow as gw


subprocess.Popen("C:\\Users\\cheluvagb\\Downloads\\Andromeda-Staff-Tag-V29-Pre-ReleaseV41.1.107\\Andromeda-Staff-Tag-V29-Pre-ReleaseV41.1.107\\ProductionTool")

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
        print ("Test pass")
    elif "Firmware loading process failed" in last_line:
        print ("test Fail")
