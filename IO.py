import time
import re
import sqlite3
from datetime import datetime

def read_thermometer(device_id, units='F'):
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


def create_database():
    """
    Create and setup the SQLite database
    :return:
    """

    temp_table = """CREATE TABLE temperature
(
    temperature REAL NOT NULL,
    record_date TEXT NOT NULL,
    location TEXT
);"""

    f = open('./sqlite.db', 'w')
    f.close()

    conn = sqlite3.connect('./sqlite.db')
    c = conn.cursor()
    c.execute(temp_table)
    conn.commit()
    conn.close()


def record_to_database(record_time, temp, location):
    """
    Insert a record into the temperature table.
    :param record_time: datetime
    :param temp: float
    :param location: string
    :return:
    """

    conn = sqlite3.connect('./sqlite.db')
    c = conn.cursor()

    insert = "INSERT INTO temperature (temperature, record_date, location) VALUES ({0}, '{1}', '{2}')".format(
        str(temp),
        record_time.strftime('%Y-%m-%d %H:%M:%S'),
        location
    )

    c.execute(insert)
    conn.commit()
    conn.close()

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
            'Living Room (North Wall)': '28-04165425e4ff',
            'Living Room (South Wall)': '28-0516710253ff',
            'Dining Room (North Wall)': '28-051670bfd2ff',
            'Outside (Street)': '28-0416719754ff'
        }

    while True:
        for location, device_id in device_ids.iteritems():
            try:
                _, temperature = read_thermometer(device_id)
                file = '/home/pi/temps.csv'
                record_to_csv(datetime.now(), temperature, location, file)
                print(location, temperature)
            except Exception as e:
                print(e)
        time.sleep(10)
