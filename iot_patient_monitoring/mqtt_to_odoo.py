#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
import xmlrpc.client
from datetime import datetime, timedelta

import paho.mqtt.client as mqtt


# ==========================================================
# CONFIGURATION MQTT
# ==========================================================

MQTT_BROKER = "192.168.137.144"
MQTT_PORT = 1883
MQTT_TOPIC = "patient/data"


# ==========================================================
# CONFIGURATION ODOO
# ==========================================================

ODOO_URL = "http://localhost:8069"
ODOO_DB = "odoo19_db"
ODOO_USERNAME = "admin"
ODOO_PASSWORD = "admin"   # change selon ton mot de passe admin


# ==========================================================
# MAPPING DEVICE → PATIENT
# ==========================================================
# Si ton Raspberry envoie device_id = RPI-001,
# ici on dit que RPI-001 correspond au patient P-00001 dans Odoo.

DEVICE_PATIENT_MAP = {
    "RPI-001": "P-00028",
}


# ==========================================================
# CONNEXION ODOO
# ==========================================================

common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})

if not uid:
    raise Exception("Connexion Odoo échouée. Vérifie DB, username ou password.")

models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")

print("Connexion Odoo réussie")


# ==========================================================
# FONCTIONS ODOO
# ==========================================================

def find_patient_by_code(patient_code):
    patient_ids = models.execute_kw(
        ODOO_DB,
        uid,
        ODOO_PASSWORD,
        "iot.patient",
        "search",
        [[("patient_code", "=", patient_code)]],
        {"limit": 1},
    )

    if not patient_ids:
        return None

    return patient_ids[0]


def update_patient_vitals(patient_id, temperature, spo2, heart_rate):
    values = {}

    if temperature is not None:
        values["temperature"] = temperature

    if spo2 is not None:
        values["spo2"] = spo2

    if heart_rate is not None:
        values["heart_rate"] = heart_rate

    if values:
        models.execute_kw(
            ODOO_DB,
            uid,
            ODOO_PASSWORD,
            "iot.patient",
            "write",
            [[patient_id], values],
        )


def create_ecg_points(patient_id, ecg_values, heart_rate=None):
    if not ecg_values:
        return

    # نحذف ECG القديم باش capture تكون نظيفة
    old_ids = models.execute_kw(
        ODOO_DB,
        uid,
        ODOO_PASSWORD,
        "iot.ecg",
        "search",
        [[("patient_id", "=", patient_id)]],
    )

    if old_ids:
        models.execute_kw(
            ODOO_DB,
            uid,
            ODOO_PASSWORD,
            "iot.ecg",
            "unlink",
            [old_ids],
        )

    now = datetime.now()

    for index, value in enumerate(ecg_values):
        record = {
            "patient_id": patient_id,
            "ecg_value": float(value),
            "bpm": int(heart_rate) if heart_rate is not None else 0,
            "sample_time": (now + timedelta(seconds=index)).strftime("%Y-%m-%d %H:%M:%S"),
        }

        models.execute_kw(
            ODOO_DB,
            uid,
            ODOO_PASSWORD,
            "iot.ecg",
            "create",
            [record],
        )

# ==========================================================
# CALLBACK MQTT
# ==========================================================

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connexion MQTT réussie")
        client.subscribe(MQTT_TOPIC)
        print(f"Abonné au topic : {MQTT_TOPIC}")
    else:
        print(f"Erreur connexion MQTT, code : {rc}")


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))

        device_id = payload.get("device_id")
        temperature = payload.get("temperature")
        spo2 = payload.get("spo2")
        heart_rate = payload.get("heart_rate")
        ecg_values = payload.get("ecg_values", [])

        if not device_id:
            print("Message ignoré : device_id manquant")
            return

        patient_code = DEVICE_PATIENT_MAP.get(device_id)

        if not patient_code:
            print(f"Device inconnu : {device_id}")
            return

        patient_id = find_patient_by_code(patient_code)

        if not patient_id:
            print(f"Patient introuvable dans Odoo : {patient_code}")
            return

        update_patient_vitals(
            patient_id=patient_id,
            temperature=temperature,
            spo2=spo2,
            heart_rate=heart_rate,
        )

        create_ecg_points(
            patient_id=patient_id,
            ecg_values=ecg_values,
            heart_rate=heart_rate,
        )

        print(
            f"Odoo mis à jour | Patient={patient_code} | "
            f"T={temperature} °C | SpO2={spo2} % | BPM={heart_rate} | "
            f"ECG points={len(ecg_values)}"
        )

    except Exception as e:
        print(f"Erreur traitement MQTT → Odoo : {e}")


# ==========================================================
# PROGRAMME PRINCIPAL
# ==========================================================

def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_BROKER, MQTT_PORT, 60)

    print("Bridge MQTT → Odoo démarré")
    client.loop_forever()


if __name__ == "__main__":
    main()