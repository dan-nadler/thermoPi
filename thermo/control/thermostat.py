#!/usr/bin/python
import RPi.GPIO as GPIO
from thermo.common.models import *
from thermo.common import local_settings
from datetime import datetime, timedelta
import time
from sqlalchemy import func


class HVAC():
    def __init__(self):
        GPIO.setmode(local_settings.GPIO_MODE)

        self.user = local_settings.USER_NUMBER

        if 'HEAT' in local_settings.GPIO_PINS:
            self.heat_pin = local_settings.GPIO_PINS['HEAT']

            GPIO.setwarnings(False)
            GPIO.setup(self.heat_pin, GPIO.OUT)
            GPIO.setwarnings(True)

        else:
            raise Exception('No configuration for heating found in thermo.common.local_settings.py')

        self.check_relays()

    def turn_heat_on(self):
        GPIO.output(self.heat_pin, GPIO.HIGH)

    def turn_heat_off(self):
        GPIO.output(self.heat_pin, GPIO.LOW)

    def heat_relay_is_on(self):
        return GPIO.input(self.heat_pin) == 1

    def check_relays(self):
        if self.heat_pin is not None:
            try:
                self.turn_heat_on()
                assert (self.heat_relay_is_on() == True)

                self.turn_heat_off()
                assert (self.heat_relay_is_on() == False)

            except AssertionError:
                print("Heating relay check failed, did you assign the correct GPIO heat_pin?")


class Thermostat():

    def __init__(self):
        self.user_id = local_settings.USER_NUMBER

    def check_recent_temperature(self, minutes=5, verbose=False):
        session = get_session()
        indoor_temperatures = session.query(
            Temperature.location,
            func.sum(Temperature.value) / func.count(Temperature.value)
        )\
            .filter(Temperature.record_time > datetime.now() - timedelta(minutes=minutes))\
            .join(Sensor)\
            .filter(Sensor.indoors == True)\
            .filter(Sensor.user == self.user_id)\
            .group_by(Temperature.location)\
            .all()

        if verbose:
            for i in indoor_temperatures:
                print "%s, %.1f" % (i[0], i[1])

        return {i[0]: i[1] for i in indoor_temperatures}


class Schedule():

    def __init__(self):
        self.schedule = self.default()

    @staticmethod
    def default():
        session = get_session()
        results = session.query(Sensor)\
            .filter(Sensor.user == local_settings.USER_NUMBER)\
            .filter(Sensor.indoors == True)\
            .all()

        session.close()
        all_locations = [r.location for r in results]
        sched = {
            l: {
                'Weekdays': [
                    (0, 60.),
                    (645, 66.),
                    (715, 60.),
                    (1715, 68.),
                    (2230, 60.),
                ],
                'Weekends': [
                    (0, 65.),
                    (645, 66.),
                    (715, 60.),
                    (1715, 68.),
                    (2230, 60.),
                ]
            }
            for l in all_locations
        }
        return sched

    def current_target_temps(self):
        is_weekend = datetime.now().strftime('%a') in ['Sat', 'Sun']
        current_time = int(datetime.now().strftime('%H%M'))
        target = {}
        for room, day in self.schedule.iteritems():
            if is_weekend:
                temp = day['Weekends']
            else:
                temp = day['Weekdays']

            if current_time < temp[0][0]:
                target[room] = temp[0][1]
            else:
                for hour, tgt in temp:
                    if current_time > hour:
                        target[room] = tgt
        return target


if __name__ == '__main__':
    zone1 = HVAC()
    thermostat = Thermostat()

    current_targets = Schedule().current_target_temps()
    current_targets['Living Room (North Wall)'] = None # a test case

    try:
        while True:
            room_temps = thermostat.check_recent_temperature(minutes=1, verbose=True)

            deltas = {}
            for room, target in current_targets.iteritems():
                if target is None:
                    continue

                deltas[room] = room_temps[room] - target

                print("%s, %s: %.2f" % (datetime.now().strftime('%m/%d/%Y %H:%M:%S'), room, deltas[room]))

                # TODO write an algorithm to deterimine when to turn on/off heat
                if room_temps[room] < target and not zone1.heat_relay_is_on():
                    print("%s at %s. Turning heat on." % (room, deltas[room]))
                    zone1.turn_heat_on()

                if room_temps[room] >= target and zone1.heat_relay_is_on():
                    print("%s as %s. Turning heat off." % (room, deltas[room]))
                    zone1.turn_heat_off()

            time.sleep(10)

    except KeyboardInterrupt:
        print("Turning heat off.")
        zone1.turn_heat_off()