import numpy as np
from flask import Flask, render_template, request, redirect, url_for

from thermo.control.UI.api import *


def aggregate_temperatures(schedule_dict, method='Median'):

    value_list = [value for key, value in schedule_dict.iteritems()]

    if method == 'Median':
        output = np.median(value_list)
    elif method == 'DateMin':
        output = min(value_list)
    else:
        output = np.median(value_list)

    return output


app = Flask(__name__, template_folder='templates')
zone = 1


@app.route('/', methods=['POST', 'GET'])
@app.route('/index', methods=['POST', 'GET'])
def index():
    minutes = 1

    room_temps = get_current_room_temperatures(local_settings.USER_NUMBER, zone, minutes)
    room_targets, next_targets = get_thermostat_schedule(zone)

    next_target_dates = {room: hour for room, (hour, target) in next_targets.iteritems()}
    next_target_temps = {room: target for room, (hour, target) in next_targets.iteritems()}

    status = get_action_status(local_settings.USER_NUMBER, zone)

    context = {
        'current_temp': aggregate_temperatures(room_temps),
        'current_target': aggregate_temperatures(room_targets),
        'next_target': aggregate_temperatures(next_target_temps),
        'next_target_start_time': aggregate_temperatures(next_target_dates, method='DateMin').strftime('%I:%M %p'),
        'status': status,
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
