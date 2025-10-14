import asyncio
from datetime import datetime
import os
import platformdirs
import re

import bleak


# characteristic UUIDs
PNP_ID = "00002a50-0000-1000-8000-00805f9b34fb" # handle 13, read
SERVICE_CHANGED = "00002a05-0000-1000-8000-00805f9b34fb" # handle 9, indicate
UNKNOWN_1 = "00010203-0405-0607-0809-0a0b0c0d2b12" # handle 16, read, write-without-response, notify
BATTERY_LEVEL = "00002a19-0000-1000-8000-00805f9b34fb" # handle 20, read, notify
UNKNOWN_2 = "00010203-0405-0607-0809-0a0b0c0d2c12" # handle 16, read, write-without-response, notify


log_file = None

def to_hex(data: bytearray, separator: str = ' ') -> str:
    return separator.join(f'{b:02x}' for b in data)

def decode_lux(data: bytearray):
    if len(data) != 20:
        raise ValueError("Unexpected buffer length")
    hi = data[8]
    lo = data[9]
    raw_value = hi * 256 + lo
    lux = raw_value * 0.02862
    return lux

def callback(sender: bleak.BleakGATTCharacteristic, data: bytearray):
    global log_file
    timestamp = datetime.now().isoformat()
    reading = decode_lux(data)
    if log_file:
        log_file.write(f'{timestamp},{reading}\n')
    print(f'{timestamp} {reading:.3f}')

async def main():
    print("VBR-SOLAR Logger v. 0.1")
    print("Scanning, please wait...")

    devices = await bleak.BleakScanner.discover()
    named_devices = [d for d in devices if d.name]

    if len(named_devices) == 0:
        print("No device found.")
        return

    num_of_devices = len(named_devices)

    if num_of_devices == 1:
        print("1 device found:")
    else:
        print(f"{num_of_devices} devices found:")

    for i, device in enumerate(named_devices):
        print(f"{i+1:>3}. {device.name}")

    while True:
        i = int(input("Select a device (0 to exit): "))
        if i <= 0:
            return
        elif i <= len(named_devices):
            break

    device = named_devices[i-1]
    listening_time = int(input("Listening time (in seconds, 0 to exit): "))

    if listening_time == 0:
        return

    log_file_path = None
    save_data_to_file = input("Save data to file [y/N]? ")
    if save_data_to_file.lower() in ['y', 'yes']:
        name = f'{datetime.now().strftime("%Y%m%d_%H%M%S")}_{device.name}'
        os_friendly_name = re.sub(r'[^\w_.)( -]', '', name)
        log_file_name = f'{os_friendly_name}.csv'
        log_file_dir = platformdirs.user_log_dir()
        os.makedirs(log_file_dir, exist_ok=True)
        log_file_path = os.path.join(log_file_dir, log_file_name)
        print(f"Data will be saved in \"{log_file_path}\"")
    else:
        print(f"Data will not be saved on disk.")

    print(f"Connecting to {device.name} ({device.address})...")

    async with bleak.BleakClient(device.address) as client:
        print(f"Connection established!")
        battery_level = await client.read_gatt_char(BATTERY_LEVEL)
        print(f"Battery level: {int(to_hex(battery_level), 16)}%")
        if log_file_path:
            global log_file
            log_file = open(log_file_path, 'w')
        await client.start_notify(UNKNOWN_2, callback)
        await asyncio.sleep(listening_time)
        await client.stop_notify(UNKNOWN_2)
        if log_file:
            log_file.close()
            log_file = None
        

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Listening aborted.")
