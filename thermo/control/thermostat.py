import time
from datetime import datetime, timedelta
import RPi.GPIO as GPIO
import numpy as np
from sqlalchemy import func
from thermo import local_settings
from thermo.common.models import *
from thermo.sensor.thermal import read_temp_sensor
import pandas as pd
from collections import namedtuple


class HVAC():
    def __init__(self, zone, log=True):
        self.log = log
        self.zone = zone

        GPIO.setmode(local_settings.GPIO_MODE)

        self.user = local_settings.USER_NUMBER
        self.unit = local_settings.UNIT_NUMBER

        try:
            session = get_session()
            local_sensors = session.query(Sensor).filter(Sensor.unit == self.unit).filter(Sensor.user == self.user).all()
            session.close()
        except:
            local_sensors = [Sensor(
                unit=local_settings.UNIT_NUMBER,
                user=local_settings.USER_NUMBER,
                serial_number=local_settings.FALLBACK['SERIAL NUMBER'],
                location=local_settings.FALLBACK['LOCATION'],
                indoors=True
            )]

        self.fallback_sensors = [ (s.location, s.serial_number) for s in local_sensors if s.indoors == True ]
        if len(self.fallback_sensors) == 0:
            print('Warning: No local backup sensors available.')

        if 'HEAT' in local_settings.GPIO_PINS:
            self.heat_pin = local_settings.GPIO_PINS['HEAT']

            GPIO.setwarnings(False)
            GPIO.setup(self.heat_pin, GPIO.OUT)
            GPIO.setwarnings(True)

            try:
                session = get_session()
                results = session.query(Action)\
                    .filter(Action.unit == self.unit)\
                    .filter(Action.name == 'HEAT')\
                    .all()
                session.close()
                if len(results) == 1:
                    self.heat_action_id = results[0].id
                else:
                    self.heat_action_id = None
                    print('Warning: Could not resolve action ID, logging is disabled!')
            except:
                self.heat_action_id = None
                print('Warning: Could not resolve action ID, logging is disabled!')

        else:
            raise Exception('No configuration for heating found in thermo.common.local_settings.py')

        try:
            self.heat_relay_is_on()
        except Exception as e:
            raise e

        self.retrieve_lags()

    def retrieve_lags(self):
        try:
            session = get_session()
            action = session.query(Action).filter(Action.id == self.heat_action_id).all()[0]
            self.heat_off_lag, self.heat_on_lag = action.expected_overshoot_above, action.expected_overshoot_below
            session.close()
        except:
            self.heat_off_lag, self.heat_on_lag = 0., 0.

    def update_lags(self, num_recent_actions=2, overwrite=False):
        above, below = self.check_recent_lag(num_recent_actions=num_recent_actions)
        session = get_session()
        action = session.query(Action).filter(Action.id == self.heat_action_id).all()[0]
        if overwrite:
            action.expected_overshoot_above = float(above)
            action.expected_overshoot_below = float(below)
        else:
            action.expected_overshoot_above += float(above)
            action.expected_overshoot_below += float(below)
        session.commit()

        self.heat_off_lag, self.heat_on_lag = action.expected_overshoot_above, action.expected_overshoot_below
        session.close()

        return self.heat_off_lag, self.heat_on_lag

    def temps_to_heat(self, target, temp, verbose=False, buffer=1.):

        if self.heat_relay_is_on():
            target += buffer
            target -= self.heat_off_lag  # turn off the heat a little early (target lower) to max out at the right temp

        else:
            target -= buffer
            target -= self.heat_on_lag  # turn on the heat a little early (target higher, heat_on_lag is negative) to bottom out at the right temp

        if temp < target and not self.heat_relay_is_on():

            if verbose:
                print("%s vs target %s. Turning heat on." % (temp, target))
            self.turn_heat_on(target=target)

        elif temp >= target and self.heat_relay_is_on():
            if verbose:
                print("%s vs target %s. Turning heat off." % (temp, target))
            self.turn_heat_off(target=target)

        else:
            if verbose:
                print('Target: %.2f, Measured: %.2f' % (target, temp))

    def log_action(self, action, value, target=None):
        if self.log == False:
            return

        elif self.heat_action_id is not None:
            session = get_session()
            try:
                new_action = ActionLog(action=action, value=value, record_time=datetime.now(), target=float(target))
                session.add(new_action)
                session.commit()
            except Exception as e:
                session.rollback()
            finally:
                session.close()

    def turn_heat_on(self, **kwargs):
        GPIO.output(self.heat_pin, GPIO.HIGH)
        self.log_action(self.heat_action_id, 1, target=kwargs.get('target', None))

    def turn_heat_off(self, **kwargs):
        GPIO.output(self.heat_pin, GPIO.LOW)
        self.log_action(self.heat_action_id, 0, target=kwargs.get('target', None))

    def heat_relay_is_on(self):
        return GPIO.input(self.heat_pin) == 1

    def cycle_relays(self):

        if self.heat_pin is not None:
            try:
                if self.heat_relay_is_on():

                    GPIO.output(self.heat_pin, GPIO.LOW)
                    assert (self.heat_relay_is_on() == False)

                    GPIO.output(self.heat_pin, GPIO.HIGH)
                    assert (self.heat_relay_is_on() == True)

                else:

                    GPIO.output(self.heat_pin, GPIO.HIGH)
                    assert (self.heat_relay_is_on() == True)

                    GPIO.output(self.heat_pin, GPIO.LOW)
                    assert (self.heat_relay_is_on() == False)

            except AssertionError:
                print("Heating relay check failed, did you assign the correct GPIO heat_pin?")

    def check_recent_temperature(self, minutes=5, verbose=False):
        session = get_session()
        indoor_temperatures = session.query(
                Temperature.location,
                func.sum(Temperature.value) / func.count(Temperature.value)
            )\
            .filter(Temperature.record_time > datetime.now() - timedelta(minutes=minutes))\
            .join(Sensor)\
            .filter(Sensor.user == self.user)\
            .filter(Sensor.zone == self.zone)\
            .group_by(Temperature.location)\
            .all()
        session.close()
        if verbose:
            for i in indoor_temperatures:
                print "%s, %.1f" % (i[0], i[1])

        return {i[0]: i[1] for i in indoor_temperatures}

    def check_recent_lag(self, minutes=3, num_recent_actions=10, verbose=False):
        """
        Check the <num_recent_actions> most recent actions, and calculate the drift in temperature
        from the action to the local min/max temperature
        :param minutes:
        :param num_recent_actions:
        :param verbose:
        :return: temp lag off, temp lag on
        """

        session = get_session()
        a = session.query(ActionLog) \
            .filter(ActionLog.action == 1) \
            .order_by(ActionLog.record_time.desc()) \
            .limit(num_recent_actions) \
            .all()
        session.close()

        actions = [(i.value, i.record_time, i.target) for i in a]

        session = get_session()
        t = session.query(Temperature) \
            .filter(Temperature.record_time >= actions[-1][1]) \
            .filter(Temperature.record_time <= actions[0][1] + timedelta(minutes=minutes)) \
            .join(Sensor) \
            .filter(Sensor.zone == self.zone).all()
        session.close()

        df = pd.DataFrame([(T.record_time, T.location, T.value) for T in t])
        df.columns = ['record_time', 'location', 'value']

        df = df.pivot_table(index='record_time', columns='location', values='value')

        df = df.resample('10S', how='mean')
        df[np.abs(df.ffill() - pd.rolling_median(df.ffill(), 5)) > 5] = np.nan
        df = df.interpolate('linear')

        df2 = pd.DataFrame(
            {
                'heat': {b: a for a, b, c in actions},
                'target': {b: c for a, b, c in actions},
                'temp': df.median(axis=1).resample('S').interpolate('linear')
            }
        )

        lag_on = []
        lag_off = []

        temp_lag_on = []
        temp_lag_off = []

        for row in df2.dropna(subset=['heat','target']).T.iteritems():
            if row[1]['heat'] == 1:
                heat_cusp = df2.ix[row[0]:row[0] + timedelta(minutes=minutes)].idxmin()['temp']
                if not pd.isnull(heat_cusp):
                    lag_on.append(heat_cusp - row[0])

                temp_cusp = df2.ix[row[0]:row[0] + timedelta(minutes=minutes)].min()['temp']
                if not pd.isnull(heat_cusp) and not pd.isnull(temp_cusp) and not pd.isnull(row[1]['target']):
                    temp_lag_on.append(temp_cusp - row[1]['target'])

            else:
                heat_cusp = df2.ix[row[0]:row[0] + timedelta(minutes=minutes)].idxmax()['temp']
                if not pd.isnull(heat_cusp):
                    lag_off.append(heat_cusp - row[0])

                temp_cusp = df2.ix[row[0]:row[0] + timedelta(minutes=minutes)].max()['temp']
                if not pd.isnull(heat_cusp) and not pd.isnull(temp_cusp) and not pd.isnull(row[1]['target']):
                    temp_lag_off.append(temp_cusp - row[1]['target'])

        return np.mean(temp_lag_off), np.mean(temp_lag_on)


