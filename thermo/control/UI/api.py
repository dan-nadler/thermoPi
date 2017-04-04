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
    results = session.query(Sensor).filter(Sensor.user == user).filter(Sensor.zone == zone)
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
def get_available_schedules(user, zone, local=False):
    """

    :param user:
    :param zone:
    :param local:
    :return: [(name, id), ...]
    """
    session = get_session(local=local)
    results = session.query(ThermostatSchedule) \
        .filter(ThermostatSchedule.zone == zone) \
        .filter(ThermostatSchedule.user == user) \
        .all()
    session.close()

    names = [(r.name, r.id) for r in results]

    return names


@fallback_locally
def get_schedules(user, local=False):
    """
    Retrieve all of a user's thermostat schedules as a python dictionary
    :param user:
    :return:
    """
    session = get_session(local=local)
    results = session.query(ThermostatSchedule, Zone) \
        .filter(ThermostatSchedule.zone == Zone.id) \
        .filter(ThermostatSchedule.user == user) \
        .all()
    session.close()

    # TODO use datetime module for this instead?
    days = {
        '0': 'Monday',
        '1': 'Tuesday',
        '2': 'Wednesday',
        '3': 'Thursday',
        '4': 'Friday',
        '5': 'Saturday',
        '6': 'Sunday'
    }

    response = {}
    for schedule, zone in results:
        try:
            response[zone.name][schedule.name] = json.loads(schedule.schedule)
        except KeyError:
            response[zone.name] = {}
            response[zone.name][schedule.name] = json.loads(schedule.schedule)

    final_response = response
    for schedule, zone in results:
        for location, sched in response[zone.name][schedule.name].iteritems():
            for day, t in sched.iteritems():
                try:
                    final_response[zone.name][schedule.name][location][days[day]] = \
                        response[zone.name][schedule.name][location][day]
                    del final_response[zone.name][schedule.name][location][day]

                    new = []
                    for hour, temp in final_response[zone.name][schedule.name][location][days[day]]:
                        h = hour[:2]
                        m = hour[2:]

                        if int(h) >= 12:
                            ap = 'pm'
                        else:
                            ap = 'am'

                        if h == '00':
                            h = '12'

                        if int(h) > 12:
                            h = int(h) - 12
                            if h < 10:
                                h = '0' + str(h)
                            else:
                                h = str(h)

                        new.append((h + ':' + m + ' ' + ap, temp))

                    final_response[zone.name][schedule.name][location][days[day]] = new

                except KeyError:
                    pass

    return final_response


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
    results = session.query(ThermostatSchedule) \
        .filter(ThermostatSchedule.zone == zone) \
        .filter(ThermostatSchedule.user == user) \
        .filter(ThermostatSchedule.name == name) \
        .all()

    if len(results) > 0:
        raise Exception('Duplicate schedule found.')

    ts = ThermostatSchedule(user=user, zone=zone, name=name, schedule=json.dumps(schedule))
    session.add(ts)
    session.commit()
    session.close()

    return


@duplicate_locally
def activate_schedule(user, zone, id, local=False):
    session = get_session(local)
    results1 = session \
        .query(ThermostatSchedule) \
        .filter(ThermostatSchedule.id == id) \
        .filter(ThermostatSchedule.user == user) \
        .filter(ThermostatSchedule.zone == zone) \
        .all()

    if len(results1) > 1:
        raise (Exception(
            'Found multiple schedules for this id/user/zone combination. id={0}, user={1}, zone={2}'.format(id, user,
                                                                                                            zone)))

    results1[0].active = 1

    results2 = session \
        .query(ThermostatSchedule) \
        .filter(ThermostatSchedule.id != id) \
        .filter(ThermostatSchedule.user == user) \
        .filter(ThermostatSchedule.zone == zone) \
        .all()
    for r in results2:
        r.active = 0

    session.commit()
    session.close()
    return True


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
            func.sum(Temperature.value - Sensor.bias) / func.count(Temperature.value)
        ) \
            .filter(Temperature.record_time > datetime.now() - timedelta(minutes=minutes)) \
            .join(Sensor) \
            .filter(Sensor.user == user) \
            .filter(Sensor.zone == zone) \
            .group_by(Temperature.location) \
            .all()
        session.close()

        room_temps = {i[0]: i[1] for i in indoor_temperatures}

    except Exception as e:
        logging.exception('Exception, falling back to local sensor.')
        room_temps = {}
        try:
            is_on, room_temps[local_settings.FALLBACK['LOCATION']] = read_temp_sensor(
                local_settings.FALLBACK['SERIAL NUMBER'])
            if not is_on:
                raise Exception

        except Exception as e2:
            logging.error('EMERGENCY: Fallback sensor unavailable!')
            logging.error('Parent Exception:')
            logging.exception(e)
            logging.error('Nested Exception:')
            logging.exception(e2)

    return room_temps


def get_thermostat_schedule(zone):
    schedule = ScheduleAPI(zone)
    schedule.get_override_messages()
    targets = schedule.current_target_temps()
    next_targets = schedule.get_next_target_temps()

    return targets, next_targets, schedule.schedule_name


class ScheduleAPI(Schedule):
    def __init__(self, zone):
        super(ScheduleAPI, self).__init__(zone)

    def get_override_messages(self):
        try:
            session = get_session()
            results = session.query(Message) \
                .filter(Message.user == local_settings.USER_NUMBER) \
                .filter(Message.received == True) \
                .filter(Message.type == 'temperature override') \
                .order_by(Message.record_time.asc()) \
                .all()

            for msg in results:
                msg_dict = json.loads(msg.json)
                target = msg_dict['target']
                try:
                    expiration = datetime.strptime(msg_dict['expiration'], "%Y-%m-%dT%H:%M:%S.%f")
                except ValueError:
                    expiration = datetime.strptime(msg_dict['expiration'], "%Y-%m-%dT%H:%M:%S")
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


def check_local(request, token=None):
    s = request.remote_addr.split('.')
    if s[0] == '192' and s[1] == '168':
        return
    else:
        session = get_session()
        results = session.query(User).filter(User.id == local_settings.USER_NUMBER).all()[0]
        key = results.api_key
        session.close()

        if request.args.get('controltoken', token) == key:
            return
        else:
            raise Exception('Failed to validate.')
