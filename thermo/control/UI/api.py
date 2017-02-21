import json
from datetime import datetime, timedelta

from sqlalchemy import func

from thermo import local_settings
from thermo.common.models import *
from thermo.control.thermostat import Schedule
from thermo.sensor.thermal import read_temp_sensor


@duplicate_locally
def set_constant_temperature(user, zone, temperature, expiration, local=False):
    """
    Send message to override temperature schedule for all sensors attached to the specified zone
    :param user: user id
    :param zone: zone affected
    :param temperature: float: temperature target
    :param expiration: datetime for expiration of temperature target
    :param local: Use the local SQLite database if true
    :return:
    """
    session = get_session(local=local)
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

    session = get_session(local=local)
    new_message = Message(record_time=datetime.now(), user=user, json=j, type='temperature override')
    session.add(new_message)
    session.commit()
    session.close()
    return

@fallback_locally
def get_schedules(user, local=False):
    """
    Retrieve all of a user's thermostat schedules as a python dictionary
    :param user:
    :return:
    """
    session = get_session(local=local)
    results = session.query(ThermostatSchedule, Zone)\
        .filter(ThermostatSchedule.zone == Zone.id)\
        .filter(ThermostatSchedule.user == user)\
        .all()

    response = {}
    for schedule, zone in results:
        response[zone.name] = {}
        response[zone.name][schedule.name] = json.loads(schedule.schedule)

    return response

@duplicate_locally
def set_schedule(user, zone, name, schedule, local=False):
    """
    Create a new thermostat schedule
    :param user:
    :param zone:
    :param name:
    :param schedule:
    :return:
    """
    session = get_session(local=local)
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

@duplicate_locally
def update_schedule(user, zone, name, schedule, local=False):
    """
    Update an existing thermostat schedule
    :param user:
    :param zone:
    :param name:
    :param schedule:
    :return:
    """
    session = get_session(local=local)
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

def get_action_status(user, zone):
    engine = get_engine()
    result = engine.execute(
        '''select record_time, value, target, unit.name as unit, action.name as name
from action, action_log, unit
where unit.user = {0}
and action.unit = unit.id
and action_log.action = action.id
and action_log.record_time >= (NOW() - INTERVAL 12 HOUR )
and action.zone = {1}
order by record_time desc
limit 1'''.format(user, zone)
    )

    last_action = result.fetchall()

    status_dict = {}
    for action in last_action:
        status_dict[action.name.title()] = {'status': action.value == 1, 'time': action.record_time}

    return status_dict

def get_current_room_temperatures(user, zone, minutes=1):
    try:
        session = get_session()
        indoor_temperatures = session.query(
            Temperature.location,
            func.sum(Temperature.value) / func.count(Temperature.value)
        ) \
            .filter(Temperature.record_time > datetime.now() - timedelta(minutes=minutes)) \
            .join(Sensor) \
            .filter(Sensor.user == user) \
            .filter(Sensor.zone == zone) \
            .group_by(Temperature.location) \
            .all()
        session.close()

        room_temps ={i[0]: i[1] for i in indoor_temperatures}

    except Exception as e:
        print('Exception, falling back to local sensor.')
        room_temps = {}
        is_on, room_temps[local_settings.FALLBACK['LOCATION']] = read_temp_sensor(local_settings.FALLBACK['SERIAL NUMBER'])
        if not is_on:
            print('EMERGENCY: Fallback sensor unavailable!')
            # TODO fallback to predictive model

    return room_temps

def get_thermostat_schedule(zone):
    schedule = ScheduleAPI(zone)
    schedule.get_override_messages()
    targets = schedule.current_target_temps()
    next_targets = schedule.get_next_target_temps()
    return targets, next_targets

class ScheduleAPI(Schedule):

    def __init__(self, zone):
        super(ScheduleAPI, self).__init__(zone)

    def get_override_messages(self):
        try:
            session = get_session()
            results = session.query(Message)\
                .filter(Message.user == local_settings.USER_NUMBER)\
                .filter(Message.received == True)\
                .filter(Message.type == 'temperature override')\
                .order_by(Message.record_time.asc())\
                .all()

            for msg in results:
                msg_dict = json.loads(msg.json)
                target = msg_dict['target']
                expiration = datetime.strptime(msg_dict['expiration'], "%Y-%m-%dT%H:%M:%S.%f")
                zone = int(msg_dict['zone'])

                for location, tgt in target.iteritems():
                    target[str(location)] = float(tgt)

                if zone == self.zone:
                    self.override = target
                    self.override_expiration = expiration

        except IndexError:
            # This error will occur if there are no unread messages
            pass

        finally:
            session.close()

        return

