# thermoPi
A multi-zone thermostat built using the Raspberry Pi

# Installation
`python setup.py install`

# Setup
## Local
Create a `local_settings.py` file in `thermo/` and add:

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

## Database
Use `python -m thermo.common.models` to create the tables in your database.

Update the `sensor`, `unit`, `user`, `zone`, and `action` tables with your configuration.

Currently, the only available action is `'HEAT'`, which controls a heating system
(furnace, in my case) via a 2-wire thermostat line attached to a relay.

# Usage
Use `python -m thermo.control.main` on each raspberry pi to run thermo.

This will detect the attached sensors and available actions via the database and `local_settings.py` file, and perform them in a loop.
