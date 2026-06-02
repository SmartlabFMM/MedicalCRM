from odoo import models, fields, api
import html
import re


class IotDashboard(models.Model):
    _name = 'iot.dashboard'
    _description = 'IoT Dashboard'

    name = fields.Char(default="Medical CRM")
    dashboard_html = fields.Html(
        string="Tableau de bord",
        compute="_compute_dashboard_html",
        sanitize=False
    )

    def _human_time(self, dt):
        if not dt:
            return "—"
        delta = fields.Datetime.now() - dt
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"il y a {seconds} sec"
        minutes = seconds // 60
        if minutes < 60:
            return f"il y a {minutes} min"
        hours = minutes // 60
        if hours < 24:
            return f"il y a {hours} h"
        return f"il y a {hours // 24} j"
    def _format_datetime(self, dt):
        if not dt:
            return "—"
        local_dt = fields.Datetime.context_timestamp(self, dt)
        return local_dt.strftime("%d/%m/%Y %H:%M")

    def _floor_class(self, floor):
        value = re.sub(r'[^a-zA-Z0-9_-]', '-', str(floor or 'none'))
        return f"floor-{value}"

    @api.depends()
    def _compute_dashboard_html(self):
        Patient = self.env['iot.patient']
        Alert = self.env['iot.alert']

        try:
            patient_action_id = self.env.ref('iot_patient_monitoring.action_iot_patient').id
        except Exception:
            patient_action_id = False
        try:
            alert_action_id = self.env.ref('iot_patient_monitoring.action_iot_alert').id
        except Exception:
            alert_action_id = False

        

        patient_action_link = f"/web#action={patient_action_id}" if patient_action_id else "#"
        alert_action_link = f"/web#action={alert_action_id}" if alert_action_id else "#"

        patients = Patient.search([], order='floor asc, room asc, id desc')
        warning_patients = Patient.search([('status', '=', 'warning')], order='write_date desc, id desc', limit=4)
        latest_alerts = Alert.search([], order='alert_date desc, id desc', limit=5)

        total_patients = len(patients)
        stable_count = Patient.search_count([('status', '=', 'stable')])
        warning_count = Patient.search_count([('status', '=', 'warning')])

        def safe(value):
            return html.escape(str(value or ""))

        def fmt(value, suffix=""):
            if value in (None, False, ""):
                return "—"
            if isinstance(value, float):
                return f"{value:.1f}{suffix}"
            return f"{value}{suffix}"

        def status_badge(status):
            if status == 'warning':
                return '<span class="miot-badge warning">Warning</span>'
            return '<span class="miot-badge stable">Stable</span>'

        def empty_state(text):
            return f'<div class="empty-state">{safe(text)}</div>'

        floors = []
        for p in patients:
            if p.floor and p.floor not in floors:
                floors.append(p.floor)
        floors = sorted(floors)

        filter_inputs = '<input type="radio" id="floor-all" name="floor-filter" checked><label for="floor-all">Tous les étages</label>'
        floor_css = ''
        active_css = ''
        for floor in floors:
            cls = self._floor_class(floor)
            filter_inputs += f'<input type="radio" id="{cls}" name="floor-filter"><label for="{cls}">Étage {safe(floor)}</label>'
            floor_css += f"#{cls}:checked ~ .patient-table-wrap tbody tr:not(.{cls}) {{ display:none; }}\n"
            active_css += f'#{cls}:checked ~ label[for="{cls}"] {{ background:#312e81; color:#fff; border-color:#312e81; }}\n'

        patient_rows = ""
        for p in patients:
            floor_label = f"Étage {p.floor}" if p.floor else "—"
            detail_link = f"/web#id={p.id}&model=iot.patient&view_type=form"
            patient_rows += f"""
                <tr class="{self._floor_class(p.floor)}">
                    <td><b>{safe(p.name)}</b><div class="muted">{safe(p.patient_code or ('P-' + str(p.id).zfill(5)))}</div></td>
                    <td>{safe(p.age)} ans</td>
                    <td>{safe(floor_label)}</td>
                    <td>{safe(p.room or '—')}</td>
                    <td>{safe(p.doctor_id.name or p.doctor_email or '—')}</td>
                    <td><a class="row-btn" href="{detail_link}">Détails</a></td>
                </tr>
            """

        warning_cards = ""
        for p in warning_patients:
            reasons = p._get_warning_reasons()
            reason_html = ''.join(f'<span>{safe(r)}</span>' for r in reasons) or '<span>Warning</span>'
            warning_cards += f"""
                <div class="warning-card">
                    <div class="warning-top"><b>{safe(p.name)}</b>{status_badge(p.status)}</div>
                    <div class="muted">Chambre {safe(p.room or '—')} · Étage {safe(p.floor or '—')}</div>
                    <div class="reason-list">{reason_html}</div>
                    <div class="vital-mini">
                        <span>💧 SpO₂ : <b>{fmt(p.spo2, ' %')}</b></span>
                        <span>❤️ BPM : <b>{fmt(p.heart_rate, ' BPM')}</b></span>
                        <span>🌡️ Température : <b>{fmt(p.temperature, ' °C')}</b></span>
                    </div>
                    <div class="measure-date">🕒 Mesuré le : <b>{self._format_datetime(p.last_measure_date or p.write_date)}</b></div>
                    <a class="small-btn" href="/web#id={p.id}&model=iot.patient&view_type=form">Détails</a>
                </div>
            """

        alert_cards = ""
        for a in latest_alerts:
            email_status = 'Envoyé' if a.email_sent else 'Non envoyé'
            email_class = 'sent' if a.email_sent else 'pending'
            alert_cards += f"""
                <div class="alert-card">
                    <div>
                        <b>{safe(a.patient_id.name)}</b>
                        <div class="muted">{safe(a.alert_type)} · {self._human_time(a.alert_date)}</div>
                    </div>
                    <span class="email-pill {email_class}">{email_status}</span>
                </div>
            """

        for rec in self:
            rec.dashboard_html = f"""
            <style>
                .miot-page {{ padding:18px; background:#f5f7fb; color:#07153a; font-family:Inter,Arial,sans-serif; }}
                .miot-hero {{ background:linear-gradient(135deg,#667eea,#8b5cf6); color:#fff; border-radius:0 0 24px 24px; padding:26px 30px; margin:-18px -18px 20px -18px; display:flex; justify-content:space-between; gap:18px; align-items:center; box-shadow:0 10px 25px rgba(102,126,234,.25); }}
                .miot-title {{ margin:0; font-size:28px; font-weight:900; }}
                .miot-subtitle {{ margin-top:7px; color:rgba(255,255,255,.88); font-weight:700; }}
                .header-actions {{ display:flex; gap:10px; flex-wrap:wrap; justify-content:flex-end; }}
                .header-btn {{ color:#fff; text-decoration:none; padding:11px 15px; border-radius:16px; font-weight:800; background:rgba(255,255,255,.18); border:1px solid rgba(255,255,255,.25); }}
                .kpi-grid {{ display:grid; grid-template-columns:repeat(3,minmax(150px,1fr)); gap:14px; margin-bottom:18px; }}
                .kpi-card {{ background:#fff; border:1px solid #e6edf8; border-radius:22px; padding:18px; box-shadow:0 8px 22px rgba(38,58,105,.06); }}
                .kpi-label {{ font-size:12px; font-weight:900; color:#64708a; text-transform:uppercase; letter-spacing:.03em; }}
                .kpi-value {{ font-size:34px; font-weight:950; margin-top:8px; }}
                .section-card {{ background:#fff; border:1px solid #e6edf8; border-radius:22px; padding:18px; margin-bottom:18px; box-shadow:0 8px 22px rgba(38,58,105,.06); }}
                .section-title {{ margin:0 0 14px 0; font-size:20px; font-weight:950; color:#111827; }}
                .main-grid {{ display:grid; grid-template-columns:1.2fr .8fr; gap:18px; }}
                .warning-grid {{ display:grid; grid-template-columns:repeat(2,minmax(200px,1fr)); gap:12px; }}
                .warning-card {{ border:1px solid #fde68a; background:#fffbeb; border-radius:18px; padding:14px; }}
                .warning-top {{ display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:6px; }}
                .reason-list {{ display:flex; flex-wrap:wrap; gap:6px; margin:10px 0; }}
                .reason-list span {{ background:#fff7ed; color:#9a3412; border:1px solid #fed7aa; border-radius:999px; padding:5px 9px; font-size:12px; font-weight:800; }}
                .vital-mini {{ display:grid; grid-template-columns:1fr; gap:6px; margin:10px 0 12px 0; color:#334155; font-size:13px; }}
                .vital-mini span {{ background:#fff; border:1px solid #fde68a; border-radius:12px; padding:7px 9px; }}
                .measure-date {{ margin:8px 0 12px 0; color:#475569; font-size:13px; font-weight:700; }}
                .miot-badge {{ display:inline-flex; align-items:center; justify-content:center; padding:6px 10px; border-radius:999px; font-size:12px; font-weight:900; }}
                .miot-badge.stable {{ background:#dcfce7; color:#166534; }}
                .miot-badge.warning {{ background:#fef3c7; color:#92400e; }}
                .alert-card {{ display:flex; justify-content:space-between; gap:12px; align-items:center; padding:12px 0; border-bottom:1px solid #edf2f7; }}
                .alert-card:last-child {{ border-bottom:none; }}
                .email-pill {{ border-radius:999px; padding:5px 9px; font-size:12px; font-weight:900; white-space:nowrap; }}
                .email-pill.sent {{ background:#dcfce7; color:#166534; }}
                .email-pill.pending {{ background:#fee2e2; color:#991b1b; }}
                .muted {{ color:#64748b; font-size:13px; }}
                .floor-filter {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:14px; }}
                .floor-filter input {{ display:none; }}
                .floor-filter label {{ cursor:pointer; background:#f1f5f9; border:1px solid #e2e8f0; border-radius:999px; padding:8px 13px; font-weight:900; color:#475569; }}
                #floor-all:checked ~ label[for="floor-all"] {{ background:#312e81; color:#fff; border-color:#312e81; }}
                {floor_css}
                {active_css}
                .patient-table-wrap {{ overflow:auto; width:100%; }}
                .patient-table {{ width:100%; border-collapse:collapse; min-width:780px; }}
                .patient-table th {{ text-align:left; background:#f8fafc; color:#475569; font-size:12px; text-transform:uppercase; padding:12px; }}
                .patient-table td {{ border-top:1px solid #edf2f7; padding:12px; vertical-align:middle; }}
                .row-btn,.small-btn {{ display:inline-flex; text-decoration:none; background:#eef2ff; color:#3730a3; border:1px solid #c7d2fe; padding:7px 11px; border-radius:12px; font-weight:900; }}
                .empty-state {{ color:#64748b; padding:18px; border:1px dashed #cbd5e1; border-radius:16px; background:#f8fafc; text-align:center; }}
                @media(max-width:1100px) {{ .kpi-grid,.main-grid {{ grid-template-columns:1fr; }} .miot-hero {{ flex-direction:column; align-items:flex-start; }} }}
            </style>

            <div class="miot-page">
                <div class="miot-hero">
                    <div>
                        <h1 class="miot-title">Medical CRM</h1>
                        <div class="miot-subtitle">Plateforme intelligente de surveillance médicale</div>
                    </div>
                    <div class="header-actions">
                        <a class="header-btn" href="{patient_action_link}">Patients</a>
                        <a class="header-btn" href="{alert_action_link}">Alertes</a>
                    </div>
                </div>

                <div class="kpi-grid">
                    <div class="kpi-card"><div class="kpi-label">Total Patients</div><div class="kpi-value" style="color:#312e81;">{total_patients}</div></div>
                    <div class="kpi-card"><div class="kpi-label">Stable</div><div class="kpi-value" style="color:#16a34a;">{stable_count}</div></div>
                    <div class="kpi-card"><div class="kpi-label">Warning</div><div class="kpi-value" style="color:#d97706;">{warning_count}</div></div>
                </div>

                <div class="main-grid">
                    <div class="section-card"><h2 class="section-title">Patients en Warning</h2><div class="warning-grid">{warning_cards if warning_cards else empty_state('Aucun patient en Warning actuellement.')}</div></div>
                    <div class="section-card"><h2 class="section-title">Dernières alertes</h2>{alert_cards if alert_cards else empty_state('Aucune alerte récente.')}</div>
                </div>

                <div class="section-card">
                    <h2 class="section-title">Liste des patients</h2>
                    <div class="floor-filter">
                        {filter_inputs}
                        <div class="patient-table-wrap">
                            <table class="patient-table">
                                <thead><tr><th>Patient</th><th>Âge</th><th>Étage</th><th>Chambre</th><th>Médecin</th><th>Détails</th></tr></thead>
                                <tbody>{patient_rows if patient_rows else '<tr><td colspan="6">Aucun patient.</td></tr>'}</tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
            <iframe style="display:none;width:0;height:0;border:0;"
                    srcdoc="&lt;script&gt;setTimeout(function(){{parent.location.reload();}}, 10000);&lt;/script&gt;"></iframe>
            """
