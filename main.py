import numpy as np
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(
    page_title="ED Nurse Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    :root {
        --critical-bg: #dc3545;
        --high-bg: #fd7e14;
        --watch-bg: #0d6efd;
        --stable-bg: #198754;
        --text-dark: #1a1a1a;
        --border-color: #dee2e6;
    }

    .main {
        max-width: 1600px;
    }

    h1, h2, h3 {
        font-weight: 700;
        letter-spacing: -0.5px;
    }

    [data-testid="metric-container"] {
        background-color: #f8f9fa;
        border: 2px solid var(--border-color);
        border-radius: 12px;
        padding: 20px !important;
    }

    [data-testid="metric-container"] > div:first-child {
        font-size: 14px !important;
        font-weight: 600 !important;
        color: #666 !important;
    }

    [data-testid="metric-container"] > div:nth-child(2) {
        font-size: 28px !important;
        font-weight: 700 !important;
        color: var(--text-dark) !important;
    }

    .status-badge {
        display: inline-block;
        padding: 6px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 13px;
    }

    .status-critical {
        background-color: var(--critical-bg);
        color: white;
    }

    .status-high {
        background-color: var(--high-bg);
        color: white;
    }

    .status-watch {
        background-color: var(--watch-bg);
        color: white;
    }

    .status-stable {
        background-color: var(--stable-bg);
        color: white;
    }

    [data-testid="dataframe"] {
        font-size: 14px !important;
    }

    .stDataFrame thead {
        font-weight: 700 !important;
        background-color: #f8f9fa !important;
    }

    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        padding: 10px 20px !important;
        border: none;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }

    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
    }

    hr {
        margin: 24px 0 !important;
        border: none;
        border-top: 2px solid var(--border-color);
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [role="tab"] {
        padding: 12px 24px !important;
        font-weight: 600;
        border-radius: 8px 8px 0 0;
    }

    .stInfo, .stSuccess, .stWarning, .stError {
        border-radius: 8px;
        border-left: 6px solid;
        padding: 16px !important;
    }
</style>
""", unsafe_allow_html=True)

def now_ts():
    return pd.Timestamp.now(tz="UTC")

def clamp(x, a, b):
    return max(a, min(b, x))

def get_patient_age_and_dob(age):
    today = pd.Timestamp.now()
    dob = today - pd.DateOffset(years=age)
    return dob.strftime("%Y-%m-%d")

def get_waiting_time(waiting_since):
    now = pd.Timestamp.now(tz="UTC")
    start = pd.to_datetime(waiting_since)
    delta = now - start
    minutes = max(0, int(delta.total_seconds() // 60))
    hours = minutes // 60
    mins = minutes % 60
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"

def format_patient_name(name, age):
    last_names = [
        "Smith", "Johnson", "Brown", "Davis", "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson",
        "White", "Harris", "Martin", "Thompson", "Garcia", "Martinez", "Robinson", "Clark", "Rodriguez", "Lewis",
        "Lee", "Walker", "Hall", "Allen", "Young", "King", "Wright", "Lopez", "Hill", "Scott",
        "Green", "Adams", "Nelson", "Carter", "Mitchell", "Roberts", "Phillips", "Campbell", "Parker", "Evans",
        "Edwards", "Collins", "Reeves", "Stewart", "Morris", "Rogers", "Morgan", "Peterson", "Cooper", "Reed",
        "Bell", "Howard"
    ]
    idx = (age * 7) % len(last_names)
    return f"{name} {last_names[idx]}"

def trend_symbol(trend):
    if trend >= 2:
        return "⬆⬆"
    if trend == 1:
        return "⬆"
    if trend == 0:
        return "→"
    if trend == -1:
        return "⬇"
    return "⬇⬇"

def risk_color(score):
    if score >= 7:
        return "#dc3545"
    if score >= 4:
        return "#fd7e14"
    if score >= 2:
        return "#0d6efd"
    return "#198754"

def show_patient_popup(patient_row):
    full_name = format_patient_name(patient_row["Name"], int(patient_row["Age"]))
    dob = get_patient_age_and_dob(int(patient_row["Age"]))
    waiting_time = get_waiting_time(patient_row["WaitingSince"])

    with st.container():
        status = patient_row["Status"]
        if "Critical" in status:
            badge_class = "status-critical"
        elif "High" in status:
            badge_class = "status-high"
        elif "Watch" in status:
            badge_class = "status-watch"
        else:
            badge_class = "status-stable"

        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; padding-bottom:16px; border-bottom:2px solid #e9ecef;">
                <div>
                    <p style="font-size:22px; font-weight:700; margin:0;">{patient_row['StatusIcon']} {full_name}</p>
                    <p style="font-size:14px; color:#666; font-weight:500; margin:4px 0 0 0;">ID: {patient_row['PatientID']}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div style="text-align:right;">
                <span class="status-badge {badge_class}">{patient_row['Status']}</span>
                <div style="margin-top:8px; font-size:13px; color:#666; font-weight:500;">
                    Risk: {int(patient_row['RiskScore'])} {trend_symbol(int(patient_row['Trend']))}
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("#### 👤 Patient Demographics")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"""
            <div style="padding:16px; background-color:#f8f9fa; border-radius:8px;">
                <div style="font-size:12px; font-weight:600; color:#666; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;">Date of Birth</div>
                <div style="font-size:16px; font-weight:600; color:#1a1a1a;">{dob}</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div style="padding:16px; background-color:#f8f9fa; border-radius:8px;">
                <div style="font-size:12px; font-weight:600; color:#666; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;">Age</div>
                <div style="font-size:16px; font-weight:600; color:#1a1a1a;">{int(patient_row['Age'])} years</div>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div style="padding:16px; background-color:#f8f9fa; border-radius:8px;">
                <div style="font-size:12px; font-weight:600; color:#666; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;">Waiting Time</div>
                <div style="font-size:16px; font-weight:600; color:#1a1a1a;">{waiting_time}</div>
            </div>
            """, unsafe_allow_html=True)
        with c4:
            st.markdown(f"""
            <div style="padding:16px; background-color:#f8f9fa; border-radius:8px;">
                <div style="font-size:12px; font-weight:600; color:#666; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;">Last Update</div>
                <div style="font-size:16px; font-weight:600; color:#1a1a1a;">{pd.to_datetime(patient_row['LastUpdate']).strftime('%H:%M:%S')}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("#### 🏥 Chief Complaint & Location")
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            st.markdown(f"""
            <div style="padding:16px; background-color:#f8f9fa; border-radius:8px;">
                <div style="font-size:12px; font-weight:600; color:#666; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;">Chief Complaint</div>
                <div style="font-size:16px; font-weight:600; color:#1a1a1a;">{patient_row['Complaint']}</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div style="padding:16px; background-color:#f8f9fa; border-radius:8px;">
                <div style="font-size:12px; font-weight:600; color:#666; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;">Location</div>
                <div style="font-size:16px; font-weight:600; color:#1a1a1a;">{patient_row['Location']}</div>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div style="padding:16px; background-color:#f8f9fa; border-radius:8px;">
                <div style="font-size:12px; font-weight:600; color:#666; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;">Triage Level</div>
                <div style="font-size:16px; font-weight:600; color:#1a1a1a;">{patient_row['Triage']}</div>
            </div>
            """, unsafe_allow_html=True)

        avpu_status = patient_row["AVPU"]
        avpu_desc = {"A": "Alert", "V": "Verbal", "P": "Pain", "U": "Unresponsive"}[avpu_status]
        avpu_color = "#198754" if avpu_status == "A" else "#fd7e14" if avpu_status == "V" else "#dc3545"

        st.markdown("#### 🧠 Consciousness Level")
        st.markdown(f"""
        <div style="padding:16px; background-color:#f8f9fa; border-radius:8px; border-left:4px solid {avpu_color};">
            <div style="font-size:12px; color:#666; text-transform:uppercase; font-weight:600; margin-bottom:6px;">AVPU Score</div>
            <div style="font-size:18px; font-weight:700; color:{avpu_color};">{avpu_status} - {avpu_desc}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("#### 🫀 Vital Signs")
        vitals = [
            ("HR", f"{int(patient_row['HR'])} bpm", 60, 100),
            ("RR", f"{int(patient_row['RR'])} br/min", 12, 20),
            ("SpO2", f"{int(patient_row['SpO2'])} %", 95, 100),
            ("SBP", f"{int(patient_row['SBP'])} mmHg", 90, 120),
            ("Temp", f"{float(patient_row['Temp']):.1f} °C", 36.5, 37.5),
            ("AVPU", avpu_desc, None, None)
        ]

        cols_top = st.columns(3)
        cols_bottom = st.columns(3)
        all_cols = cols_top + cols_bottom

        for i, (label, value, low, high) in enumerate(vitals):
            abnormal = False
            if low is not None and high is not None:
                numeric = float(value.split()[0])
                abnormal = numeric < low or numeric > high
            border = "#dc3545" if abnormal else "#e9ecef"
            bg = "rgba(220, 53, 69, 0.05)" if abnormal else "white"
            color = "#dc3545" if abnormal else "#1a1a1a"
            range_text = f"{low}-{high}" if low is not None else ""
            with all_cols[i]:
                st.markdown(f"""
                <div style="padding:16px; background-color:{bg}; border:2px solid {border}; border-radius:8px; text-align:center;">
                    <div style="font-size:12px; font-weight:600; color:#666; text-transform:uppercase; margin-bottom:8px;">{label}</div>
                    <div style="font-size:20px; font-weight:700; color:{color}; margin-bottom:4px;">{value}</div>
                    <div style="font-size:11px; color:#999;">{range_text}</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("#### ⚠️ Risk Assessment")
        risk_score = int(patient_row["RiskScore"])
        trend = int(patient_row["Trend"])

        def get_risk_text(score):
            if score <= 0:
                return "Stable - No significant concerns"
            if score == 1:
                return "Low Risk - Monitor"
            if score in [2, 3]:
                return "Watch - Close monitoring"
            if score in [4, 5, 6]:
                return "High - Urgent attention"
            if score >= 7:
                return "Critical - Emergency intervention"
            return "Unknown"

        trend_text = {
            -2: "🟢 Significant Improvement",
            -1: "🟢 Improving",
            0: "🟡 Stable",
            1: "🟠 Deteriorating",
            2: "🔴 Rapid Deterioration"
        }

        rc1, rc2 = st.columns(2)
        with rc1:
            color = risk_color(risk_score)
            st.markdown(f"""
            <div style="padding:16px; background-color:#f8f9fa; border-radius:8px; border-left:4px solid {color};">
                <div style="font-size:12px; color:#666; text-transform:uppercase; font-weight:600; margin-bottom:6px;">Risk Score</div>
                <div style="font-size:28px; font-weight:700; color:{color}; margin-bottom:8px;">{risk_score}</div>
                <div style="font-size:14px; color:#1a1a1a;">{get_risk_text(risk_score)}</div>
            </div>
            """, unsafe_allow_html=True)
        with rc2:
            trend_color = "#198754" if trend <= -1 else "#0d6efd" if trend == 0 else "#fd7e14" if trend == 1 else "#dc3545"
            st.markdown(f"""
            <div style="padding:16px; background-color:#f8f9fa; border-radius:8px; border-left:4px solid {trend_color};">
                <div style="font-size:12px; color:#666; text-transform:uppercase; font-weight:600; margin-bottom:6px;">Trend</div>
                <div style="font-size:20px; font-weight:700; color:{trend_color}; margin-bottom:8px;">{trend_text.get(trend, 'Unknown')}</div>
                <div style="font-size:14px; color:#1a1a1a;">Score change: {'+' if trend > 0 else ''}{trend} points</div>
            </div>
            """, unsafe_allow_html=True)

def compute_risk(row, prev_row=None):
    hr = row["HR"]
    spo2 = row["SpO2"]
    rr = row["RR"]
    sbp = row["SBP"]
    temp = row["Temp"]
    avpu = row["AVPU"]

    score = 0

    if rr <= 8 or rr >= 25:
        score += 3
    elif rr >= 21:
        score += 2
    elif rr < 12:
        score += 1

    if spo2 <= 91:
        score += 3
    elif spo2 <= 93:
        score += 2
    elif spo2 <= 95:
        score += 1

    if temp <= 35.0 or temp >= 39.1:
        score += 2
    elif temp >= 38.1:
        score += 1

    if sbp <= 90:
        score += 3
    elif sbp <= 100:
        score += 2
    elif sbp <= 110:
        score += 1

    if hr <= 40 or hr >= 131:
        score += 3
    elif hr >= 111:
        score += 2
    elif hr >= 91:
        score += 1
    elif hr <= 50:
        score += 1

    if avpu != "A":
        score += 3

    trend = 0
    if prev_row is not None:
        prev_score = int(prev_row.get("RiskScore", 0))
        delta = score - prev_score
        if delta >= 2:
            trend = 2
        elif delta == 1:
            trend = 1
        elif delta <= -2:
            trend = -2
        elif delta == -1:
            trend = -1

    return int(clamp(score, 0, 10)), trend

def status_from_score(score):
    if score >= 7:
        return "Critical", "🔴"
    if score >= 4:
        return "High", "🟠"
    if score >= 2:
        return "Watch", "🟡"
    return "Stable", "🟢"

def assign_statuses(df):
    scored = df.copy()

    scored = scored.sort_values(
        ["RiskScore", "Trend", "SpO2", "WaitingSince"],
        ascending=[False, False, True, True]
    ).reset_index()

    total = len(scored)

    critical_candidates = scored["RiskScore"] >= 7
    high_candidates = scored["RiskScore"] >= 4
    watch_candidates = scored["RiskScore"] >= 2

    critical_n = min(3, int(critical_candidates.sum()))

    remaining_idx = scored.index[critical_n:]
    high_n = min(15, int((scored.loc[remaining_idx, "RiskScore"] >= 4).sum()))

    remaining_idx = scored.index[critical_n + high_n:]
    watch_n = min(15, int((scored.loc[remaining_idx, "RiskScore"] >= 2).sum()))

    statuses = []
    adjusted_scores = []

    for i in range(total):
        original_score = int(scored.loc[i, "RiskScore"])

        if i < critical_n and original_score >= 7:
            statuses.append("Critical")
            adjusted_scores.append(max(7, min(original_score, 10)))
        elif i < critical_n + high_n and original_score >= 4:
            statuses.append("High")
            adjusted_scores.append(min(original_score, 6))
        elif i < critical_n + high_n + watch_n and original_score >= 2:
            statuses.append("Watch")
            adjusted_scores.append(min(original_score, 3))
        else:
            statuses.append("Stable")
            adjusted_scores.append(min(original_score, 1))

    scored["Status"] = statuses
    scored["RiskScore"] = adjusted_scores
    scored["StatusIcon"] = scored["Status"].map({
        "Critical": "🔴",
        "High": "🟠",
        "Watch": "🟡",
        "Stable": "🟢"
    })

    scored = scored.set_index("index").sort_index()
    return scored

def make_initial_patients(n=40, seed=7):
    rng = np.random.default_rng(seed)

    first_names = [
        "Alex", "Mina", "Jordan", "Sam", "Taylor", "Chris", "Ava", "Noah", "Ivy", "Leo",
        "Zoe", "Omar", "Nina", "Eli", "Maya", "Sophie", "Marcus", "Isabella", "James", "Emma",
        "Liam", "Olivia", "Benjamin", "Amelia", "Lucas", "Harper", "Mason", "Evelyn", "Logan", "Abigail",
        "Ethan", "Charlotte", "Aiden", "Mia", "Jackson", "Aria", "Sebastian", "Scarlett", "Daniel", "Chloe",
        "Michael", "Layla", "Matthew", "Grace", "David", "Ella", "Joseph", "Hannah", "Andrew", "Lily",
        "Joshua", "Victoria", "Nathan", "Sofia", "Ryan", "Penelope", "Gabriel", "Riley", "Caleb", "Lucy"
    ]

    complaints = [
        "Chest pain", "Shortness of breath", "Abdominal pain", "Fever", "Headache",
        "Fall injury", "Dizziness", "Weakness", "Allergic reaction", "Nausea/vomiting",
        "Back pain", "Cough", "Palpitations", "Dehydration", "Migraine"
    ]

    triage = ["CTAS 2", "CTAS 3", "CTAS 4", "CTAS 5"]
    locations = ["Waiting A", "Waiting B", "Hallway", "Overflow", "Observation"]

    complaint_profiles = {
        "Chest pain": {
            "hr": (96, 14), "rr": (20, 3), "spo2": (96, 2), "sbp": (108, 18), "temp": (37.0, 0.3),
            "avpu": ["A", "V"], "avpu_p": [0.94, 0.06]
        },
        "Shortness of breath": {
            "hr": (104, 16), "rr": (24, 4), "spo2": (91, 4), "sbp": (108, 14), "temp": (37.3, 0.5),
            "avpu": ["A", "V"], "avpu_p": [0.90, 0.10]
        },
        "Abdominal pain": {
            "hr": (92, 12), "rr": (18, 3), "spo2": (97, 1), "sbp": (112, 14), "temp": (37.3, 0.6),
            "avpu": ["A"], "avpu_p": [1.0]
        },
        "Fever": {
            "hr": (102, 12), "rr": (20, 3), "spo2": (96, 2), "sbp": (108, 12), "temp": (38.4, 0.7),
            "avpu": ["A", "V"], "avpu_p": [0.95, 0.05]
        },
        "Headache": {
            "hr": (84, 10), "rr": (16, 2), "spo2": (98, 1), "sbp": (118, 14), "temp": (37.0, 0.3),
            "avpu": ["A"], "avpu_p": [1.0]
        },
        "Fall injury": {
            "hr": (90, 14), "rr": (18, 3), "spo2": (97, 2), "sbp": (114, 18), "temp": (36.9, 0.3),
            "avpu": ["A", "V"], "avpu_p": [0.92, 0.08]
        },
        "Dizziness": {
            "hr": (88, 12), "rr": (17, 2), "spo2": (97, 1), "sbp": (106, 16), "temp": (36.9, 0.3),
            "avpu": ["A"], "avpu_p": [1.0]
        },
        "Weakness": {
            "hr": (92, 12), "rr": (18, 3), "spo2": (96, 2), "sbp": (104, 14), "temp": (37.0, 0.4),
            "avpu": ["A", "V"], "avpu_p": [0.95, 0.05]
        },
        "Allergic reaction": {
            "hr": (102, 16), "rr": (22, 4), "spo2": (94, 3), "sbp": (104, 14), "temp": (36.9, 0.3),
            "avpu": ["A", "V"], "avpu_p": [0.92, 0.08]
        },
        "Nausea/vomiting": {
            "hr": (96, 14), "rr": (18, 3), "spo2": (97, 1), "sbp": (102, 14), "temp": (37.2, 0.5),
            "avpu": ["A"], "avpu_p": [1.0]
        },
        "Back pain": {
            "hr": (86, 10), "rr": (16, 2), "spo2": (98, 1), "sbp": (118, 14), "temp": (36.8, 0.3),
            "avpu": ["A"], "avpu_p": [1.0]
        },
        "Cough": {
            "hr": (92, 12), "rr": (20, 3), "spo2": (95, 3), "sbp": (112, 12), "temp": (37.8, 0.7),
            "avpu": ["A"], "avpu_p": [1.0]
        },
        "Palpitations": {
            "hr": (110, 18), "rr": (19, 3), "spo2": (97, 1), "sbp": (114, 16), "temp": (36.9, 0.3),
            "avpu": ["A"], "avpu_p": [1.0]
        },
        "Dehydration": {
            "hr": (100, 14), "rr": (19, 3), "spo2": (97, 1), "sbp": (100, 14), "temp": (37.4, 0.6),
            "avpu": ["A", "V"], "avpu_p": [0.95, 0.05]
        },
        "Migraine": {
            "hr": (86, 10), "rr": (16, 2), "spo2": (98, 1), "sbp": (116, 14), "temp": (36.9, 0.3),
            "avpu": ["A"], "avpu_p": [1.0]
        }
    }

    def sample_from_profile(profile, severity_band):
        hr_mu, hr_sd = profile["hr"]
        rr_mu, rr_sd = profile["rr"]
        spo2_mu, spo2_sd = profile["spo2"]
        sbp_mu, sbp_sd = profile["sbp"]
        temp_mu, temp_sd = profile["temp"]

        hr = rng.normal(hr_mu, hr_sd)
        rr = rng.normal(rr_mu, rr_sd)
        spo2 = rng.normal(spo2_mu, spo2_sd)
        sbp = rng.normal(sbp_mu, sbp_sd)
        temp = rng.normal(temp_mu, temp_sd)

        if severity_band == "stable":
            hr += rng.normal(-4, 4)
            rr += rng.normal(-1, 1)
            spo2 += rng.normal(1.2, 0.8)
            sbp += rng.normal(4, 6)
            temp += rng.normal(-0.2, 0.2)
        elif severity_band == "watch":
            hr += rng.normal(2, 5)
            rr += rng.normal(1, 1.5)
            spo2 += rng.normal(-0.8, 1.0)
            sbp += rng.normal(-2, 6)
            temp += rng.normal(0.1, 0.2)
        elif severity_band == "high":
            hr += rng.normal(10, 7)
            rr += rng.normal(4, 2)
            spo2 += rng.normal(-3.0, 1.5)
            sbp += rng.normal(-10, 8)
            temp += rng.normal(0.4, 0.3)
        else:
            hr += rng.normal(20, 10)
            rr += rng.normal(8, 3)
            spo2 += rng.normal(-7, 2)
            sbp += rng.normal(-22, 10)
            temp += rng.normal(0.8, 0.4)

        hr = int(round(clamp(hr, 48, 155)))
        rr = int(round(clamp(rr, 10, 36)))
        spo2 = int(round(clamp(spo2, 80, 100)))
        sbp = int(round(clamp(sbp, 75, 170)))
        temp = round(float(clamp(temp, 36.0, 40.3)), 1)

        avpu = rng.choice(profile["avpu"], p=profile["avpu_p"])

        if severity_band == "critical":
            if rng.random() < 0.55:
                avpu = rng.choice(["V", "P"], p=[0.7, 0.3])
        elif severity_band == "high":
            if rng.random() < 0.12:
                avpu = "V"
        else:
            avpu = "A" if rng.random() < 0.97 else avpu

        return hr, rr, spo2, sbp, temp, avpu

    def tune_for_complaint(complaint, severity_band, hr, rr, spo2, sbp, temp, avpu):
        if complaint == "Shortness of breath":
            rr = int(clamp(rr + rng.integers(1, 4), 12, 36))
            spo2 = int(clamp(spo2 - rng.integers(1, 4), 80, 100))
        elif complaint == "Palpitations":
            hr = int(clamp(hr + rng.integers(4, 12), 50, 155))
            spo2 = int(clamp(spo2, 92, 100))
        elif complaint == "Fever":
            temp = round(float(clamp(temp + rng.choice([0.1, 0.2, 0.3]), 36.0, 40.3)), 1)
            hr = int(clamp(hr + rng.integers(2, 8), 50, 155))
        elif complaint == "Dehydration":
            hr = int(clamp(hr + rng.integers(2, 8), 50, 155))
            sbp = int(clamp(sbp - rng.integers(2, 8), 75, 170))
        elif complaint == "Allergic reaction":
            rr = int(clamp(rr + rng.integers(1, 3), 12, 36))
            spo2 = int(clamp(spo2 - rng.integers(0, 3), 80, 100))
        elif complaint == "Chest pain":
            hr = int(clamp(hr + rng.integers(0, 8), 50, 155))
            sbp = int(clamp(sbp + rng.integers(-10, 11), 75, 170))
        elif complaint == "Nausea/vomiting":
            sbp = int(clamp(sbp - rng.integers(0, 8), 75, 170))
            hr = int(clamp(hr + rng.integers(0, 6), 50, 155))
        elif complaint == "Cough":
            temp = round(float(clamp(temp + rng.choice([0.0, 0.1, 0.2]), 36.0, 40.3)), 1)
            spo2 = int(clamp(spo2 - rng.integers(0, 2), 80, 100))

        if severity_band == "stable":
            abnormal_count = sum([
                hr < 60 or hr > 100,
                rr < 12 or rr > 20,
                spo2 < 95,
                sbp < 90 or sbp > 120,
                temp < 36.5 or temp > 37.5,
                avpu != "A"
            ])
            if abnormal_count > 2:
                hr = int(clamp(hr, 58, 104))
                rr = int(clamp(rr, 12, 22))
                spo2 = int(clamp(spo2, 94, 100))
                sbp = int(clamp(sbp, 90, 130))
                temp = round(float(clamp(temp, 36.4, 38.0)), 1)
                avpu = "A"

        if severity_band == "watch":
            hr = int(clamp(hr, 60, 118))
            rr = int(clamp(rr, 12, 24))
            spo2 = int(clamp(spo2, 91, 98))
            sbp = int(clamp(sbp, 88, 128))
            temp = round(float(clamp(temp, 36.3, 38.7)), 1)
            if avpu != "A" and rng.random() < 0.8:
                avpu = "A"

        if severity_band == "high":
            hr = int(clamp(hr, 72, 135))
            rr = int(clamp(rr, 16, 30))
            spo2 = int(clamp(spo2, 86, 96))
            sbp = int(clamp(sbp, 78, 118))
            temp = round(float(clamp(temp, 36.4, 39.4)), 1)
            if avpu == "P":
                avpu = "V"

        if severity_band == "critical":
            hr = int(clamp(hr, 85, 150))
            rr = int(clamp(rr, 20, 36))
            spo2 = int(clamp(spo2, 80, 92))
            sbp = int(clamp(sbp, 70, 102))
            temp = round(float(clamp(temp, 36.5, 40.3)), 1)

        return hr, rr, spo2, sbp, temp, avpu

    rows = []
    base_time = now_ts()

    complaint_weights = {
        "Chest pain": 0.08,
        "Shortness of breath": 0.08,
        "Abdominal pain": 0.09,
        "Fever": 0.07,
        "Headache": 0.07,
        "Fall injury": 0.07,
        "Dizziness": 0.07,
        "Weakness": 0.07,
        "Allergic reaction": 0.05,
        "Nausea/vomiting": 0.08,
        "Back pain": 0.07,
        "Cough": 0.06,
        "Palpitations": 0.05,
        "Dehydration": 0.05,
        "Migraine": 0.04
    }

    complaint_list = list(complaint_weights.keys())
    complaint_probs = list(complaint_weights.values())

    for i in range(n):
        age = int(clamp(rng.normal(49, 19), 18, 92))
        complaint = rng.choice(complaint_list, p=complaint_probs)

        if i < 3:
            severity_band = "critical"
        elif i < 18:
            severity_band = "high"
        elif i < 33:
            severity_band = "watch"
        else:
            severity_band = "stable"

        profile = complaint_profiles[complaint]
        hr, rr, spo2, sbp, temp, avpu = sample_from_profile(profile, severity_band)
        hr, rr, spo2, sbp, temp, avpu = tune_for_complaint(
            complaint, severity_band, hr, rr, spo2, sbp, temp, avpu
        )

        if severity_band == "stable":
            triage_value = rng.choice(triage, p=[0.01, 0.12, 0.47, 0.40])
        elif severity_band == "watch":
            triage_value = rng.choice(triage, p=[0.04, 0.28, 0.46, 0.22])
        elif severity_band == "high":
            triage_value = rng.choice(triage, p=[0.18, 0.46, 0.28, 0.08])
        else:
            triage_value = rng.choice(triage, p=[0.52, 0.34, 0.11, 0.03])

        waiting_minutes = int(rng.integers(15, 361))
        waiting_since = base_time - pd.Timedelta(minutes=waiting_minutes)

        rows.append({
            "PatientID": f"P{i+1:03d}",
            "Name": rng.choice(first_names),
            "Age": age,
            "Triage": triage_value,
            "Location": rng.choice(locations, p=[0.36, 0.26, 0.16, 0.12, 0.10]),
            "Complaint": complaint,
            "HR": hr,
            "RR": rr,
            "SpO2": spo2,
            "SBP": sbp,
            "Temp": temp,
            "AVPU": avpu,
            "WaitingSince": waiting_since,
            "LastUpdate": base_time
        })

    df = pd.DataFrame(rows)
    df["RiskScore"] = 0
    df["Trend"] = 0
    df["Status"] = ""
    df["StatusIcon"] = ""

    for idx in df.index:
        score, trend = compute_risk(df.loc[idx].to_dict(), None)
        df.loc[idx, "RiskScore"] = score
        df.loc[idx, "Trend"] = trend

    df = assign_statuses(df)
    return df

def simulate_next(df, rng, deterioration_bias=0.22):
    out = df.copy()
    out["LastUpdate"] = now_ts()

    complaint_effects = {
        "Shortness of breath": {"hr": (0, 3), "rr": (0, 3), "spo2": (-2, 0), "sbp": (-3, 2), "temp": (0.0, 0.1)},
        "Chest pain": {"hr": (0, 4), "rr": (0, 2), "spo2": (-1, 0), "sbp": (-4, 4), "temp": (0.0, 0.1)},
        "Palpitations": {"hr": (0, 5), "rr": (0, 2), "spo2": (-1, 1), "sbp": (-3, 3), "temp": (0.0, 0.1)},
        "Fever": {"hr": (0, 3), "rr": (0, 2), "spo2": (-1, 1), "sbp": (-2, 2), "temp": (0.0, 0.2)},
        "Dehydration": {"hr": (0, 3), "rr": (0, 2), "spo2": (-1, 1), "sbp": (-4, 1), "temp": (0.0, 0.2)},
        "Allergic reaction": {"hr": (0, 4), "rr": (0, 3), "spo2": (-2, 0), "sbp": (-3, 2), "temp": (0.0, 0.1)},
        "Nausea/vomiting": {"hr": (0, 3), "rr": (0, 2), "spo2": (-1, 1), "sbp": (-3, 1), "temp": (0.0, 0.1)},
        "Cough": {"hr": (0, 2), "rr": (0, 2), "spo2": (-2, 0), "sbp": (-2, 2), "temp": (0.0, 0.1)}
    }

    for idx in out.index:
        current_status = out.loc[idx, "Status"]
        complaint = out.loc[idx, "Complaint"]

        if current_status == "Critical":
            p_det = clamp(0.24 + deterioration_bias * 0.10, 0.18, 0.40)
            p_imp = 0.14
        elif current_status == "High":
            p_det = clamp(0.16 + deterioration_bias * 0.10, 0.08, 0.30)
            p_imp = 0.10
        elif current_status == "Watch":
            p_det = clamp(0.10 + deterioration_bias * 0.08, 0.04, 0.22)
            p_imp = 0.08
        else:
            p_det = clamp(0.04 + deterioration_bias * 0.05, 0.01, 0.12)
            p_imp = 0.06

        deteriorate = rng.random() < p_det
        improve = (not deteriorate) and (rng.random() < p_imp)

        hr = int(out.loc[idx, "HR"])
        rr = int(out.loc[idx, "RR"])
        spo2 = int(out.loc[idx, "SpO2"])
        sbp = int(out.loc[idx, "SBP"])
        temp = float(out.loc[idx, "Temp"])
        avpu = out.loc[idx, "AVPU"]

        effect = complaint_effects.get(
            complaint,
            {"hr": (0, 2), "rr": (0, 2), "spo2": (-1, 1), "sbp": (-2, 2), "temp": (0.0, 0.1)}
        )

        if deteriorate:
            hr += int(rng.integers(effect["hr"][0], effect["hr"][1] + 1))
            rr += int(rng.integers(effect["rr"][0], effect["rr"][1] + 1))
            spo2 += int(rng.integers(effect["spo2"][0], effect["spo2"][1] + 1))
            sbp += int(rng.integers(effect["sbp"][0], effect["sbp"][1] + 1))
            temp += float(rng.choice([effect["temp"][0], effect["temp"][1]]))

            if current_status == "Critical":
                hr += int(rng.integers(0, 3))
                rr += int(rng.integers(0, 2))
                spo2 -= int(rng.integers(0, 2))
                sbp -= int(rng.integers(0, 3))
            elif current_status == "High":
                hr += int(rng.integers(0, 2))
                rr += int(rng.integers(0, 2))
                spo2 -= int(rng.integers(0, 2))
                sbp -= int(rng.integers(0, 2))

            if current_status in ["Critical", "High"] and avpu == "A" and rng.random() < 0.04:
                avpu = rng.choice(["V", "P"], p=[0.8, 0.2])

        elif improve:
            hr -= int(rng.integers(0, 4))
            rr -= int(rng.integers(0, 3))
            spo2 += int(rng.integers(0, 3))
            sbp += int(rng.integers(0, 4))
            temp -= float(rng.choice([0.0, 0.1, 0.2]))
            if avpu in ["V", "P"] and rng.random() < 0.25:
                avpu = "A"
        else:
            hr += int(rng.integers(-2, 3))
            rr += int(rng.integers(-1, 2))
            spo2 += int(rng.integers(-1, 2))
            sbp += int(rng.integers(-3, 4))
            temp += float(rng.choice([-0.1, 0.0, 0.1], p=[0.20, 0.60, 0.20]))

        if complaint == "Palpitations":
            spo2 = int(clamp(spo2, 93, 100))
        if complaint in ["Headache", "Migraine", "Back pain"] and current_status != "Critical":
            spo2 = int(clamp(spo2, 95, 100))
            rr = int(clamp(rr, 12, 22))
        if complaint == "Fever":
            temp = round(float(clamp(temp, 37.0 if current_status != "Stable" else 36.6, 40.3)), 1)

        out.loc[idx, "HR"] = int(clamp(hr, 48, 155))
        out.loc[idx, "RR"] = int(clamp(rr, 10, 36))
        out.loc[idx, "SpO2"] = int(clamp(spo2, 80, 100))
        out.loc[idx, "SBP"] = int(clamp(sbp, 70, 170))
        out.loc[idx, "Temp"] = round(float(clamp(temp, 36.0, 40.3)), 1)
        out.loc[idx, "AVPU"] = avpu

    return out

def ensure_state():
    if "rng" not in st.session_state:
        st.session_state.rng = np.random.default_rng(13)
    if "patients" not in st.session_state:
        st.session_state.patients = make_initial_patients(n=40, seed=7)
    if "prev_patients" not in st.session_state:
        st.session_state.prev_patients = st.session_state.patients.copy()
    if "alerts" not in st.session_state:
        st.session_state.alerts = []
    if "ack" not in st.session_state:
        st.session_state.ack = set()
    if "selected_patient" not in st.session_state:
        st.session_state.selected_patient = None

def update_and_score(deterioration_bias):
    prev = st.session_state.patients.copy()
    nxt = simulate_next(prev, st.session_state.rng, deterioration_bias=deterioration_bias)

    scored = nxt.copy()
    for idx in scored.index:
        row = scored.loc[idx].to_dict()
        prev_row = prev.loc[idx].to_dict()
        score, trend = compute_risk(row, prev_row=prev_row)
        scored.loc[idx, "RiskScore"] = score
        scored.loc[idx, "Trend"] = trend

    scored = assign_statuses(scored)

    new_alerts = []
    for idx in scored.index:
        pid = scored.loc[idx, "PatientID"]
        score = int(scored.loc[idx, "RiskScore"])
        trend = int(scored.loc[idx, "Trend"])
        status = scored.loc[idx, "Status"]
        if pid in st.session_state.ack:
            continue
        if status == "Critical":
            new_alerts.append((pid, status, score, trend, "Critical risk score"))
        elif trend >= 2:
            new_alerts.append((pid, status, score, trend, "Rapid deterioration"))

    ts = now_ts()
    for pid, status, score, trend, reason in new_alerts:
        st.session_state.alerts.insert(0, {
            "Time": ts.isoformat(),
            "PatientID": pid,
            "Status": status,
            "RiskScore": score,
            "Trend": trend,
            "Reason": reason
        })

    st.session_state.prev_patients = prev
    st.session_state.patients = scored

def build_patient_table(df):
    table = df.copy()
    table["TrendDisplay"] = table["Trend"].apply(lambda x: f"{trend_symbol(int(x))} ({int(x)})")
    table["StatusDisplay"] = table.apply(lambda r: f"{r['StatusIcon']} {r['Status']}", axis=1)
    table["WaitingTime"] = table["WaitingSince"].apply(get_waiting_time)
    table["TempDisplay"] = table["Temp"].apply(lambda x: f"{float(x):.1f}")
    table["HRDisplay"] = table["HR"].apply(lambda x: f"{int(x)}")
    table["RRDisplay"] = table["RR"].apply(lambda x: f"{int(x)}")
    table["SBPDisplay"] = table["SBP"].apply(lambda x: f"{int(x)}")
    table["SpO2Display"] = table["SpO2"].apply(lambda x: f"{int(x)}%")

    status_priority = {
        "Critical": 0,
        "High": 1,
        "Watch": 2,
        "Stable": 3
    }

    table["StatusPriority"] = table["Status"].map(status_priority)

    table = table.sort_values(
        ["StatusPriority", "RiskScore", "WaitingSince", "SpO2"],
        ascending=[True, False, True, True]
    )

    return table[[
        "PatientID", "Name", "Age", "Triage", "Location", "StatusDisplay",
        "RiskScore", "TrendDisplay", "SpO2Display", "RRDisplay", "HRDisplay", "SBPDisplay",
        "TempDisplay", "AVPU", "Complaint", "WaitingTime"
    ]].rename(columns={
        "StatusDisplay": "Status",
        "TrendDisplay": "Trend",
        "SpO2Display": "SpO2",
        "RRDisplay": "RR",
        "HRDisplay": "HR",
        "SBPDisplay": "SBP",
        "TempDisplay": "Temp"
    })

def style_patient_table(df):
    def row_style(row):
        status = str(row["Status"])

        if "Critical" in status:
            return ["background-color: rgba(220, 53, 69, 0.18); font-weight: 600;"] * len(row)
        if "High" in status:
            return ["background-color: rgba(255, 193, 7, 0.14); font-weight: 500;"] * len(row)
        if "Watch" in status:
            return ["background-color: rgba(13, 110, 253, 0.08);"] * len(row)
        return [""] * len(row)

    def col_style(col):
        styles = []
        for val in col:
            text = str(val)

            if col.name == "RiskScore":
                score = int(val)
                if score >= 7:
                    styles.append("font-weight: 900; font-size: 20px; color: white; background-color: #dc3545; text-align: center;")
                elif score >= 4:
                    styles.append("font-weight: 900; font-size: 18px; color: white; background-color: #fd7e14; text-align: center;")
                elif score >= 2:
                    styles.append("font-weight: 800; font-size: 17px; color: white; background-color: #0d6efd; text-align: center;")
                else:
                    styles.append("font-weight: 800; font-size: 16px; color: white; background-color: #198754; text-align: center;")
                continue

            if col.name == "SpO2":
                value = float(text.replace("%", ""))
                if value < 95:
                    styles.append("color: #dc3545; font-weight: 700;")
                else:
                    styles.append("")
                continue

            if col.name == "RR":
                value = float(text)
                if value < 12 or value > 20:
                    styles.append("color: #dc3545; font-weight: 700;")
                else:
                    styles.append("")
                continue

            if col.name == "HR":
                value = float(text)
                if value < 60 or value > 100:
                    styles.append("color: #dc3545; font-weight: 700;")
                else:
                    styles.append("")
                continue

            if col.name == "SBP":
                value = float(text)
                if value < 90 or value > 120:
                    styles.append("color: #dc3545; font-weight: 700;")
                else:
                    styles.append("")
                continue

            if col.name == "Temp":
                value = float(text)
                if value < 36.5 or value > 37.5:
                    styles.append("color: #dc3545; font-weight: 700;")
                else:
                    styles.append("")
                continue

            if col.name == "AVPU":
                if text != "A":
                    styles.append("color: #dc3545; font-weight: 700;")
                else:
                    styles.append("")
                continue

            styles.append("")

        return styles

    return df.style.apply(row_style, axis=1).apply(col_style, axis=0)

ensure_state()

if "reset_filters" not in st.session_state:
    st.session_state.reset_filters = False

if st.session_state.reset_filters:
    st.session_state.filter_q = ""
    st.session_state.filter_statuses = ["Critical", "High", "Watch", "Stable"]
    st.session_state.filter_triage = ["CTAS 2", "CTAS 3", "CTAS 4", "CTAS 5"]
    st.session_state.filter_locations = sorted(st.session_state.patients["Location"].unique().tolist())
    st.session_state.reset_filters = False

with st.sidebar:
    st.markdown("### ⚙️ Dashboard Controls")
    refresh_sec = st.slider("Auto-refresh (sec)", 3, 20, 6, 1, key="refresh_sec")

    st.divider()

    st.markdown("### 🔍 Filters & Search")

    all_statuses = ["Critical", "High", "Watch", "Stable"]
    all_triage = ["CTAS 2", "CTAS 3", "CTAS 4", "CTAS 5"]
    all_locations = sorted(st.session_state.patients["Location"].unique().tolist())

    q = st.text_input(
        "Search by ID / name / complaint",
        placeholder="Type here...",
        label_visibility="collapsed",
        key="filter_q"
    )

    st.markdown("**Status**")
    statuses = st.multiselect(
        "Select statuses",
        all_statuses,
        default=all_statuses,
        label_visibility="collapsed",
        key="filter_statuses"
    )

    st.markdown("**Triage Level**")
    triage_filter = st.multiselect(
        "Select triage",
        all_triage,
        default=all_triage,
        label_visibility="collapsed",
        key="filter_triage"
    )

    st.markdown("**Location**")
    location_filter = st.multiselect(
        "Select locations",
        all_locations,
        default=all_locations,
        label_visibility="collapsed",
        key="filter_locations"
    )

    if st.button("Reset Filters", use_container_width=True):
        st.session_state.reset_filters = True
        st.rerun()

    st.divider()

    st.markdown("### 📋 Alert Rules")
    st.markdown("""
    - **🔴 Critical**: RiskScore ≥ 7
    - **🟠 High**: RiskScore ≥ 4
    - **🟡 Watch**: RiskScore ≥ 2
    - **🟢 Stable**: RiskScore < 2

    Initial waiting time is randomized from 15 minutes to 6 hours
    """)

deterioration_bias = 0.22

update_and_score(deterioration_bias)

df = st.session_state.patients.copy()
df = df[df["Status"].isin(statuses)]
df = df[df["Triage"].isin(triage_filter)]
df = df[df["Location"].isin(location_filter)]

if q.strip():
    s = q.strip().lower()
    df = df[
        df["PatientID"].str.lower().str.contains(s)
        | df["Name"].str.lower().str.contains(s)
        | df["Complaint"].str.lower().str.contains(s)
    ]

status_priority = {
    "Critical": 0,
    "High": 1,
    "Watch": 2,
    "Stable": 3
}

df["StatusPriority"] = df["Status"].map(status_priority)

df = df.sort_values(
    ["StatusPriority", "RiskScore", "WaitingSince", "SpO2"],
    ascending=[True, False, True, True]
)
df = df.drop(columns=["StatusPriority"])

counts = st.session_state.patients["Status"].value_counts().to_dict()
crit = int(counts.get("Critical", 0))
high = int(counts.get("High", 0))
watch = int(counts.get("Watch", 0))
stable = int(counts.get("Stable", 0))

alerts_df = pd.DataFrame(st.session_state.alerts[:50])
if not alerts_df.empty:
    alerts_df = alerts_df[~alerts_df["PatientID"].isin(list(st.session_state.ack))]
last_updated = pd.to_datetime(st.session_state.patients["LastUpdate"]).max().strftime("%H:%M:%S")

st.markdown(f"""
<div style="background-color:#f8f9fa; border:2px solid #dee2e6; border-radius:10px; padding:12px 16px; margin-bottom:16px;">
    <span style="font-size:13px; font-weight:600; color:#666; text-transform:uppercase; letter-spacing:0.4px;">Last Updated</span><br/>
    <span style="font-size:22px; font-weight:700; color:#1a1a1a;">{last_updated}</span>
</div>
""", unsafe_allow_html=True)

st.markdown("## Patient Status Overview")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div style="background-color: rgba(220, 53, 69, 0.1); padding: 20px; border-radius: 8px; border-left: 4px solid #dc3545; text-align: center;">
        <div style="font-size: 24px; font-weight: 700; color: #dc3545;">{crit}</div>
        <div style="font-size: 12px; color: #666; margin-top: 4px;">Critical</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div style="background-color: rgba(255, 193, 7, 0.1); padding: 20px; border-radius: 8px; border-left: 4px solid #fd7e14; text-align: center;">
        <div style="font-size: 24px; font-weight: 700; color: #fd7e14;">{high}</div>
        <div style="font-size: 12px; color: #666; margin-top: 4px;">High Risk</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div style="background-color: rgba(13, 110, 253, 0.1); padding: 20px; border-radius: 8px; border-left: 4px solid #0d6efd; text-align: center;">
        <div style="font-size: 24px; font-weight: 700; color: #0d6efd;">{watch}</div>
        <div style="font-size: 12px; color: #666; margin-top: 4px;">Watch</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div style="background-color: rgba(25, 135, 84, 0.1); padding: 20px; border-radius: 8px; border-left: 4px solid #198754; text-align: center;">
        <div style="font-size: 24px; font-weight: 700; color: #198754;">{stable}</div>
        <div style="font-size: 12px; color: #666; margin-top: 4px;">Stable</div>
    </div>
    """, unsafe_allow_html=True)

tab_patients, tab_alerts = st.tabs(["Patients", "Alerts"])

with tab_patients:
    st.markdown("### Patients in Waiting Area")

    st.caption(f"📋 Showing {len(df)} of {len(st.session_state.patients)} patients")

    table = build_patient_table(df)
    styled = style_patient_table(table)
    st.dataframe(styled, use_container_width=True, height=520, hide_index=True)

    st.divider()

with tab_alerts:
    st.markdown("### Active Alerts & Notifications")
    if alerts_df.empty:
        st.success("✓ No unacknowledged alerts right now. Great job!")
    else:
        for idx, alert in alerts_df.iterrows():
            pid = alert["PatientID"]
            status = alert["Status"]
            score = int(alert["RiskScore"])
            reason = alert["Reason"]
            time = pd.to_datetime(alert["Time"]).strftime("%H:%M:%S")

            if score >= 7:
                color = "#dc3545"
                bg = "rgba(220, 53, 69, 0.1)"
            elif score >= 4:
                color = "#fd7e14"
                bg = "rgba(255, 193, 7, 0.1)"
            else:
                color = "#0d6efd"
                bg = "rgba(13, 110, 253, 0.1)"

            c1, c2, c3 = st.columns([3, 1, 1])

            with c1:
                st.markdown(f"""
                <div style="background-color: {bg}; padding: 12px; border-radius: 8px; border-left: 4px solid {color};">
                    <strong style="color: {color};">{pid}</strong> - {reason}<br/>
                    <small style="color: #666;">{time} | Risk: {score}</small>
                </div>
                """, unsafe_allow_html=True)

            with c2:
                if st.button("View", key=f"view_{pid}_{idx}", use_container_width=True):
                    st.session_state.selected_patient = pid
                    st.rerun()

            with c3:
                if st.button("✓ Ack", key=f"ack_{pid}_{idx}", use_container_width=True):
                    st.session_state.ack.add(pid)
                    st.rerun()

        st.divider()
        if st.button("Acknowledge All Alerts", use_container_width=True):
            for pid in alerts_df["PatientID"].unique():
                st.session_state.ack.add(pid)
            st.success("All alerts acknowledged!")
            st.rerun()

st_autorefresh(interval=refresh_sec * 1000, key="auto_refresh")