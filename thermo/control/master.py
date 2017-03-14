import time

from thermo import local_settings
from thermo.common.models import *
from thermo.control import thermostat
from thermo.sensor import thermal


def main(available_actions, available_sensors, structs, **kwargs):


    # Assume all sensors are thermal for now
    # Check thermal sensors:
    thermal.main(
        local_settings.USER_NUMBER,
        local_settings.UNIT_NUMBER,
        available_sensors,
        verbosity=kwargs.get('verbosity', 0)
    )

    for a in available_actions:
        if a.name == 'HEAT':
            # Check thermostat / HVAC:
            thermostat.main(structs['HVAC'], verbosity=kwargs.get('verbosity', 0))


def setup(**kwargs):
    # Get all available actions and sensors for this unit
    available_actions = None

    try:
        session = get_session()
        unit = session.query(Unit).filter(Unit.user == local_settings.USER_NUMBER).filter(
            Unit.id == local_settings.UNIT_NUMBER).all()

        if len(unit) > 1:
            raise Exception("Non-unique unit and user combination")

        unit = unit[0]

        available_sensors = unit.sensors
        available_actions = unit.actions
        session.close()
    except:
        available_sensors = [
            Sensor(
                unit=local_settings.UNIT_NUMBER,
                user=local_settings.USER_NUMBER,
                serial_number=local_settings.FALLBACK['SERIAL NUMBER'],
                location=local_settings.FALLBACK['LOCATION'],
                indoors=True
            )
        ]

        if 'HEAT' in local_settings.GPIO_PINS:
            available_actions = [Action(name='HEAT', zone=local_settings.FALLBACK['ZONE'])]

    structs = {}
    for a in available_actions:
        if a.name == 'HEAT':
            structs['HVAC'] = thermostat.HVAC(a.zone, log=kwargs.get('log', True), schedule=kwargs.get('schedule', None))
            if kwargs.get('initial', False):
                if verbosity >= 2:
                    print('Testing relays for HVAC.')
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

    args = parser.parse_args()

    time.sleep(args.boot_sleep)

    verbosity = args.verbosity
    log = args.disable_log
    dry_run = args.dry_run
    sleep = args.sleep

    if verbosity >= 1:
        print('Updating available actions and sensors.')

    try:
        available_actions, available_sensors, structs = setup(log=log, verbosity=verbosity, initial=True)
    except Exception as e:
        print(e)
        raise(e)

    i = 0
    while True:
        i += 1

        if i % (60/sleep) == 0 or sleep > 60: # update available sensors and actions every minute
            if verbosity >= 1:
                print('Updating available actions and sensors.')
            try:
                schedule = structs['HVAC'].schedule # pass the existing schedule to HVAC if it is set
            except:
                schedule = None # default, otherwise

            try:
                available_actions, available_sensors, structs = setup(log=log, verbosity=verbosity, schedule=schedule)
            except:
                pass

        main(available_actions, available_sensors, structs, log=log, verbosity=verbosity)
        time.sleep(sleep)
