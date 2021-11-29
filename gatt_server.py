#!/usr/bin/python3

"""Copyright (c) 2019, Douglas Otwell

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import dbus
import pyaudio 
import numpy as np
import random
import csv
from datetime import datetime
from advertisement import Advertisement
from service import Application, Service, Characteristic, Descriptor
from gpiozero import CPUTemperature
import time
import board
import adafruit_dht
import spidev
import RPi.GPIO as GPIO

GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"
NOTIFY_TIMEOUT = 5000
AUDIO_TIMEOUT = 5

# child of advertisement class
class ThermometerAdvertisement(Advertisement):
    def __init__(self, index):
        Advertisement.__init__(self, index, "peripheral")
        self.add_local_name("Thermometer")
        self.include_tx_power = True

# thermometer service class inherits from service class
class ThermometerService(Service):
    THERMOMETER_SVC_UUID = "00000001-710e-4a5b-8d75-3e5b444bc3cf"

    def __init__(self, index):
        self.farenheit = True
        
        Service.__init__(self, index, self.THERMOMETER_SVC_UUID, True)
        self.add_characteristic(TempCharacteristic(self))
        self.add_characteristic(UnitCharacteristic(self))

    def is_farenheit(self):
        return self.farenheit

    def set_farenheit(self, farenheit):
        self.farenheit = farenheit

# child  of characteristic subclass, added to thermometer service
# main characteristic of service
class TempCharacteristic(Characteristic):
    TEMP_CHARACTERISTIC_UUID = "00000002-710e-4a5b-8d75-3e5b444bc3cf"

    def __init__(self, service):
        self.notifying = False

        Characteristic.__init__(
                self, self.TEMP_CHARACTERISTIC_UUID,
                ["notify", "read"], service)
        self.add_descriptor(TempDescriptor(self))

    def get_temperature(self):
        value = []
        unit = "C"

        cpu = CPUTemperature()
        temp = cpu.temperature
        temp = 100
        if self.service.is_farenheit():
            temp = (temp * 1.8) + 32
            unit = "F"

        strtemp = str(round(temp, 1)) + " " + unit
        
        print(f'The temperature is {strtemp}')
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")
        
        with open('CPU_TEMP_TIMESTAMP_SERVER.csv', 'a', encoding = 'UTF8') as f:
            writer = csv.writer(f)
            writer.writerow([strtemp, current_time])
            f.close()
            
        for c in strtemp:
            value.append(dbus.Byte(c.encode()))
        
        print(f'The value has been ecoded as {value}')
        
        return value

    def set_temperature_callback(self):
        if self.notifying:
            value = self.get_temperature()
            self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": value}, [])

        return self.notifying

    def StartNotify(self):
        if self.notifying:
            return

        self.notifying = True

        value = self.get_temperature()
        self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": value}, [])
        # makes call to callback function, reading the temperature
        self.add_timeout(NOTIFY_TIMEOUT, self.set_temperature_callback)

    def StopNotify(self):
        self.notifying = False

    def ReadValue(self, options):
        value = self.get_temperature()

        return value

class TempDescriptor(Descriptor):
    TEMP_DESCRIPTOR_UUID = "2901"
    TEMP_DESCRIPTOR_VALUE = "CPU Temperature"

    def __init__(self, characteristic):
        Descriptor.__init__(
                self, self.TEMP_DESCRIPTOR_UUID,
                ["read"],
                characteristic)

    def ReadValue(self, options):
        value = []
        desc = self.TEMP_DESCRIPTOR_VALUE

        for c in desc:
            value.append(dbus.Byte(c.encode()))

        return value
    
# child  of characteristic subclass, added to thermometer service
# describes the unit (celsius or farenheit)
class UnitCharacteristic(Characteristic):
    UNIT_CHARACTERISTIC_UUID = "00000003-710e-4a5b-8d75-3e5b444bc3cf"

    def __init__(self, service):
        Characteristic.__init__(
                self, self.UNIT_CHARACTERISTIC_UUID,
                ["read", "write"], service)
        self.add_descriptor(UnitDescriptor(self))

    def WriteValue(self, value, options):
        val = str(value[0]).upper()
        if val == "C":
            self.service.set_farenheit(False)
        elif val == "F":
            self.service.set_farenheit(True)

    def ReadValue(self, options):
        value = []

        if self.service.is_farenheit(): val = "F"
        else: val = "C"
        value.append(dbus.Byte(val.encode()))

        return value

class UnitDescriptor(Descriptor):
    UNIT_DESCRIPTOR_UUID = "2901"
    UNIT_DESCRIPTOR_VALUE = "Temperature Units (F or C)"

    def __init__(self, characteristic):
        Descriptor.__init__(
                self, self.UNIT_DESCRIPTOR_UUID,
                ["read"],
                characteristic)

    def ReadValue(self, options):
        value = []
        desc = self.UNIT_DESCRIPTOR_VALUE

        for c in desc:
            value.append(dbus.Byte(c.encode()))

        return value
    
class AirHumidityTempService(Service):
    

    def __init__(self, index):
        self.AIR_HUMIDITY_SVC_UUID = "9a1aefb0-3221-11ec-8d3d-0242ac130003"
        self.notifying = False
        self.dhtDevice = adafruit_dht.DHT22(board.D3, use_pulseio=False)
        
        Service.__init__(self, index, self.AIR_HUMIDITY_SVC_UUID, True)
        self.add_characteristic(AirTempCharacteristic(self))
        self.add_characteristic(AirHumidityCharacteristic(self))
    
    def is_farenheit(self):
        return self.farenheit

    def set_farenheit(self, farenheit):
        self.farenheit = farenheit


class AirTempCharacteristic(Characteristic):
    def __init__(self, service):
        self.notifying = False
        self.AIR_HUMIDITY_CHARACTERISTIC_UUID = "9a1aefb1-3221-11ec-8d3d-0242ac130003"
        Characteristic.__init__(self, self.AIR_HUMIDITY_CHARACTERISTIC_UUID,
                                ["notify", "read"], service)
        self.dhtDevice = service.dhtDevice

    def get_air_temp(self):
        value = []

        try:
            temp = self.dhtDevice.temperature
            temp_str = f'Temperature: {temp}'

            print(f'The air humidity is {temp_str}')

            for c in temp_str:
                value.append(dbus.Byte(c.encode()))
            return value

        except RuntimeError as error:
            # Errors happen fairly often, DHT's are hard to read, just keep going
            print(error.args[0])
            return (error.args[0])
            # time.sleep(1.0)


        except Exception as error:
            dhtDevice.exit()
            return (str(error))
            # raise error

    def set_temp_callback(self):
        if self.notifying:
            value = self.get_air_temp()
            self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": value}, [])

        return self.notifying

    def StartNotify(self):
        if self.notifying:
            return

        self.notifying = True

        value = self.get_air_temp()
        self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": value}, [])
        # makes call to callback function, reading the temperature
        self.add_timeout(NOTIFY_TIMEOUT, self.set_temp_callback)

    def StopNotify(self):
        self.notifying = False

    def ReadValue(self, options):
        value = self.get_air_temp()

        return value

class AirHumidityCharacteristic(Characteristic):
    def __init__(self, service):
        self.notifying = False
        self.AIR_HUMIDITY_CHARACTERISTIC_UUID = "9a1aefb2-3221-11ec-8d3d-0242ac130003"
        Characteristic.__init__(self, self.AIR_HUMIDITY_CHARACTERISTIC_UUID,
                ["notify", "read"], service)
        self.dhtDevice = service.dhtDevice
        
    def get_air_humidity(self):
        value = []
        
        try:
            humidity = self.dhtDevice.humidity
            humidity_str = f'Humidity: {humidity}'
            
            print(f'The air humidity is {humidity_str}')
            
            for c in humidity_str:
                value.append(dbus.Byte(c.encode()))
            return value
        
        except RuntimeError as error:
            # Errors happen fairly often, DHT's are hard to read, just keep going
            print(error.args[0])
            return(error.args[0])
            #time.sleep(1.0)
            
        
        except Exception as error:
            dhtDevice.exit()
            return (str(error))
            #raise error
        
        
    
    def set_humidity_callback(self):
        if self.notifying:
            value = self.get_air_humidity()
            self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": value}, [])

        return self.notifying

    def StartNotify(self):
        if self.notifying:
            return

        self.notifying = True

        value = self.get_air_humidity()
        self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": value}, [])
        # makes call to callback function, reading the temperature
        self.add_timeout(NOTIFY_TIMEOUT, self.set_humidity_callback)

    def StopNotify(self):
        self.notifying = False

    def ReadValue(self, options):
        value = self.get_air_humidity()

        return value
    
class VolumeService(Service):
    

    def __init__(self, index):
        self.VOLUME_SVC_UUID = "9a1aefb0-3221-11ec-8d3d-0242ac130003"
        Service.__init__(self, index, self.VOLUME_SVC_UUID, True)
        self.add_characteristic(VolumeLevelCharacteristic(self))

class VolumeLevelCharacteristic(Characteristic):
    
    def __init__(self, service):
        self.VOLUME_LEVEL_CHARACTERISTIC_UUID = "989f22a4-48ac-11ec-81d3-0242ac130003"
        Characteristic.__init__(
                self, self.VOLUME_LEVEL_CHARACTERISTIC_UUID,
                ["write-without-response"], service)
        
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self.spi.max_speed_hz = 976000
        
    def write_pot(self, input):
        print(input)
        msb = input >> 8
        lsb = input & 0xFF
        self.spi.xfer([msb, lsb])
    
    def WriteValue(self, value, options):
        try:
            #val = str(value[0]).upper()
            #print(value)
            #print(value)
            val = ord(bytes(value))
            self.write_pot((val))
            #print(hex(val))
        except(e):
            print(e)
class FanService(Service):
    

    def __init__(self, index):
        self.FAN_SVC_UUID = "185cfc0a-48b2-11ec-81d3-0242ac130003"
        Service.__init__(self, index, self.FAN_SVC_UUID, True)
        self.add_characteristic(FanToggleCharacteristic(self))

class FanToggleCharacteristic(Characteristic):
    

    def __init__(self, service):
        self.FAN_TOGGLE_CHARACTERISTIC_UUID = "40146757-3237-11EC-8D3D-0242AC130003"
        Characteristic.__init__(
                self, self.FAN_TOGGLE_CHARACTERISTIC_UUID,
                ["write-without-response"], service)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(17, GPIO.OUT)
        
        
    def write_transistor(self, input):
        if (input == 1):
            GPIO.output(17, True)
        else:
            GPIO.output(17, False)
        print(input)
    
    def WriteValue(self, value, options):
        try:
            #val = str(value[0]).upper()
            #print(value)
            #print(value)
            val = ord(bytes(value))
            self.write_transistor((val))
            #print(hex(val))
        except(e):
            print(e)

class FontService(Service):
    

    def __init__(self, index):
        self.FONT_SVC_UUID = "9a1aefb1-3221-11ec-8d3d-0242ac130003"
        Service.__init__(self, index, self.FONT_SVC_UUID, True)
        self.add_characteristic(FontSizeCharacteristic(self))

class FontSizeCharacteristic(Characteristic):
    

    def __init__(self, service):
        self.FONT_SIZE_CHARACTERISTIC_UUID = "40146758-3237-11EC-8D3D-0242AC130003"
        Characteristic.__init__(
                self, self.FONT_SIZE_CHARACTERISTIC_UUID,
                ["write-without-response"], service)
        self.queue = queue    
        
    
    def WriteValue(self, value, options):
        try:
            #val = str(value[0]).upper()
            #print(value)
            #print(value)
            val = ord(bytes(value))
            self.write_pot((val))
            #print(hex(val))
        except(e):
            print(e)
            

    

