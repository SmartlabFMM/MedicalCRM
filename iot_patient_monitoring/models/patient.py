from odoo import models, fields

class Patient(models.Model):
    _name = 'iot.patient'
    _description = 'IoT Patient Monitoring'

    name = fields.Char(string="Nom du patient")

    heart_rate = fields.Integer(string="Fréquence cardiaque (bpm)")
    spo2 = fields.Float(string="SpO2 (%)")
    temperature = fields.Float(string="Température (°C)")
    ecg_value = fields.Float(string="ECG")
    respiration = fields.Float(string="Fréquence respiratoire")
    fall_detected = fields.Boolean(string="Chute détectée")