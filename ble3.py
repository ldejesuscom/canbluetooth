# ble3.py (main application)
import can
import dbus
import dbus.mainloop.glib
from gi.repository import GLib
from bluetooth_utils import (
    register_app,
    register_ad_manager,
    register_advertisement,
    create_gatt_service,
    create_gatt_characteristic,
)

# --- Constants ---
CAN_DATA_SVC_UUID = "12345678-1234-5678-1234-56789abcdef0"
CAN_DATA_CHAR_UUID = "12345678-1234-5678-1234-56789abcdef1"

# --- CAN Interface Setup ---
canbus = can.interface.Bus(channel="vcan0", bustype="socketcan")

# --- Bluetooth Setup ---
mainloop = GLib.MainLoop()
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

bus = dbus.SystemBus()
app = register_app(bus)
ad_manager = register_ad_manager(bus)

# --- GATT Service and Characteristic ---
service = create_gatt_service(bus, CAN_DATA_SVC_UUID)
can_data_characteristic = create_gatt_characteristic(
    bus,
    CAN_DATA_CHAR_UUID,
    service,
    ["read", "notify", "write"],  # Include "write" flag
    dbus.Array(signature="ay"),
)

# --- Advertisement ---
advertisement = register_advertisement(
    bus,
    ad_manager,
    {
        "Type": "peripheral",
        "LocalName": dbus.String("CAN-BLE-Gateway"),
        "ServiceUUIDs": dbus.Array([CAN_DATA_SVC_UUID], signature="s"),
    },
)

# --- CAN Frame Handling ---
def handle_can_frame(msg):
    can_id = msg.arbitration_id
    can_data = msg.data
    # Format data for Bluetooth transmission (example)
    bluetooth_data = can_id.to_bytes(4, byteorder="big") + can_data
    # Update GATT characteristic value
    can_data_characteristic.WriteValue(bluetooth_data, {})

# Attach handler to CAN bus
notifier = can.Notifier(canbus, [handle_can_frame])

# --- Main Loop ---
try:
    mainloop.run()
except KeyboardInterrupt:
    advertisement.Release()
    print("Exiting...")
