import os, json, tempfile, subprocess, sys
import streamlit as st
import requests
import streamlit.components.v1 as components
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from shock_rate import predict_shock


# =========================================
# Page Config
# =========================================
st.set_page_config(
    page_title="SHIELD HRV",
    page_icon="🫀",
    layout="wide"
)


# =========================================
# CSS
# =========================================
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }

    .main-header {
        background: linear-gradient(135deg, #12355b, #2563eb);
        padding: 22px 28px;
        border-radius: 18px;
        color: white;
        margin-bottom: 22px;
        box-shadow: 0 8px 22px rgba(15, 23, 42, 0.16);
    }

    .main-title {
        font-size: 30px;
        font-weight: 850;
        margin-bottom: 4px;
        letter-spacing: 0.5px;
    }

    .main-subtitle {
        font-size: 15px;
        color: #dbeafe;
    }

    .section-card {
        background: white;
        border-radius: 16px;
        padding: 20px 22px;
        margin-bottom: 18px;
        box-shadow: 0 4px 16px rgba(15, 23, 42, 0.08);
        border: 1px solid #e5e7eb;
    }

    .section-title {
        font-size: 20px;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 6px;
    }

    .section-desc {
        color: #64748b;
        font-size: 14px;
        line-height: 1.6;
    }

    .risk-card {
        background: white;
        border-radius: 18px;
        padding: 24px;
        text-align: center;
        border: 1px solid #e5e7eb;
        box-shadow: 0 4px 16px rgba(15, 23, 42, 0.08);
    }

    .risk-percent {
        font-size: 46px;
        font-weight: 900;
        margin: 8px 0 2px;
    }

    .risk-label {
        font-size: 20px;
        font-weight: 800;
        margin-bottom: 14px;
    }

    .notice-box {
        background: #eff6ff;
        border-left: 4px solid #2563eb;
        border-radius: 12px;
        padding: 13px 15px;
        color: #1e3a8a;
        font-size: 14px;
        line-height: 1.6;
        text-align: left;
        margin-top: 14px;
    }

    .small-muted {
        color: #64748b;
        font-size: 14px;
    }

    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        padding: 14px 12px;
        border-radius: 14px;
        box-shadow: 0 3px 12px rgba(15, 23, 42, 0.06);
    }

    div[data-testid="stMetricValue"] {
        font-size: 22px;
        font-weight: 800;
        color: #0f172a;
    }

    div[data-testid="stMetricLabel"] {
        color: #475569;
        font-weight: 700;
    }

    .stTextInput input {
        border-radius: 10px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================
# UI Header
# =========================================
st.markdown(
    """
    <div class="main-header">
        <div class="main-title">SHIELD</div>
        <div class="main-subtitle">
            HRV Sepsis Early Warning System Powered by AI
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

risk_placeholder = st.empty()
ecg_hrv_placeholder = st.empty()

qp = st.experimental_get_query_params()
token_q = qp.get("token", [""])[0]
obs_q = qp.get("obs", [""])[0]


# =========================================
# Check Models
# =========================================
@st.cache_resource
def _check_models_exist():
    assert os.path.exists("models/model_focalloss.h5"), "Missing models/model_focalloss.h5"
    assert os.path.exists("models/xgb_model.json"), "Missing models/xgb_model.json"


_check_models_exist()


# =========================================
# FHIR Fetch
# =========================================
def fetch_observation(token, obs_url):
    r = requests.get(
        obs_url,
        headers={"Authorization": f"Bearer {token}"},
        verify=False,
        timeout=20
    )
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=600)
def fetch_observation_cached(token, obs_url):
    return fetch_observation(token, obs_url)


# =========================================
# Sidebar Input
# =========================================
with st.sidebar:
    st.markdown("### SHIELD HRV")
    st.caption("FHIR Observation Input")

    token = st.text_input("Token", value=token_q, type="password")
    obs_url = st.text_input("Observation URL", value=obs_q)

    st.markdown("---")
    st.caption("This app analyzes HRV features from FHIR observation data.")


# =========================================
# Patient Data Placeholder
# =========================================
patient_data_placeholder = st.empty()


# =========================================
# Reset cache if token/obs_url changed
# =========================================
current_key = f"{token}||{obs_url}"

if "analysis_key" not in st.session_state:
    st.session_state.analysis_key = ""

if st.session_state.analysis_key != current_key:
    for k in [
        "analysis_done", "obs", "ecg_signal", "hrv_df", "preds",
        "risk_pct", "risk_label", "risk_color", "hr_signal"
    ]:
        if k in st.session_state:
            del st.session_state[k]

    st.session_state.analysis_key = current_key


# =========================================
# Auto Run Logic
# =========================================
if token and obs_url:

    if "analysis_done" not in st.session_state:
        try:
            with st.spinner("Fetching Patient Data..."):
                obs = fetch_observation_cached(token, obs_url)

            st.session_state.obs = obs

            with tempfile.TemporaryDirectory() as td:
                obs_path = os.path.join(td, "obs.json")
                ecg_csv = os.path.join(td, "ECG_5min.csv")
                h0_csv = os.path.join(td, "h0.csv")

                with open(obs_path, "w") as f:
                    json.dump(obs, f)

                with st.spinner("Parsing ECG..."):
                    proc = subprocess.run(
                        [sys.executable, "parse_fhir_ecg_to_csv.py", obs_path, ecg_csv],
                        capture_output=True,
                        text=True
                    )

                    if proc.returncode != 0:
                        raise RuntimeError(proc.stderr or "parse_fhir_ecg_to_csv.py failed")

                    if not os.path.exists(ecg_csv):
                        raise RuntimeError("ECG CSV not created by parse_fhir_ecg_to_csv.py")

                    ecg_df = pd.read_csv(ecg_csv, header=None)

                    ecg_signal = (
                        pd.to_numeric(ecg_df.iloc[:, 0], errors="coerce")
                        .dropna()
                        .to_numpy(dtype=float)
                        .ravel()
                    )

                    if ecg_signal.size == 0:
                        raise RuntimeError("ECG signal is empty after parsing")

                with st.spinner("Generating HRV features..."):
                    proc = subprocess.run(
                        [sys.executable, "generate_HRV_10_features.py", ecg_csv, h0_csv],
                        capture_output=True,
                        text=True
                    )

                    if proc.returncode != 0:
                        raise RuntimeError(proc.stderr or "generate_HRV_10_features.py failed")

                    h0_json = proc.stdout.splitlines()[-1]
                    hrv_df = pd.read_json(h0_json, orient="records")

                with st.spinner("Predicting shock risk..."):
                    preds = predict_shock(h0_csv)

            st.session_state.ecg_signal = ecg_signal
            st.session_state.hrv_df = hrv_df
            st.session_state.preds = preds

            risk_pct = round(float(preds[0]) * 100, 2)

            if risk_pct < 20:
                risk_label = "LOW RISK"
                risk_color = "#16a34a"
            elif risk_pct < 40:
                risk_label = "MODERATE RISK"
                risk_color = "#f59e0b"
            else:
                risk_label = "HIGH RISK"
                risk_color = "#dc2626"

            st.session_state.risk_pct = risk_pct
            st.session_state.risk_label = risk_label
            st.session_state.risk_color = risk_color
            st.session_state.analysis_done = True

            st.success("Analysis completed.")

        except Exception as e:
            st.error(f"Pipeline failed: {e}")
            st.stop()

    # =========================================
    # Patient Data
    # =========================================
    with patient_data_placeholder.container():
        with st.expander("Patient Data", expanded=False):
            st.json(st.session_state.get("obs", {}))

    # =========================================
    # Risk Visualization
    # =========================================
    risk_pct = st.session_state.risk_pct
    risk_label = st.session_state.risk_label
    risk_color = st.session_state.risk_color

    with risk_placeholder.container():
        st.markdown(
            """
            <div class="section-card">
                <div class="section-title">Shock Risk Prediction</div>
                <div class="section-desc">
                    Prediction result generated from HRV features extracted from the selected ECG observation.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            f"""
            <div class="risk-card">
                <div class="small-muted">Predicted Risk</div>
                <div class="risk-percent" style="color:{risk_color};">
                    {risk_pct:.2f}%
                </div>
                <div class="risk-label" style="color:{risk_color};">
                    {risk_label}
                </div>
                <div class="notice-box">
                    This result is generated by the SHIELD HRV model and is intended
                    for decision-support reference only.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # =========================================
    # ECG Input & HRV Features
    # =========================================
    with ecg_hrv_placeholder.container():
        st.markdown(
            """
            <div class="section-card">
                <div class="section-title">ECG Input & HRV Features</div>
                <div class="section-desc">
                    ECG signal preview and generated HRV feature values.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        try:
            ecg_signal = st.session_state.ecg_signal

            if "hr_signal" not in st.session_state:
                st.session_state.hr_signal = np.asarray(ecg_signal, dtype=float).ravel()

            hr = st.session_state.hr_signal
            n = len(hr)
            x = np.arange(n)

            start_idx = st.slider(
                "View start index",
                min_value=0,
                max_value=max(0, n - 500),
                value=min(750, max(0, n - 50)),
                step=1
            )

            window_size = 500
            end_idx = min(n, start_idx + window_size)

            hr_win = hr[start_idx:end_idx]
            x_win = x[start_idx:end_idx]

            ymin, ymax = float(hr_win.min()), float(hr_win.max())

            if ymin == ymax:
                ymin -= 1
                ymax += 1

            pad = 0.05 * (ymax - ymin)

            fig, ax = plt.subplots(figsize=(10, 3))
            ax.plot(x_win, hr_win, linewidth=1)
            ax.set_title("Heart Rate / ECG Signal Preview")
            ax.set_xlabel("Index (Sample Rate: 125Hz)")
            ax.set_ylabel("Voltage (mV)")
            ax.set_xlim(start_idx, end_idx)
            ax.set_ylim(ymin - pad, ymax + pad)
            ax.grid(alpha=0.3)

            st.pyplot(fig)
            plt.close(fig)

        except Exception as e:
            st.warning(f"Failed to plot HR: {e}")

        try:
            hrv_df = st.session_state.hrv_df

            st.markdown("### Generated HRV Features")

            row = hrv_df.iloc[0]
            feature_names = list(row.index)[:10]
            feature_values = row.values[:10]

            cols1 = st.columns(5)
            for i in range(5):
                with cols1[i]:
                    st.metric(feature_names[i], f"{feature_values[i]:.3f}")

            cols2 = st.columns(5)
            for i in range(5, 10):
                with cols2[i - 5]:
                    st.metric(feature_names[i], f"{feature_values[i]:.3f}")

            st.markdown(
                "🔗 Reference of Features: "
                "[https://doi.org/10.1016/j.bspc.2024.106854]"
                "(https://doi.org/10.1016/j.bspc.2024.106854)"
            )

        except Exception as e:
            st.warning(f"Failed to render HRV features: {e}")

else:
    st.info("Please enter Token and Observation URL to start calculation.")
