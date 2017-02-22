from sqlalchemy import create_engine, Column, Float, DateTime, Integer, String, ForeignKey, Boolean, BLOB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from thermo.local_settings import DATABASE, LOCAL_DATABASE_PATH, USER_NUMBER


def get_engine(local=False):

    if local == True:
        connection_string = 'sqlite:///' + LOCAL_DATABASE_PATH

    else:
        connection_string = '{0}://{1}:{2}@{3}:{4}/{5}'.format(
            DATABASE.TYPE, DATABASE.USERNAME, DATABASE.PASSWORD, DATABASE.HOST, DATABASE.PORT, DATABASE.NAME
        )

    engine = create_engine(connection_string, echo=False)
    return engine

def get_session(local=False):
    engine = get_engine(local=local)
    Session = sessionmaker(bind=engine)
    session = Session()
    return session

def copy_data_to_local(user):

    def duplicate(type, obj):
        x = {k: v for k, v in obj.__dict__.iteritems() if k != '_sa_instance_state'}
        return type(**x)

    session = get_session(local=False)
    sensors = session.query(Sensor).filter(Sensor.user == user).all()
    zones = session.query(Zone).filter(Zone.user == user).all()
    units = session.query(Unit).filter(Unit.user == user).all()
    schedules = session.query(ThermostatSchedule).filter(ThermostatSchedule.user == user).all()
    actions, _ = zip(*session.query(Action, Unit).filter(Action.unit == Unit.id).filter(Unit.user == user).all())
    users = session.query(User).filter(User.id == user).all()
    session.close()

    session2 = get_session(local=True)
    session2.add_all([duplicate(Sensor, s) for s in sensors])
    session2.add_all([duplicate(Zone, s) for s in zones])
    session2.add_all([duplicate(Unit, s) for s in units])
    session2.add_all([duplicate(ThermostatSchedule, s) for s in schedules])
    session2.add_all([duplicate(Action, s) for s in actions])
    session2.add_all([duplicate(User, s) for s in users])
    session2.commit()
    session2.close()

    return

def duplicate_locally(function):
    """
    Call the function with the local SQLite database in addition to the remote database
    :param function:
    :return:
    """
    def wrapper(*args, **kwargs):
        try :
            function(*args, local=False, **kwargs)
        except Exception as e:
            print('Failed using remote database.')

        try:
            function(*args, local=True, **kwargs)
        except Exception as e:
            print('Failed using local database.')
            raise(e)

        return

    return wrapper

def fallback_locally(function):
    """
    Call the function with the local SQLite database if the remote database connection fails
    :param function:
    :return:
    """
    def wrapper(*args, **kwargs):
        try :
            results = function(*args, local=False, **kwargs)
        except Exception as e:
            print('Failed using remote database.')

            try:
                results = function(*args, local=True, **kwargs)
            except Exception as e:
                print('Failed using local database.')
                raise(e)

        return results

    return wrapper

Base = declarative_base()


class Temperature(Base):
    __tablename__ = 'temperature'
    id = Column(Integer, autoincrement=True, index=True)
    value = Column(Float)
    record_time = Column(DateTime, primary_key=True, index=True)
    location = Column(String(250))
    sensor = Column(Integer, ForeignKey('sensor.id'), primary_key=True, index=True)

    def __repr__(self):
        return "<Temperature(value={0}, record_time={1}, location={2})>".format(
            str(self.value), self.record_time.strftime('%Y-%m-%d %H:%M:%S'), str(self.location)
        )


class Sensor(Base):
    __tablename__ = 'sensor'
    id = Column(Integer, autoincrement=True, primary_key=True)
    location = Column(String(250))
    temperatures = relationship('Temperature')
    serial_number = Column(String(250))
    user = Column(Integer, ForeignKey('user.id'), index=True)
    unit = Column(Integer, ForeignKey('unit.id'), index=True)
    indoors = Column(Boolean, default=1, nullable=False)
    zone = Column(Integer, ForeignKey('zone.id'), index=True)

    def __repr__(self):
        return self.location


class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, autoincrement=True, primary_key=True, index=True)
    sensors = relationship('Sensor')
    thermostat_schedule = relationship('ThermostatSchedule')
    zones = relationship('Zone')
    messages = relationship('Message')
    # username = Column(String(150), unique=True, index=True) TODO Add to MySQL database
    first_name = Column(String(150))
    last_name = Column(String(150))
    address = Column(String(250))
    api_key = Column(String(250))

    def __repr__(self):
        return "{0}: {1} {2}".format(self.id, self.first_name, self.last_name)


class ThermostatSchedule(Base):
    __tablename__ = 'thermostat_schedule'
    id = Column(Integer, autoincrement=True, primary_key=True, index=True)
    user = Column(Integer, ForeignKey('user.id'), nullable=False)
    zone = Column(Integer, ForeignKey('zone.id'), nullable=False)
    schedule = Column(BLOB, nullable=False)
    name = Column(String(250))

    def __repr__(self):
        return "{0} for zone {1} for user {2}".format(self.name, self.zone, self.user)


class Zone(Base):
    __tablename__ = 'zone'
    id = Column(Integer, autoincrement=True, primary_key=True, index=True)
    name = Column(String(250))
    user = Column(Integer, ForeignKey('user.id'))
    sensors = relationship('Sensor')
    actions = relationship('Action')
    thermostat_schedule = relationship('ThermostatSchedule')

    def __repr__(self):
        return "{0}: {1} {2}".format(self.id, self.name, self.user)


class ActionLog(Base):
    __tablename__ = 'action_log'
    id = Column(Integer, autoincrement=True, primary_key=True, index=True)
    action = Column(Integer, ForeignKey('action.id'), index=True)
    value = Column(Integer, nullable=True)
    record_time = Column(DateTime, index=True)
    target = Column(Float, nullable=True)

    def __repr__(self):
        return "{0}: {1}".format(self.action, self.value)


class Action(Base):
    __tablename__ = 'action'
    id = Column(Integer, autoincrement=True, primary_key=True, index=True)
    action_logs = relationship('ActionLog')
    unit = Column(ForeignKey('unit.id'), default=1, index=True)
    name = Column(String(250))
    zone = Column(Integer, ForeignKey('zone.id'), index=True)
    expected_overshoot_above = Column(Float, nullable=False, default=0.)
    expected_overshoot_below = Column(Float, nullable=False, default=0.)


    def __repr__(self):
        return "{0}: {1} {2} {3}".format(self.id, self.name, self.unit, self.zone)


class Unit(Base):
    __tablename__ = 'unit'
    id = Column(Integer, autoincrement=True, primary_key=True, index=True)
    user = Column(Integer, ForeignKey('user.id'), index=True)
    sensors = relationship('Sensor')
    actions = relationship('Action')
    messages = relationship('Message')
    name = Column(String(250))

    def __repr__(self):
        return "{0}: {1} {2}".format(self.id, self.user, self.name)


class Message(Base):
    __tablename__ = 'message'
    id = Column(Integer, autoincrement=True, primary_key=True, index=True)
    record_time = Column(DateTime)
    user = Column(Integer, ForeignKey('user.id'), index=True)
    json = Column(BLOB, nullable=False)
    received = Column(Boolean, nullable=False, default=False)
    type = Column(String(250), nullable=False)
    unit = Column(Integer, ForeignKey('unit.id'), index=True, nullable=True)


if __name__ == '__main__':
    engine = get_engine()
    Base.metadata.create_all(engine)

    engine = get_engine(local=True)
    Base.metadata.create_all(engine)

    copy_data_to_local(USER_NUMBER)
    print('Done')
