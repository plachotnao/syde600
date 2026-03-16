import numpy as np
import pandas as pd
import streamlit as st
import json
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components

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

    .stButton > button {
        background-color: #6c757d;
        color: white;
        border-radius: 6px;
        font-weight: 600;
        padding: 8px 16px !important;
        border: none;
        transition: all 0.2s ease-in-out;
    }

    .stButton > button:hover {
        background-color: #5a6268;
        color: white;
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }

    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
    }

    hr {
        margin: 24px 0 !important;
        border: none;
        border-top: 2px solid var(--border-color);
    }
</style>
""", unsafe_allow_html=True)


def now_ts():
    return pd.Timestamp.now(tz="America/Toronto")


def clamp(x, a, b):
    return max(a, min(b, x))


def get_waiting_time(waiting_since):
    now = pd.Timestamp.now(tz="America/Toronto")
    start = pd.to_datetime(waiting_since).tz_convert("America/Toronto")
    delta = now - start
    minutes = max(0, int(delta.total_seconds() // 60))
    hours = minutes // 60
    mins = minutes % 60
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"


def get_elapsed_time(start_ts):
    now = pd.Timestamp.now(tz="America/Toronto")
    start = pd.to_datetime(start_ts).tz_convert("America/Toronto")
    delta = now - start
    minutes = max(0, int(delta.total_seconds() // 60))
    hours = minutes // 60
    mins = minutes % 60
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"


def compute_risk_details(row):
    hr = row["HR"]
    spo2 = row["SpO2"]
    rr = row["RR"]
    sbp = row["SBP"]
    temp = row["Temp"]
    avpu = row["AVPU"]

    details = []

    if rr <= 8 or rr >= 25:
        details.append(f"RR {rr}: +3")
    elif rr >= 21:
        details.append(f"RR {rr}: +2")
    elif rr < 12:
        details.append(f"RR {rr}: +1")

    if spo2 <= 91:
        details.append(f"SpO2 {spo2}%: +3")
    elif spo2 <= 93:
        details.append(f"SpO2 {spo2}%: +2")
    elif spo2 <= 95:
        details.append(f"SpO2 {spo2}%: +1")

    if temp <= 35.0 or temp >= 39.1:
        details.append(f"Temp {temp:.1f}: +2")
    elif temp >= 38.1:
        details.append(f"Temp {temp:.1f}: +1")

    if sbp <= 90:
        details.append(f"SBP {sbp}: +3")
    elif sbp <= 100:
        details.append(f"SBP {sbp}: +2")
    elif sbp <= 110:
        details.append(f"SBP {sbp}: +1")

    if hr <= 40 or hr >= 131:
        details.append(f"HR {hr}: +3")
    elif hr >= 111:
        details.append(f"HR {hr}: +2")
    elif hr >= 91:
        details.append(f"HR {hr}: +1")
    elif hr <= 50:
        details.append(f"HR {hr}: +1")

    if avpu != "A":
        details.append(f"AVPU {avpu}: +3")

    return "\n".join(details) if details else "No abnormal vital thresholds triggered"


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


def assign_statuses(df):
    scored = df.copy()

    scored = scored.sort_values(
        ["RiskScore", "Trend", "SpO2", "WaitingSince"],
        ascending=[False, False, True, True]
    ).reset_index()

    total = len(scored)

    critical_candidates = scored["RiskScore"] >= 7

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

    last_names = [
        "Smith", "Johnson", "Brown", "Davis", "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson",
        "White", "Harris", "Martin", "Thompson", "Garcia", "Martinez", "Robinson", "Clark", "Rodriguez", "Lewis",
        "Lee", "Walker", "Hall", "Allen", "Young", "King", "Wright", "Lopez", "Hill", "Scott"
    ]

    genders = ["Female", "Male"]

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

    complaint_list = list(complaint_weights.keys())
    complaint_probs = list(complaint_weights.values())

    rows = []
    base_time = now_ts()

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
        gender = rng.choice(genders)
        last_reassessment = base_time - pd.Timedelta(minutes=int(rng.integers(5, 181)))

        rows.append({
            "PatientID": f"P{i + 1:03d}",
            "Name": f"{rng.choice(first_names)} {rng.choice(last_names)}",
            "Gender": gender,
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
            "LastReassessment": last_reassessment,
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

    return assign_statuses(df)


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

    st.session_state.prev_patients = prev
    st.session_state.patients = scored


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

    st.markdown("### 📋 Alert Rules")
    st.markdown("""
        - **🔴 Critical**: RiskScore ≥ 7
        - **🟠 High**: RiskScore ≥ 4
        - **🟡 Watch**: RiskScore ≥ 2
        - **🟢 Stable**: RiskScore < 2
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

last_updated = pd.to_datetime(st.session_state.patients["LastUpdate"]).dt.tz_convert("America/Toronto").max().strftime("%H:%M:%S")

st.markdown(f"""
<div style="background-color:#f8f9fa; border:2px solid #dee2e6; border-radius:10px; padding:12px 16px; margin-bottom:16px;">
    <span style="font-size:13px; font-weight:600; color:#666; text-transform:uppercase; letter-spacing:0.4px;">Last Updated (EST)</span><br/>
    <span style="font-size:22px; font-weight:700; color:#1a1a1a;">{last_updated}</span>
</div>
""", unsafe_allow_html=True)

