# thermoPi
A multi-zone thermostat built using the Raspberry Pi

# Installation
`python setup.py install`

# Setup
## Local
Create a `local_settings.py` file in `thermo/` and add:

```python
from collections import namedtuple
from RPi.GPIO import BCM

def convert(dictionary):
    return namedtuple('GenericDict', dictionary.keys())(**dictionary)

# The database where thermoPi data is stored
DATABASE = {
    'TYPE': 'mysql+___',
    'HOST': 'xxx.xxx.xxx.xxx',
    'PORT': '3306',
    'USERNAME': 'user',
    'PASSWORD': 'password',
    'NAME': 'dbname',
}

DATABASE = convert(DATABASE)

# The path for an SQLite database where a local copy of some information is stored in case the database cannot be reached
# This database is created automatically by thermo.common.models
LOCAL_DATABASE_PATH = '/home/pi/thermo.db'

USER_NUMBER = 1 # Your user ID number from the `user` table
UNIT_NUMBER = 2 # A unique ID number assigned to each Raspberry Pi in the `unit` table

GPIO_MODE = BCM # The mode for designating GPIO pins
GPIO_PINS = {
    'HEAT': 17 # The GPIO pin that the heat control relay is connected to
}

# A local sensor that the heating control algorithm will fall back to in the event that the database cannot be reached
FALLBACK = {
    'LOCATION': 'Sensor Name Here', # the sensor's name
    'SERIAL NUMBER': '28-0416930a31ff', # the sensor's serial number
    'ZONE': 1 # the heating zone the sensor is assigned to
}
```

## Database
Use `python -m thermo.common.models` to create the tables in your database.

Update the `sensor`, `unit`, `user`, `zone`, and `action` tables with your configuration.

Currently, the only available action is `'HEAT'`, which controls a heating system
(furnace, in my case) via a 2-wire thermostat line attached to a relay.

# Usage
Use `python -m thermo.control.master` on each raspberry pi to run thermo.

This will detect the attached sensors and available actions via the database and `local_settings.py` file, and perform them in a loop.

# Web Interface
If you install uwsgi via apt-get and pip, you can use the following command to host the control UI from the Raspberry Pi:

`sudo /usr/local/bin/uwsgi --socket :80 --protocol=http -w wsgi:app`

Alternatively, you can host with Flask, or another webserver of your choosing.

# Creating a Service
Copy thermo.service to `/lib/systemd/system/`, then run `sudo systemctl enable thermo` and `sudo systemctl start thermo`

This service is configured to automatically restart if the process crashes.