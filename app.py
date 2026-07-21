import os, json, tempfile, subprocess, sys
import streamlit as st
import requests
import streamlit.components.v1 as components
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from shock_rate import predict_shock

# 頁籤圖示
st.set_page_config(
    page_title="SHIELD HRV",
    page_icon="🫀",
    layout="wide"
)

# =========================================
# UI Header
# =========================================

st.title("SHIELD")
st.caption("HRV Sepsis Early Warning System Powered by AI")
st.divider()

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

# =========================================
# Sidebar Input
# =========================================
with st.sidebar:
    st.header("SHIELD HRV")
    st.caption("FHIR Observation Input")

    token = st.text_input("Token", value=token_q, type="password")
    obs_url = st.text_input("Observation URL", value=obs_q)

    st.divider()
    st.caption("This app analyzes HRV features from FHIR observation data.")

# =========================================
# Patient Data Placeholder
# =========================================
patient_data_placeholder = st.empty()
with patient_data_placeholder.container():
    st.expander("Patient Data (Click to Expand)", expanded=False)

# =========================================
# Reset cache if token/obs_url changed (修正：補上 risk_status)
# =========================================
current_key = f"{token}||{obs_url}"
if "analysis_key" not in st.session_state:
    st.session_state.analysis_key = ""
if st.session_state.analysis_key != current_key:
    # 清掉舊資料，避免換病人仍顯示舊結果
    for k in [
        "analysis_done", "obs", "ecg_signal", "hrv_df", "preds",
        "risk_pct", "risk_label", "risk_color", "risk_status", "hr_signal"
    ]:
        if k in st.session_state:
            del st.session_state[k]
    st.session_state.analysis_key = current_key

