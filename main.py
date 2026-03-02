import numpy as np
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(
    page_title="ED Nurse Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional ED dashboard styling
st.markdown("""
<style>
    /* Color scheme - WCAG AA compliant high contrast */
    :root {
        --critical-bg: #dc3545;
        --critical-light: #f8d7da;
        --high-bg: #fd7e14;
        --high-light: #fff3cd;
        --watch-bg: #0d6efd;
        --watch-light: #cfe2ff;
        --stable-bg: #198754;
        --stable-light: #d1e7dd;
        --text-dark: #1a1a1a;
        --text-light: #ffffff;
        --border-color: #dee2e6;
    }
    
    /* Main container padding and spacing */
    .main {
        max-width: 1600px;
    }
    
    /* Typography improvements */
    h1, h2, h3 {
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    
    /* Metric cards styling */
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
    
    /* Status badge styling */
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
    
    /* Alert banner styling */
    .alert-banner {
        background-color: var(--critical-bg);
        color: white;
        padding: 16px;
        border-radius: 8px;
        margin-bottom: 20px;
        border-left: 6px solid #8b0000;
        font-weight: 600;
    }
    
    /* Patient table improvements */
    [data-testid="dataframe"] {
        font-size: 14px !important;
    }
    
    /* Dataframe header styling */
    .stDataFrame thead {
        font-weight: 700 !important;
        background-color: #f8f9fa !important;
    }
    
    /* Button styling */
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
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
    }
    
    /* Section dividers */
    hr {
        margin: 24px 0 !important;
        border: none;
        border-top: 2px solid var(--border-color);
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [role="tab"] {
        padding: 12px 24px !important;
        font-weight: 600;
        border-radius: 8px 8px 0 0;
    }
    
    /* Better spacing for info/success boxes */
    .stInfo, .stSuccess, .stWarning, .stError {
        border-radius: 8px;
        border-left: 6px solid;
        padding: 16px !important;
    }
    
    /* Vital range indicator */
    .vital-normal {
        color: #198754;
        font-weight: 600;
    }
    
    .vital-abnormal {
        color: #dc3545;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

def now_ts():
    return pd.Timestamp.now(tz="UTC")

def clamp(x, a, b):
    return max(a, min(b, x))

def get_patient_age_and_dob(age):
    """Calculate approximate DOB from age"""
    today = pd.Timestamp.now()
    dob = today - pd.DateOffset(years=age)
    return dob.strftime("%Y-%m-%d")

def get_waiting_time(last_update):
    """Calculate how long patient has been waiting"""
    now = pd.Timestamp.now(tz="UTC")
    last = pd.to_datetime(last_update)
    delta = now - last

    minutes = int(delta.total_seconds() // 60)
    hours = minutes // 60
    mins = minutes % 60

    if hours > 0:
        return f"{hours}h {mins}m"
    else:
        return f"{mins}m"

def format_patient_name(name, age):
    """Format patient name with last name placeholder (simulated)"""
    # Since we only have first names, create a last name based on age/id pattern
    last_names = ["Smith", "Johnson", "Brown", "Davis", "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin", "Thompson", "Garcia", "Martinez", "Robinson", "Clark", "Rodriguez", "Lewis", "Lee", "Walker", "Hall", "Allen", "Young", "King", "Wright", "Lopez", "Hill", "Scott", "Green", "Adams", "Nelson", "Carter", "Mitchell", "Roberts", "Phillips", "Campbell", "Parker", "Evans", "Edwards", "Collins", "Reeves", "Stewart", "Morris", "Rogers", "Morgan", "Peterson", "Cooper", "Reed", "Bell", "Howard"]
    # Use age as seed for consistent last name per patient
    idx = (age * 7) % len(last_names)
    last_name = last_names[idx]
    return f"{name} {last_name}"

def is_vital_abnormal(vital_name, value):
    """Check if a vital sign is outside normal range"""
    ranges = {
        "HR": (60, 100),
        "RR": (12, 20),
        "SpO2": (95, 100),
        "SBP": (90, 120),
        "Temp": (36.5, 37.5)
    }
    if vital_name not in ranges:
        return False
    min_val, max_val = ranges[vital_name]
    return value < min_val or value > max_val

def get_vital_range_display(vital_name):
    """Get readable vital sign normal range"""
    ranges = {
        "HR": "60-100 bpm",
        "RR": "12-20 br/min",
        "SpO2": "≥95%",
        "SBP": "90-120 mmHg",
        "Temp": "36.5-37.5°C"
    }
    return ranges.get(vital_name, "")

def show_patient_popup(patient_row):
    """Display detailed patient information in a popup modal"""

    # Calculate derived information
    full_name = format_patient_name(patient_row["Name"], int(patient_row["Age"]))
    dob = get_patient_age_and_dob(int(patient_row["Age"]))
    waiting_time = get_waiting_time(patient_row["LastUpdate"])

    # Create the popup modal
    with st.container():
        st.markdown("""
        <style>
            .patient-modal {
                background: white;
                border-radius: 12px;
                padding: 24px;
                border-left: 6px solid;
                margin-bottom: 20px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            }
            .patient-modal.critical {
                border-left-color: #dc3545;
                background-color: rgba(220, 53, 69, 0.02);
            }
            .patient-modal.high {
                border-left-color: #fd7e14;
                background-color: rgba(255, 193, 7, 0.02);
            }
            .patient-modal.watch {
                border-left-color: #0d6efd;
                background-color: rgba(13, 110, 253, 0.02);
            }
            .patient-modal.stable {
                border-left-color: #198754;
                background-color: rgba(25, 135, 84, 0.02);
            }
            .patient-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
                padding-bottom: 16px;
                border-bottom: 2px solid #e9ecef;
            }
            .patient-name {
                font-size: 22px;
                font-weight: 700;
                margin: 0;
            }
            .patient-id {
                font-size: 14px;
                color: #666;
                font-weight: 500;
                margin: 4px 0 0 0;
            }
            .patient-status {
                display: inline-block;
                padding: 6px 14px;
                border-radius: 20px;
                font-weight: 600;
                font-size: 13px;
            }
            .status-critical {
                background-color: #dc3545;
                color: white;
            }
            .status-high {
                background-color: #fd7e14;
                color: white;
            }
            .status-watch {
                background-color: #0d6efd;
                color: white;
            }
            .status-stable {
                background-color: #198754;
                color: white;
            }
            .info-grid {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 20px;
                margin-bottom: 24px;
            }
            .info-section {
                padding: 16px;
                background-color: #f8f9fa;
                border-radius: 8px;
            }
            .info-label {
                font-size: 12px;
                font-weight: 600;
                color: #666;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 6px;
            }
            .info-value {
                font-size: 16px;
                font-weight: 600;
                color: #1a1a1a;
                margin-bottom: 12px;
            }
            .vital-grid {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 16px;
                margin-top: 20px;
            }
            .vital-card {
                padding: 16px;
                background-color: white;
                border: 2px solid #e9ecef;
                border-radius: 8px;
                text-align: center;
            }
            .vital-card.abnormal {
                border-color: #dc3545;
                background-color: rgba(220, 53, 69, 0.05);
            }
            .vital-name {
                font-size: 12px;
                font-weight: 600;
                color: #666;
                text-transform: uppercase;
                margin-bottom: 8px;
            }
            .vital-value {
                font-size: 20px;
                font-weight: 700;
                color: #1a1a1a;
                margin-bottom: 4px;
            }
            .vital-value.abnormal {
                color: #dc3545;
            }
            .vital-range {
                font-size: 11px;
                color: #999;
            }
            .close-btn {
                background: none;
                border: none;
                font-size: 24px;
                cursor: pointer;
                color: #666;
                padding: 0;
                margin: 0;
            }
            .close-btn:hover {
                color: #1a1a1a;
            }
        </style>
        """, unsafe_allow_html=True)

        # Determine status color
        status = patient_row["Status"]
        if "Critical" in status:
            status_class = "critical"
            badge_class = "status-critical"
        elif "High" in status:
            status_class = "high"
            badge_class = "status-high"
        elif "Watch" in status:
            status_class = "watch"
            badge_class = "status-watch"
        else:
            status_class = "stable"
            badge_class = "status-stable"

        # Header with patient name, ID, and status
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"""
            <div class="patient-header">
                <div>
                    <p class="patient-name">{patient_row['StatusIcon']} {full_name}</p>
                    <p class="patient-id">ID: {patient_row['PatientID']}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div style="text-align: right;">
                <span class="patient-status {badge_class}">{patient_row['Status']}</span>
                <div style="margin-top: 8px; font-size: 13px; color: #666; font-weight: 500;">
                    Risk: {int(patient_row['RiskScore'])} {trend_symbol(int(patient_row['Trend']))}
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Patient demographics
        st.markdown("#### 👤 Patient Demographics")
        demo_col1, demo_col2, demo_col3, demo_col4 = st.columns(4)

        with demo_col1:
            st.markdown(f"""
            <div class="info-section">
                <div class="info-label">Date of Birth</div>
                <div class="info-value">{dob}</div>
            </div>
            """, unsafe_allow_html=True)

        with demo_col2:
            st.markdown(f"""
            <div class="info-section">
                <div class="info-label">Age</div>
                <div class="info-value">{int(patient_row['Age'])} years</div>
            </div>
            """, unsafe_allow_html=True)

        with demo_col3:
            st.markdown(f"""
            <div class="info-section">
                <div class="info-label">Waiting Time</div>
                <div class="info-value">{waiting_time}</div>
            </div>
            """, unsafe_allow_html=True)

        with demo_col4:
            st.markdown(f"""
            <div class="info-section">
                <div class="info-label">Last Update</div>
                <div class="info-value">{pd.to_datetime(patient_row['LastUpdate']).strftime('%H:%M:%S')}</div>
            </div>
            """, unsafe_allow_html=True)

        # Chief complaint and location
        st.markdown("#### 🏥 Chief Complaint & Location")
        complaint_col1, complaint_col2, complaint_col3 = st.columns([2, 1, 1])

        with complaint_col1:
            st.markdown(f"""
            <div class="info-section">
                <div class="info-label">Chief Complaint</div>
                <div class="info-value">{patient_row['Complaint']}</div>
            </div>
            """, unsafe_allow_html=True)

        with complaint_col2:
            st.markdown(f"""
            <div class="info-section">
                <div class="info-label">Location</div>
                <div class="info-value">{patient_row['Location']}</div>
            </div>
            """, unsafe_allow_html=True)

        with complaint_col3:
            st.markdown(f"""
            <div class="info-section">
                <div class="info-label">Triage Level</div>
                <div class="info-value">{patient_row['Triage']}</div>
            </div>
            """, unsafe_allow_html=True)

        # AVPU Assessment
        avpu_status = patient_row['AVPU']
        avpu_desc = {"A": "Alert", "V": "Verbal", "P": "Pain", "U": "Unresponsive"}[avpu_status]
        avpu_color = "#198754" if avpu_status == "A" else "#fd7e14" if avpu_status == "V" else "#dc3545"

        st.markdown("#### 🧠 Consciousness Level")
        st.markdown(f"""
        <div style="padding: 16px; background-color: #f8f9fa; border-radius: 8px; border-left: 4px solid {avpu_color};">
            <div style="font-size: 12px; color: #666; text-transform: uppercase; font-weight: 600; margin-bottom: 6px;">AVPU Score</div>
            <div style="font-size: 18px; font-weight: 700; color: {avpu_color};">{avpu_status} - {avpu_desc}</div>
        </div>
        """, unsafe_allow_html=True)

        # Vital Signs Grid
        st.markdown("#### 🫀 Vital Signs")

        vital_col1, vital_col2, vital_col3 = st.columns(3)

        vitals_data = [
            ("HR", "Heart Rate", f"{int(patient_row['HR'])}", "bpm", (60, 100)),
            ("RR", "Respiratory Rate", f"{int(patient_row['RR'])}", "br/min", (12, 20)),
            ("SpO2", "Oxygen Saturation", f"{int(patient_row['SpO2'])}", "%", (95, 100)),
            ("SBP", "Systolic BP", f"{int(patient_row['SBP'])}", "mmHg", (90, 120)),
            ("Temp", "Temperature", f"{float(patient_row['Temp']):.1f}", "°C", (36.5, 37.5)),
            ("AVPU", "Status", avpu_desc, "", (None, None))
        ]

        columns = [vital_col1, vital_col2, vital_col3]
        for idx, (code, name, value, unit, (min_val, max_val)) in enumerate(vitals_data[:3]):
            col = columns[idx % 3]

            # Check if abnormal
            is_abnormal = False
            if min_val is not None and max_val is not None:
                try:
                    val_float = float(value)
                    is_abnormal = val_float < min_val or val_float > max_val
                except:
                    pass

            abnormal_class = " abnormal" if is_abnormal else ""
            abnormal_color = "color: #dc3545;" if is_abnormal else ""

            with col:
                st.markdown(f"""
                <div class="vital-card{abnormal_class}">
                    <div class="vital-name">{code}</div>
                    <div class="vital-value{abnormal_class}" style="{abnormal_color}">{value} {unit}</div>
                    <div class="vital-range">{min_val}-{max_val} {unit if min_val else ''}</div>
                </div>
                """, unsafe_allow_html=True)

        vital_col4, vital_col5, vital_col6 = st.columns(3)

        for idx, (code, name, value, unit, (min_val, max_val)) in enumerate(vitals_data[3:]):
            col = [vital_col4, vital_col5, vital_col6][idx]

            # Check if abnormal
            is_abnormal = False
            if min_val is not None and max_val is not None:
                try:
                    val_float = float(value)
                    is_abnormal = val_float < min_val or val_float > max_val
                except:
                    pass

            abnormal_class = " abnormal" if is_abnormal else ""
            abnormal_color = "color: #dc3545;" if is_abnormal else ""

            with col:
                st.markdown(f"""
                <div class="vital-card{abnormal_class}">
                    <div class="vital-name">{code}</div>
                    <div class="vital-value{abnormal_color}" style="{abnormal_color}">{value} {unit}</div>
                    <div class="vital-range">{min_val}-{max_val} {unit if min_val else ''}</div>
                </div>
                """, unsafe_allow_html=True)

        # Risk Assessment
        st.markdown("#### ⚠️ Risk Assessment")
        risk_score = int(patient_row['RiskScore'])
        trend = int(patient_row['Trend'])

        risk_text = {
            0: "Stable - No significant concerns",
            1: "Low Risk - Monitor",
            2: "Watch - Concerning signs",
            3: "Watch - Close monitoring",
            4: "High - Urgent attention",
            5: "High - Immediate attention",
            6: "High - Immediate intervention",
            7: "Critical - Emergency intervention",
            8: "Critical - Life-threatening",
            9: "Critical - Severe condition",
            10: "Critical - Emergency resuscitation"
        }

        trend_text = {
            -2: "🟢 Significant Improvement",
            -1: "🟢 Improving",
            0: "🟡 Stable",
            1: "🟠 Deteriorating",
            2: "🔴 Rapid Deterioration"
        }

        risk_col1, risk_col2 = st.columns(2)

        with risk_col1:
            risk_color = "#198754" if risk_score < 2 else "#0d6efd" if risk_score < 4 else "#fd7e14" if risk_score < 7 else "#dc3545"
            st.markdown(f"""
            <div style="padding: 16px; background-color: #f8f9fa; border-radius: 8px; border-left: 4px solid {risk_color};">
                <div style="font-size: 12px; color: #666; text-transform: uppercase; font-weight: 600; margin-bottom: 6px;">Risk Score</div>
                <div style="font-size: 28px; font-weight: 700; color: {risk_color}; margin-bottom: 8px;">{risk_score}/10</div>
                <div style="font-size: 14px; color: #1a1a1a;">{risk_text.get(min(risk_score, 10), 'Unknown')}</div>
            </div>
            """, unsafe_allow_html=True)

        with risk_col2:
            trend_color = "#198754" if trend <= -1 else "#0d6efd" if trend == 0 else "#fd7e14" if trend == 1 else "#dc3545"
            st.markdown(f"""
            <div style="padding: 16px; background-color: #f8f9fa; border-radius: 8px; border-left: 4px solid {trend_color};">
                <div style="font-size: 12px; color: #666; text-transform: uppercase; font-weight: 600; margin-bottom: 6px;">Trend</div>
                <div style="font-size: 20px; font-weight: 700; color: {trend_color}; margin-bottom: 8px;">{trend_text.get(trend, 'Unknown')}</div>
                <div style="font-size: 14px; color: #1a1a1a;">Score change: {'+' if trend > 0 else ''}{trend} points</div>
            </div>
            """, unsafe_allow_html=True)

def status_from_score(score):
    if score >= 7:
        return "Critical", "🔴"
    if score >= 4:
        return "High", "🟠"
    if score >= 2:
        return "Watch", "🟡"
    return "Stable", "🟢"

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
    elif 12 <= rr <= 20:
        score += 0
    else:
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
        delta = score - prev_row.get("RiskScore", 0)
        if delta >= 2:
            trend = 2
        elif delta == 1:
            trend = 1
        elif delta <= -2:
            trend = -2
        elif delta == -1:
            trend = -1

    return score, trend

def make_initial_patients(n=12, seed=7):
    rng = np.random.default_rng(seed)
    names = ["Alex", "Mina", "Jordan", "Sam", "Taylor", "Chris", "Ava", "Noah", "Ivy", "Leo", "Zoe", "Omar", "Nina", "Eli", "Maya", "Sophie", "Marcus", "Isabella", "James", "Emma", "Liam", "Olivia", "Benjamin", "Amelia", "Lucas", "Harper", "Mason", "Evelyn", "Logan", "Abigail", "Ethan", "Charlotte", "Aiden", "Mia", "Jackson", "Aria", "Sebastian", "Scarlett"]
    complaints = ["Chest pain", "Shortness of breath", "Abdominal pain", "Fever", "Headache", "Fall injury", "Dizziness", "Weakness", "Allergic reaction", "Nausea/vomiting"]
    triage = ["CTAS 2", "CTAS 3", "CTAS 4", "CTAS 5"]
    locations = ["Waiting A", "Waiting B", "Hallway", "Overflow"]

    rows = []
    base_time = now_ts()

    for i in range(n):
        # Age-based realistic distributions
        age = int(clamp(rng.normal(52, 20), 18, 92))

        # Heart Rate: Mean varies by severity, realistic range 50-140
        # Normal: 60-100, tachycardia >100, bradycardia <60
        hr_mean = rng.choice([75, 88, 105, 120], p=[0.40, 0.35, 0.15, 0.10])
        hr = int(clamp(rng.normal(hr_mean, 12), 45, 145))

        # Respiratory Rate: Mean 14-16 normal, elevated with distress
        # Normal: 12-20, elevated: 21-25, critical: >25 or <8
        rr_mean = rng.choice([15, 18, 22, 26], p=[0.45, 0.30, 0.15, 0.10])
        rr = int(clamp(rng.normal(rr_mean, 3), 8, 35))

        # SpO2: High baseline (most ED patients have adequate O2)
        # Normal: >=95%, mild hypoxia: 90-94%, severe: <90%
        spo2_mean = rng.choice([98, 96, 92, 88], p=[0.50, 0.30, 0.15, 0.05])
        spo2 = int(clamp(rng.normal(spo2_mean, 2.5), 82, 100))

        # Systolic BP: Age and severity dependent
        # Normal: 90-120, elevated: 121-139, hypertensive: 140+, hypotensive: <90
        age_factor = (age - 50) / 10  # Older patients tend toward higher BP
        sbp_mean = rng.choice([115, 128, 142, 155], p=[0.40, 0.35, 0.15, 0.10])
        sbp_mean = max(90, min(160, sbp_mean + age_factor * 3))  # Age-adjusted
        sbp = int(clamp(rng.normal(sbp_mean, 15), 70, 190))

        # Temperature: Mostly normal, some fever, few hypothermia
        # Normal: 36.5-37.5, low-grade fever: 37.6-38.5, fever: 38.6-39.5, critical: >39.5
        temp_mean = rng.choice([37.0, 37.8, 38.5, 39.2], p=[0.65, 0.20, 0.10, 0.05])
        temp = round(float(clamp(rng.normal(temp_mean, 0.5), 35.0, 40.5)), 1)

        rows.append({
            "PatientID": f"P{i+1:03d}",
            "Name": rng.choice(names),
            "Age": age,
            "Triage": rng.choice(triage, p=[0.12, 0.45, 0.33, 0.10]),
            "Location": rng.choice(locations, p=[0.42, 0.30, 0.18, 0.10]),
            "Complaint": rng.choice(complaints),
            "HR": hr,
            "RR": rr,
            "SpO2": spo2,
            "SBP": sbp,
            "Temp": temp,
            "AVPU": "A",
            "LastUpdate": base_time
        })

    df = pd.DataFrame(rows)
    df["RiskScore"] = 0
    df["Trend"] = 0
    df["Status"] = ""
    df["StatusIcon"] = ""
    return df

def simulate_next(df, rng, deterioration_bias=0.22):
    out = df.copy()
    out["LastUpdate"] = now_ts()

    for idx in out.index:
        t = out.loc[idx, "Triage"]
        base_risk = {"CTAS 2": 0.35, "CTAS 3": 0.22, "CTAS 4": 0.13, "CTAS 5": 0.08}[t]
        p_det = clamp(base_risk + deterioration_bias * 0.25, 0.05, 0.65)

        deteriorate = rng.random() < p_det
        improve = (not deteriorate) and (rng.random() < 0.08)

        hr = out.loc[idx, "HR"]
        rr = out.loc[idx, "RR"]
        spo2 = out.loc[idx, "SpO2"]
        sbp = out.loc[idx, "SBP"]
        temp = out.loc[idx, "Temp"]

        if deteriorate:
            # Realistic deterioration patterns
            # HR increases (stress response, compensation)
            hr += int(rng.integers(2, 8))
            # RR increases (compensation for hypoxia or distress)
            rr += int(rng.integers(1, 4))
            # SpO2 decreases (respiratory/cardiac issues)
            spo2 -= int(rng.integers(1, 4))
            # SBP decreases (shock/hemodynamic compromise) or increases (pain/stress)
            sbp_change = rng.choice([-8, -5, -2, 2, 5], p=[0.10, 0.20, 0.20, 0.30, 0.20])
            sbp += sbp_change
            # Temp usually increases slowly with infection/sepsis
            temp += float(rng.choice([0.0, 0.1, 0.2, 0.3], p=[0.30, 0.40, 0.20, 0.10]))
            # Small chance of altered consciousness
            if rng.random() < 0.02:
                out.loc[idx, "AVPU"] = rng.choice(["V", "P"], p=[0.7, 0.3])
        elif improve:
            # Realistic improvement patterns
            # HR decreases (normalization)
            hr -= int(rng.integers(1, 5))
            # RR decreases (better oxygenation/relaxation)
            rr -= int(rng.integers(0, 3))
            # SpO2 increases (treatment response)
            spo2 += int(rng.integers(0, 2))
            # SBP stabilizes/improves
            sbp += int(rng.integers(1, 6))
            # Temp decreases slightly if fever present
            temp -= float(rng.choice([0.0, 0.1, 0.2], p=[0.50, 0.35, 0.15]))

        # Small random fluctuations (realistic normal variation)
        if not deteriorate and not improve:
            hr += int(rng.integers(-2, 3))
            rr += int(rng.integers(-1, 2))
            spo2 += int(rng.integers(-1, 2))
            sbp += int(rng.integers(-3, 4))
            temp += float(rng.choice([-0.1, 0.0, 0.1], p=[0.25, 0.50, 0.25]))

        # Apply realistic bounds
        out.loc[idx, "HR"] = int(clamp(hr, 40, 160))
        out.loc[idx, "RR"] = int(clamp(rr, 6, 40))
        out.loc[idx, "SpO2"] = int(clamp(spo2, 80, 100))
        out.loc[idx, "SBP"] = int(clamp(sbp, 60, 200))
        out.loc[idx, "Temp"] = round(float(clamp(temp, 35.0, 40.5)), 1)

    return out

def ensure_state():
    if "rng" not in st.session_state:
        st.session_state.rng = np.random.default_rng(13)
    if "patients" not in st.session_state:
        st.session_state.patients = make_initial_patients(n=12, seed=7)
    if "prev_patients" not in st.session_state:
        st.session_state.prev_patients = st.session_state.patients.copy()
    if "alerts" not in st.session_state:
        st.session_state.alerts = []
    if "ack" not in st.session_state:
        st.session_state.ack = set()
    if "selected_patient" not in st.session_state:
        st.session_state.selected_patient = None

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

def update_and_score(deterioration_bias):
    prev = st.session_state.patients.copy()
    nxt = simulate_next(prev, st.session_state.rng, deterioration_bias=deterioration_bias)

    scored = nxt.copy()
    for idx in scored.index:
        row = scored.loc[idx].to_dict()
        prev_row = prev.loc[idx].to_dict()
        score, trend = compute_risk(row, prev_row=prev_row)
        status, icon = status_from_score(score)
        scored.loc[idx, "RiskScore"] = score
        scored.loc[idx, "Trend"] = trend
        scored.loc[idx, "Status"] = status
        scored.loc[idx, "StatusIcon"] = icon

    new_alerts = []
    for idx in scored.index:
        pid = scored.loc[idx, "PatientID"]
        score = int(scored.loc[idx, "RiskScore"])
        trend = int(scored.loc[idx, "Trend"])
        status = scored.loc[idx, "Status"]
        if pid in st.session_state.ack:
            continue
        if score >= 7:
            new_alerts.append((pid, status, score, trend, "Critical risk score"))
        elif trend >= 2:
            new_alerts.append((pid, status, score, trend, "Rapid deterioration"))

    ts = now_ts()
    for (pid, status, score, trend, reason) in new_alerts:
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
    table["Trend"] = table["Trend"].apply(lambda x: f"{trend_symbol(int(x))} ({int(x)})")
    table["Status"] = table.apply(lambda r: f"{r['StatusIcon']} {r['Status']}", axis=1)
    table["LastUpdate"] = pd.to_datetime(table["LastUpdate"]).dt.strftime("%H:%M:%S")
    table["Temp"] = table["Temp"].apply(lambda x: f"{float(x):.1f}")

    # Format vitals with better display
    table["HR"] = table["HR"].apply(lambda x: f"{int(x)}")
    table["RR"] = table["RR"].apply(lambda x: f"{int(x)}")
    table["SBP"] = table["SBP"].apply(lambda x: f"{int(x)}")
    table["SpO2"] = table["SpO2"].apply(lambda x: f"{int(x)}%")

    cols = ["PatientID", "Name", "Age", "Triage", "Location", "Status", "RiskScore", "Trend", "SpO2", "RR", "HR", "SBP", "Temp", "AVPU", "LastUpdate", "Complaint"]
    return table[cols]

def style_patient_table(df):
    def row_style(row):
        status = row["Status"]
        score = row["RiskScore"]
        if "Critical" in status or score >= 7:
            return ["background-color: rgba(220, 53, 69, 0.18); font-weight: 600;"] * len(row)
        if "High" in status or score >= 4:
            return ["background-color: rgba(255, 193, 7, 0.14); font-weight: 500;"] * len(row)
        if "Watch" in status or score >= 2:
            return ["background-color: rgba(13, 110, 253, 0.08);"] * len(row)
        return [""] * len(row)

    def col_style(col):
        styles = []
        for val in col:
            # Highlight abnormal vitals
            try:
                val_float = float(str(val).split()[0])
                if col.name == "HR" and (val_float < 60 or val_float > 100):
                    styles.append("color: #dc3545; font-weight: 700;")
                elif col.name == "RR" and (val_float < 12 or val_float > 20):
                    styles.append("color: #dc3545; font-weight: 700;")
                elif col.name == "SpO2" and val_float < 95:
                    styles.append("color: #dc3545; font-weight: 700;")
                elif col.name == "SBP" and (val_float < 90 or val_float > 120):
                    styles.append("color: #dc3545; font-weight: 700;")
                elif col.name == "Temp" and (val_float < 36.5 or val_float > 37.5):
                    styles.append("color: #dc3545; font-weight: 700;")
                else:
                    styles.append("")
            except:
                styles.append("")
        return styles

    return df.style.apply(row_style, axis=1).apply(col_style)

ensure_state()


with st.sidebar:
    st.markdown("### ⚙️ Dashboard Controls")
    refresh_sec = st.slider("Auto-refresh (sec)", 3, 20, 6, 1)
    deterioration_bias = st.slider("Simulation intensity", 0.0, 0.8, 0.22, 0.01)

    st.divider()

    st.markdown("### 🔍 Filters & Search")
    q = st.text_input("Search by ID / name / complaint", placeholder="Type here...", label_visibility="collapsed")

    st.markdown("**Status**")
    statuses = st.multiselect("Select statuses", ["Critical", "High", "Watch", "Stable"], ["Critical", "High", "Watch", "Stable"], label_visibility="collapsed")

    st.markdown("**Triage Level**")
    triage_filter = st.multiselect("Select triage", ["CTAS 2", "CTAS 3", "CTAS 4", "CTAS 5"], ["CTAS 2", "CTAS 3", "CTAS 4", "CTAS 5"], label_visibility="collapsed")

    st.markdown("**Location**")
    locations = sorted(st.session_state.patients["Location"].unique().tolist())
    location_filter = st.multiselect("Select locations", locations, locations, label_visibility="collapsed")

    st.markdown("**Sort By**")
    sort_key = st.selectbox("Sort patients by", ["Priority (RiskScore)", "SpO2 (lowest)", "Last update", "Triage"], index=0, label_visibility="collapsed")

    st.divider()

    st.markdown("### 📋 Alert Rules")
    st.markdown("""
    - **🔴 Critical**: RiskScore ≥ 7
    - **🟠 High**: RiskScore ≥ 4
    - **🟡 Watch**: RiskScore ≥ 2
    - **🟢 Stable**: RiskScore < 2
    
    Deterioration alert: Score jump ≥ 2 points
    """)

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

if sort_key == "Priority (RiskScore)":
    df = df.sort_values(["RiskScore", "Triage"], ascending=[False, True])
elif sort_key == "SpO2 (lowest)":
    df = df.sort_values(["SpO2", "RiskScore"], ascending=[True, False])
elif sort_key == "Last update":
    df = df.sort_values(["LastUpdate"], ascending=[False])
else:
    df = df.sort_values(["Triage", "RiskScore"], ascending=[True, False])

counts = st.session_state.patients["Status"].value_counts().to_dict()
crit = int(counts.get("Critical", 0))
high = int(counts.get("High", 0))
watch = int(counts.get("Watch", 0))
stable = int(counts.get("Stable", 0))

alerts_df = pd.DataFrame(st.session_state.alerts[:50])
if not alerts_df.empty:
    alerts_df = alerts_df[~alerts_df["PatientID"].isin(list(st.session_state.ack))]
unacked = 0 if alerts_df.empty else int(len(alerts_df))

# Status overview with color coding
st.markdown("## Patient Status Overview")
col1, col2, col3, col4, col5 = st.columns(5)

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

with col5:
    alert_color = "#dc3545" if unacked > 0 else "#198754"
    alert_bg = "rgba(220, 53, 69, 0.1)" if unacked > 0 else "rgba(25, 135, 84, 0.1)"
    st.markdown(f"""
    <div style="background-color: {alert_bg}; padding: 20px; border-radius: 8px; border-left: 4px solid {alert_color}; text-align: center;">
        <div style="font-size: 24px; font-weight: 700; color: {alert_color};">{unacked}</div>
        <div style="font-size: 12px; color: #666; margin-top: 4px;">Unacked Alerts</div>
    </div>
    """, unsafe_allow_html=True)

tab_patients, tab_alerts, tab_selected = st.tabs(["Patients", "Alerts", "Selected patient"])

with tab_patients:
    st.markdown("### Patients in Waiting Area")

    # Display patient count and filter info
    col_info1, col_info2 = st.columns([2, 1])
    with col_info1:
        st.caption(f"📋 Showing {len(df)} of {len(st.session_state.patients)} patients")
    with col_info2:
        if st.button("Reset Filters", use_container_width=True):
            st.rerun()

    # Initialize expanded patients state
    if "expanded_patients" not in st.session_state:
        st.session_state.expanded_patients = set()

    table = build_patient_table(df)
    styled = style_patient_table(table)
    st.dataframe(styled, use_container_width=True, height=520)

    st.divider()
    st.markdown("### Quick Actions")

    ids = table["PatientID"].tolist()
    if ids:
        col_select, col_open, col_ack = st.columns([2, 1, 1])

        with col_select:
            pick = st.selectbox("Select patient", [""] + ids, index=0, label_visibility="collapsed")

        with col_open:
            if st.button("👁️ View Details", disabled=(pick == ""), use_container_width=True):
                st.session_state.selected_patient = pick
                st.rerun()

        with col_ack:
            if st.button("✓ Acknowledge", disabled=(pick == ""), use_container_width=True):
                st.session_state.ack.add(pick)
                st.success(f"Alerts for {pick} acknowledged")

        # Additional patient info popup button
        st.divider()
        st.markdown("### Patient Information")

        popup_col1, popup_col2 = st.columns([2, 1])

        with popup_col1:
            popup_pick = st.selectbox("View patient info", [""] + ids, index=0, label_visibility="collapsed", key="popup_select")

        with popup_col2:
            show_popup = st.button("ℹ️ Show Info", use_container_width=True)

        if show_popup and popup_pick:
            # Get full patient data
            full_patient = st.session_state.patients[st.session_state.patients["PatientID"] == popup_pick].iloc[0]

            # Create an expander for the patient info
            with st.expander(f"📋 {format_patient_name(full_patient['Name'], int(full_patient['Age']))} ({popup_pick})", expanded=True):
                show_patient_popup(full_patient)
    else:
        st.info("No patients match current filters.")

with tab_alerts:
    st.markdown("### Active Alerts & Notifications")
    if alerts_df.empty:
        st.success("✓ No unacknowledged alerts right now. Great job!")
    else:
        show = alerts_df.copy()
        show["Time"] = pd.to_datetime(show["Time"]).dt.strftime("%H:%M:%S")
        show = show[["Time", "PatientID", "Status", "RiskScore", "Trend", "Reason"]]

        # Display alerts with status color coding
        for idx, alert in alerts_df.iterrows():
            pid = alert["PatientID"]
            status = alert["Status"]
            score = int(alert["RiskScore"])
            reason = alert["Reason"]
            time = pd.to_datetime(alert["Time"]).strftime("%H:%M:%S")

            # Color based on status
            if "Critical" in status or score >= 7:
                color = "#dc3545"
                bg = "rgba(220, 53, 69, 0.1)"
            elif "High" in status or score >= 4:
                color = "#fd7e14"
                bg = "rgba(255, 193, 7, 0.1)"
            else:
                color = "#0d6efd"
                bg = "rgba(13, 110, 253, 0.1)"

            col1, col2, col3 = st.columns([3, 1, 1])

            with col1:
                st.markdown(f"""
                <div style="background-color: {bg}; padding: 12px; border-radius: 8px; border-left: 4px solid {color};">
                    <strong style="color: {color};">{pid}</strong> - {reason}<br/>
                    <small style="color: #666;">{time} | Risk: {score}</small>
                </div>
                """, unsafe_allow_html=True)

            with col2:
                if st.button("View", key=f"view_{pid}_{idx}", use_container_width=True):
                    st.session_state.selected_patient = pid
                    st.rerun()

            with col3:
                if st.button("✓ Ack", key=f"ack_{pid}_{idx}", use_container_width=True):
                    st.session_state.ack.add(pid)
                    st.rerun()

        st.divider()
        if st.button("Acknowledge All Alerts", use_container_width=True):
            for pid in alerts_df["PatientID"].unique():
                st.session_state.ack.add(pid)
            st.success("All alerts acknowledged!")
            st.rerun()

with tab_selected:
    st.markdown("### Selected Patient Detail")
    pid = st.session_state.selected_patient
    if not pid:
        st.info("📋 Select a patient from the Patients tab to view detailed information.")
    else:
        full = st.session_state.patients
        if (full["PatientID"] == pid).any():
            row = full[full["PatientID"] == pid].iloc[0]

            # Show patient info popup
            show_patient_popup(row)

            st.divider()

            # Action buttons
            action_cols = st.columns(3)
            with action_cols[0]:
                if st.button("✓ Acknowledge Alerts", key="ack_selected", use_container_width=True):
                    st.session_state.ack.add(pid)
                    st.success(f"Alerts for {pid} acknowledged")

            with action_cols[1]:
                if st.button("🔄 Refresh Data", key="refresh_selected", use_container_width=True):
                    st.rerun()

            with action_cols[2]:
                if st.button("✕ Clear Selection", key="clear_selected", use_container_width=True):
                    st.session_state.selected_patient = None
                    st.rerun()
        else:
            st.warning("⚠️ Selected patient not found (may be filtered out).")

st_autorefresh(interval=refresh_sec * 1000, key="auto_refresh")