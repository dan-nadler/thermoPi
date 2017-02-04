from setuptools import setup, find_packages

setup(
    name='thermo',
    requires=[
        'sqlalchemy',
        'pymysql',
        'pandas'
    ],
    version='0.1.4',
    packages=find_packages()
)