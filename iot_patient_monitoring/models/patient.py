from odoo import models, fields, api
import html
from datetime import timedelta


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

    ecg_ids = fields.One2many('iot.ecg', 'patient_id', string='ECG Records')
    alert_ids = fields.One2many('iot.alert', 'patient_id', string='Alerts')

    ecg_chart_html = fields.Html(
        string="Courbe ECG",
        compute="_compute_ecg_chart_html",
        sanitize=False
    )

    @api.depends('next_followup_date')
    def _compute_reminder_needed(self):
        today = fields.Date.today()
        for rec in self:
            rec.reminder_needed = bool(
                rec.next_followup_date and rec.next_followup_date <= today
            )

    @api.depends('ecg_ids', 'ecg_ids.ecg_value', 'ecg_ids.sample_time')
    def _compute_ecg_chart_html(self):
        for rec in self:
            ecg_points = [float(e.ecg_value or 0) for e in rec.ecg_ids.sorted(lambda r: r.sample_time or r.id)]

            if len(ecg_points) < 2:
                rec.ecg_chart_html = """
                    <div style="padding:15px; color:#777;">
                        Pas assez de données ECG pour afficher la courbe.
                    </div>
                """
                continue

            width = 760
            height = 240
            min_val = min(ecg_points)
            max_val = max(ecg_points)

            if max_val == min_val:
                max_val = min_val + 1

            points_str = []
            for i, val in enumerate(ecg_points):
                x = (i / max(len(ecg_points) - 1, 1)) * (width - 20) + 10
                y = height - (((val - min_val) / (max_val - min_val)) * (height - 40) + 20)
                points_str.append(f"{x},{y}")

            rec.ecg_chart_html = f"""
                <div style="margin-top:10px;">
                    <svg width="100%" height="260" viewBox="0 0 {width} {height}"
                         style="background:#fbfbfb;border:1px solid #e5e5e5;border-radius:8px;">
                        <defs>
                            <pattern id="smallGrid" width="20" height="20" patternUnits="userSpaceOnUse">
                                <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#eeeeee" stroke-width="1"/>
                            </pattern>
                            <pattern id="grid" width="100" height="100" patternUnits="userSpaceOnUse">
                                <rect width="100" height="100" fill="url(#smallGrid)"/>
                                <path d="M 100 0 L 0 0 0 100" fill="none" stroke="#dddddd" stroke-width="1"/>
                            </pattern>
                        </defs>
                        <rect width="100%" height="100%" fill="url(#grid)" />
                        <polyline fill="none" stroke="#2e8b57" stroke-width="4"
                                  stroke-linejoin="round" stroke-linecap="round"
                                  points="{' '.join(points_str)}" />
                    </svg>
                </div>
            """

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
    _order = 'alert_date desc'

    patient_id = fields.Many2one('iot.patient', string="Patient", required=True)
    alert_type = fields.Char(string="Type d’alerte", required=True)
    alert_value = fields.Char(string="Valeur")
    alert_level = fields.Selection([
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ], string="Niveau", required=True)
    alert_date = fields.Datetime(string="Date", default=fields.Datetime.now)

    is_seen = fields.Boolean(string="Alerte vue", default=False)
    seen_date = fields.Datetime(string="Date de consultation")
    doctor_email = fields.Char(string="Email du médecin")
    escalation_sent = fields.Boolean(string="Escalade envoyée", default=False)
    escalation_deadline = fields.Datetime(string="Délai d'escalade")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.alert_level == 'critical' and rec.alert_date:
                rec.escalation_deadline = rec.alert_date + timedelta(minutes=1)
            if rec.patient_id and rec.patient_id.doctor_email and not rec.doctor_email:
                rec.doctor_email = rec.patient_id.doctor_email
        return records

    def action_mark_as_seen(self):
        for rec in self:
            rec.is_seen = True
            rec.seen_date = fields.Datetime.now()

    @api.model
    def cron_check_unseen_critical_alerts(self):
        now = fields.Datetime.now()
        alerts = self.search([
            ('alert_level', '=', 'critical'),
            ('is_seen', '=', False),
            ('escalation_sent', '=', False),
            ('doctor_email', '!=', False),
            ('escalation_deadline', '!=', False),
            ('escalation_deadline', '<=', now),
        ])

        for alert in alerts:
            mail_values = {
                'subject': f"Escalade alerte critique - {alert.patient_id.name}",
                'body_html': f"""
                    <p>Bonjour,</p>
                    <p>Une alerte critique concernant le patient <b>{alert.patient_id.name}</b> n’a pas été consultée dans le délai prévu.</p>
                    <p><b>Type d’alerte :</b> {alert.alert_type}</p>
                    <p><b>Valeur :</b> {alert.alert_value}</p>
                    <p><b>Date :</b> {alert.alert_date}</p>
                    <p>Merci d’intervenir rapidement.</p>
                    <p>Cordialement,<br/>Système IoT Monitoring</p>
                """,
                'email_to': alert.doctor_email,
            }
            self.env['mail.mail'].create(mail_values).send()
            alert.escalation_sent = True


class IotEcg(models.Model):
    _name = 'iot.ecg'
    _description = 'IoT ECG Sample'
    _order = 'sample_time desc'

    patient_id = fields.Many2one('iot.patient', string="Patient", required=True)
    ecg_value = fields.Float(string="ECG Value", required=True)
    bpm = fields.Integer(string="BPM")
    signal_status = fields.Selection([
        ('normal', 'Normal'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ], string="Signal Status", default='normal')
    sample_time = fields.Datetime(string="Sample Time", default=fields.Datetime.now)