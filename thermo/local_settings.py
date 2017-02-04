from collections import namedtuple
from RPi.GPIO import BCM

def convert(dictionary):
    return namedtuple('GenericDict', dictionary.keys())(**dictionary)

DATABASE = {
    'TYPE': 'mysql+pymysql',
    'HOST': '104.196.166.159',
    'PORT': '3306',
    'USERNAME': 'root',
    'PASSWORD': '3DumbMoose',
    'NAME': 'thermopi',
}

DATABASE = convert(DATABASE)

USER_NUMBER = 1
UNIT_NUMBER = 1

GPIO_MODE = BCM
GPIO_PINS = {
    'HEAT': 25
}

