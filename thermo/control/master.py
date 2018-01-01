import time

import RPi.GPIO as GPIO

from thermo import local_settings
from thermo.common.models import *
from thermo.control import thermostat
from thermo.sensor import thermal


def main(available_actions, available_sensors, structs, **kwargs):
    # Assume all sensors are thermal for now
    # Check thermal sensors:
    try:
        thermal.main(
            local_settings.USER_NUMBER,
            local_settings.UNIT_NUMBER,
            available_sensors,
            verbosity=kwargs.get('verbosity', 0),
            validate=kwargs.get('validate', True)
        )
    except Exception as e:
        logging.error('thermal.main error')
        logging.exception(e)

    try:
        clean_old_temps_from_local()
    except Exception as e:
        logging.error('Encountered an error while removing old temperatures from the local db.')
        logging.exception(e)

    for a in available_actions:
        if a.name == 'HEAT':
            # Check thermostat / HVAC:
            try:
                thermostat.main(structs['HVAC'], verbosity=kwargs.get('verbosity', 0))
            except Exception as e:
                logging.error('Uncaught exception in thermostat.main.')
                structs['HVAC'].turn_heat_off()
                logging.exception(e)


@fallback_locally
def setup(local=False, **kwargs):
    # Get all available actions and sensors for this unit

    session = get_session(local=local)
    unit = session.query(Unit).filter(Unit.user == local_settings.USER_NUMBER).filter(
        Unit.id == local_settings.UNIT_NUMBER).all()

    if len(unit) > 1:
        logging.error('Non-unique unit and user combination')
        raise Exception('Non-unique unit and user combination')

    unit = unit[0]

    available_sensors = unit.sensors
    available_actions = unit.actions
    session.close()

    structs = {}
    for i in range(len(available_actions)):
        a = available_actions[i]
        logging.debug('Action %s' % a.name)

        if a.enabled == False:
            logging.debug('Action disabled.')
            del available_actions[i]
            continue

        if a.name == 'HEAT':
            structs['HVAC'] = thermostat.HVAC(a.zone, log=kwargs.get('log', True),
                                              schedule=kwargs.get('schedule', None))
            if kwargs.get('initial', False):
                logging.debug('Testing relays for HVAC.')
                structs['HVAC'].cycle_relays()

    return available_actions, available_sensors, structs


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--verbosity', type=int, default=0)
    parser.add_argument('--disable-log', default=True, action='store_false')
    parser.add_argument('--dry-run', default=False, action='store_true')
    parser.add_argument('--sleep', default=10, type=int)
    parser.add_argument('--boot-sleep', default=0, type=int)
    parser.add_argument('--validate', default=1, type=int)

    args = parser.parse_args()

    time.sleep(args.boot_sleep)

    logging.basicConfig(**local_settings.LOGGING)
    verbosity = args.verbosity
    validate = bool(args.validate)
    log = args.disable_log
    dry_run = args.dry_run
    sleep = args.sleep

    # This is done as a precaution to avoid a runaway furnace. In the event that an uncaught exception causes thermoPi
    # to crash, it is possible that the furnace relay will be in the 'on' position. The script, upon restarting, may
    # not be able to resume the thermostat control program. This block ensures that the heat relay is switched off
    # in such a circumstance.
    if 'HEAT' in local_settings.GPIO_PINS:
        GPIO.setmode(local_settings.GPIO_MODE)
        GPIO.setwarnings(False)
        GPIO.setup(local_settings.GPIO_PINS['HEAT'], GPIO.OUT)
        GPIO.setwarnings(True)
        GPIO.output(local_settings.GPIO_PINS['HEAT'], GPIO.LOW)

    logging.debug('Updating available actions and sensors.')

    available_actions, available_sensors, structs = setup(log=log, verbosity=verbosity, initial=True)

    i = 0
    while True:
        i += 1

        if i % (60 / sleep) == 0 or sleep > 60:  # update available sensors and actions every minute

            logging.debug('Updating available actions and sensors.')
            try:
                schedule = structs['HVAC'].schedule  # pass the existing schedule to HVAC if it is set
            except:
                schedule = None  # default, otherwise

            try:
                available_actions, available_sensors, structs = setup(log=log, verbosity=verbosity, schedule=schedule)
            except:
                pass

        main(available_actions, available_sensors, structs, log=log, verbosity=verbosity, validate=validate)
        time.sleep(sleep)
