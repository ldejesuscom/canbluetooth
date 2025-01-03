#!/usr/bin/python3

import dbus
import dbus.exceptions
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib
import can
import bluetooth_constants
import bluetooth_exceptions
import bluetooth_gatt

class Advertisement(dbus.service.Object):
    PATH_BASE = '/org/bluez/example/advertisement'

    def __init__(self, bus, index, advertising_type):
        self.path = self.PATH_BASE + str(index)
        self.bus = bus
        self.ad_type = advertising_type
        self.service_uuids = ["12345678-1234-5678-1234-56789abcdef0"]  # Custom UUID for CAN Service
        self.local_name = "RaspberryPi-CAN"
        self.include_tx_power = True
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        properties = {
            "Type": self.ad_type,
            "ServiceUUIDs": dbus.Array(self.service_uuids, signature='s'),
            "LocalName": dbus.String(self.local_name),
            "Includes": dbus.Array(["tx-power"], signature='s'),
        }
        return {bluetooth_constants.ADVERTISEMENT_INTERFACE: properties}

    def get_path(self):
        return dbus.ObjectPath(self.path)

    @dbus.service.method(bluetooth_constants.ADVERTISEMENT_INTERFACE,
                         in_signature='', out_signature='')
    def Release(self):
        print('%s: Released' % self.path)

class CANCharacteristic(bluetooth_gatt.Characteristic):
    def __init__(self, bus, index, service):
        super().__init__(
            bus, index,
            "12345678-1234-5678-1234-56789abcdef1",  # Characteristic UUID
            ["notify"], service)
        self.notifying = False
        print(f"Characteristic path: {self.path}")  # Debugging log for characteristic path

    def StartNotify(self):
        if self.notifying:
            return
        print("Starting notifications")
        self.notifying = True
        self.send_can_data()

    def StopNotify(self):
        if not self.notifying:
            return
        print("Stopping notifications")
        self.notifying = False

    def send_can_data(self):
        if not self.notifying:
            return
        try:
            for message in bus:
                value = [dbus.Byte(b) for b in message.data]
                self.PropertiesChanged(bluetooth_constants.GATT_CHARACTERISTIC_INTERFACE,
                                       {"Value": value}, [])
        except Exception as e:
            print(f"Error reading CAN data: {e}")
        GLib.timeout_add(100, self.send_can_data)

class CANService(bluetooth_gatt.Service):
    def __init__(self, bus, index):
        super().__init__(bus, '/org/bluez/example', index,
                         "12345678-1234-5678-1234-56789abcdef0", True)
        print(f"Service path: {self.path}")  # Debugging log for service path
        self.add_characteristic(CANCharacteristic(bus, 0, self))

class Application(dbus.service.Object):
    def __init__(self, bus):
        self.path = '/'
        self.services = []
        dbus.service.Object.__init__(self, bus, self.path)
        self.add_service(CANService(bus, 0))

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_service(self, service):
        self.services.append(service)

    @dbus.service.method(bluetooth_constants.DBUS_OM_IFACE,
                         out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        response = {}
        for service in self.services:
            print(f"Registering service path: {service.get_path()}")
            response[service.get_path()] = service.get_properties()
            for characteristic in service.characteristics:
                print(f"Registering characteristic path: {characteristic.get_path()}")
                response[characteristic.get_path()] = characteristic.get_properties()
        print(f"Managed Objects Response: {response}")  # Debug the entire response
        return response


def register_ad_cb():
    print("Advertisement registered")

def register_ad_error_cb(error):
    print(f"Failed to register advertisement: {str(error)}")
    mainloop.quit()

def register_app_cb():
    print("GATT application registered")

def register_app_error_cb(error):
    print(f"Failed to register application: {str(error)}")
    mainloop.quit()

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()

adapter_path = "/org/bluez/hci0"
ad_manager = dbus.Interface(bus.get_object(bluetooth_constants.BLUEZ_SERVICE_NAME, adapter_path),
                            bluetooth_constants.ADVERTISING_MANAGER_INTERFACE)
gatt_manager = dbus.Interface(bus.get_object(bluetooth_constants.BLUEZ_SERVICE_NAME, adapter_path),
                               bluetooth_constants.GATT_MANAGER_INTERFACE)

app = Application(bus)
ad = Advertisement(bus, 0, "peripheral")

ad_manager.RegisterAdvertisement(ad.get_path(), {}, reply_handler=register_ad_cb, error_handler=register_ad_error_cb)
gatt_manager.RegisterApplication(app.get_path(), {}, reply_handler=register_app_cb, error_handler=register_app_error_cb)

print("Application running")
mainloop = GLib.MainLoop()
mainloop.run()
