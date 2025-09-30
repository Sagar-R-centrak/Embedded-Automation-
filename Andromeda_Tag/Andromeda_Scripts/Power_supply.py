import time
import json
from koradserial import KoradSerial


class KoradPowerSupply:
    def __init__(self, config_file="config.json"):
        """
        Initializes the power supply by reading the configuration file.

        Parameters:
            config_file (str): Path to the JSON configuration file.
        """
        try:
            with open(config_file, "r") as file:
                config = json.load(file)
            self.com_port = config.get("POWER_SUPPLY", {}).get("COM_PORT", "COM5")
            self.device = None
        except Exception as e:
            print(f"Error reading config file: {e}")
            self.com_port = "COM5"

    def connect(self):
        """Establishes connection to the power supply."""
        try:
            self.device = KoradSerial(self.com_port)
            print("Connected to:", self.device.model)
        except Exception as e:
            print("Error connecting to power supply:", e)

    def set_voltage(self, voltage, current_limit=1.0):
        """
        Sets the specified voltage on Channel 1 of the power supply.

        Parameters:
            voltage (float): The desired output voltage.
            current_limit (float): The current limit (default: 1.0A).
        """
        if not self.device:
            print("Power supply is not connected.")
            return

        try:
            self.device.channels[0].voltage = voltage  # Set voltage
            self.device.channels[0].current = current_limit  # Set current limit

            self.device.output = True  # Turn on output

            print(f"Voltage set to {voltage}V on Channel 1")
            print(f"Output Current: {self.device.channels[0].output_current}A")

            time.sleep(1)  # Allow settings to apply

        except Exception as e:
            print("Error setting voltage:", e)

    def disconnect(self):
        """Disconnects from the power supply."""
        if self.device:
            self.device.close()
            print("Power supply disconnected.")


# Example Usage:
if __name__ == "__main__":
    psu = KoradPowerSupply()
    psu.connect()
    psu.set_voltage(3)  # Set voltage to 5V
    psu.disconnect()


