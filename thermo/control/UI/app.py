import urllib

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
    check_local(request)
    minutes = 1

    room_temps = get_current_room_temperatures(local_settings.USER_NUMBER, zone, minutes)
    room_targets, next_targets, schedule_name = get_thermostat_schedule(zone)
    next_target_dates = {room: hour for room, (hour, target) in next_targets.iteritems()}
    next_target_temps = {room: target for room, (hour, target) in next_targets.iteritems()}
    status = get_action_status(local_settings.USER_NUMBER, zone)
    schedules = get_available_schedules(local_settings.USER_NUMBER, zone)

    context = {
        'current_temp': aggregate_temperatures(room_temps),
        'current_target': aggregate_temperatures(room_targets),
        'next_target': aggregate_temperatures(next_target_temps),
        'next_target_start_time': aggregate_temperatures(next_target_dates, method='DateMin').strftime('%I:%M %p'),
        'status': status,
        'active_schedule_name': schedule_name,
        'schedules': schedules,
        'controltoken': request.args.get('controltoken', '')
    }

    return render_template('index.html', **context)


@app.route('/schedule/set_active', methods=['POST'])
def set_active_schedule():
    check_local(request, token=request.form.get('controltoken', False))

    schedule_id = request.form.get('schedule')
    activate_schedule(local_settings.USER_NUMBER, zone, schedule_id)

    return redirect(url_for('index') + '?' + urllib.urlencode(request.form))


@app.route('/override', methods=['POST'])
def override():
    check_local(request, token=request.form.get('controltoken', False))

    temperature = request.form.get('target')
    expiration = datetime.now() + timedelta(hours=float(request.form.get('hours')))
    set_constant_temperature(local_settings.USER_NUMBER, zone, temperature, expiration)

    return redirect(url_for('index') + '?' + urllib.urlencode(request.form))


@app.route('/schedule', methods=['GET'])
def schedule():
    schedules = get_schedules(local_settings.USER_NUMBER)

    return render_template('schedule.html', schedules=schedules)


@app.route('/skip-to-next', methods=['GET'])
def skip():
    room_targets, next_targets, schedule_name = get_thermostat_schedule(zone)
    next_target_dates = {room: hour for room, (hour, target) in next_targets.iteritems()}
    next_target_temps = {room: target for room, (hour, target) in next_targets.iteritems()}

    next_temp = aggregate_temperatures(next_target_temps)
    expiration = aggregate_temperatures(next_target_dates, method='DateMin')

    set_constant_temperature(local_settings.USER_NUMBER, zone, next_temp, expiration)

    ct = request.args.get('controltoken', None)
    if ct is not None:
        query_string = urllib.urlencode({'controltoken': ct})
    else:
        query_string = ''

    return redirect(url_for('index') + '?' + query_string)


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
