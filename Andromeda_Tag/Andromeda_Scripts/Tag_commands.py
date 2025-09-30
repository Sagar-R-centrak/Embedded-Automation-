import socket
import time



# Global constant for server IP
SERVER_IP = "192.168.1.10"  # Replace with your server IP
PORT = 8181


def send_command(tag_id: int, command: int, value: int):
    """Sends command to the server with given tag_id, command, and value."""
    # Command buffer for sending data
    buf = bytearray(13)

    # Prepare the buffer (Assuming 3x command structure)
    n_command_type = 1  # Command type: 1 - Tag command
    tag_id |= 0x80000000

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
        tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_client.connect((SERVER_IP, PORT))
        tcp_client.send(buf)
        response = tcp_client.recv(1024)  # Read response from the server
        tcp_client.close()
        print(f"Response from server: {response.hex() if response else 'No response received'}")
        return response
    except Exception as ex:
        print(f"Error sending command: {ex}")
        return None



# Reset Command
tag_id = 17684981
command = 0x1
value = 1
send_command(tag_id, command, value)


# Led on Command
tag_id = 17684981
command = 0x2
value = 100
send_command(tag_id, command, value)


# Led off Command
tag_id = 17684981
command = 0x3
value = 100
send_command(tag_id, command, value)


#  Frequency index change Command
tag_id = 17684981
command = 0x4
value = 2
send_command(tag_id, command, value)


# Get profile Command
tag_id = 17684981
command = 0x5
value = 2
send_command(tag_id, command, value)







# Get version Command
tag_id = 17684981
command = 0x6
value = 2
send_command(tag_id, command, value)




# Get battery status Command
tag_id = 17684981
command = 0x7
value = 2
send_command(tag_id, command, value)


# set WLAN Channel mask Command
tag_id = 17684981
command = 0x8
value = 2
send_command(tag_id, command, value)


# Clear summary info Command
tag_id = 17684981
command = 0x22
value = 2
send_command(tag_id, command, value)

# Get summary info Command
tag_id = 17684981
command = 0xD
value = 2
send_command(tag_id, command, value)


# Get summary info Command
tag_id = 17684981
command = 0x20
value = 0
send_command(tag_id, command, value)

