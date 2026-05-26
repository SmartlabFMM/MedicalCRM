from odoo import models, fields, api
from datetime import timedelta
import html


class Patient(models.Model):
    _name = 'iot.patient'
    _description = 'IoT Patient Monitoring'
    _order = 'id desc'

    name = fields.Char(string="Nom du patient", required=True)
    age = fields.Integer(string="Âge")
    gender = fields.Selection([
        ('female', 'Femme'),
        ('male', 'Homme'),
        ('other', 'Autre'),
    ], string="Genre")

    patient_code = fields.Char(string="Code patient", copy=False, readonly=True)
    device_id = fields.Char(string="Device ID", copy=False, index=True,
                            help="Identifiant unique du dispositif IoT associé au patient, ex. RPI-001.")
    doctor_id = fields.Many2one('res.users', string="Médecin responsable")
    doctor_email = fields.Char(string="Email du médecin")
    floor = fields.Selection([
        ('1', 'Étage 1'),
        ('2', 'Étage 2'),
        ('3', 'Étage 3'),
        ('4', 'Étage 4'),
        ('5', 'Étage 5'),
    ], string="Étage")
    room = fields.Char(string="Chambre")

    temperature = fields.Float(string="🌡️ Température (°C)")
    spo2 = fields.Float(string="💧 SpO₂ (%)")
    heart_rate = fields.Integer(string="❤️ Fréquence cardiaque (BPM)")
    last_measure_date = fields.Datetime(string="Dernière mesure", readonly=True)


    status = fields.Selection([
        ('stable', 'Stable'),
        ('warning', 'Warning'),
    ], string="État", default='stable', readonly=True)

    alert_level = fields.Selection([
        ('stable', 'Stable'),
        ('warning', 'Warning'),
    ], string="Niveau médical", default='stable', readonly=True)

    alert_unseen = fields.Boolean(
        string="Alerte non vue",
        compute="_compute_alert_unseen",
        store=True
    )

    notes = fields.Text(string="Notes médicales")

    ecg_ids = fields.One2many('iot.ecg', 'patient_id', string='Signaux ECG')
    alert_ids = fields.One2many('iot.alert', 'patient_id', string='Alertes')
    vital_ids = fields.One2many('iot.vital.history', 'patient_id', string='Historique des signes vitaux')

    vital_chart_html = fields.Html(
        string="Courbes des signes vitaux",
        compute="_compute_vital_chart_html",
        sanitize=False
    )

    ecg_chart_html = fields.Html(
        string="Courbe ECG",
        compute="_compute_ecg_chart_html",
        sanitize=False
    )

    @api.onchange('doctor_id')
    def _onchange_doctor_id(self):
        for rec in self:
            if rec.doctor_id and rec.doctor_id.email:
                rec.doctor_email = rec.doctor_id.email

    @api.depends('alert_ids.is_seen', 'alert_ids.alert_level')
    def _compute_alert_unseen(self):
        for rec in self:
            rec.alert_unseen = any(
                alert.alert_level == 'warning' and not alert.is_seen
                for alert in rec.alert_ids
            )

    def _get_warning_reasons(self):
        self.ensure_one()
        reasons = []

        if self.temperature and self.temperature > 38:
            reasons.append("Température élevée")

        if self.spo2 and self.spo2 < 92:
            reasons.append("SpO₂ basse")

        if self.heart_rate and self.heart_rate > 100:
            reasons.append("Fréquence cardiaque élevée")
        elif self.heart_rate and self.heart_rate < 60:
            reasons.append("Fréquence cardiaque basse")

        return reasons

    def _update_medical_state(self, create_alert=True):
        for rec in self:
            reasons = rec._get_warning_reasons()
            level = 'warning' if reasons else 'stable'

            if rec.status != level or rec.alert_level != level:
                rec.with_context(skip_medical_state_update=True).write({
                    'status': level,
                    'alert_level': level,
                })

            if create_alert and level == 'warning':
                alert_type = ', '.join(reasons)
                existing_alert = self.env['iot.alert'].search([
                    ('patient_id', '=', rec.id),
                    ('alert_level', '=', 'warning'),
                    ('alert_type', '=', alert_type),
                    ('is_seen', '=', False),
                ], limit=1)

                if not existing_alert:
                    self.env['iot.alert'].create({
                        'patient_id': rec.id,
                        'alert_type': alert_type,
                        'alert_level': 'warning',
                    })

    @api.model_create_multi
    def create(self, vals_list):
        monitored_fields = {'temperature', 'spo2', 'heart_rate'}
        history_flags = []
        for vals in vals_list:
            if vals.get('doctor_id') and not vals.get('doctor_email'):
                doctor = self.env['res.users'].browse(vals['doctor_id'])
                vals['doctor_email'] = doctor.email
            has_measure = bool(monitored_fields.intersection(vals.keys()))
            history_flags.append(has_measure)
            if has_measure and not vals.get('last_measure_date'):
                vals['last_measure_date'] = fields.Datetime.now()

        records = super().create(vals_list)

        for rec in records:
            if not rec.patient_code:
                rec.with_context(skip_medical_state_update=True).write({
                    'patient_code': f"P-{rec.id:05d}"
                })

        for rec, has_measure in zip(records, history_flags):
            if has_measure:
                rec._record_vital_history()

        if not self.env.context.get('skip_medical_state_update'):
            records._update_medical_state(create_alert=True)

        return records

    def write(self, vals):
        if vals.get('doctor_id') and not vals.get('doctor_email'):
            doctor = self.env['res.users'].browse(vals['doctor_id'])
            vals['doctor_email'] = doctor.email

        monitored_fields = {'temperature', 'spo2', 'heart_rate'}
        has_measure = bool(monitored_fields.intersection(vals.keys()))
        if has_measure and not vals.get('last_measure_date'):
            vals['last_measure_date'] = fields.Datetime.now()

        result = super().write(vals)

        if has_measure:
            self._record_vital_history()

        if not self.env.context.get('skip_medical_state_update') and has_measure:
            self._update_medical_state(create_alert=True)

        return result

    def _record_vital_history(self):
        History = self.env['iot.vital.history']
        for rec in self:
            if rec.spo2 or rec.heart_rate or rec.temperature:
                History.create({
                    'patient_id': rec.id,
                    'spo2': rec.spo2,
                    'heart_rate': rec.heart_rate,
                    'temperature': rec.temperature,
                    'measure_date': rec.last_measure_date or fields.Datetime.now(),
                })

    @api.depends('vital_ids', 'vital_ids.spo2', 'vital_ids.heart_rate', 'vital_ids.temperature', 'vital_ids.measure_date')
    def _compute_vital_chart_html(self):
        def fmt_time(rec, dt):
            return fields.Datetime.context_timestamp(rec, dt).strftime('%H:%M') if dt else ''

        def build_chart(rec, points, color, fill, y_label):
            width = 360
            height = 145
            left = 38
            right = 12
            top = 18
            bottom = 30

            if len(points) < 2:
                return """
                    <div style="height:145px;background:#f8fafc;border-radius:14px;display:flex;align-items:center;justify-content:center;color:#64748b;font-weight:700;">
                        Aucun historique suffisant
                    </div>
                """

            values = [float(v or 0) for _, v in points]
            min_val = min(values)
            max_val = max(values)

            if max_val == min_val:
                max_val = min_val + 1

            margin = (max_val - min_val) * 0.15
            min_val -= margin
            max_val += margin

            line_points = []
            area_points = []

            for i, (date, value) in enumerate(points):
                x = left + (i / max(len(points) - 1, 1)) * (width - left - right)
                y = top + ((max_val - float(value or 0)) / (max_val - min_val)) * (height - top - bottom)
                line_points.append(f"{x:.1f},{y:.1f}")
                area_points.append((x, y))

            area = (
                f"{left},{height-bottom} "
                + " ".join(f"{x:.1f},{y:.1f}" for x, y in area_points)
                + f" {width-right},{height-bottom}"
            )

            first_label = fmt_time(rec, points[0][0])
            last_label = fmt_time(rec, points[-1][0])

            return f"""
                <svg width="100%" height="165" viewBox="0 0 {width} {height}" preserveAspectRatio="none"
                     style="background:#f8fafc;border-radius:14px;border:1px solid #e5e7eb;display:block;">
                    <line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#94a3b8" stroke-width="1"/>
                    <line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#94a3b8" stroke-width="1"/>

                    <text x="8" y="24" fill="#475569" font-size="11" font-weight="700">{html.escape(y_label)}</text>
                    <text x="{left}" y="{height-10}" fill="#475569" font-size="10">{html.escape(first_label)}</text>
                    <text x="{width-right}" y="{height-10}" fill="#475569" font-size="10" text-anchor="end">{html.escape(last_label)}</text>
                    <text x="{width/2}" y="{height-3}" fill="#475569" font-size="10" font-weight="700" text-anchor="middle">Temps</text>

                    <polygon points="{area}" fill="{fill}" opacity="0.75"/>
                    <polyline points="{' '.join(line_points)}"
                              fill="none"
                              stroke="{color}"
                              stroke-width="3.5"
                              stroke-linecap="round"
                              stroke-linejoin="round"/>
                </svg>
            """

        def card(rec, title, emoji, value, unit, points, color, fill, label):
            return f"""
                <div style="border:1px solid #dbeafe;border-radius:18px;background:#fff;padding:14px;min-width:0;box-sizing:border-box;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;gap:10px;">
                        <div style="font-weight:900;color:#0f172a;font-size:17px;white-space:nowrap;">{emoji} {html.escape(title)}</div>
                        <div style="font-weight:900;color:{color};font-size:19px;white-space:nowrap;">{value} {html.escape(unit)}</div>
                    </div>
                    {build_chart(rec, points, color, fill, label)}
                </div>
            """

        for rec in self:
            history = rec.vital_ids.sorted(lambda h: h.measure_date or h.id)[-12:]

            if len(history) < 2:
                rec.vital_chart_html = """
                    <div style="padding:18px;color:#64748b;background:#f8fafc;border:1px solid #e5e7eb;border-radius:14px;font-weight:700;">
                        Aucun historique des signes vitaux pour afficher les courbes.
                    </div>
                """
                continue

            bpm_points = [(h.measure_date, h.heart_rate or 0) for h in history]
            spo2_points = [(h.measure_date, h.spo2 or 0) for h in history]
            temp_points = [(h.measure_date, h.temperature or 0) for h in history]

            rec.vital_chart_html = f"""
                <div style="margin-top:12px;width:100%;box-sizing:border-box;">
                    <h2 style="font-size:22px;font-weight:900;color:#0f172a;margin:0 0 4px 0;">Courbes des signes vitaux</h2>
                    <div style="color:#475569;margin-bottom:14px;font-size:14px;">Axe X : Temps · Axe Y : valeur médicale</div>

                    <div style="display:grid;grid-template-columns:repeat(3, minmax(0, 1fr));gap:16px;width:100%;box-sizing:border-box;">
                        {card(rec, 'Fréquence cardiaque', '❤️', f'{rec.heart_rate:.0f}', 'BPM', bpm_points, '#ef4444', '#fee2e2', 'BPM')}
                        {card(rec, 'SpO₂', '💧', f'{rec.spo2:.1f}', '%', spo2_points, '#2563eb', '#dbeafe', 'SpO₂ (%)')}
                        {card(rec, 'Température', '🌡️', f'{rec.temperature:.1f}', '°C', temp_points, '#16a34a', '#dcfce7', '°C')}
                    </div>
                </div>
            """

    @api.depends('ecg_ids', 'ecg_ids.ecg_value', 'ecg_ids.sample_time')
    def _compute_ecg_chart_html(self):
        for rec in self:
            ecg_records = rec.ecg_ids.sorted(lambda r: r.sample_time or r.id)
            ecg_points = [float(e.ecg_value or 0) for e in ecg_records]

            if len(ecg_points) < 2:
                rec.ecg_chart_html = """
                    <div style="padding:18px;color:#6b7280;background:#f9fafb;border:1px solid #e5e7eb;border-radius:14px;">
                        Aucun signal ECG suffisant pour afficher la courbe.
                    </div>
                """
                continue

            width = 900
            height = 280
            min_val = min(ecg_points)
            max_val = max(ecg_points)
            if max_val == min_val:
                max_val = min_val + 1

            points_str = []
            for i, val in enumerate(ecg_points):
                x = (i / max(len(ecg_points) - 1, 1)) * (width - 30) + 15
                y = height - (((val - min_val) / (max_val - min_val)) * (height - 50) + 25)
                points_str.append(f"{x:.1f},{y:.1f}")

            rec.ecg_chart_html = f"""
                <div style="margin-top:10px;background:#fff;border:1px solid #e5e7eb;border-radius:18px;padding:14px;">
                    <div style="font-weight:800;margin-bottom:10px;color:#111827;">Signal ECG enregistré</div>
                    <svg width="100%" height="300" viewBox="0 0 {width} {height}" preserveAspectRatio="none"
                         style="background:#fff7f7;border:1px solid #fecaca;border-radius:12px;">
                        <defs>
                            <pattern id="smallGrid" width="20" height="20" patternUnits="userSpaceOnUse">
                                <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#fee2e2" stroke-width="1"/>
                            </pattern>
                            <pattern id="grid" width="100" height="100" patternUnits="userSpaceOnUse">
                                <rect width="100" height="100" fill="url(#smallGrid)"/>
                                <path d="M 100 0 L 0 0 0 100" fill="none" stroke="#fecaca" stroke-width="1"/>
                            </pattern>
                        </defs>
                        <rect width="100%" height="100%" fill="url(#grid)"/>
                        <polyline fill="none" stroke="#dc2626" stroke-width="3.5"
                                  stroke-linejoin="round" stroke-linecap="round"
                                  points="{' '.join(points_str)}"/>
                    </svg>
                    <div style="color:#6b7280;margin-top:8px;font-size:13px;">
                        Affichage uniquement du signal ECG, sans classification normal/anormal.
                    </div>
                </div>
            """


