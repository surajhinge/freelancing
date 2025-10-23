import socket
import time

# LED display IP and port
LED_IP = "192.168.1.100"
LED_PORT = 5005  # Default Huidu port; may vary

# Function to send command to LED
def send_to_led(message):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((LED_IP, LED_PORT))
        # Construct Huidu command for scrolling text
        # This is a simple example; actual commands depend on your LED firmware
        cmd = f"[00]{message}"  # placeholder for actual LED protocol
        sock.send(cmd.encode("utf-8"))
        print(f"Sent to LED: {message}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        sock.close()

# Example live update loop
if __name__ == "__main__":
    while True:
        # Here you can fetch live data from any source
        text_to_display = input("Enter text for LED: ")
        send_to_led(text_to_display)
        time.sleep(1)
