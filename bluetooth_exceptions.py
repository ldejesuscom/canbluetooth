from dbus.exceptions import DBusException

class InvalidArgsException(DBusException):
    _dbus_error_name = 'org.freedesktop.DBus.Error.InvalidArgs'

class NotPermittedException(DBusException):
    _dbus_error_name = 'org.freedesktop.DBus.Error.NotPermitted'

class NotSupportedException(DBusException):
    _dbus_error_name = 'org.freedesktop.DBus.Error.NotSupported'

class FailedException(DBusException):
    _dbus_error_name = 'org.freedesktop.DBus.Error.Failed'
