from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Float, DateTime, Integer, String
from local_settings import DATABASE

def get_engine():
    connection_string = '{0}://{1}:{2}@{3}:{4}/{5}'.format(
        DATABASE.TYPE, DATABASE.USERNAME, DATABASE.PASSWORD, DATABASE.HOST, DATABASE.PORT, DATABASE.NAME
    )
    engine = create_engine(connection_string, echo=False)
    return engine

Base = declarative_base()


class Temperature(Base):
    __tablename__ = 'temperature'
    id = Column(Integer, autoincrement=True)
    value = Column(Float)
    record_time = Column(DateTime, primary_key=True)
    location = Column(String(250), primary_key=True)

    def __repr__(self):
        return "<Temperature(value={0}, record_time={1}, location={2})>".format(
            str(self.value), self.record_time.strftime('%Y-%m-%d %H:%M:%S'), self.location
        )


if __name__ == '__main__':
    engine = get_engine()
    Base.metadata.create_all(engine)
    print('Done')
