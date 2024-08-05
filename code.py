import gc
import time
from os import getenv

import adafruit_connection_manager
import adafruit_esp32spi_socketpool as socketpool
import adafruit_logging
import adafruit_requests
import board
import busio
import displayio
import framebufferio
import microcontroller
import rgbmatrix
import terminalio
from adafruit_display_text import label
from adafruit_esp32spi import adafruit_esp32spi
from digitalio import DigitalInOut

# Create a logger
logger = adafruit_logging.Logger("Logger")
logger.setLevel(adafruit_logging.INFO)

# Set up a log file - this requires device to be in write mode
file_handler = adafruit_logging.FileHandler("./people-counter-display.log")
logger.addHandler(file_handler)

# Initialise display
displayio.release_displays()
matrix = rgbmatrix.RGBMatrix(
    width=64,
    height=32,
    bit_depth=4,
    rgb_pins=[
        board.MTX_R1,
        board.MTX_G1,
        board.MTX_B1,
        board.MTX_R2,
        board.MTX_G2,
        board.MTX_B2,
    ],
    addr_pins=[board.MTX_ADDRA, board.MTX_ADDRB, board.MTX_ADDRC, board.MTX_ADDRD],
    clock_pin=board.MTX_CLK,
    latch_pin=board.MTX_LAT,
    output_enable_pin=board.MTX_OE,
)
display = framebufferio.FramebufferDisplay(matrix, auto_refresh=True)

# Prepare initial text for the display
top_label = label.Label(terminalio.FONT, text="CTH Daily")
top_label.x = 5
top_label.y = 6

second_label = label.Label(terminalio.FONT, text="Entry")
second_label.x = 5
second_label.y = 15

third_label = label.Label(terminalio.FONT, text="Count")
third_label.x = 5
third_label.y = 26

# Question mark for count because we haven't connected to the wifi yet
count_label = label.Label(terminalio.FONT, text=" ?", scale=2)
count_label.x = 37
count_label.y = 22

# Put the text in a group and put group in display
g = displayio.Group()
g.append(top_label)
g.append(second_label)
g.append(third_label)
g.append(count_label)
display.root_group = g

# Get wifi details and more from a settings.toml file
# tokens used by this Demo: CIRCUITPY_WIFI_SSID, CIRCUITPY_WIFI_PASSWORD
secrets = {
    "ssid": getenv("CIRCUITPY_WIFI_SSID"),
    "password": getenv("CIRCUITPY_WIFI_PASSWORD"),
}
if secrets == {"ssid": None, "password": None}:
    try:
        # Fallback on secrets.py until depreciation is over and option is removed
        from secrets import secrets
    except ImportError:
        print("WiFi secrets are kept in settings.toml, please add them there!")
        raise

# If you are using a board with pre-defined ESP32 Pins:
esp32_cs = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)

# Secondary (SCK1) SPI used to connect to WiFi board on Arduino Nano Connect RP2040
if "SCK1" in dir(board):
    spi = busio.SPI(board.SCK1, board.MOSI1, board.MISO1)
else:
    spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

pool = adafruit_connection_manager.get_radio_socketpool(esp)
ssl_context = adafruit_connection_manager.get_radio_ssl_context(esp)
requests = adafruit_requests.Session(pool, ssl_context)

if esp.status == adafruit_esp32spi.WL_IDLE_STATUS:
    print("ESP32 found and in idle mode")
print("Firmware vers.", esp.firmware_version.decode("utf-8"))
print("MAC addr:", ":".join("%02X" % byte for byte in esp.MAC_address))

for ap in esp.scan_networks():
    print("\t%-23s RSSI: %d" % (str(ap["ssid"], "utf-8"), ap["rssi"]))

print("Connecting to AP...")
while not esp.is_connected:
    try:
        esp.connect_AP(secrets["ssid"], secrets["password"])
    except OSError as e:
        logger.error(str(e))
        print("could not connect to AP, retrying: ", e)
        continue
print("Connected to", str(esp.ssid, "utf-8"), "\tRSSI:", esp.rssi)
print("My IP address is", esp.pretty_ip(esp.ip_address))

# Define the URL of the server you want to connect to
url = "http://192.168.0.100:8000/count"

# Check for changes in entry count every 30 seconds
polling_interval = 30

# Use a counter to see if requests.get causes an exception 5 times in a row
FAILURE_COUNT = 0
FAILURE_LIMIT = 5


def retrieve_visitor_count():
    print("Polling...")
    with requests.get(url) as response:
        if response.status_code == 200:
            data = response.json()
            return "%02d" % data["value"]
        else:
            msg = "Failed to fetch integer value: {response.status_code} - {response.reason}"
            print(msg)
            logger.error(msg)
            return "Er"


while True:

    try:
        count_label.text = retrieve_visitor_count()
        FAILURE_COUNT = 0  # no exception so reset failure count
    except Exception as e:
        # force gargage collection in case memory is the culprit
        gc.collect()
        # increase failure count
        FAILURE_COUNT += 1
        print(f"An error occurred: {e}")
        # log the exception
        logger.exception(e)
        # put a message on the display
        count_label.text = "Ex"

    if FAILURE_COUNT == 5:
        top_label.text = "Resetting!"
        second_label.text = third_label.text = count_label.text = ""
        # leave the resetting message on the display for a bit so we can see that this has happened
        time.sleep(5)
        logger.critical("Reset due to multiple failures")
        microcontroller.reset()

    time.sleep(30)
