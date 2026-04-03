from odoo import models, fields, api


class Patient(models.Model):
    _name = 'iot.patient'
    _description = 'IoT Patient Monitoring'
    _order = 'id desc'

    name = fields.Char(string="Nom du patient", required=True)
    temperature = fields.Float(string="Température (°C)")
    spo2 = fields.Float(string="SpO2 (%)")
    heart_rate = fields.Integer(string="Fréquence cardiaque (bpm)")

    status = fields.Selection([
        ('prospect', 'Prospect'),
        ('follow_up', 'Suivi'),
        ('retention', 'Fidélisation'),
    ], string="Pipeline", default='prospect')

    alert_level = fields.Selection([
        ('stable', 'Stable'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ], string="Niveau d’alerte", default='stable')

    ai_prediction = fields.Char(string="Prédiction IA")

    next_followup_date = fields.Date(string="Date du prochain rappel")
    doctor_email = fields.Char(string="Email du médecin")
    notes = fields.Text(string="Notes")

    reminder_needed = fields.Boolean(
        string="Rappel nécessaire",
        compute="_compute_reminder_needed",
        store=True
    )

    reminder_sent = fields.Boolean(string="Rappel envoyé", default=False)

    @api.depends('next_followup_date')
    def _compute_reminder_needed(self):
        today = fields.Date.today()
        for rec in self:
            rec.reminder_needed = bool(
                rec.next_followup_date and rec.next_followup_date <= today
            )

    def action_send_followup_email(self):
        for rec in self:
            if rec.doctor_email and rec.next_followup_date:
                mail_values = {
                    'subject': f"Rappel de suivi médical - {rec.name}",
                    'body_html': f"""
                        <p>Bonjour,</p>
                        <p>Le patient <b>{rec.name}</b> nécessite un suivi médical.</p>
                        <p>Date prévue du rappel : <b>{rec.next_followup_date}</b></p>
                        <p>Niveau d’alerte : <b>{rec.alert_level}</b></p>
                        <p>Prédiction IA : <b>{rec.ai_prediction or 'Non disponible'}</b></p>
                        <p>Merci de vérifier son dossier dans Odoo.</p>
                        <p>Cordialement,<br/>Système IoT Monitoring</p>
                    """,
                    'email_to': rec.doctor_email,
                }
                self.env['mail.mail'].create(mail_values).send()
                rec.reminder_sent = True

    @api.model
    def cron_send_followup_reminders(self):
        today = fields.Date.today()
        patients = self.search([
            ('next_followup_date', '<=', today),
            ('doctor_email', '!=', False),
            ('reminder_sent', '=', False),
        ])
        for patient in patients:
            patient.action_send_followup_email()


class IotAlert(models.Model):
    _name = 'iot.alert'
    _description = 'IoT Medical Alert'

    patient_id = fields.Many2one('iot.patient', string="Patient", required=True)
    alert_type = fields.Char(string="Type d’alerte", required=True)
    alert_value = fields.Char(string="Valeur")
    alert_level = fields.Selection([
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ], string="Niveau", required=True)
    alert_date = fields.Datetime(string="Date", default=fields.Datetime.now)


class IotEcg(models.Model):
    _name = 'iot.ecg'
    _description = 'IoT ECG Sample'

    patient_id = fields.Many2one('iot.patient', string="Patient", required=True)
    ecg_value = fields.Float(string="ECG Value", required=True)
    bpm = fields.Integer(string="BPM")
    signal_status = fields.Selection([
        ('normal', 'Normal'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ], string="Signal Status", default='normal')
    sample_time = fields.Datetime(string="Sample Time", default=fields.Datetime.now)