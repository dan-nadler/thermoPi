# thermoPi
A multi-zone thermostat built using the Raspberry Pi

See https://github.com/dan-nadler/thermoDashboard for a Flask/Zappa app that monitors the database created by this project.

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
```

Use `python -m thermo.common.models` to create the tables in your database.

Update the `sensor` table with your sensors.

# Usage
Use `python IO.py` to stream temperatures to the database every 10 seconds.
