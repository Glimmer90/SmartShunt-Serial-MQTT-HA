#!/usr/bin/with-contenv bashio

SERIAL_PORT=$(bashio::config 'serial_port')
MQTT_HOST=$(bashio::config 'mqtt_host')
MQTT_PORT=$(bashio::config 'mqtt_port')
MQTT_USER=$(bashio::config 'mqtt_user')
MQTT_PASSWORD=$(bashio::config 'mqtt_password')

export SERIAL_PORT
export MQTT_HOST
export MQTT_PORT
export MQTT_USER
export MQTT_PASSWORD

python3 /smartshunt.py