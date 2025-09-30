import socket
import json
import time


class DevCommandSender:
    def __init__(self, config_file="config.json"):
        """
        Initializes the command sender by loading server configuration.
        """
        self.load_config(config_file)

    def load_config(self, config_file):
        """
        Loads server configuration from a JSON file.
        """
        try:
            with open(config_file, "r") as file:
                config = json.load(file)
                self.SERVER_IP = config.get("SERVER_IP", "192.168.1.10")
                self.TCP_COMMAND_PORT = config.get("tcp_command_port", 8181)
        except Exception as e:
            print(f"Error loading config file: {e}")
            self.SERVER_IP = "192.168.1.10"
            self.TCP_COMMAND_PORT = 8181

    def send_command(self, tag_id: int, command: int, value: int):
        """
        Sends a command to the server with the given tag_id, command, and value.

        Parameters:
            tag_id (int): The tag identifier.
            command (int): The command code.
            value (int): The command value.

        Returns:
            bytes: The response from the server.
        """
        buf = bytearray(13)

        # Prepare the command buffer
        n_command_type = 1  # Command type: 1 - Tag command
        tag_id |= 0x80000000  # Set MSB for tag_id

        buf[0] = n_command_type
        buf[1] = (tag_id & 0xFF)
        buf[2] = (tag_id >> 8) & 0xFF
        buf[3] = (tag_id >> 16) & 0xFF
        buf[4] = (tag_id >> 24) & 0xFF
        buf[5] = (command & 0xFF)
        buf[6] = (command >> 8) & 0xFF
        buf[7] = (value & 0xFF)
        buf[8] = (value >> 8) & 0xFF

        # Send command to the server
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_client:
                print(f"Connecting to {self.SERVER_IP}:{self.TCP_COMMAND_PORT}...")
                tcp_client.connect((self.SERVER_IP, self.TCP_COMMAND_PORT))
                tcp_client.send(buf)
                response = tcp_client.recv(1024)  # Read response from the server

            print(f"Response from server: {response.hex() if response else 'No response received'}")
            return response
        except Exception as ex:
            print(f"Error sending command: {ex}")
            return None


if __name__ == "__main__":
    # Create an instance of the class
    sender = DevCommandSender()

    # List of commands to send
    commands = [
        (17684981, 0x1, 1),  # Reset Command
        (17684981, 0x2, 100),  # Led on Command
        (17684981, 0x3, 100),  # Led off Command
        (17684981, 0x4, 2),  # Frequency index change Command
        (17684981, 0x5, 2),  # Get profile Command
        (17684981, 0x6, 2),  # Get version Command
        (17684981, 0x7, 2),  # Get battery status Command
        (17684981, 0x8, 2),  # Set WLAN Channel mask Command
        (17684981, 0x22, 2),  # Clear summary info Command
        (17684981, 0xD, 2),  # Get summary info Command
        (17684981, 0x20, 0)   # Get summary info Command
    ]


    for tag_id, command, value in commands:
        sender.send_command(tag_id, command, value)
        time.sleep(20)
