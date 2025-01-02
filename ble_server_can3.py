from dbus import Byte
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib
import can
import threading

# Constants for the BLE server
SERVICE_UUID = "12345678-1234-5678-1234-56789abcdef0"
CHARACTERISTIC_UUID = "12345678-1234-5678-1234-56789abcdef1"
LOCAL_NAME = "Raspberry Pi"
CAN_INTERFACE = "vcan0"

# Initialize the D-Bus main loop
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)


class BLEServer:
    def __init__(self):
        self.bus = dbus.SystemBus()
        self.mainloop = None

    def register_gatt_server(self):
        # Get the object manager for BlueZ
        obj_manager = dbus.Interface(self.bus.get_object('org.bluez', '/'), 'org.freedesktop.DBus.ObjectManager')

        # Find the adapter path
        bluez_objects = obj_manager.GetManagedObjects()
        adapter_path = None
        for path, interfaces in bluez_objects.items():
            if 'org.bluez.Adapter1' in interfaces:
                adapter_path = path
                break

        if not adapter_path:
            raise Exception("Bluetooth adapter not found!")

        # Enable the adapter
        adapter = dbus.Interface(self.bus.get_object('org.bluez', adapter_path), 'org.freedesktop.DBus.Properties')
        adapter.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(1))

        # Create and register the GATT application
        app = GattApplication(self.bus)
        manager = dbus.Interface(
            self.bus.get_object('org.bluez', adapter_path),
            'org.bluez.GattManager1'
        )
        manager.RegisterApplication(app.path, {}, reply_handler=self._success, error_handler=self._error)

        # Start advertising
        self.start_advertising(adapter_path)

        # Return the GATT application instance for further use
        return app

    def start_advertising(self, adapter_path):
        advertisement = Advertisement(self.bus, 0)
        advertising_manager = dbus.Interface(
            self.bus.get_object('org.bluez', adapter_path),
            'org.bluez.LEAdvertisingManager1'
        )
        advertising_manager.RegisterAdvertisement(advertisement.path, {},
                                                  reply_handler=self._success,
                                                  error_handler=self._error)

    def _success(self):
        print("Operation successful!")

    def _error(self, error):
        print(f"Failed operation: {error}")

    def run(self):
        self.mainloop = GLib.MainLoop()
        self.mainloop.run()

    def stop(self):
        if self.mainloop:
            self.mainloop.quit()


class Advertisement(dbus.service.Object):
    PATH_BASE = '/com/example/ble/advertisement'

    def __init__(self, bus, index):
        self.path = self.PATH_BASE + str(index)
        self.bus = bus
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {
            'org.bluez.LEAdvertisement1': {
                'Type': 'peripheral',
                'ServiceUUIDs': [SERVICE_UUID],
                'LocalName': LOCAL_NAME,
                'Includes': ['tx-power'],
            }
        }

    @dbus.service.method('org.freedesktop.DBus.Properties', in_signature='', out_signature='a{sv}')
    def GetAll(self, interface):
        return self.get_properties()[interface]

    @dbus.service.method('org.bluez.LEAdvertisement1', in_signature='', out_signature='')
    def Release(self):
        print(f"{self.path}: Released")


class GattApplication(dbus.service.Object):
    def __init__(self, bus):
        self.bus = bus
        self.services = [GattService(bus)]
        self.path = '/com/example/ble'
        dbus.service.Object.__init__(self, bus, self.path)

    @dbus.service.method('org.freedesktop.DBus.ObjectManager', in_signature='', out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        objects = {}
        for service in self.services:
            objects.update(service.get_properties())
        print(f"Managed Objects: {objects}")  # Debugging output
        return objects



class GattService(dbus.service.Object):
    def __init__(self, bus):
        self.bus = bus
        self.path = '/com/example/ble/service0'
        self.characteristics = [GattCharacteristic(bus)]
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        properties = {
            self.path: {
                'org.bluez.GattService1': {
                    'UUID': SERVICE_UUID,
                    'Primary': True,
                    'Characteristics': [c.path for c in self.characteristics],
                }
            }
        }
        for characteristic in self.characteristics:
            properties.update(characteristic.get_properties())
        return properties



class GattCharacteristic(dbus.service.Object):
    def __init__(self, bus):
        self.bus = bus
        self.path = '/com/example/ble/char0'
        self.value = [Byte(0)]
        self.notify_enabled = False
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {
            self.path: {
                'org.bluez.GattCharacteristic1': {
                    'UUID': CHARACTERISTIC_UUID,
                    'Service': '/com/example/ble/service0',
                    'Value': self.value,  # Ensure this is a valid D-Bus byte array
                    'Flags': ['read', 'write', 'notify'],  # Flags must match BlueZ requirements
                }
            }
        }


    @dbus.service.method('org.bluez.GattCharacteristic1', in_signature='', out_signature='ay')
    def ReadValue(self, options):
        print("Read request received")
        return self.value

    @dbus.service.method('org.bluez.GattCharacteristic1', in_signature='aya{sv}', out_signature='')
    def WriteValue(self, value, options):
        print(f"Write request received: {value}")
        self.value = value

    @dbus.service.method('org.bluez.GattCharacteristic1', out_signature='')
    def StartNotify(self):
        print("Notifications enabled")
        self.notify_enabled = True

    @dbus.service.method('org.bluez.GattCharacteristic1', out_signature='')
    def StopNotify(self):
        print("Notifications disabled")
        self.notify_enabled = False

    def send_notification(self, value):
        if self.notify_enabled:
            print(f"Sending notification: {value}")
            self.value = value
            self.PropertiesChanged('org.bluez.GattCharacteristic1', {'Value': self.value}, [])


def monitor_can(characteristic):
    """Monitor CAN frames on vcan0 and send them via BLE."""
    bus = can.interface.Bus(channel=CAN_INTERFACE, bustype='socketcan')
    print("Monitoring CAN frames...")
    for msg in bus:
        can_data = f"ID: {msg.arbitration_id}, Data: {msg.data.hex()}"
        print(f"Received CAN frame: {can_data}")
        characteristic.send_notification(can_data.encode('utf-8'))


if __name__ == '__main__':
    server = BLEServer()
    try:
        print("Starting BLE server...")

        # Register the GATT server and get the GATT application instance
        app = server.register_gatt_server()

        # Retrieve the existing GattCharacteristic instance
        gatt_characteristic = app.services[0].characteristics[0]

        # Start monitoring CAN in a separate thread
        can_thread = threading.Thread(target=monitor_can, args=(gatt_characteristic,))
        can_thread.start()

        server.run()
    except KeyboardInterrupt:
        print("Stopping BLE server...")
        server.stop()