st.markdown("## Patient Status Overview")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div style="background-color: #fce8e8; padding: 20px; border-radius: 8px; border-top: 4px solid #dc3545; text-align: center;">
        <div style="font-size: 24px; font-weight: 700; color: #dc3545;">{crit}</div>
        <div style="font-size: 14px; color: #dc3545; margin-top: 4px;">Critical</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div style="background-color: #fff8cc; padding: 20px; border-radius: 8px; border-top: 4px solid #fd7e14; text-align: center;">
        <div style="font-size: 24px; font-weight: 700; color: #fd7e14;">{high}</div>
        <div style="font-size: 14px; color: #fd7e14; margin-top: 4px;">High Risk</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div style="background-color: #e6f2ff; padding: 20px; border-radius: 8px; border-top: 4px solid #0d6efd; text-align: center;">
        <div style="font-size: 24px; font-weight: 700; color: #0d6efd;">{watch}</div>
        <div style="font-size: 14px; color: #0d6efd; margin-top: 4px;">Watch</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div style="background-color: #f1f8f1; padding: 20px; border-radius: 8px; border-top: 4px solid #198754; text-align: center;">
        <div style="font-size: 24px; font-weight: 700; color: #198754;">{stable}</div>
        <div style="font-size: 14px; color: #198754; margin-top: 4px;">Stable</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br/>", unsafe_allow_html=True)
st.markdown("### Patients in Waiting Area")
st.caption(f"📋 Showing {len(df)} of {len(st.session_state.patients)} patients")

rows_data = []

for _, row in df.iterrows():
    def abn(val, lo, hi):
        try:
            return float(str(val).replace("%", "")) < lo or float(str(val).replace("%", "")) > hi
        except Exception:
            return False

    rows_data.append({
        "pid": str(row["PatientID"]),
        "status_short": str(row["Status"]),
        "risk": int(row["RiskScore"]),
        "risk_info": compute_risk_details(row.to_dict()),
        "trend": f"{trend_symbol(int(row['Trend']))} ({int(row['Trend'])})",
        "name": str(row["Name"]),
        "gender": str(row["Gender"]),
        "age": str(row["Age"]),
        "triage": str(row["Triage"]),
        "location": str(row["Location"]),
        "complaint": str(row["Complaint"]),
        "wait": get_waiting_time(row["WaitingSince"]),
        "trs": get_elapsed_time(row["LastReassessment"]),
        "vitals": {
            "hr": {"v": str(int(row["HR"])), "abn": abn(row["HR"], 60, 100)},
            "rr": {"v": str(int(row["RR"])), "abn": abn(row["RR"], 12, 20)},
            "spo2": {"v": f"{int(row['SpO2'])}%", "abn": abn(str(row["SpO2"]).replace("%", ""), 95, 100)},
            "sbp": {"v": str(int(row["SBP"])), "abn": abn(row["SBP"], 90, 120)},
            "temp": {"v": f"{float(row['Temp']):.1f}", "abn": abn(row["Temp"], 36.5, 37.5)},
            "avpu": {"v": str(row["AVPU"]), "abn": str(row["AVPU"]) != "A"},
        }
    })

patients_vitals = {}
for _, prow in st.session_state.patients.iterrows():
    pid = prow["PatientID"]
    patients_vitals[pid] = {
        "name": prow["Name"],
        "age": int(prow["Age"]),
        "hr": int(prow["HR"]),
        "rr": int(prow["RR"]),
        "spo2": int(prow["SpO2"]),
        "sbp": int(prow["SBP"]),
        "temp": float(prow["Temp"]),
        "avpu": prow["AVPU"],
        "status": prow["Status"],
        "complaint": prow["Complaint"],
    }

vitals_attr = json.dumps(patients_vitals).replace("'", "&#39;")
table_attr = json.dumps(rows_data).replace("'", "&#39;")

injector_html = f"""
<div id="data-div" data-vitals='{vitals_attr}' data-table='{table_attr}'></div>
<script>
  try {{
    const div = document.getElementById('data-div');
    window.top.localStorage.setItem('ed_vitals_data', div.getAttribute('data-vitals'));
    window.top.localStorage.setItem('ed_table_data', div.getAttribute('data-table'));
  }} catch(e) {{
    try {{
      const div = document.getElementById('data-div');
      localStorage.setItem('ed_vitals_data', div.getAttribute('data-vitals'));
      localStorage.setItem('ed_table_data', div.getAttribute('data-table'));
    }} catch(e2) {{}}
  }}
</script>
"""
components.html(injector_html, height=0, scrolling=False)

