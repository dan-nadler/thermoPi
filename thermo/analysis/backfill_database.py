from datetime import datetime
from sys import stdout
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from ..common.models import Temperature, get_engine

engine = get_engine()
Session = sessionmaker(bind=engine)
session = Session()

backfill = []
with open('/home/pi/temps.csv', 'r') as f:
    line = f.readline()
    i = 0
    while line:
        temperature, record_time, location = line.split(',')
        location = location.replace('\n', '')
        record_time = datetime.strptime(record_time, '%Y-%m-%d %H:%M:%S')
        temperature = float(temperature)
        backfill.append(
            Temperature(value=temperature, record_time=record_time, location=location)
        )
        line = f.readline()
        i += 1

        stdout.write('\r{}\t\t'.format(str(i)))
        if i % 100 == 0:
            try:
                session.add_all(backfill)
                session.commit()
            except IntegrityError:
                session.rollback()
            finally:
                backfill = []

try:
    session.add_all(backfill)
    session.commit()
except IntegrityError:
    session.rollback()
finally:
    backfill = []
