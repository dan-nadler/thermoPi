#!/usr/bin/python
import time
from datetime import datetime, timedelta
import RPi.GPIO as GPIO
import numpy as np
from sqlalchemy import func
from thermo import local_settings
from thermo.common.models import *


class HVAC():
    def __init__(self):
        GPIO.setmode(local_settings.GPIO_MODE)

        self.user = local_settings.USER_NUMBER

        if 'HEAT' in local_settings.GPIO_PINS:
            self.heat_pin = local_settings.GPIO_PINS['HEAT']

            GPIO.setwarnings(False)
            GPIO.setup(self.heat_pin, GPIO.OUT)
            GPIO.setwarnings(True)

            session = get_session()
            results = session.query(Action)\
                .filter(Action.user == local_settings.USER_NUMBER)\
                .filter(Action.unit == local_settings.UNIT_NUMBER)\
                .filter(Action.name == 'Heat')\
                .all()
            if len(results) == 1:
                self.heat_action_id = results[0].id
            else:
                self.heat_action_id = None
                raise Warning('Could not resolve action ID, logging is disabled!')

        else:
            raise Exception('No configuration for heating found in thermo.common.local_settings.py')

        self.check_relays()

    def temps_to_heat(self, target, temp, verbose=False):
        if room_temps[room] < target and not self.heat_relay_is_on():
            if verbose:
                print("%s vs target %s. Turning heat on." % (temp, target))
            self.turn_heat_on()

        if room_temps[room] >= target and self.heat_relay_is_on():
            if verbose:
                print("%s vs target %s. Turning heat off." % (temp, target))
            self.turn_heat_off()

    def log_action(self, action, value):
        if self.heat_action_id is not None:
            session = get_session()
            try:
                new_action = ActionLog(action = action, value=value, record_time=datetime.now())
                session.add(new_action)
                session.commit()
            except Exception as e:
                session.rollback()
            finally:
                session.close()

    def turn_heat_on(self):
        GPIO.output(self.heat_pin, GPIO.HIGH)
        self.log_action(self.heat_action_id, 1)

    def turn_heat_off(self):
        GPIO.output(self.heat_pin, GPIO.LOW)
        self.log_action(self.heat_action_id, 0)

    def heat_relay_is_on(self):
        return GPIO.input(self.heat_pin) == 1

    def check_relays(self):
        if self.heat_pin is not None:
            try:
                GPIO.output(self.heat_pin, GPIO.HIGH)
                assert (self.heat_relay_is_on() == True)

                GPIO.output(self.heat_pin, GPIO.LOW)
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
        self.schedule = self.default_temperatures()

    @staticmethod
    def default_temperatures():
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
                    (715, 60.),
                    (1715, 68.),
                    (2230, 60.),
                ],
                'Weekends': [
                    (0, 60.),
                    (800, 67.),
                    (1715, 68.),
                    (2230, 60.),
                ]
            }
            for l in all_locations if l != 'Bedroom'
        }

        sched['Bedroom'] = {
            'Weekdays': [
                (0, 60.),
                (645, 66.),
                (730, 60.),
                (2000, 68.),
                (2230, 60.),
            ],
            'Weekends': [
                (0, 60.),
                (800, 66.),
                (1000, 60.),
                (2100, 64.),
                (2230, 60.),
            ]
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

    try:
        while True:
            room_temps = thermostat.check_recent_temperature(minutes=1)

            deltas = {}
            for room, target in current_targets.iteritems():
                if target is None:
                    continue

                deltas[room] = room_temps[room] - target

                print("%s, %s: %.2f, %.2f, %.2f" % (datetime.now().strftime('%m/%d/%Y %H:%M:%S'), room, target, room_temps[room], deltas[room]))

            zone1_target = np.median([val for key, val in current_targets.iteritems()])
            zone1_temp = np.median([val for key, val in room_temps.iteritems()])

            zone1.temps_to_heat(zone1_target, zone1_temp, verbose=True)

            time.sleep(10)

    except KeyboardInterrupt:
        print("Turning heat off.")
        zone1.turn_heat_off()