class IotAlert(models.Model):
    _name = 'iot.alert'
    _description = 'IoT Medical Alert'
    _order = 'alert_date desc'

    patient_id = fields.Many2one('iot.patient', string="Patient", required=True, ondelete='cascade')
    alert_type = fields.Char(string="Anomalies détectées", required=True)
    alert_value = fields.Char(string="Valeur", help="Champ conservé techniquement, non utilisé dans l'email.")

    alert_level = fields.Selection([
        ('warning', 'Warning'),
    ], string="Niveau", required=True, default='warning')

    alert_date = fields.Datetime(string="Date", default=fields.Datetime.now)
    is_seen = fields.Boolean(string="Alerte vue", default=False)
    seen_date = fields.Datetime(string="Date de consultation")
    doctor_email = fields.Char(string="Email du médecin")
    email_sent = fields.Boolean(string="Email envoyé", default=False)
    email_sent_date = fields.Datetime(string="Date d'envoi email")

    is_seen_display = fields.Char(string="Alerte vue", compute="_compute_display_status")
    email_sent_display = fields.Char(string="Email", compute="_compute_display_status")

    @api.depends('is_seen', 'email_sent')
    def _compute_display_status(self):
        for rec in self:
            rec.is_seen_display = "Vue" if rec.is_seen else "Non vue"
            rec.email_sent_display = "Envoyé" if rec.email_sent else "Non envoyé"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.patient_id:
                recipient = rec.patient_id.doctor_id.email or rec.patient_id.doctor_email
                if recipient and not rec.doctor_email:
                    rec.doctor_email = recipient
        return records

    def _send_unseen_alert_email(self):
        for rec in self:
            if rec.email_sent or rec.is_seen or not rec.doctor_email:
                continue

            patient_name = html.escape(rec.patient_id.name or '')
            room = html.escape(rec.patient_id.room or 'Non renseignée')
            reasons = [r.strip() for r in (rec.alert_type or '').split(',') if r.strip()]
            reasons_html = ''.join(f"<li>{html.escape(reason)}</li>" for reason in reasons) or '<li>Warning</li>'

            body_html = f"""
                <p>Bonjour,</p>
                <p>Une alerte concernant le patient <b>{patient_name}</b> n’a pas été consultée dans le délai prévu.</p>
                <p><b>État :</b> Warning<br/>
                <b>Chambre :</b> {room}</p>
                <p><b>Anomalies détectées :</b></p>
                <ul>{reasons_html}</ul>
                <p>Merci d’intervenir rapidement.</p>
                <p>Cordialement,<br/>Système MedIoT</p>
            """

            self.env['mail.mail'].create({
                'subject': f"Alerte MedIoT non consultée - Patient {rec.patient_id.name}",
                'body_html': body_html,
                'email_to': rec.doctor_email,
            }).send()
            rec.write({
                'email_sent': True,
                'email_sent_date': fields.Datetime.now(),
            })

    def action_mark_as_seen(self):
        for rec in self:
            rec.write({
                'is_seen': True,
                'seen_date': fields.Datetime.now(),
            })

    @api.model
    def cron_check_unseen_alerts(self):
        delay_limit = fields.Datetime.now() - timedelta(minutes=2)
        alerts = self.search([
            ('alert_level', '=', 'warning'),
            ('is_seen', '=', False),
            ('email_sent', '=', False),
            ('alert_date', '<=', delay_limit),
        ])
        alerts._send_unseen_alert_email()
        return True

    @api.model
    def cron_check_unseen_critical_alerts(self):
        # Compatibilité avec une ancienne action planifiée, si elle existe déjà.
        return self.cron_check_unseen_alerts()



class IotVitalHistory(models.Model):
    _name = 'iot.vital.history'
    _description = 'Historique des signes vitaux'
    _order = 'measure_date asc, id asc'

    patient_id = fields.Many2one('iot.patient', string="Patient", required=True, ondelete='cascade')
    spo2 = fields.Float(string="💧 SpO₂ (%)")
    heart_rate = fields.Integer(string="❤️ Fréquence cardiaque (BPM)")
    temperature = fields.Float(string="🌡️ Température (°C)")
    measure_date = fields.Datetime(string="Date de mesure", default=fields.Datetime.now, required=True)


class IotEcg(models.Model):
    _name = 'iot.ecg'
    _description = 'IoT ECG Sample'
    _order = 'sample_time asc, id asc'

    patient_id = fields.Many2one('iot.patient', string="Patient", required=True, ondelete='cascade')
    ecg_value = fields.Float(string="Valeur ECG", required=True)
    bpm = fields.Integer(string="BPM")
    sample_time = fields.Datetime(string="Date", default=fields.Datetime.now)
