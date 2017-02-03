#!/usr/bin/python
import RPi.GPIO as GPIO
from thermo.common.models import *
from datetime import datetime, timedelta
import time
from sqlalchemy import func


class HVAC():
    def __init__(self, heat_gpio_pin, gpio_mode=GPIO.BCM):
        self.heat_pin = heat_gpio_pin

        GPIO.setwarnings(False)
        GPIO.setmode(gpio_mode)
        GPIO.setup(heat_gpio_pin, GPIO.OUT)
        GPIO.setwarnings(True)

        self.check_relays()

    def __exit__(self):
        GPIO.cleanup()

    def turn_heat_on(self):
        GPIO.output(self.heat_pin, GPIO.HIGH)

    def turn_heat_off(self):
        GPIO.output(self.heat_pin, GPIO.LOW)

    def heat_relay_is_on(self):
        return GPIO.input(self.heat_pin) == 1

    def check_relays(self):
        try:
            self.turn_heat_on()
            assert (self.heat_relay_is_on() == True)

            self.turn_heat_off()
            assert (self.heat_relay_is_on() == False)

        except AssertionError:
            print("Heating relay check failed, did you assign the correct GPIO heat_pin?")


class Thermostat():

    def __init__(self, user_id):
        self.user_id = user_id

    def check_recent_temperature(self, window=5, verbose=False):
        session = get_session()
        indoor_temperatures = session.query(
            Temperature.location,
            func.sum(Temperature.value) / func.count(Temperature.value)
        ).filter(
            Temperature.record_time > datetime.now() - timedelta(minutes=window)
        ).join(Sensor).filter(
            Sensor.indoors == True and Sensor.user == self.user_id
        ).group_by(
            Temperature.location
        ).all()

        if verbose:
            for i in indoor_temperatures:
                print "%s, %.1f" % (i[0], i[1])

        return {i[0]: i[1] for i in indoor_temperatures}

if __name__ == '__main__':
    zone1 = HVAC(25)

    thermostat = Thermostat(1)

    while True:

        room_temps = thermostat.check_recent_temperature(window=5)

        target = 70
        room = 'Living Room (South Wall)'

        print("%s: %.2f" % (datetime.now().strftime('%m/%d/%Y %H:%M:%S'), room_temps[room]))

        if room_temps[room] < target and not zone1.heat_relay_is_on():
            print("Turning heat on.")
            zone1.turn_heat_on()

        elif room_temps[room] >= target and zone1.heat_relay_is_on():
            print("Turning heat off.")
            zone1.turn_heat_off()

        time.sleep(10)