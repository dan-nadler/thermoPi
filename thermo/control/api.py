from thermo.common.models import *
from datetime import datetime, timedelta
import json


def set_constant_temperature(user, zone, temperature, expiration):
    """
    Send message to override temperature schedule for all sensors attached to the specified zone
    :param user: user id
    :param zone: zone affected
    :param temperature: float: temperature target
    :param expiration: datetime for expiration of temperature target
    :return:
    """
    session = get_session()
    results = session.query(Sensor).filter(Sensor.user==user).filter(Sensor.zone==zone)
    session.close()

    target = {}
    for sensor in results:
        target[sensor.location] = temperature

    message = {
        'target': target,
        'expiration': expiration.isoformat(),
        'zone': zone,
    }

    j = json.dumps(message)

    session = get_session()
    new_message = Message(record_time=datetime.now(), user=user, json=j, type='temperature override')
    session.add(new_message)
    session.commit()
    session.close()
    return

if __name__ == '__main__':
    set_constant_temperature(1,1,60,datetime.now()+timedelta(seconds=30))

def get_schedules(user):
    """
    Retrieve all of a user's thermostat schedules as a python dictionary
    :param user:
    :return:
    """
    session = get_session()
    results = session.query(ThermostatSchedule, Zone)\
        .filter(ThermostatSchedule.zone == Zone.id)\
        .filter(ThermostatSchedule.user == user)\
        .all()

    response = {}
    for schedule, zone in results:
        response[zone.name] = {}
        response[zone.name][schedule.name] = json.loads(schedule.schedule)

    return response

def set_schedule(user, zone, name, schedule):
    """
    Create a new thermostat schedule
    :param user:
    :param zone:
    :param name:
    :param schedule:
    :return:
    """
    session = get_session()
    results = session.query(ThermostatSchedule)\
        .filter(ThermostatSchedule.zone == zone)\
        .filter(ThermostatSchedule.user == user)\
        .filter(ThermostatSchedule.name == name)\
        .all()

    if len(results) > 0:
        raise Exception('Duplicate schedule found.')

    ts = ThermostatSchedule(user=user, zone=zone, name=name, schedule=json.dumps(schedule))
    session.add(ts)
    session.commit()
    session.close()

    return

def update_schedule(user, zone, name, schedule):
    """
    Update an existing thermostat schedule
    :param user:
    :param zone:
    :param name:
    :param schedule:
    :return:
    """
    session = get_session()
    results = session.query(ThermostatSchedule) \
        .filter(ThermostatSchedule.zone == zone) \
        .filter(ThermostatSchedule.user == user) \
        .filter(ThermostatSchedule.name == name) \
        .all()

    if len(results) == 0:
        raise Exception('Schedule not found.')

    if len(results) > 1:
        raise Exception('Multiple schedules found.')

    results[0] = ThermostatSchedule(user=user, zone=zone, name=name, schedule=json.dumps(schedule))
    session.commit()
    session.close()

    return
