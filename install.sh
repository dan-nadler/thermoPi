#!/usr/bin/env bash
#sudo python setup.py develop

#python -m thermo.common.models

sudo cp thermo.service /lib/systemd/system/
#sudo systemctl enable thermo
sudo systemctl start thermo
