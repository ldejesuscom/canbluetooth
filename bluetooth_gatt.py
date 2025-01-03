import dbus
import dbus.service
import bluetooth_constants
import bluetooth_exceptions

class Service(dbus.service.Object):
    def __init__(self, bus, path_base, index, uuid, primary):
        self.path = f"{path_base}/service{index}"
        self.bus = bus
        self.uuid = uuid
        self.primary = primary
        self.characteristics = []
        dbus.service.Object.__init__(self, bus, self.path)

    def add_characteristic(self, characteristic):
        self.characteristics.append(characteristic)

    def get_characteristic_paths(self):
        return [char.get_path() for char in self.characteristics]

    def get_properties(self):
        return {
            bluetooth_constants.GATT_SERVICE_INTERFACE: {
                'UUID': self.uuid,
                'Primary': self.primary,
                'Characteristics': dbus.Array(self.get_characteristic_paths(), signature='o')
            }
        }

    @dbus.service.method(bluetooth_constants.DBUS_PROPERTIES,
                         in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != bluetooth_constants.GATT_SERVICE_INTERFACE:
            raise bluetooth_exceptions.InvalidArgsException()
        return self.get_properties()[bluetooth_constants.GATT_SERVICE_INTERFACE]

class Characteristic(dbus.service.Object):
    def __init__(self, bus, index, uuid, flags, service):
        self.path = f"{service.path}/char{index}"
        self.bus = bus
        self.uuid = uuid
        self.flags = flags
        self.service = service
        self.descriptors = []
        dbus.service.Object.__init__(self, bus, self.path)

    def add_descriptor(self, descriptor):
        self.descriptors.append(descriptor)

    def get_descriptor_paths(self):
        return [desc.get_path() for desc in self.descriptors]

    def get_properties(self):
        return {
            bluetooth_constants.GATT_CHARACTERISTIC_INTERFACE: {
                'UUID': self.uuid,
                'Service': self.service.get_path(),
                'Flags': dbus.Array(self.flags, signature='s'),
                'Descriptors': dbus.Array(self.get_descriptor_paths(), signature='o')
            }
        }

    @dbus.service.method(bluetooth_constants.DBUS_PROPERTIES,
                         in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != bluetooth_constants.GATT_CHARACTERISTIC_INTERFACE:
            raise bluetooth_exceptions.InvalidArgsException()
        return self.get_properties()[bluetooth_constants.GATT_CHARACTERISTIC_INTERFACE]

    @dbus.service.method(bluetooth_constants.GATT_CHARACTERISTIC_INTERFACE,
                         in_signature='a{sv}', out_signature='ay')
    def ReadValue(self, options):
        print("Default ReadValue called, returning error")
        raise bluetooth_exceptions.NotSupportedException()

    @dbus.service.method(bluetooth_constants.GATT_CHARACTERISTIC_INTERFACE,
                         in_signature='aya{sv}', out_signature='')
    def WriteValue(self, value, options):
        print("Default WriteValue called, returning error")
        raise bluetooth_exceptions.NotSupportedException()

    @dbus.service.method(bluetooth_constants.GATT_CHARACTERISTIC_INTERFACE,
                         in_signature='', out_signature='')
    def StartNotify(self):
        print("Default StartNotify called, returning error")
        raise bluetooth_exceptions.NotSupportedException()

    @dbus.service.method(bluetooth_constants.GATT_CHARACTERISTIC_INTERFACE,
                         in_signature='', out_signature='')
    def StopNotify(self):
        print("Default StopNotify called, returning error")
        raise bluetooth_exceptions.NotSupportedException()
