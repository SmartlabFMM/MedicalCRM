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
        Ecg = self.env['iot.ecg']

        total_patients = Patient.search_count([])
        stable_count = Patient.search_count([('alert_level', '=', 'stable')])
        warning_count = Patient.search_count([('alert_level', '=', 'warning')])
        critical_count = Patient.search_count([('alert_level', '=', 'critical')])

        latest_alerts = Alert.search([], order='alert_date desc', limit=5)
        latest_patients = Patient.search([], order='id desc', limit=5)
        latest_ecg = Ecg.search([], order='sample_time desc', limit=30)

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

        patients_rows = ""
        for p in latest_patients:
            patients_rows += f"""
            <tr>
                <td style="padding:10px;">{safe(p.name)}</td>
                <td style="padding:10px;">{safe(p.temperature)} °C</td>
                <td style="padding:10px;">{safe(p.spo2)} %</td>
                <td style="padding:10px;">{safe(p.heart_rate)} bpm</td>
                <td style="padding:10px;">{badge(p.alert_level)}</td>
            </tr>
            """

        ecg_points = list(reversed([float(e.ecg_value or 0) for e in latest_ecg]))
        latest_bpm = latest_ecg[-1].bpm if latest_ecg else 0
        latest_signal = latest_ecg[-1].signal_status if latest_ecg else "normal"

        def signal_badge(sig):
            sig = (sig or "").lower()
            if sig == "normal":
                return '<span style="color:#5f9f6f;font-weight:bold;">● Signal normal</span>'
            if sig == "warning":
                return '<span style="color:#f0ad4e;font-weight:bold;">● Signal warning</span>'
            if sig == "critical":
                return '<span style="color:#d9534f;font-weight:bold;">● Signal critical</span>'
            return f"<span>{safe(sig)}</span>"

        svg_polyline = ""
        if len(ecg_points) >= 2:
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

            svg_polyline = f"""
            <svg width="100%" height="260" viewBox="0 0 {width} {height}" style="background:#fbfbfb;border:1px solid #e5e5e5;border-radius:8px;">
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
                <polyline fill="none" stroke="#2e8b57" stroke-width="4" stroke-linejoin="round" stroke-linecap="round" points="{' '.join(points_str)}" />
            </svg>
            """
        else:
            svg_polyline = """
            <div style="padding:20px; color:#777;">Pas assez de données ECG pour afficher la courbe.</div>
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

                </div>

                <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px;">

                    <div style="background:white; border-radius:12px; padding:20px; box-shadow:0 2px 8px rgba(0,0,0,0.08);">
                        <h2 style="margin-top:0;">Active Alerts</h2>
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
                        <h2 style="margin-top:0;">Dernières Mesures</h2>
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
                                {patients_rows if patients_rows else '<tr><td colspan="5" style="padding:10px;">Aucune donnée.</td></tr>'}
                            </tbody>
                        </table>
                    </div>

                    <div style="background:white; border-radius:12px; padding:20px; box-shadow:0 2px 8px rgba(0,0,0,0.08); grid-column:1 / span 2;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                            <h2 style="margin:0;">ECG</h2>
                            <div>{signal_badge(latest_signal)}</div>
                        </div>

                        <div style="font-size:18px; font-weight:bold; margin-bottom:10px;">
                            {latest_bpm} bpm
                        </div>

                        {svg_polyline}
                    </div>

                </div>
            </div>
            """