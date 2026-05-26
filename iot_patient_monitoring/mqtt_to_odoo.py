import json
import xmlrpc.client
import paho.mqtt.client as mqtt

# ---------------- MQTT config ----------------
BROKER = "192.168.137.144"
PORT = 1883
TOPIC = "patient/data"

# ---------------- Odoo config ----------------
url = "http://localhost:8069"
db = "odoo19_db"
username = "admin"
password = "admin"

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})

if not uid:
    print("Echec de connexion a Odoo")
    exit()

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connecte a MQTT")
        client.subscribe(TOPIC)
        print(f"Abonne a : {TOPIC}")
    else:
        print("Erreur connexion MQTT, code:", rc)


def on_message(client, userdata, msg):
    payload = msg.payload.decode().strip()
    print(f"\nMessage recu sur {msg.topic}: {payload}")

    if not payload:
        print("Payload vide, message ignore.")
        return

    try:
        data = json.loads(payload)

        device_id = data.get("device_id")
        patient_code = data.get("patient_code") or data.get("code")

        temperature = float(data.get("temperature", data.get("body_temperature", 0)) or 0)
        spo2 = float(data.get("spo2", data.get("SpO2", 0)) or 0)
        heart_rate = int(data.get("heart_rate", data.get("pulse", 0)) or 0)

        print(
            f"Device={device_id} | Code patient={patient_code} | "
            f"Temp={temperature} | SpO2={spo2} | BPM={heart_rate}"
        )

        # Version finale : recherche par device_id.
        # Fallback patient_code gardé seulement pour compatibilité avec anciens tests.
        if device_id:
            domain = [("device_id", "=", device_id)]
        elif patient_code:
            domain = [("patient_code", "=", patient_code)]
        else:
            print("Aucun device_id/patient_code dans le message. Message ignore.")
            return

        patient_ids = models.execute_kw(
            db, uid, password,
            "iot.patient", "search",
            [domain],
            {"limit": 1}
        )

        if not patient_ids:
            print("Aucun patient associe a ce device_id/code. Message ignore.")
            print("Dans Odoo, associe le Device ID du patient, ex : RPI-001.")
            return

        patient_id = patient_ids[0]

        patient_vals = {
            "temperature": temperature,
            "spo2": spo2,
            "heart_rate": heart_rate,
        }

        models.execute_kw(
            db, uid, password,
            "iot.patient", "write",
            [[patient_id], patient_vals]
        )

        print(f"Patient mis a jour dans Odoo avec ID : {patient_id}")

        # ECG: mesure ponctuelle. Envoyer ecg_value seulement quand une mesure ECG est disponible.
        if "ecg_value" in data and data.get("ecg_value") not in (None, ""):
            ecg_value = float(data.get("ecg_value") or 0)
            ecg_id = models.execute_kw(
                db, uid, password,
                "iot.ecg", "create",
                [{
                    "patient_id": patient_id,
                    "ecg_value": ecg_value,
                    "bpm": heart_rate,
                }]
            )
            print(f"ECG cree avec ID : {ecg_id}")

    except Exception as e:
        print("Erreur :", e)


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, 60)
client.loop_forever()