# =========================================
# Auto Run Logic
# =========================================
if token and obs_url:

    # -----------------------------------------
    # Heavy pipeline: run ONCE
    # -----------------------------------------
    if "analysis_done" not in st.session_state:
        try:
            with st.spinner("Fetching Patient Data..."):
                obs = fetch_observation(token, obs_url)

            st.session_state.obs = obs

            with tempfile.TemporaryDirectory() as td:
                obs_path = os.path.join(td, "obs.json")
                ecg_csv  = os.path.join(td, "ECG_5min.csv")
                h0_csv   = os.path.join(td, "h0.csv")

                with open(obs_path, "w") as f:
                    json.dump(obs, f)

                # ----- Parse ECG -----
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

                # ----- Generate HRV Features -----
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

                # ----- Predict Shock Risk -----
                with st.spinner("Predicting shock risk..."):
                    preds = predict_shock(h0_csv)

            # ===== 存進 session_state =====
            st.session_state.ecg_signal = ecg_signal
            st.session_state.hrv_df = hrv_df
            st.session_state.preds = preds

            risk_pct = round(float(preds[0]) * 100, 2)
            if risk_pct < 20:
                risk_label = "LOW RISK"
                risk_color = "#2ecc71"
                risk_status = "success"
            elif risk_pct < 40:
                risk_label = "MODERATE RISK"
                risk_color = "#f39c12"
                risk_status = "warning"
            else:
                risk_label = "HIGH RISK"
                risk_color = "#e74c3c"
                risk_status = "error"

            st.session_state.risk_pct = risk_pct
            st.session_state.risk_label = risk_label
            st.session_state.risk_color = risk_color
            st.session_state.risk_status = risk_status  # 修正：確實寫入 Session
            st.session_state.analysis_done = True
            st.success("Analysis Completed Successfully!", icon="✅")

        except Exception as e:
            st.error(f"Pipeline failed: {e}")
            st.stop()

    # -----------------------------------------
    # Always show Patient Data (no heavy rerun)
    # -----------------------------------------
    with patient_data_placeholder.container():
        with st.expander("Patient Data (Click to Expand)", expanded=False):
            st.json(st.session_state.get("obs", {}))

    # -----------------------------------------
    # Risk Visualization (修正：安全地從 session_state 讀取)
    # -----------------------------------------
    risk_pct = st.session_state.risk_pct
    risk_label = st.session_state.risk_label
    risk_color = st.session_state.risk_color
    risk_status = st.session_state.risk_status
    
    with risk_placeholder.container():
        st.subheader("Predicted Shock Risk")

        left, right = st.columns([1, 1], gap="medium")

        with left:
            fig, ax = plt.subplots(figsize=(3.2, 1.8))
            theta = np.linspace(np.pi, 0, 120)

            ax.plot(np.cos(theta[:40]), np.sin(theta[:40]), linewidth=11, color="#16a34a", solid_capstyle="butt")
            ax.plot(np.cos(theta[39:80]), np.sin(theta[39:80]), linewidth=11, color="#f59e0b", solid_capstyle="butt")
            ax.plot(np.cos(theta[79:]), np.sin(theta[79:]), linewidth=11, color="#dc2626", solid_capstyle="butt")

            angle = np.pi * (1 - (risk_pct + 8) / 100)
            ax.plot([0, 0.52 * np.cos(angle)], [0, 0.52 * np.sin(angle)], linewidth=2.6, color="#1f2937")
            ax.scatter([0], [0], s=45, color="#1f2937")

            ax.text(-1.03, -0.16, "Low", fontsize=8, color="#64748b", ha="center")
            ax.text(1.03, -0.16, "High", fontsize=8, color="#64748b", ha="center")

            ax.set_xlim(-1.12, 1.12)
            ax.set_ylim(-0.22, 1.08)
            ax.axis("off")

            st.pyplot(fig)
            plt.close(fig)

        with right:
            st.caption("Risk Probability")

            st.markdown(
                f"""
                <div style="
                    font-size:40px;
                    font-weight:850;
                    line-height:1.1;
                    color:#1f2937;
                    margin-bottom:12px;
                ">
                    {risk_pct:.2f}%
                </div>
                """,
                unsafe_allow_html=True
            )

            # ---- 圓圈樣式不變，只改字的顏色 ----
            if risk_status == "success":
                st.markdown(
                    """
                    <div style="display: flex; align-items: center; margin-bottom: 16px;">
                        <div style="
                            width: 20px; 
                            height: 20px; 
                            background: radial-gradient(circle at 35% 35%, #76ff03, #32cb00); 
                            border-radius: 50%; 
                            box-shadow: 0 0 8px #4caf50, inset -2px -2px 6px rgba(0,0,0,0.3);
                            margin-right: 10px;
                        "></div>
                        <span style="font-size: 20px; font-weight: bold; color: #32cb00; letter-spacing: 0.5px;">LOW RISK</span>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            elif risk_status == "warning":
                st.markdown(
                    """
                    <div style="display: flex; align-items: center; margin-bottom: 16px;">
                        <div style="
                            width: 20px; 
                            height: 20px; 
                            background: radial-gradient(circle at 35% 35%, #ffb74d, #f57c00); 
                            border-radius: 50%; 
                            box-shadow: 0 0 8px #ff9800, inset -2px -2px 6px rgba(0,0,0,0.3);
                            margin-right: 10px;
                        "></div>
                        <span style="font-size: 20px; font-weight: bold; color: #f57c00; letter-spacing: 0.5px;">MODERATE RISK</span>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    """
                    <div style="display: flex; align-items: center; margin-bottom: 16px;">
                        <div style="
                            width: 20px; 
                            height: 20px; 
                            background: radial-gradient(circle at 35% 35%, #ff5252, #d32f2f); 
                            border-radius: 50%; 
                            box-shadow: 0 0 8px #f44336, inset -2px -2px 6px rgba(0,0,0,0.3);
                            margin-right: 10px;
                        "></div>
                        <span style="font-size: 20px; font-weight: bold; color: #d32f2f; letter-spacing: 0.5px;">HIGH RISK</span>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )

            st.caption(
                "This result is generated by the SHIELD HRV model and is intended "
                "for clinical decision-support reference only."
            )
        st.divider()

    # =========================================
    # ECG Input & HRV Features
    # =========================================
    with ecg_hrv_placeholder.container():
        st.subheader("ECG Input & HRV Features")
        st.caption("ECG signal preview and generated HRV feature values.")

        # ----- HR Plot -----
        try:
            ecg_signal = st.session_state.ecg_signal
            if "hr_signal" not in st.session_state:
                st.session_state.hr_signal = np.asarray(ecg_signal, dtype=float).ravel()

            hr = st.session_state.hr_signal
            n = len(hr)
            x = np.arange(n)

            start_idx = st.slider(
                "選擇觀測時間",
                min_value=0,
                max_value=max(0, n - 500),
                value=min(750, max(0, n - 500)),
                step=125,
                help="每前進 1 秒等於前進 125 個數據點"
            )

            window_size = 500
            end_idx = min(n, start_idx + window_size)

            current_start_sec = start_idx / 125
            current_end_sec = end_idx / 125
            
            start_min, start_sec = divmod(int(current_start_sec), 60)
            end_min, end_sec = divmod(int(current_end_sec), 60)
            
            st.info(
                f"**當前檢視時段：** {start_min:02d} 分 {start_sec:02d} 秒 ～ {end_min:02d} 分 {end_sec:02d} 秒 "
                f" （共 {current_start_sec:.1f} 秒 ～ {current_end_sec:.1f} 秒） \n\n"
                f"**底層數據索引：** 數據起點為 `#{start_idx}`，終點為 #{end_idx} （總長度：500 點）"
            )

            hr_win = hr[start_idx:end_idx]
            x_win = x[start_idx:end_idx]

            ymin, ymax = float(hr_win.min()), float(hr_win.max())
            if ymin == ymax:
                ymin -= 1
                ymax += 1
            pad = 0.05 * (ymax - ymin)

            fig, ax = plt.subplots(figsize=(10, 3))
            ax.plot(x_win, hr_win, linewidth=1, color="#0284c7") # 改為更清晰的臨床藍色
            ax.set_title("Heart Rate (index-based view of ECG)")
            ax.set_xlabel("Index (Sample Rate:125Hz)")
            ax.set_ylabel("Voltage (mV)")
            ax.set_xlim(start_idx, end_idx)
            ax.set_ylim(ymin - pad, ymax + pad)
            ax.grid(alpha=0.3)
            st.pyplot(fig)
            plt.close(fig)

        except Exception as e:
            st.warning(f"Failed to plot HR: {e}")

        # ----- HRV Features (修正：相容點號與底線) -----
        try:
            hrv_df = st.session_state.hrv_df
            st.markdown("### Generated HRV Features")

            # 修正防呆：同時支援點號與底線命名
            hrv_thresholds = {
                "Mean.rate":    {"label": "Mean.rate (平均心率)",    "type": "high", "limit": 90.0, "unit": "bpm", "msg": "心率偏高"},
                "Mean_rate":    {"label": "Mean.rate (平均心率)",    "type": "high", "limit": 90.0, "unit": "bpm", "msg": "心率偏高"},
                "SDNN":         {"label": "SDNN (心率變異標準差)",  "type": "low",  "limit": 30.0, "unit": "ms",  "msg": "自主神經調節變差"},
                "RMSSD":        {"label": "RMSSD (心率變異均方根)", "type": "low",  "limit": 25.0, "unit": "ms",  "msg": "副交感活性偏低"},
                "pNN50":        {"label": "pNN50 (五毫秒百分比)",   "type": "low",  "limit": 10.0, "unit": "%",   "msg": "心率變異度低"},
                "LF":           {"label": "LF (低頻功率)",          "type": "normal", "limit": None, "unit": "ms²", "msg": ""},
                "HF":           {"label": "HF (高頻功率)",          "type": "normal", "limit": None, "unit": "ms²", "msg": ""},
                "LF_HF_ratio":  {"label": "LF/HF ratio (交感平衡)", "type": "high", "limit": 2.0,  "unit": "",    "msg": "交感過度興奮"},
                "SD1":          {"label": "SD1 (短期心率變異)",      "type": "normal", "limit": None, "unit": "ms",  "msg": ""},
                "SD2":          {"label": "SD2 (長期心率變異)",      "type": "normal", "limit": None, "unit": "ms",  "msg": ""},
                "ApEn":         {"label": "ApEn (近似熵)",          "type": "normal", "limit": None, "unit": "",    "msg": ""}
            }

            row = hrv_df.iloc[0]
            feature_names = list(row.index)[:10]

            # 渲染前五個特徵
            cols1 = st.columns(5)
            for i in range(5):
                feat = feature_names[i]
                val = float(row[feat])
                with cols1[i]:
                    if feat in hrv_thresholds:
                        cfg = hrv_thresholds[feat]
                        delta_val = "正常範圍"
                        d_color = "normal"
                        if cfg["type"] == "high" and val > cfg["limit"]:
                            delta_val = f"🔺 +{val - cfg['limit']:.2f} {cfg['msg']}"
                            d_color = "inverse"
                        elif cfg["type"] == "low" and val < cfg["limit"]:
                            delta_val = f"🔻 -{cfg['limit'] - val:.2f} {cfg['msg']}"
                            d_color = "inverse"
                        st.metric(label=cfg["label"], value=f"{val:.2f} {cfg['unit']}", delta=delta_val, delta_color=d_color)
                    else:
                        st.metric(feat, f"{val:.3f}")

            # 渲染後五個特徵
            cols2 = st.columns(5)
            for i in range(5, 10):
                feat = feature_names[i]
                val = float(row[feat])
                with cols2[i - 5]:
                    if feat in hrv_thresholds:
                        cfg = hrv_thresholds[feat]
                        delta_val = "正常範圍"
                        d_color = "normal"
                        if cfg["type"] == "high" and val > cfg["limit"]:
                            delta_val = f"🔺 +{val - cfg['limit']:.2f} {cfg['msg']}"
                            d_color = "inverse"
                        elif cfg["type"] == "low" and val < cfg["limit"]:
                            delta_val = f"🔻 -{cfg['limit'] - val:.2f} {cfg['msg']}"
                            d_color = "inverse"
                        elif cfg["type"] == "normal":
                            delta_val = None
                            d_color = "normal"
                        st.metric(label=cfg["label"], value=f"{val:.2f} {cfg['unit']}", delta=delta_val, delta_color=d_color)
                    else:
                        st.metric(feat, f"{val:.3f}")

            st.markdown(
                "🔗 Reference of Features: "
                "[Biomedical Signal Processing and Control (2025)](https://doi.org/10.1016/j.bspc.2024.106854) \n\n"
            )

        except Exception as e:
            st.warning(f"Failed to render HRV features: {e}")

else:
    st.info("Please enter Token and Observation URL to start calculation")
