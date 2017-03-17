import re
import time
from datetime import datetime, timedelta

import numpy as np
from sqlalchemy.orm import sessionmaker

from thermo.common.models import Temperature, get_engine, Sensor, get_session

try:
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    database_connection = True
except:
    database_connection = False


def read_temp_sensor(device_id, units='F'):
    """
    Read temperature from the sensor and convert to <units>
    :param device_id:
    :param units:
    :return:
    """

    path = '/sys/bus/w1/devices/{0}/w1_slave'.format(device_id)
    with open(path, 'r') as f:
        line1 = f.readline().strip()
        line2 = f.readline().strip()

    is_on = re.search('[A-Z]+', line1).group()
    if is_on == 'NO':
        raise Exception('Sensor {} is offline.'.format(device_id))

    temp_raw_string = re.search('(t\=)(\-|)[0-9]+', line2).group()
    temp_raw = re.search('(\-|)[0-9]+', temp_raw_string).group()

    temp_celsius = float(temp_raw) / 1000.
    temp_fahrenheit = (temp_celsius * 9./5.) + 32.

    if units == 'F':
        out = temp_fahrenheit
    elif units == 'C':
        out = temp_celsius
    else:
        raise Exception('Units not recognized.')

    return is_on, out


def validate_temperature(value, sensor, record_time, deviation=3, lookback=5, limit=50, verbosity=0, local=False):
    """

    :param value: float
    :param sensor: Sensor SQLAlchemy ORM model
    :param record_time: datetime
    :return:
    """

    session = get_session(local=local)
    results = session.query(Temperature)\
        .filter(Temperature.record_time > record_time - timedelta(minutes=lookback))\
        .filter(Temperature.record_time <= record_time)\
        .join(Sensor).filter(Temperature.sensor == Sensor.id)\
        .filter(Sensor.user == sensor.user)\
        .filter(Sensor.zone == sensor.zone)\
        .order_by(Temperature.record_time)

    data = np.unique([r.value for r in results[-limit:]])
    session.close()

    if len(data) < 5:
        return True

    s = np.std(data)
    m = np.mean(data)
    z = np.abs(value-m) / s

    if verbosity >= 3:
        print('Std: {0}, Mean: {1}'.format(s,m))

    if verbosity >= 2:
        print('%.2f is %.2f standard deviations from mean of %.2f' % (value, z, m))

    if z >= deviation:
        return False

    return True


def record_to_database(record_time, temp, location):
    """
    Insert a record into the temperature table.
    :param record_time: datetime
    :param temp: float
    :param location: string
    :return:
    """
    if not database_connection:
        raise Exception('Not connected to database')

    try:
        session = Session()
        sensors = session.query(Sensor).filter_by(location=location)
        if sensors.count() == 1:
            sensor_id = sensors.all()[0].id

        new_observation = Temperature(value=temp, record_time=record_time, location=location, sensor=sensor_id)
        session.add(new_observation)
        session.commit()
    except:
        print('Error inserting records')
        session.rollback()
        raise Exception('Error inserting records')
    finally:
        session.close()


def record_to_csv(record_time, temp, location, file):
    with open(file, 'a+') as f:
        line = "{0},{1},{2}\n".format(
            str(temp),
            record_time.strftime('%Y-%m-%d %H:%M:%S'),
            location
        )
        f.write(line)


def main(user_id, unit, devices, local=False, **kwargs):
    verbosity = kwargs.get('verbosity', 0)
    for d in devices:
        print(d)
        device_id = d.serial_number
        location = d.location

        try:
            _, temperature = read_temp_sensor(device_id)
            print(location, temperature)
        except Exception as e:
            print('Sensor read failed for {0}: {1}'.format(location, device_id))
            continue # there is no data to record.

        # if kwargs.get('validate', False):
        #     try:
        #         valid = validate_temperature(temperature, d, datetime.now(), local=local, verbosity=verbosity)
        #         if valid == False:
        #             if verbosity >= 1:
        #                 print('Sensor reading is invalid.')
        #             continue #sensor data is invalid
        #     except Exception as e:
        #         print('Validation error.')

        try:
            record_to_database(datetime.now(), temperature, location)
        except Exception as e:
            print('Error during database insert: ', e)
            print('Writing to CSV.')
            record_to_csv(datetime.now(), temperature, location, '/home/pi/temperature_log.csv')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('user_id', type=int)
    parser.add_argument('--unit', type=int, default=1)
    args = parser.parse_args()

    user_id = args.user_id
    unit = args.unit

    def check_sensors(user_id, unit):
        session = Session()
        devices = session.query(Sensor).filter(
                Sensor.unit == unit,
                Sensor.user == user_id
            ).all()
        session.close()
        return [d for d in devices]

    i = 0
    sleep = 10
    sensor_check_interval = 60
    cycles_per_check = sensor_check_interval / sleep

    while True:
        if i % cycles_per_check == 0:
            devices = check_sensors(user_id, unit)

        main(user_id, unit, devices)

        i += 1
        time.sleep(sleep)