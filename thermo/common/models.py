from sqlalchemy import create_engine, Column, Float, DateTime, Integer, String, ForeignKey, Boolean, BLOB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from thermo.local_settings import DATABASE


def get_engine():
    connection_string = '{0}://{1}:{2}@{3}:{4}/{5}'.format(
        DATABASE.TYPE, DATABASE.USERNAME, DATABASE.PASSWORD, DATABASE.HOST, DATABASE.PORT, DATABASE.NAME
    )
    engine = create_engine(connection_string, echo=False)
    return engine


def get_session():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()
    return session


Base = declarative_base()


class Temperature(Base):
    __tablename__ = 'temperature'
    id = Column(Integer, autoincrement=True, index=True)
    value = Column(Float)
    record_time = Column(DateTime, primary_key=True)
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
    record_time = Column(DateTime, primary_key=True)
    user = Column(Integer, ForeignKey('user.id'), index=True)
    json = Column(BLOB, nullable=False)
    received = Column(Boolean, nullable=False, default=False)
    type = Column(String(250), nullable=False)
    unit = Column(Integer, ForeignKey('unit.id'), index=True, nullable=True)


if __name__ == '__main__':
    engine = get_engine()
    Base.metadata.create_all(engine)
    print('Done')
