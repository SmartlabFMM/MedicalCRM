import paho.mqtt.client as mqtt
import xmlrpc.client

# MQTT
broker = "localhost"
topic = "patient/temperature"

# Odoo
url = "http://localhost:8069"
db = "odoo19_db"
username = "admin"
password = "admin"

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

def on_message(client, userdata, msg):
    temperature = float(msg.payload.decode())
    print("Température reçue:", temperature)

    models.execute_kw(
        db, uid, password,
        'iot.patient', 'create',
        [{
            'name': 'Patient Test',
            'temperature': temperature
        }]
    )

client = mqtt.Client()
client.on_message = on_message

client.connect(broker, 1883)
client.subscribe(topic)

client.loop_forever()