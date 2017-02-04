# thermoPi
A multi-zone thermostat built using the Raspberry Pi

# Installation
`python setup.py install`

# Setup
Create a `local_settings.py` file in `thermo/common/` and add:

```python
from collections import namedtuple

def convert(dictionary):
    return namedtuple('GenericDict', dictionary.keys())(**dictionary)

DATABASE = {
    'TYPE': 'mysql+___',
    'HOST': 'xxx.xxx.xxx.xxx',
    'PORT': '3306',
    'USERNAME': 'user',
    'PASSWORD': 'password',
    'NAME': 'dbname',
}

DATABASE = convert(DATABASE)

USER_NUMBER = 1
UNIT_NUMBER = 1 # For multiple Raspberry Pis, assign a unit number and record it in the `unit` table in your database

GPIO_MODE = BCM
GPIO_PINS = {
    'HEAT': 25 # GPIO Pin for Heating relay (required for thermo.control.thermostat, only)
}

```

Use `python -m thermo.common.models` to create the tables in your database.

Update the `sensor` table with your sensors.

# Usage
Use `python -m thermo.sensor.thermal` to stream temperatures to the database every 10 seconds.
