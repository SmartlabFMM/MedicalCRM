import xmlrpc.client
import random
import time
from datetime import datetime

# ---------------- Odoo config ----------------
url = "http://localhost:8069"
db = "odoo19_db"
username = "admin"
password = "admin"

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})

if not uid:
    print("Échec de connexion à Odoo")
    exit()

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# ---------------- Patient names ----------------
patients = [
    "Patient A",
    "Patient B",
    "Patient C",
]

# ---------------- Evaluation rules ----------------
def evaluate_status(temperature, spo2, heart_rate):
    if temperature > 38 or spo2 < 92:
        return "follow_up", "critical", "Température élevée ou SpO2 critique"
    elif temperature >= 37.5 or spo2 < 95 or heart_rate < 60 or heart_rate > 100:
        return "prospect", "warning", "Valeurs à surveiller"
    else:
        return "retention", "stable", None

# ---------------- Create patient ----------------
def create_patient(name, temperature, spo2, heart_rate, status, alert_level):
    return models.execute_kw(
        db,
        uid,
        password,
        'iot.patient',
        'create',
        [{
            'name': name,
            'temperature': temperature,
            'spo2': spo2,
            'heart_rate': heart_rate,
            'status': status,
            'alert_level': alert_level,
        }]
    )

# ---------------- Create alert ----------------
def create_alert(patient_id, message, alert_level, value_text):
    models.execute_kw(
        db,
        uid,
        password,
        'iot.alert',
        'create',
        [{
            'patient_id': patient_id,
            'alert_type': message,
            'alert_value': value_text,
            'alert_level': alert_level,
        }]
    )

# ---------------- Create ECG sample ----------------
def create_ecg(patient_id, bpm, signal_status):
    ecg_value = round(random.uniform(0.6, 1.4), 2)

    models.execute_kw(
        db,
        uid,
        password,
        'iot.ecg',
        'create',
        [{
            'patient_id': patient_id,
            'ecg_value': ecg_value,
            'bpm': bpm,
            'signal_status': signal_status,
        }]
    )

# ---------------- Main loop ----------------
while True:
    print("\n--- Nouvelle simulation ---")

    for name in patients:
        temperature = round(random.uniform(36.5, 39.5), 1)
        spo2 = round(random.uniform(90, 99), 1)
        heart_rate = random.randint(55, 110)

        status, alert_level, alert_message = evaluate_status(
            temperature, spo2, heart_rate
        )

        patient_id = create_patient(
            name, temperature, spo2, heart_rate, status, alert_level
        )

        print(
            f"{name} | Temp={temperature}°C | SpO2={spo2}% | HR={heart_rate} bpm "
            f"| Status={status} | Alert={alert_level} | ID={patient_id}"
        )

        if alert_message:
            value_text = f"T={temperature}°C, SpO2={spo2}%, HR={heart_rate} bpm"
            create_alert(patient_id, alert_message, alert_level, value_text)
            print(f"  -> Alerte créée pour {name}")

        create_ecg(patient_id, heart_rate, alert_level if alert_level != "stable" else "normal")
        print(f"  -> ECG sample créé pour {name}")

    time.sleep(10)