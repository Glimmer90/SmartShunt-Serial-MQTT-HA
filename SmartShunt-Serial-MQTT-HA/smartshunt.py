#!/usr/bin/env python3

import json
import logging
import os
import sys
import time
from typing import Dict, Any

import paho.mqtt.client as mqtt
import serial

# Config
SERIAL_PORT   = os.getenv("SERIAL_PORT"  , "/dev/ttyUSB0")
MQTT_HOST     = os.getenv("MQTT_HOST"    , "core-mosquitto")
MQTT_PORT     = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER     = os.getenv("MQTT_USER"    , "homeassistant")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)sZ %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

# MQTT
def on_connect(client: mqtt.Client, userdata, flags, rc, _):
    if rc == 0:
        logging.info("Connected to MQTT broker")
    else:
        logging.warning("MQTT connection failed (rc=%s)", rc)


def on_disconnect(client: mqtt.Client, userdata, flags, rc, _):
    logging.warning("MQTT disconnected (rc=%s), auto‑reconnecting", rc)


def connect_mqtt() -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    client.reconnect_delay_set(min_delay=1, max_delay=60)

    client.connect(MQTT_HOST, MQTT_PORT, 60)
    return client

# Serial
def open_serial() -> serial.Serial:
    return serial.Serial(
        port=SERIAL_PORT,
        baudrate=19200,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=1,
    )

# Data processing
def coerce(value: str) -> Any: # Try to turn strings into int/float when possible
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def process_data(raw: Dict[str, str]) -> Dict[str, Any]:
    out = {k: coerce(v) for k, v in raw.items()}
    frame: Dict[str, Any] = {}

    if "V" in out:    frame["v"]   = round(out["V"] / 1000, 2)          # Volts
    if "I" in out:    frame["a"]   = round(out["I"] / 1000, 2)          # Amps
    if "P" in out:    frame["w"]   = int(out["P"])                      # Watts
    if "CE" in out:   frame["ce"]  = round(out["CE"] / 1000, 2)         # mAh
    if "SOC" in out:  frame["soc"] = round(out["SOC"] / 10, 1)          # %
    if "TTG" in out:  frame["time"] = int(out["TTG"])                   # Minutes

    # Alarms
    if "Alarm" in out: frame["alarm"] = out["Alarm"]                    # ON/OFF
    if "AR" in out:    frame["ar"]    = int(out["AR"])                  # Enum

    # History
    if "H1"  in out: frame["h_ddist"]     = round(out["H1"] / 1000, 2)
    if "H2"  in out: frame["h_ldist"]     = round(out["H2"] / 1000, 2)
    if "H3"  in out: frame["h_adist"]     = round(out["H3"] / 1000, 2)
    if "H4"  in out: frame["h_chgcyc"]    = int(out["H4"])
    if "H5"  in out: frame["h_fulldist"]  = int(out["H5"])
    if "H6"  in out: frame["h_totalmah"]  = round(out["H6"] / 1000, 2)
    if "H7"  in out: frame["h_bminv"]     = round(out["H7"] / 1000, 2)
    if "H8"  in out: frame["h_bmaxv"]     = round(out["H8"] / 1000, 2)
    if "H9"  in out: frame["h_lastchg"]   = int(out["H9"] // 60)
    if "H17" in out: frame["h_totaldis"]  = round(out["H17"] / 100, 2)
    if "H18" in out: frame["h_totalchg"]  = round(out["H18"] / 100, 2)

    return frame


# Main loop
def main() -> None:
    mqttc = connect_mqtt()
    mqttc.loop_start()

    try:
        while True:
            try:
                ser = open_serial()
                logging.info("Opened serial port %s", SERIAL_PORT)
            except (serial.SerialException, OSError) as exc:
                logging.error("Unable to open %s: %s – retrying in 3s",
                              SERIAL_PORT, exc)
                time.sleep(3)
                continue

            frame: Dict[str, str] = {}

            while True:
                try:
                    line = ser.readline().decode("ascii", "ignore").strip()
                    if not line or "\t" not in line:
                        continue

                    key, value = line.split("\t", 1)

                    if key.startswith("H18"):
                        frame[key] = value
                        payload = json.dumps(process_data(frame))

                        res = mqttc.publish("victron/smartshunt", payload)
                        if res.rc != 0:
                            logging.warning("Publish failed (rc=%s), retrying once",
                                            res.rc)
                            mqttc.publish("victron/smartshunt", payload)

                        logging.debug("Published %d keys", len(frame))
                        frame.clear()
                        continue

                    if key.startswith("Checksum"):
                        continue  # Skip CRC line

                    frame[key] = value

                except (serial.SerialException, OSError) as exc:
                    logging.error("Serial read error: %s – reopening in 3s", exc)
                    time.sleep(3)
                    break

    except KeyboardInterrupt:
        logging.info("Keyboard interrupt – exiting")

    finally:
        mqttc.loop_stop()
        try:
            mqttc.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    main()
