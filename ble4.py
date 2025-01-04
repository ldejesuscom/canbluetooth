import bluetooth_constants
import bluetooth_gatt
import bluetooth_exceptions
import dbus
import dbus.exceptions
import dbus.service
import dbus.mainloop.glib
import sys
import can
import threading
from gi.repository import GLib

bus = None
adapter_path = None
adv_mgr_interface = None
connected = 0

class Advertisement(dbus.service.Object):
    PATH_BASE = '/org/bluez/ldsg/advertisement'

    def __init__(self, bus, index, advertising_type):
        self.path = self.PATH_BASE + str(index)
        self.bus = bus
        self.ad_type = advertising_type
        self.service_uuids = UUID_NAMES
        self.manufacturer_data = None
        self.solicit_uuids = None
        self.service_data = None
        self.local_name = 'CAN Adapter'
        self.include_tx_power = False
        self.data = None
        self.discoverable = True
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        properties = dict()
        properties['Type'] = self.ad_type
        if self.service_uuids is not None:
            properties['ServiceUUIDs'] = dbus.Array(self.service_uuids, signature='s')
        if self.solicit_uuids is not None:
            properties['SolicitUUIDs'] = dbus.Array(self.solicit_uuids, signature='s')
        if self.manufacturer_data is not None:
            properties['ManufacturerData'] = dbus.Dictionary(self.manufacturer_data, signature='qv')
        if self.service_data is not None:
            properties['ServiceData'] = dbus.Dictionary(self.service_data, signature='sv')
        if self.local_name is not None:
            properties['LocalName'] = dbus.String(self.local_name)
        if self.discoverable is not None and self.discoverable == True:
            properties['Discoverable'] = dbus.Boolean(self.discoverable)
        if self.include_tx_power:
            properties['Includes'] = dbus.Array(["tx-power"], signature='s')

        if self.data is not None:
            properties['Data'] = dbus.Dictionary(self.data, signature='yv')
        print(properties)
        return {bluetooth_constants.ADVERTISING_MANAGER_INTERFACE: properties}

    def get_path(self):
        return dbus.ObjectPath(self.path)

    @dbus.service.method(bluetooth_constants.DBUS_PROPERTIES, in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != bluetooth_constants.ADVERTISEMENT_INTERFACE:
            raise bluetooth_exceptions.InvalidArgsException()
        return self.get_properties()[bluetooth_constants.ADVERTISING_MANAGER_INTERFACE]

    @dbus.service.method(bluetooth_constants.ADVERTISING_MANAGER_INTERFACE, in_signature='', out_signature='')
    def Release(self):
        print('%s: Released' % self.path)


class Application(dbus.service.Object):
    def __init__(self, bus):
        self.path = '/'
        self.services = []
        dbus.service.Object.__init__(self, bus, self.path)
        print("Adding CANService to the Application")
        self.add_service(CANService(bus, '/org/bluez/ldsg', 0))

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_service(self, service):
        self.services.append(service)

    @dbus.service.method(bluetooth_constants.DBUS_OM_IFACE, out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        response = {}
        print('GetManagedObjects')

        for service in self.services:
            print("GetManagedObjects: service=" + service.get_path())
            response[service.get_path()] = service.get_properties()
            chrcs = service.get_characteristics()
            for chrc in chrcs:
                response[chrc.get_path()] = chrc.get_properties()
                descs = chrc.get_descriptors()
                for desc in descs:
                    response[desc.get_path()] = desc.get_properties()

        return response


class CANService(bluetooth_gatt.Service):
    def __init__(self, bus, path_base, index):
        print("Initializing CANService object")
        bluetooth_gatt.Service.__init__(self, bus, path_base, index, '12345678-1234-5678-1234-56789abcdef0', True)
        print("Adding CANCharacteristic to the service")
        self.add_characteristic(CANCharacteristic(bus, 0, self))


class CANCharacteristic(bluetooth_gatt.Characteristic):
    def __init__(self, bus, index, service):
        bluetooth_gatt.Characteristic.__init__(
            self, bus, index,
            '12345678-1234-5678-1234-56789abcdef1',
            ['read', 'notify'],
            service
        )
        self.notifying = False
        self.value = []
        self.start_can_listener()

    def start_can_listener(self):
        self.listener_thread = threading.Thread(target=self.listen_to_can)
        self.listener_thread.daemon = True
        self.listener_thread.start()

    def listen_to_can(self):
        bus = can.interface.Bus(channel='vcan0', bustype='socketcan')
        for msg in bus:
            can_data = bytearray(msg.data)
            self.value = list(can_data)
            print(f"Received CAN data: {self.value}")
            if self.notifying:
                self.notify_can_data()

    def ReadValue(self, options):
        print("ReadValue in CANCharacteristic called")
        return [dbus.Byte(v) for v in self.value]

    def notify_can_data(self):
        print(f"Notifying CAN data: {self.value}")
        self.PropertiesChanged(
            bluetooth_constants.GATT_CHARACTERISTIC_INTERFACE,
            {'Value': dbus.Array(self.value, signature='y')},
            []
        )

    def StartNotify(self):
        print("Starting CAN notifications")
        self.notifying = True

    def StopNotify(self):
        print("Stopping CAN notifications")
        self.notifying = False


def register_ad_cb():
    print('Advertisement registered OK')

def register_ad_error_cb(error):
    print('Error: Failed to register advertisement: ' + str(error))
    mainloop.quit()

def register_app_cb():
    print('GATT application registered')

def register_app_error_cb(error):
    print('Failed to register application: ' + str(error))
    mainloop.quit()

def set_connected_status(status):
    global connected
    if status == 1:
        print("connected")
        connected = 1
        stop_advertising()
    else:
        print("disconnected")
        connected = 0
        start_advertising()

def properties_changed(interface, changed, invalidated, path):
    if interface == bluetooth_constants.DEVICE_INTERFACE:
        if "Connected" in changed:
            set_connected_status(changed["Connected"])

def interfaces_added(path, interfaces):
    if bluetooth_constants.DEVICE_INTERFACE in interfaces:
        properties = interfaces[bluetooth_constants.DEVICE_INTERFACE]
        if "Connected" in properties:
            set_connected_status(properties["Connected"])

def stop_advertising():
    global adv
    global adv_mgr_interface
    print("Unregistering advertisement", adv.get_path())
    adv_mgr_interface.UnregisterAdvertisement(adv.get_path())

def start_advertising():
    global adv
    global adv_mgr_interface
    print("Registering advertisement", adv.get_path())
    adv_mgr_interface.RegisterAdvertisement(
        adv.get_path(), {},
        reply_handler=register_ad_cb,
        error_handler=register_ad_error_cb
    )


dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()
adapter_path = bluetooth_constants.BLUEZ_NAMESPACE + bluetooth_constants.ADAPTER_NAME
adv_mgr_interface = dbus.Interface(bus.get_object(bluetooth_constants.BLUEZ_SERVICE_NAME, adapter_path), bluetooth_constants.ADVERTISING_MANAGER_INTERFACE)

bus.add_signal_receiver(properties_changed,
                        dbus_interface=bluetooth_constants.DBUS_PROPERTIES,
                        signal_name="PropertiesChanged",
                        path_keyword="path")

bus.add_signal_receiver(interfaces_added,
                        dbus_interface=bluetooth_constants.DBUS_OM_IFACE,
                        signal_name="InterfacesAdded")

adv = Advertisement(bus, 0, 'peripheral')
start_advertising()

mainloop = GLib.MainLoop()

app = Application(bus)

print('Registering GATT application...')

service_manager = dbus.Interface(
    bus.get_object(bluetooth_constants.BLUEZ_SERVICE_NAME, adapter_path),
    bluetooth_constants.GATT_MANAGER_INTERFACE)

service_manager.RegisterApplication(app.get_path(), {},
                                     reply_handler=register_app_cb,
                                     error_handler=register_app_error_cb)

mainloop.run()