TABLE_HTML = """
<style>
    *{box-sizing:border-box;margin:0;padding:0;}
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8f9fa;font-size:14px;overflow:hidden;}
    #wrap{
        height:520px;
        overflow-y:auto;
        overflow-x:auto;
        border-radius:8px;
        border:1px solid #e0e0e0;
        background:#fff;
        position:relative;
    }
    table{
        border-collapse:separate;
        border-spacing:0;
        width:100%;
        min-width:1280px;
    }
    thead tr{
        position:sticky;
        top:0;
        z-index:20;
    }
    th{
        padding:12px;
        text-align:left;
        font-size:12px;
        font-weight:700;
        color:#555;
        border-bottom:2px solid #ddd;
        background:#f8f9fa;
        white-space:nowrap;
    }
    td{
        padding:10px 12px;
        vertical-align:middle;
        white-space:nowrap;
        border-bottom:1px solid #eee;
        color:#1a1a1a;
    }
    tbody tr{transition:background 0.1s;}
    tbody tr:hover{filter:brightness(0.96);}
    .vit-abn{color:#dc2626;font-weight:700;}
    .mb{
        border-radius:6px;
        padding:4px 10px;
        font-size:16px;
        font-weight:600;
        cursor:pointer;
        border:1px solid #0d6efd;
        background:#fff;
        color:#0d6efd;
        transition:all 0.12s;
    }
    .mb:hover{background:#e6f2ff;}
    .mb.on{background:#0d6efd;color:#fff;}
    .risk-wrap{
        display:inline-flex;
        align-items:center;
        gap:6px;
    }
    .ib{
        width:18px;
        height:18px;
        border-radius:50%;
        border:1px solid #6c757d;
        background:#fff;
        color:#6c757d;
        font-size:11px;
        font-weight:700;
        line-height:16px;
        text-align:center;
        cursor:pointer;
        padding:0;
        flex:0 0 auto;
    }
    .ib:hover{background:#f1f3f5;}
    #risk-tip{
        display:none;
        position:fixed;
        z-index:999999;
        width:280px;
        max-width:min(280px, calc(100vw - 24px));
        background:#ffffff;
        border:1px solid #9fb3c3;
        border-radius:2px;
        box-shadow:0 6px 18px rgba(0,0,0,0.18);
        padding:12px 14px;
        color:#1f2328;
        --arrow-top: 24px;
    }
    #risk-tip.show{display:block;}
    #risk-tip-title{
        font-size:14px;
        font-weight:700;
        margin-bottom:8px;
        line-height:1.2;
    }
    #risk-tip-body{
        font-size:12px;
        line-height:1.45;
        white-space:pre-line;
        word-break:break-word;
    }
    #risk-tip.tip-right::before,
    #risk-tip.tip-right::after,
    #risk-tip.tip-left::before,
    #risk-tip.tip-left::after{
        content:"";
        position:absolute;
        top:var(--arrow-top);
        width:0;
        height:0;
        transform:translateY(-50%);
    }
    #risk-tip.tip-right::before{
        left:-12px;
        border-top:10px solid transparent;
        border-bottom:10px solid transparent;
        border-right:12px solid #9fb3c3;
    }
    #risk-tip.tip-right::after{
        left:-10px;
        border-top:9px solid transparent;
        border-bottom:9px solid transparent;
        border-right:11px solid #ffffff;
    }
    #risk-tip.tip-left::before{
        right:-12px;
        border-top:10px solid transparent;
        border-bottom:10px solid transparent;
        border-left:12px solid #9fb3c3;
    }
    #risk-tip.tip-left::after{
        right:-10px;
        border-top:9px solid transparent;
        border-bottom:9px solid transparent;
        border-left:11px solid #ffffff;
    }
</style>

<div id='wrap'>
    <table>
        <thead>
            <tr>
                <th>PatientID</th><th>Name</th><th>Gender</th><th>Age</th><th>Triage</th><th>Location</th><th>Status</th>
                <th>RiskScore</th><th>Trend</th><th>SpO2</th><th>RR</th><th>HR</th><th>SBP</th>
                <th>Temp</th><th>AVPU</th><th>LOS</th><th>TRS</th><th>Complaint</th><th style="text-align:center;">🖥️</th>
            </tr>
        </thead>
        <tbody id='tb'></tbody>
    </table>
</div>

<div id="risk-tip" role="dialog" aria-live="polite" aria-hidden="true">
    <div id="risk-tip-title">Risk score details</div>
    <div id="risk-tip-body"></div>
</div>

<script>
    var LS = 'ed_selected_patient';
    var OPEN_TIP_KEY = 'ed_open_risk_tip';
    var wrapEl = document.getElementById('wrap');
    var tipEl = document.getElementById('risk-tip');
    var tipBodyEl = document.getElementById('risk-tip-body');

    function getSel(){ try{ return localStorage.getItem(LS)||''; }catch(e){ return ''; } }
    function setSel(p){ try{ localStorage.setItem(LS,p); }catch(e){} }
    function clrSel(){ try{ localStorage.removeItem(LS); }catch(e){} }

    function getOpenTip(){ try{ return localStorage.getItem(OPEN_TIP_KEY)||''; }catch(e){ return ''; } }
    function setOpenTip(id){ try{ localStorage.setItem(OPEN_TIP_KEY,id); }catch(e){} }
    function clearOpenTip(){ try{ localStorage.removeItem(OPEN_TIP_KEY); }catch(e){} }

    window.toggleSel = function(pid) {
        getSel() === pid ? clrSel() : setSel(pid);
        renderFromData();
    };

    function vit(d){
        return '<span class="'+(d.abn?'vit-abn':'')+'">'+d.v+'</span>';
    }

    function esc(s){
        return String(s)
            .replace(/&/g,'&amp;')
            .replace(/</g,'&lt;')
            .replace(/>/g,'&gt;')
            .replace(/"/g,'&quot;')
            .replace(/'/g,'&#39;');
    }

    function clampValue(val, min, max){
        return Math.max(min, Math.min(max, val));
    }

    function isButtonVisibleInWrap(btn){
        if(!btn || !wrapEl) return false;
        var btnRect = btn.getBoundingClientRect();
        var wrapRect = wrapEl.getBoundingClientRect();
        var verticallyVisible = btnRect.bottom > wrapRect.top && btnRect.top < wrapRect.bottom;
        var horizontallyVisible = btnRect.right > wrapRect.left && btnRect.left < wrapRect.right;
        return verticallyVisible && horizontallyVisible;
    }

    function hideTip(){
        tipEl.classList.remove('show', 'tip-right', 'tip-left');
        tipEl.setAttribute('aria-hidden', 'true');
        tipEl.style.left = '-9999px';
        tipEl.style.top = '-9999px';
    }

    function positionTipForButton(btn){
        if(!btn) return false;
        if(!isButtonVisibleInWrap(btn)) return false;

        var rect = btn.getBoundingClientRect();

        tipEl.classList.add('show');
        tipEl.setAttribute('aria-hidden', 'false');
        tipEl.style.left = '-9999px';
        tipEl.style.top = '-9999px';
        tipEl.classList.remove('tip-right', 'tip-left');

        var tipRect = tipEl.getBoundingClientRect();
        var gap = 14;
        var arrowPad = 12;
        var placement = 'right';

        var left = rect.right + gap + arrowPad;
        if (left + tipRect.width > window.innerWidth - 12) {
            left = rect.left - tipRect.width - gap - arrowPad;
            placement = 'left';
        }

        if (left < 12) {
            if (rect.right + gap + arrowPad + tipRect.width <= window.innerWidth - 12) {
                left = rect.right + gap + arrowPad;
                placement = 'right';
            } else {
                left = 12;
            }
        }

        if (left + tipRect.width > window.innerWidth - 12) {
            left = window.innerWidth - tipRect.width - 12;
        }

        var top = rect.top + (rect.height / 2) - (tipRect.height / 2);
        if (top < 12) top = 12;
        if (top + tipRect.height > window.innerHeight - 12) {
            top = window.innerHeight - tipRect.height - 12;
        }

        tipEl.classList.add(placement === 'right' ? 'tip-right' : 'tip-left');
        tipEl.style.left = left + 'px';
        tipEl.style.top = top + 'px';

        var tipFinalRect = tipEl.getBoundingClientRect();
        var buttonCenterY = rect.top + rect.height / 2;
        var arrowTop = buttonCenterY - tipFinalRect.top;
        arrowTop = clampValue(arrowTop, 18, tipFinalRect.height - 18);
        tipEl.style.setProperty('--arrow-top', arrowTop + 'px');

        return true;
    }

    function syncOpenTip(){
        var openTip = getOpenTip();
        if(!openTip){
            hideTip();
            return;
        }

        var btn = document.querySelector('[data-tip-id="'+openTip+'"]');
        if(!btn){
            hideTip();
            return;
        }

        var content = btn.getAttribute('data-tip-content') || '';
        tipBodyEl.textContent = content;

        if(!positionTipForButton(btn)){
            hideTip();
        }
    }

    window.toggleInfo = function(btnId) {
        var current = getOpenTip();

        if(current === btnId){
            clearOpenTip();
            hideTip();
            return;
        }

        setOpenTip(btnId);
        syncOpenTip();
    };

    function closeTooltipAnywhere(){
        clearOpenTip();
        hideTip();
    }

    document.addEventListener('click', function(e){
        if(!e.target.closest('.risk-wrap') && !e.target.closest('#risk-tip') && !e.target.closest('#wrap')){
            closeTooltipAnywhere();
        }
    }, true);

    try {
        window.top.document.addEventListener('click', function(e){
            try {
                var iframeEl = window.frameElement;
                if (iframeEl && e.target === iframeEl) {
                    return;
                }
            } catch(err) {}
            closeTooltipAnywhere();
        }, true);
    } catch(e) {}

    window.addEventListener('blur', function(){
        closeTooltipAnywhere();
    });

    function renderFromData() {
        var openTip = getOpenTip();
        var raw = localStorage.getItem('ed_table_data');
        if(!raw) return;
        var rows = JSON.parse(raw);
        var sel = getSel();
        var html = '';

        rows.forEach(function(r){
            var isOn = sel === r.pid;
            var bg = '#ffffff';
            var tipId = 'tip-' + r.pid;

            if(r.status_short === 'Critical') bg = '#fce8e8';
            else if(r.status_short === 'High') bg = '#fff8cc';
            else if(r.status_short === 'Watch') bg = '#e6f2ff';

            html += '<tr style="background:'+bg+';">'
                + '<td style="color:#555;">'+r.pid+'</td>'
                + '<td style="font-weight:600;">'+esc(r.name)+'</td>'
                + '<td>'+esc(r.gender)+'</td>'
                + '<td>'+r.age+'</td>'
                + '<td>'+r.triage+'</td>'
                + '<td>'+r.location+'</td>'
                + '<td style="font-weight:600;">'+(r.status_short === 'Critical' ? '🔴 Critical' : r.status_short === 'High' ? '🟠 High' : r.status_short === 'Watch' ? '🟡 Watch' : '🟢 Stable')+'</td>'
                + '<td><div class="risk-wrap"><strong>'+r.risk+'</strong><button class="ib" data-tip-id="'+tipId+'" data-tip-content="'+esc(r.risk_info)+'" onclick="toggleInfo(\\''+tipId+'\\')" title="How risk score was derived" aria-label="Risk score details">i</button></div></td>'
                + '<td>'+r.trend+'</td>'
                + '<td>'+vit(r.vitals.spo2)+'</td>'
                + '<td>'+vit(r.vitals.rr)+'</td>'
                + '<td>'+vit(r.vitals.hr)+'</td>'
                + '<td>'+vit(r.vitals.sbp)+'</td>'
                + '<td>'+vit(r.vitals.temp)+'</td>'
                + '<td>'+vit(r.vitals.avpu)+'</td>'
                + '<td>'+r.wait+'</td>'
                + '<td>'+r.trs+'</td>'
                + '<td>'+esc(r.complaint)+'</td>'
                + '<td style="text-align:center;"><button class="mb'+(isOn?' on':'')+'" onclick="toggleSel(\\''+r.pid+'\\')" title="Monitor Patient">🖥️</button></td>'
                + '</tr>';
        });

        document.getElementById('tb').innerHTML = html;

        requestAnimationFrame(function(){
            if(openTip){
                syncOpenTip();
            } else {
                hideTip();
            }
        });
    }

    wrapEl.addEventListener('scroll', function(){
        requestAnimationFrame(syncOpenTip);
    });

    window.addEventListener('resize', function(){
        requestAnimationFrame(syncOpenTip);
    });

    window.addEventListener('scroll', function(){
        requestAnimationFrame(syncOpenTip);
    }, true);

    setInterval(function(){
        renderFromData();
    }, 500);

    renderFromData();
</script>
"""
components.html(TABLE_HTML, height=530, scrolling=False)

