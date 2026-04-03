import json
import xmlrpc.client
import paho.mqtt.client as mqtt
import joblib
import pandas as pd

# ---------------- Odoo config ----------------
url = "http://localhost:8069"
db = "odoo_db"
username = "admin"
password = "admin"

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})

if not uid:
    print("Échec de connexion à Odoo")
    exit()

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# ---------------- Load AI model ----------------
try:
    model = joblib.load("risk_model.pkl")
    print("Modèle IA chargé avec succès.")
except Exception as e:
    print("Erreur lors du chargement du modèle IA :", e)
    exit()

# ---------------- Rules ----------------
def evaluate_patient_status(temperature, spo2, heart_rate):
    if temperature > 38 or spo2 < 92:
        return "follow_up", "critical", "Température élevée ou SpO2 critique"
    elif temperature >= 37.5 or spo2 < 95 or heart_rate < 60 or heart_rate > 100:
        return "prospect", "warning", "Valeurs à surveiller"
    else:
        return "retention", "stable", None

# ---------------- AI prediction ----------------
def predict_risk_level(temperature, heart_rate, spo2):
    sample = pd.DataFrame([{
        "Temperature": temperature,
        "Heart_Rate": heart_rate,
        "Oxygen_Saturation": spo2
    }])
    prediction = model.predict(sample)[0]
    return prediction

# ---------------- MQTT callbacks ----------------
def on_connect(client, userdata, flags, rc):
    print("Connecté à MQTT")
    client.subscribe("patient/data")
    print("Abonné à : patient/data")

def on_message(client, userdata, msg):
    payload = msg.payload.decode().strip()
    print(f"Message reçu sur {msg.topic}: {payload}")

    if not payload:
        print("Payload vide, message ignoré.")
        return

    try:
        data = json.loads(payload)

        name = data.get("name", "Patient MQTT")
        temperature = float(data.get("temperature", 0))
        spo2 = float(data.get("spo2", 0))
        heart_rate = int(data.get("heart_rate", 0))
        ecg_value = float(data.get("ecg_value", 0))

        # Règles classiques
        patient_status, alert_level, alert_message = evaluate_patient_status(
            temperature, spo2, heart_rate
        )

        # IA prediction
        ai_prediction = predict_risk_level(temperature, heart_rate, spo2)

        print(
            f"Patient={name} | Temp={temperature} | SpO2={spo2} | HR={heart_rate} "
            f"| ECG={ecg_value} | Status={patient_status} | Alert={alert_level} "
            f"| IA={ai_prediction}"
        )

        # 1) create patient
        patient_id = models.execute_kw(
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
                'status': patient_status,
                'alert_level': alert_level,
                'ai_prediction': ai_prediction,
            }]
        )

        print(f"Patient créé dans Odoo avec ID : {patient_id}")

        # 2) create alert if needed
        if alert_message:
            alert_value = (
                f"T={temperature}°C, SpO2={spo2}%, HR={heart_rate} bpm, IA={ai_prediction}"
            )

            alert_id = models.execute_kw(
                db,
                uid,
                password,
                'iot.alert',
                'create',
                [{
                    'patient_id': patient_id,
                    'alert_type': alert_message,
                    'alert_value': alert_value,
                    'alert_level': alert_level,
                }]
            )

            print(f"Alerte créée avec ID : {alert_id}")

        # 3) create ECG sample
        signal_status = "normal"
        if alert_level == "warning":
            signal_status = "warning"
        elif alert_level == "critical":
            signal_status = "critical"

        ecg_id = models.execute_kw(
            db,
            uid,
            password,
            'iot.ecg',
            'create',
            [{
                'patient_id': patient_id,
                'ecg_value': ecg_value,
                'bpm': heart_rate,
                'signal_status': signal_status,
            }]
        )

        print(f"ECG créé avec ID : {ecg_id}")

    except Exception as e:
        print("Erreur :", e)

# ---------------- MQTT client ----------------
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect("localhost", 1883, 60)
client.loop_forever()