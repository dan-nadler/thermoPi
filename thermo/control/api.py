from thermo.common.models import *
from datetime import datetime, timedelta
import json


def set_constant_temperature(user, zone, temperature, expiration):
    """
    Send message to override temperature schedule for all sensors attached to the specified zone
    :param user: user id
    :param zone: zone affected
    :param temperature: float: temperature target
    :param expiration: datetime for expiration of temperature target
    :return:
    """
    session = get_session()
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

    session = get_session()
    new_message = Message(record_time=datetime.now(), user=user, json=j, type='temperature override')
    session.add(new_message)
    session.commit()
    session.close()
    return

if __name__ == '__main__':
    set_constant_temperature(1,1,60,datetime.now()+timedelta(seconds=30))
