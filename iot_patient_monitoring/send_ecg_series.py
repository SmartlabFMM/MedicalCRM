import json
import time
import paho.mqtt.publish as publish

values = [0.6, 0.9, 0.7, 1.6, 0.5, 0.8, 0.7, 1.5, 0.6, 0.9, 0.7, 1.7, 0.5, 0.8, 0.7]

for v in values:
    data = {
        "name": "Patient ECG",
        "temperature": 38.2,
        "spo2": 91,
        "heart_rate": 110,
        "ecg_value": v
    }

    publish.single("patient/data", json.dumps(data), hostname="localhost")
    print("Envoyé:", data)
    time.sleep(0.5)