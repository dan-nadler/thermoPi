import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mat
from models import Temperature, get_engine
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker


def get_dataframe(hours=24):
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    q = session.query(Temperature).filter(Temperature.record_time >= datetime.now() - timedelta(hours=hours))
    df = pd.read_sql(q.statement, q.session.bind)

    df = df.reset_index().pivot_table(index='record_time', columns='location', values='value')
    return df


def get_plotting_dataframe(hours=24, resolution='60S', interpolation='linear'):
    mat.style.use('ggplot')
    df = get_dataframe(hours=hours)

    while (df.ffill().diff().abs() > 5).sum().sum() > 0:
        df[df.ffill().diff().abs() > 5] = pd.np.nan
    df['Dining Room (North Wall)'] = df['Dining Room (North Wall)'].dropna()
    df['Living Room (South Wall)'] = df['Living Room (South Wall)'].dropna()

    df2 = df.resample(resolution).mean().interpolate(interpolation)
    return df2


def create_standard_plot(hours=24, resolution='60S', interpolation='linear'):
    df = get_plotting_dataframe(hours, resolution, interpolation)
    ax = df.plot(secondary_y=['Outside (Street)'], figsize=(10, 6), legend=False);

    ax.right_ax.grid(False)
    ax.grid(True)
    lines = ax.get_lines() + ax.right_ax.get_lines()
    ax.legend(lines, [l.get_label() for l in lines], loc='upper left', fontsize=8)

    return plt.gcf()


def create_group_by_day_plot(location,  hours=24, resolution='60S', interpolation='linear'):
    df = get_plotting_dataframe(hours, resolution, interpolation)
    df.pivot_table(values=location, index=df.index.strftime('%H:%M:%S'), columns=df.index.strftime('%A, %m/%d')).plot(title=location)
    return plt.gcf()

if __name__ == '__main__':
    create_group_by_day_plot('Living Room (North Wall)', hours=48+20)
    plt.show()
