from sqlalchemy import create_engine, Column, Float, DateTime, Integer, String, ForeignKey, Boolean
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

    def __repr__(self):
        return self.location


class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, autoincrement=True, primary_key=True, index=True)
    sensors = relationship('Sensor')
    thermostats = relationship('Thermostat')
    # actions = relationship('Action')
    # username = Column(String(150), unique=True, index=True) TODO Add to MySQL database
    first_name = Column(String(150))
    last_name = Column(String(150))
    address = Column(String(250))

    def __repr__(self):
        return "{0}: {1} {2}".format(self.id, self.first_name, self.last_name)


class Thermostat(Base):
    # TODO check usage of this table. Seems to be unnecessary.
    __tablename__ = 'thermostat'
    id = Column(Integer, autoincrement=True, primary_key=True, index=True)
    user = Column(Integer, ForeignKey('user.id'))
    zone = Column(Integer)
    name = Column(String(250))


class ActionLog(Base):
    __tablename__ = 'action_log'
    id = Column(Integer, autoincrement=True, primary_key=True, index=True)
    action = Column(Integer, ForeignKey('action.id'), index=True)
    value = Column(Integer, nullable=True)
    record_time = Column(DateTime, index=True)


class Action(Base):
    __tablename__ = 'action'
    id = Column(Integer, autoincrement=True, primary_key=True, index=True)
    action_logs = relationship('ActionLog')
    user = Column(Integer, ForeignKey('user.id'), index=True)
    unit = Column(ForeignKey('unit.id'), default=1, index=True)
    name = Column(String(250))


class Unit(Base):
    __tablename__ = 'unit'
    id = Column(Integer, autoincrement=True, primary_key=True, index=True)
    user = Column(Integer, ForeignKey('user.id'), index=True)
    sensors = relationship('Sensor')
    name = Column(String(250))

if __name__ == '__main__':
    engine = get_engine()
    Base.metadata.create_all(engine)
    print('Done')
