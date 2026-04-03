import xmlrpc.client

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

patient_id = models.execute_kw(
    db,
    uid,
    password,
    'iot.patient',
    'create',
    [{
        'name': 'Patient Test Python',
        'temperature': 39.2,
        'spo2': 96.0,
        'heart_rate': 88,
        
        'status': 'prospect',
    }]
)

print(f"Patient créé avec ID : {patient_id}")