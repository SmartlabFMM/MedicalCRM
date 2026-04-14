from odoo import models, fields, api
import html


class IotDashboard(models.Model):
    _name = 'iot.dashboard'
    _description = 'IoT Dashboard'

    name = fields.Char(default="Dashboard")
    dashboard_html = fields.Html(
        string="Dashboard",
        compute="_compute_dashboard_html",
        sanitize=False
    )

    @api.depends()
    def _compute_dashboard_html(self):
        Patient = self.env['iot.patient']
        Alert = self.env['iot.alert']

        total_patients = Patient.search_count([])
        stable_count = Patient.search_count([('alert_level', '=', 'stable')])
        warning_count = Patient.search_count([('alert_level', '=', 'warning')])
        critical_count = Patient.search_count([('alert_level', '=', 'critical')])
        total_alerts = Alert.search_count([])
        reminders_needed = Patient.search_count([('reminder_needed', '=', True)])

        latest_alerts = Alert.search([], order='alert_date desc', limit=5)
        latest_patients = Patient.search([], order='write_date desc, id desc', limit=5)
        recent_patients = Patient.search([], order='write_date desc, id desc', limit=5)

        def safe(val):
            return html.escape(str(val or ""))

        def badge(level):
            level = (level or "").lower()
            if level == "stable":
                return '<span style="background:#7cc576;color:white;padding:4px 12px;border-radius:12px;font-size:13px;">Stable</span>'
            if level == "warning":
                return '<span style="background:#f0ad4e;color:white;padding:4px 12px;border-radius:12px;font-size:13px;">Warning</span>'
            if level == "critical":
                return '<span style="background:#d9534f;color:white;padding:4px 12px;border-radius:12px;font-size:13px;">Critical</span>'
            return f"<span>{safe(level)}</span>"

        alerts_rows = ""
        for a in latest_alerts:
            alerts_rows += f"""
            <tr>
                <td style="padding:10px;">{safe(a.patient_id.name)}</td>
                <td style="padding:10px;">{safe(a.alert_type)}</td>
                <td style="padding:10px;">{safe(a.alert_value)}</td>
                <td style="padding:10px;">{safe(a.alert_date)}</td>
            </tr>
            """

        mesures_rows = ""
        for p in latest_patients:
            mesures_rows += f"""
            <tr>
                <td style="padding:10px;">{safe(p.name)}</td>
                <td style="padding:10px;">{safe(p.temperature)} °C</td>
                <td style="padding:10px;">{safe(p.spo2)} %</td>
                <td style="padding:10px;">{safe(p.heart_rate)} bpm</td>
                <td style="padding:10px;">{badge(p.alert_level)}</td>
            </tr>
            """

        patients_rows = ""
        for p in recent_patients:
            detail_link = f"/web#id={p.id}&model=iot.patient&view_type=form"
            last_date = p.write_date or p.create_date or ""
            patients_rows += f"""
            <tr>
                <td style="padding:10px;">{safe(p.name)}</td>
                <td style="padding:10px;">{badge(p.alert_level)}</td>
                <td style="padding:10px;">{safe(last_date)}</td>
                <td style="padding:10px;">
                    <a href="{detail_link}" style="background:#4e73df;color:white;padding:6px 12px;border-radius:8px;text-decoration:none;font-size:13px;">
                        Détail
                    </a>
                </td>
            </tr>
            """

        for rec in self:
            rec.dashboard_html = f"""
            <div style="padding:20px; font-family:Arial, sans-serif; background:#f5f6fa;">
                <h1 style="margin-bottom:20px;">Dashboard</h1>

                <div style="display:flex; gap:20px; margin-bottom:25px; flex-wrap:wrap;">

                    <div style="flex:1; min-width:220px; background:#58b8d8; color:white; border-radius:14px; padding:20px;">
                        <h2 style="margin:0; font-size:22px;">Total Patients</h2>
                        <p style="font-size:34px; margin:10px 0 0 0; font-weight:bold;">{total_patients}</p>
                    </div>

                    <div style="flex:1; min-width:220px; background:#8bcf93; color:white; border-radius:14px; padding:20px;">
                        <h2 style="margin:0; font-size:22px;">Stable</h2>
                        <p style="font-size:34px; margin:10px 0 0 0; font-weight:bold;">{stable_count}</p>
                    </div>

                    <div style="flex:1; min-width:220px; background:#f0b04e; color:white; border-radius:14px; padding:20px;">
                        <h2 style="margin:0; font-size:22px;">Warning</h2>
                        <p style="font-size:34px; margin:10px 0 0 0; font-weight:bold;">{warning_count}</p>
                    </div>

                    <div style="flex:1; min-width:220px; background:#d96666; color:white; border-radius:14px; padding:20px;">
                        <h2 style="margin:0; font-size:22px;">Critical</h2>
                        <p style="font-size:34px; margin:10px 0 0 0; font-weight:bold;">{critical_count}</p>
                    </div>

                    <div style="flex:1; min-width:220px; background:#6c8ebf; color:white; border-radius:14px; padding:20px;">
                        <h2 style="margin:0; font-size:22px;">Total Alerts</h2>
                        <p style="font-size:34px; margin:10px 0 0 0; font-weight:bold;">{total_alerts}</p>
                    </div>

                    <div style="flex:1; min-width:220px; background:#8e7cc3; color:white; border-radius:14px; padding:20px;">
                        <h2 style="margin:0; font-size:22px;">Reminders Needed</h2>
                        <p style="font-size:34px; margin:10px 0 0 0; font-weight:bold;">{reminders_needed}</p>
                    </div>

                </div>

                <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px;">

                    <div style="background:white; border-radius:12px; padding:20px; box-shadow:0 2px 8px rgba(0,0,0,0.08);">
                        <h2 style="margin-top:0;">Dernières alertes</h2>
                        <table style="width:100%; border-collapse:collapse;">
                            <thead>
                                <tr style="background:#f2f2f2;">
                                    <th style="padding:10px; text-align:left;">Patient</th>
                                    <th style="padding:10px; text-align:left;">Alert</th>
                                    <th style="padding:10px; text-align:left;">Value</th>
                                    <th style="padding:10px; text-align:left;">Date</th>
                                </tr>
                            </thead>
                            <tbody>
                                {alerts_rows if alerts_rows else '<tr><td colspan="4" style="padding:10px;">Aucune alerte.</td></tr>'}
                            </tbody>
                        </table>
                    </div>

                    <div style="background:white; border-radius:12px; padding:20px; box-shadow:0 2px 8px rgba(0,0,0,0.08);">
                        <h2 style="margin-top:0;">Dernières mesures</h2>
                        <table style="width:100%; border-collapse:collapse;">
                            <thead>
                                <tr style="background:#f2f2f2;">
                                    <th style="padding:10px; text-align:left;">Patient</th>
                                    <th style="padding:10px; text-align:left;">Température</th>
                                    <th style="padding:10px; text-align:left;">SpO2</th>
                                    <th style="padding:10px; text-align:left;">Pouls</th>
                                    <th style="padding:10px; text-align:left;">Statut</th>
                                </tr>
                            </thead>
                            <tbody>
                                {mesures_rows if mesures_rows else '<tr><td colspan="5" style="padding:10px;">Aucune donnée.</td></tr>'}
                            </tbody>
                        </table>
                    </div>

                    <div style="background:white; border-radius:12px; padding:20px; box-shadow:0 2px 8px rgba(0,0,0,0.08); grid-column:1 / span 2;">
                        <h2 style="margin-top:0;">Patients récents</h2>
                        <table style="width:100%; border-collapse:collapse;">
                            <thead>
                                <tr style="background:#f2f2f2;">
                                    <th style="padding:10px; text-align:left;">Nom</th>
                                    <th style="padding:10px; text-align:left;">Statut</th>
                                    <th style="padding:10px; text-align:left;">Dernière mesure</th>
                                    <th style="padding:10px; text-align:left;">Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                {patients_rows if patients_rows else '<tr><td colspan="4" style="padding:10px;">Aucun patient.</td></tr>'}
                            </tbody>
                        </table>
                    </div>

                </div>
            </div>
            """