MONITOR_HTML = """<!DOCTYPE html>
<html>
<head>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body {
background: #000; overflow: hidden; width: 100%; height: 480px;
font-family: Arial, Helvetica, sans-serif;
}
#no-selection {
display: flex; align-items: center; justify-content: center;
height: 480px; color: #333; font-size: 13px; letter-spacing: 2px;
text-transform: uppercase; background: #000;
}
#monitor { display: none; width: 100%; height: 480px; flex-direction: row; background: #000; }
#waveforms {
flex: 1; display: flex; flex-direction: column;
background: #000; border-right: 1px solid #1c1c1c;
min-width: 0;
}
#top-bar {
display: flex; align-items: center; gap: 18px;
padding: 3px 10px; background: #000;
border-bottom: 1px solid #111; flex-shrink: 0; height: 22px;
}
.top-tag { font-size: 11px; font-weight: 700; letter-spacing: 1px; }
.wave-row { flex: 1; position: relative; border-bottom: 1px solid #0d0d0d; min-height: 0; }
.row-label {
position: absolute; top: 4px; left: 8px; z-index: 2;
font-size: 11px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase;
}
canvas.wc { position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: block; }
#numerics { width: 230px; display: flex; flex-direction: column; background: #000; flex-shrink: 0; border-left: 1px solid #1a1a1a; }
.nc {
flex: 1; border-bottom: 1px solid #1a1a1a;
padding: 5px 10px 4px 12px; position: relative;
display: flex; flex-direction: column; justify-content: center; min-height: 0;
}
.nc-lbl  { font-size: 10px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 1px; }
.nc-unit { position: absolute; top: 5px; right: 8px; font-size: 9px; color: #444; letter-spacing: 0.5px; }
.nc-big  { font-size: 64px; font-weight: 700; line-height: 0.9; letter-spacing: -3px; }
.nc-sub  { font-size: 10px; margin-top: 3px; letter-spacing: 1px; }
.nc-row2 { display: flex; align-items: stretch; height: 100%; }
.nc-col  { flex: 1; display: flex; flex-direction: column; justify-content: center; padding: 2px 0; }
.nc-col + .nc-col { border-left: 1px solid #1a1a1a; padding-left: 10px; }
.nc-med  { font-size: 40px; font-weight: 700; line-height: 0.9; letter-spacing: -2px; }
.nc-sm   { font-size: 22px; font-weight: 700; line-height: 1; }
.nc-tiny { font-size: 9px; color: #444; letter-spacing: 0.5px; margin-top: 1px; }
.nc-bp-row { display: flex; align-items: baseline; justify-content: space-between; }
.nc-bp-val { font-size: 28px; font-weight: 700; letter-spacing: -1px; line-height: 1.1; }
.nc-bp-map { font-size: 24px; font-weight: 700; }
.nc-bp-row2 { display: flex; align-items: baseline; justify-content: space-between; margin-top: 2px; }
.nc-bp-val2 { font-size: 20px; font-weight: 700; letter-spacing: -0.5px; color: #555; }
.nc-bp-map2 { font-size: 18px; font-weight: 700; color: #555; }
#spo2-bar { display: flex; flex-direction: column; gap: 2px; align-items: flex-end; margin-top: 2px; }
#clock-bar {
height: 22px; background: #000; border-top: 1px solid #1a1a1a;
display: flex; align-items: center; justify-content: flex-end;
padding: 0 10px; flex-shrink: 0;
}
#clock { font-size: 12px; color: #00ff41; font-family: monospace; letter-spacing: 1.5px; }
</style>
</head>
<body>

<div id="no-selection">NO PATIENT SELECTED</div>

<div id="monitor">
<div id="waveforms">
<div id="top-bar">
  <span class="top-tag" style="color:#00ff41;" id="tb-lead">II &nbsp; X1</span>
  <span class="top-tag" style="color:#00ff41;" id="tb-mode">Diagnostic</span>
  <span class="top-tag" style="color:#ccc;margin-left:16px;" id="tb-name">—</span>
  <span class="top-tag" style="color:#aaa;" id="tb-info">—</span>
  <span class="top-tag" style="color:#ffc107;" id="tb-complaint">—</span>
</div>
<div class="wave-row"><div class="row-label" style="color:#00ff41;">ECG</div><canvas class="wc" id="c-ecg"></canvas></div>
<div class="wave-row"><div class="row-label" style="color:#ffff00;">RESP</div><canvas class="wc" id="c-resp"></canvas></div>
<div class="wave-row"><div class="row-label" style="color:#00e5ff;">Pleth</div><canvas class="wc" id="c-pleth"></canvas></div>
<div class="wave-row"><div class="row-label" style="color:#ff40ff;">CO2</div><canvas class="wc" id="c-co2"></canvas></div>
<div class="wave-row"><div class="row-label" style="color:#ff4444;">CH1:Art</div><canvas class="wc" id="c-art"></canvas></div>
</div>

<div id="numerics">
<div class="nc" style="flex:1.6;">
  <div class="nc-lbl" style="color:#00ff41;">ECG &nbsp; bpm</div>
  <div class="nc-big" style="color:#00ff41;" id="n-hr">--</div>
  <div class="nc-sub" id="n-hr-sub" style="color:#555;"></div>
</div>
<div class="nc" style="flex:1.0; padding:0;">
  <div class="nc-row2" style="height:100%;">
    <div class="nc-col" style="padding:5px 0 4px 12px;">
      <div class="nc-lbl" style="color:#ffff00;">RESP</div>
      <div class="nc-med" style="color:#ffff00;" id="n-rr">--</div>
    </div>
    <div class="nc-col" style="padding:5px 0 4px 10px;">
      <div class="nc-lbl" style="color:#aaaaaa;">TEMP</div>
      <div class="nc-sm"  style="color:#aaaaaa;" id="n-temp">--</div>
      <div class="nc-tiny">T1</div>
      <div class="nc-tiny">T2</div>
      <div class="nc-tiny">TD</div>
    </div>
  </div>
</div>
<div class="nc" style="flex:1.1;">
  <div class="nc-lbl" style="color:#00e5ff;">SpO2</div>
  <div class="nc-unit">%</div>
  <div style="display:flex;align-items:flex-end;gap:10px;">
    <div class="nc-big" style="color:#00e5ff;" id="n-spo2">--</div>
    <div id="spo2-bar"></div>
  </div>
</div>
<div class="nc" style="flex:1.1;">
  <div class="nc-lbl" style="color:#ff40ff;">CO2</div>
  <div class="nc-unit">mmHg</div>
  <div class="nc-big" style="color:#ff40ff;" id="n-co2">--</div>
</div>
<div class="nc" style="flex:1.3;">
  <div class="nc-lbl" style="color:#ff7043;">IBP (1,2)</div>
  <div class="nc-unit">mmHg</div>
  <div class="nc-bp-row">
    <div class="nc-bp-val" style="color:#ff7043;" id="n-ibp">--/--</div>
    <div class="nc-bp-map" style="color:#ff7043;" id="n-map">(--)</div>
  </div>
  <div class="nc-bp-row2">
    <div class="nc-bp-val2">---/---</div>
    <div class="nc-bp-map2">( 10 )</div>
  </div>
</div>
<div class="nc" style="flex:1.3;">
  <div class="nc-lbl" style="color:#fff;">NIBP</div>
  <div class="nc-unit">mmHg</div>
  <div class="nc-bp-row">
    <div class="nc-bp-val" style="color:#fff;" id="n-nibp">--/--</div>
    <div class="nc-bp-map" style="color:#fff;" id="n-nibp-map">(--)</div>
  </div>
  <div class="nc-sub" style="color:#555;">Manual</div>
</div>
<div id="clock-bar"><span id="clock">00:00:00</span></div>
</div>
</div>

<script>
const SEL_KEY    = 'ed_selected_patient';
const VITALS_KEY = 'ed_vitals_data';
const SWEEP      = 160;

function buildEcgLut(hr, avpu) {
const N = 1000, lut = new Float32Array(N);
const aberrant = avpu !== 'A' || hr > 130 || hr < 45;
const noise = () => (Math.random() - 0.5) * 0.01;
for (let i = 0; i < N; i++) {
const p = i / N; let v = noise();
if (p < 0.18) v += 0.13 * Math.sin(Math.PI * p / 0.18);
if (p >= 0.22 && p < 0.26) v -= 0.10 * Math.sin(Math.PI * (p-0.22)/0.04);
if (p >= 0.26 && p < 0.36) {
  const x = (p-0.26)/0.10;
  v += aberrant ? 0.80 * Math.sin(Math.PI * Math.pow(x,0.5)) - 0.12*Math.sin(2*Math.PI*x)
                : 1.00 * Math.pow(Math.sin(Math.PI * x), 1.6);
}
if (p >= 0.36 && p < 0.44) v -= 0.20 * Math.sin(Math.PI * (p-0.36)/0.08);
if (p >= 0.52 && p < 0.78) {
  const x = (p-0.52)/0.26;
  v += (aberrant ? 0.28 : 0.22) * Math.sin(Math.PI * Math.pow(x, 0.7));
}
if (hr < 70 && p >= 0.80 && p < 0.92) v += 0.04 * Math.sin(Math.PI*(p-0.80)/0.12);
lut[i] = v;
}
return lut;
}

function buildPlethLut(spo2) {
const N = 1000, lut = new Float32Array(N);
const amp = 0.15 + Math.pow(Math.max(0, spo2 - 80) / 20, 1.5) * 0.80;
const noise = () => (Math.random() - 0.5) * 0.010;
for (let i = 0; i < N; i++) {
const p = i / N; let v = noise();
if (p < 0.20)      v += amp * Math.pow(Math.sin(Math.PI * p / 0.20), 0.55);
else if (p < 0.32) v += amp * (0.55*(1-(p-0.20)/0.12) + 0.09*Math.sin(Math.PI*(p-0.20)/0.06));
else if (p < 0.72) v += amp * 0.42 * Math.exp(-(p-0.32)/0.40 * 3.2);
lut[i] = v;
}
return lut;
}

function buildArtLut(sbp) {
const N = 1000, lut = new Float32Array(N);
const dbp = Math.round(sbp * 0.62);
const pp  = sbp - dbp;
const amp = Math.max(0.08, pp / 120) * 1.4;
const baseline = -0.25 - (120 - Math.min(sbp, 120)) / 120 * 0.15;
const noise = () => (Math.random()-0.5)*0.008;
for (let i = 0; i < N; i++) {
const p = i / N; let v = noise();
if (p < 0.22)      v = baseline + amp * Math.pow(Math.sin(Math.PI * p / 0.22), 0.5);
else if (p < 0.30) v = baseline + amp * (0.72 - (p-0.22)/0.08 * 0.28) + 0.04*Math.sin(Math.PI*(p-0.22)/0.04);
else               v = baseline + amp * 0.60 * Math.exp(-(p-0.30)/0.70 * 2.8);
lut[i] = v + noise();
}
return lut;
}

let respT = 0;
function respSample(dt, rr) {
respT += dt;
const period = 60 / rr * (1 + 0.05*Math.sin(respT*0.28));
const phase = (respT % period) / period;
const amp = 0.55 + Math.max(0, (20 - rr)) / 20 * 0.35;
let v = phase < 0.42 ? amp * Math.sin(Math.PI * phase / 0.42) : -amp * 0.35 * Math.sin(Math.PI * (phase-0.42) / 0.58);
return v + (Math.random()-0.5)*0.015;
}

let co2T = 0;
function co2Sample(dt, rr, etco2) {
co2T += dt;
const period = 60 / rr;
const phase = (co2T % period) / period;
const amp = etco2 / 50 * 0.9;
let v = 0;
if (phase < 0.08)      v = 0;
else if (phase < 0.20) v = amp * (phase-0.08)/0.12;
else if (phase < 0.52) v = amp * (1 + 0.06*Math.sin(Math.PI*(phase-0.20)/0.32));
else if (phase < 0.60) v = amp * (1 - (phase-0.52)/0.08);
else                   v = 0;
return v + (Math.random()-0.5)*0.008;
}

class SweepRenderer {
constructor(id, color, mid_frac) {
this.el    = document.getElementById(id);
this.color = color;
this.mid   = mid_frac !== undefined ? mid_frac : 0.55;
this.buf   = null;
this.wp    = 0;
this.blank = 16;
this.ready = false;
}
init() {
const c = this.el;
c.width  = c.offsetWidth  || c.parentElement.offsetWidth  || 500;
c.height = c.offsetHeight || c.parentElement.offsetHeight || 80;
this.ctx = c.getContext('2d');
this.buf = new Float32Array(c.width).fill(0);
this.wp  = 0;
this.ready = true;
}
push(v) {
if (!this.ready) return;
this.buf[this.wp % this.buf.length] = v;
this.wp++;
}
flush() {
if (this.buf) this.buf.fill(0);
}
draw() {
if (!this.ready) return;
const ctx = this.ctx;
const W = this.el.width, H = this.el.height;
const mid = H * this.mid, scale = H * 0.38;
const wp  = this.wp % W;

ctx.fillStyle = '#000';
ctx.fillRect(0, 0, W, H);

ctx.strokeStyle = '#111'; ctx.lineWidth = 0.5;
for (let x = 0; x < W; x += 40) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
for (let y = 0; y < H; y += H / 4) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }

ctx.strokeStyle = this.color; ctx.lineWidth = 1.8; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
ctx.shadowColor = this.color; ctx.shadowBlur = 4;
ctx.beginPath();

let first = true;
for (let dx = this.blank + 1; dx < W; dx++) {
  const bx = (wp + dx) % W;
  const x  = dx;
  const y  = mid - this.buf[bx] * scale;
  if (first) { ctx.moveTo(x, y); first = false; }
  else       { ctx.lineTo(x, y); }
}
ctx.stroke(); ctx.shadowBlur = 0;
ctx.fillStyle = '#000'; ctx.fillRect(0, 0, this.blank + 1, H);
}
}

function renderSpo2Bar(spo2) {
const el = document.getElementById('spo2-bar');
if (!el) return;
const total = 6;
const filled = Math.round(Math.max(0, Math.min(1, (spo2 - 80) / 20)) * total);
el.innerHTML = '';
el.style.cssText = 'display:flex;flex-direction:column;gap:2px;align-items:flex-end;margin-bottom:6px;';
for (let i = total - 1; i >= 0; i--) {
const b = document.createElement('div');
const w = 8 + i * 3;
b.style.cssText = `width:${w}px;height:5px;background:${i < filled ? '#00e5ff' : '#1a1a1a'};border-radius:1px;`;
el.appendChild(b);
}
}

const ecgR   = new SweepRenderer('c-ecg',   '#00ff41', 0.55);
const respR  = new SweepRenderer('c-resp',  '#ffff00', 0.50);
const plethR = new SweepRenderer('c-pleth', '#00e5ff', 0.55);
const co2R   = new SweepRenderer('c-co2',   '#ff40ff', 0.72);
const artR   = new SweepRenderer('c-art',   '#ff4444', 0.55);

let V = null, pid = null, animId = null, lastTs = null;
let ecgLut = null, plethLut = null, artLut = null;
let ecgPhase = 0, plethPhase = 0, artPhase = 0;

function buildLuts(v) {
ecgLut   = buildEcgLut(v.hr, v.avpu);
plethLut = buildPlethLut(v.spo2);
artLut   = buildArtLut(v.sbp);
}

function computeDerived(v) {
const dbp  = Math.round(v.sbp * 0.62);
const map  = Math.round(dbp + (v.sbp - dbp) / 3);
const etco2 = Math.round(35 + (v.rr - 14) * 0.5);
return { dbp, map, etco2 };
}

function updateNumerics(v) {
const { dbp, map, etco2 } = computeDerived(v);
const set = (id, txt) => { const el = document.getElementById(id); if (el) el.textContent = txt; };

set('n-hr',       v.hr);
set('n-rr',       v.rr);
set('n-temp',     v.temp.toFixed(1) + '°');
set('n-spo2',     v.spo2);
set('n-co2',      etco2);
set('n-ibp',      v.sbp + '/' + dbp);
set('n-map',      '(' + map + ')');
set('n-nibp',     v.sbp + '/' + dbp);
set('n-nibp-map', '(' + map + ')');

const hrSubEl = document.getElementById('n-hr-sub');
if (hrSubEl) {
hrSubEl.textContent = v.hr < 60 ? '▲ BRADYCARDIA' : v.hr > 100 ? '▲ TACHYCARDIA' : '';
hrSubEl.style.color = '#888';
}
renderSpo2Bar(v.spo2);
}

setInterval(() => {
const d = new Date();
const el = document.getElementById('clock');
if (el) el.textContent = [d.getHours(),d.getMinutes(),d.getSeconds()].map(x=>String(x).padStart(2,'0')).join(':');
}, 500);

function frame(ts) {
if (!lastTs) lastTs = ts;
const dt = Math.min((ts - lastTs) / 1000, 0.05);
lastTs = ts;

if (V) {
const steps = Math.max(1, Math.round(SWEEP * dt));
const sd = dt / steps;

for (let s = 0; s < steps; s++) {
  const beatPeriod = 60 / V.hr * (1 + 0.025*Math.sin(respT*0.7));

  ecgPhase += sd / beatPeriod; if (ecgPhase >= 1) ecgPhase -= 1;
  ecgR.push(ecgLut[Math.floor(ecgPhase * ecgLut.length)]);

  plethPhase += sd / beatPeriod; if (plethPhase >= 1) plethPhase -= 1;
  plethR.push(plethLut[Math.floor(plethPhase * plethLut.length)]);

  artPhase += sd / beatPeriod; if (artPhase >= 1) artPhase -= 1;
  artR.push(artLut[Math.floor(artPhase * artLut.length)]);

  respR.push(respSample(sd, V.rr));
  const { etco2 } = computeDerived(V);
  co2R.push(co2Sample(sd, V.rr, etco2));
}

ecgR.draw(); respR.draw(); plethR.draw(); co2R.draw(); artR.draw();
}

animId = requestAnimationFrame(frame);
}

let monitorsInitialized = false;

function pidSeed(pidStr) {
let h = 0;
for (let i = 0; i < pidStr.length; i++) h = (Math.imul(31, h) + pidStr.charCodeAt(i)) | 0;
return Math.abs(h) / 2147483647;
}

function startMonitor(newPid, v) {
const isSwitch = monitorsInitialized && (pid !== newPid);
pid = newPid; V = v;
buildLuts(v);

document.getElementById('no-selection').style.display = 'none';
document.getElementById('monitor').style.display = 'flex';
document.getElementById('tb-name').textContent      = v.name + '  ·  ' + newPid;
document.getElementById('tb-info').textContent      = 'Age ' + v.age + '  ·  ' + v.status + '  ·  AVPU: ' + v.avpu;
document.getElementById('tb-complaint').textContent = v.complaint;
updateNumerics(v);

const seed = pidSeed(newPid);

if (!monitorsInitialized) {
setTimeout(() => {
  [ecgR, respR, plethR, co2R, artR].forEach(r => r.init());
  ecgPhase   = seed;
  plethPhase = (seed + 0.15) % 1;
  artPhase   = (seed + 0.05) % 1;
  respT      = seed * 60;
  co2T       = (seed + 0.3) * 60;
  monitorsInitialized = true;
}, 80);
} else if (isSwitch) {
[ecgR, respR, plethR, co2R, artR].forEach(r => r.flush());
ecgPhase   = seed;
plethPhase = (seed + 0.15) % 1;
artPhase   = (seed + 0.05) % 1;
respT      = seed * 60;
co2T       = (seed + 0.3) * 60;
}
}

function stopMonitor() {
V = null;
pid = null;
document.getElementById('no-selection').style.display = 'flex';
document.getElementById('monitor').style.display = 'none';
}

function pollData() {
const sel = localStorage.getItem(SEL_KEY);
if (sel) {
  try {
    const db = JSON.parse(localStorage.getItem(VITALS_KEY)||'{}');
    if (db[sel]) {
        const nv = db[sel];
        if (!V || pid !== sel || nv.hr !== V.hr || nv.spo2 !== V.spo2 || nv.sbp !== V.sbp) {
            startMonitor(sel, nv);
        }
    }
  } catch(e) {}
} else if (pid) {
  stopMonitor();
}
setTimeout(pollData, 500);
}

pollData();
animId = requestAnimationFrame(frame);
</script>
</body>
</html>"""
components.html(MONITOR_HTML, height=480, scrolling=False)

st_autorefresh(interval=refresh_sec * 1000, key="auto_refresh")