from thermo.common.models import get_engine, Temperature, Sensor
from thermo.analysis.IO import get_plotting_dataframe
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker
import pandas as pd
from flask import Flask, render_template

engine = get_engine()
Session = sessionmaker(bind=engine)

def get_data(lookback=3):
    session = Session()
    q = session.query(Temperature).filter(Temperature.record_time >= datetime.now() - timedelta(hours=lookback))
    df = pd.read_sql(q.statement, q.session.bind)
    session.close()
    return df


class Cache:
    def __init__(self, cache_duration_seconds=5):
        """
        :param lookback:
        :param cache_duration_seconds: duration of cached in seconds
        """
        self.cache_duration = cache_duration_seconds
        self.last_retrieval = datetime.now() - timedelta(days=1000)
        self.df = None

    def data(self):
        cache_duration = self.cache_duration
        if (datetime.now() - self.last_retrieval) > timedelta(seconds=cache_duration):
            print('updating cache')
            self.last_retrieval = datetime.now()
            self.df = self._get_data()
        return self.df

    def _get_data(self):
        pass


class RawDataFrame(Cache):
    def __init__(self, *args, **kwargs):
        super(RawDataFrame, self).__init__(*args, **kwargs)

    def _get_data(self, lookback=3):
        return get_data(lookback)


class PlotDataFrame(Cache):
    def __init__(self, *args, **kwargs):
        super(PlotDataFrame, self).__init__(*args, **kwargs)

    def _get_data(self, lookback=3):
        return get_plotting_dataframe(hours=lookback)


class RecentTemperature(Cache):
    def __init__(self, *args, **kwargs):
        super(RecentTemperature, self).__init__(*args, **kwargs)

    def _get_data(self):
        df = get_plotting_dataframe(hours=3, resolution='10S')
        df = df.resample('60S').last()
        return df


data = RawDataFrame()
chart_data = PlotDataFrame()
last_data = RecentTemperature(cache_duration_seconds=10)

app = Flask(__name__)

@app.route('/')
@app.route('/index')
def index(chartID = 'Current', chart_type = 'bar', chart_height = 350):
    data1 = last_data.data().ix[-1, :]
    data2 = last_data.data().ix[0, :]
    chart = {"renderTo": chartID, "type": chart_type, "height": chart_height, }
    series = [
        {
            "name": str(data1.name),
            "data": list(data1.values),
            "dataLabels":
                {
                    'enabled': 'true',
                    'allowOverlap': 'true',
                    'format': '{point.y:.1f}',
                    'style': {
                        'fontSize': '8px',
                    }
                }
        },
        {
            "name": str(data2.name),
            "data": list(data2.values),
            "dataLabels":
                {
                    'enabled': 'true',
                    'allowOverlap': 'true',
                    'format': '{point.y:.1f}',
                    'color': '#777777',
                    'style': {
                        'fontSize': '8px',
                    }
                }
        },
    ]
    title = {"text": 'Current Temperature'}
    xAxis = {"categories": list(data1.index)}
    yAxis = {"title": {"text": 'Degrees Fahrenheit'}}
    return render_template('index.html', chartID=chartID, chart=chart, series=series, title=title, xAxis=xAxis, yAxis=yAxis)


@app.route('/raw')
def raw():
    return data.data().to_html()

@app.route('/chart-data/')
def plot():
    return chart_data.data().to_html()

@app.route('/last-data')
def last():
    return last_data.data().to_frame().to_html()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, passthrough_errors=True)