class Schedule():

    def __init__(self):
        self.schedule = self.default_temperatures()

    @staticmethod
    def default_temperatures():
        try:
            session = get_session()
            results = session.query(Sensor)\
                .filter(Sensor.user == local_settings.USER_NUMBER)\
                .filter(Sensor.indoors == True)\
                .all()
            session.close()
            all_locations = [r.location for r in results]
        except:
            all_locations = [local_settings.FALLBACK['LOCATION']]

        sched = {
            l: {
                'Weekdays': [
                    (0, 60.),
                    (630, 66.),
                    (715, 64.),
                    (1715, 68.),
                    (2230, 62.),
                ],
                'Weekends': [
                    (0, 60.),
                    (800, 67.),
                    (1715, 63.),
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


def main(hvac, verbosity=0):

    # Placeholder:
    current_targets = Schedule().current_target_temps()

    try:
        room_temps = hvac.check_recent_temperature(minutes=1)
    except Exception as e:
        print('Exception, falling back to local sensor.')
        room_temps = {}
        for location, serial_number in hvac.fallback_sensors:
            is_on, room_temps[location] = read_temp_sensor(serial_number)
            if not is_on:
                print('EMERGENCY: Fallback sensor unavailable!')
                # TODO fallback to predictive model
                return

    deltas = {}
    for room, target in current_targets.iteritems():
        if room not in room_temps:
            continue
        if target is None:
            continue


        deltas[room] = room_temps[room] - target

        if verbosity >= 2:
            print("%s, %s: %.2f, %.2f, %.2f" % (datetime.now().strftime('%m/%d/%Y %H:%M:%S'), room, target, room_temps[room], deltas[room]))

    zone_target = float(np.median([val for key, val in current_targets.iteritems()]))
    zone_temp = float(np.median([val for key, val in room_temps.iteritems()]))

    hvac.temps_to_heat(zone_target, zone_temp, verbose=True if verbosity >= 1 else False, buffer=.5)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbosity', type=int, default=0)
    parser.add_argument('--disable-log', default=True, action='store_false')
    parser.add_argument('--dry-run', default=False, action='store_true')
    args = parser.parse_args()
    verbosity = args.verbosity
    log = args.disable_log
    dry_run = args.dry_run

    session = get_session()
    available_actions = session.query(User)\
        .filter(User.id == local_settings.USER_NUMBER)\
        .join(Action)\
        .filter(Action.unit == local_settings.UNIT_NUMBER)
    session.close()

    action_pins = {}
    for a in available_actions:

        if a.name == 'HEAT':
            hvac = HVAC(a.zone, log=log)

    if dry_run:
        hvac.heat_pin = 0;

    try:
        while True:
            main(hvac)
            time.sleep(10)

    except KeyboardInterrupt:
        print("Turning heat off.")
        if hvac.heat_relay_is_on():
            hvac.turn_heat_off()
        GPIO.cleanup()