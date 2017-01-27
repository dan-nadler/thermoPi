import time
import re
from datetime import datetime
from models import Temperature, get_engine, Sensor
from sqlalchemy.orm import sessionmaker


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


def record_to_csv(record_time, temp, location, file):
    with open(file, 'a+') as f:
        line = "{0},{1},{2}\n".format(
            str(temp),
            record_time.strftime('%Y-%m-%d %H:%M:%S'),
            location
        )
        f.write(line)


if __name__ == '__main__':
    device_ids = {
            'Living Room (North Wall)':         '28-04165425e4ff',
            'Living Room (South Wall)':         '28-0516710253ff',
            'Dining Room (North Wall)':         '28-051670bfd2ff',
            'Dining Room (North Wall High)':    '28-0416717d75ff',
            'Outside (Street)':                 '28-0416719754ff'
        }

    file_path = '/home/pi/temps.csv'

    while True:

        for location, device_id in device_ids.iteritems():

            try:
                _, temperature = read_temp_sensor(device_id)
                record_to_csv(datetime.now(), temperature, location, file_path)

                try:
                    record_to_database(datetime.now(), temperature, location)

                except Exception as e:
                    print('Error during database insert: ', e)

                print(location, temperature)

            except Exception as e:
                print(e)

        time.sleep(10)
