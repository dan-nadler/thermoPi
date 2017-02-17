from flask import Flask, render_template, request, redirect, url_for
from thermo.control.UI.api import *
from thermo import local_settings
import numpy as np
from datetime import datetime, timedelta


def aggregate_temperatures(temperatures, minutes=1, method='Median'):

    temp_list = [value for key, value in temperatures.iteritems()]

    if method == 'Median':
        current_temp = np.median(temp_list)
    else:
        current_temp = np.median(temp_list)

    return current_temp


app = Flask(__name__)
zone = 1

@app.route('/', methods=['POST', 'GET'])
@app.route('/index', methods=['POST', 'GET'])
def index():
    minutes = 1

    room_temps = get_current_room_temperatures(local_settings.USER_NUMBER, zone, minutes)
    room_targets = get_current_target_temperatures(zone)

    context = {
        'current_temp': aggregate_temperatures(room_temps),
        'current_target': aggregate_temperatures(room_targets)
    }

    return render_template('index.html', **context)


@app.route('/override.html', methods=['POST'])
def override():
    temperature = request.form.get('target')
    expiration = datetime.now() + timedelta(hours=int(request.form.get('hours')))
    set_constant_temperature(local_settings.USER_NUMBER, zone, temperature, expiration)
    return redirect(url_for('index'))

if __name__ == '__main__':

    app.run(debug=True, port=8080, host='0.0.0.0')
