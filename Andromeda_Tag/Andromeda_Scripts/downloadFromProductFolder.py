import os
import time
import zipfile
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import os
import subprocess
import keyboard
from pyautogui import hotkey
import os,time
import subprocess
import keyboard
from pyautogui import hotkey
import pygetwindow as gw


# CONFIGURABLE SECTION
url = "https://centrak-apps.sourcerepo.com/redmine/centrak/attachments/download/153783"
username = "Cheluva.GB"
password = "Infinite@1234"
username_field_id = "username"  # ID as per HTML
password_field_id = "password"  # ID as per HTML
login_button_id = "login-submit"       # ID as per HTML
downloads_path = os.path.join(os.path.expanduser("~"), "C:\\Users\\cheluvagb\\Downloads")
unzip_to_folder = "C:\\Users\\cheluvagb\\Downloads\\Firmwares\\SafetyBracelet"

# STEP 1: Open link & login
driver = webdriver.Chrome() # or webdriver.Firefox() etc.
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
        print ("Test pass")
    elif "Firmware loading process failed" in last_line:
        print ("test Fail")
