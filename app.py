<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8" />
  <title>SHIELD HRV Risk Prediction System</title>

  <script src="https://cdn.jsdelivr.net/npm/fhirclient/build/fhir-client.min.js"></script>

  <style>
    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      font-family: "Segoe UI", Arial, sans-serif;
      background: #f4f7fb;
      color: #0f172a;
    }

    .page {
      display: flex;
      min-height: 100vh;
    }

    .sidebar {
      width: 260px;
      background: linear-gradient(180deg, #0f2a44, #061827);
      color: white;
      padding: 28px 22px;
    }

    .brand {
      font-size: 32px;
      font-weight: 800;
      margin-bottom: 6px;
    }

    .subtitle {
      font-size: 14px;
      color: #cbd5e1;
      margin-bottom: 36px;
    }

    .nav-item {
      padding: 14px 16px;
      border-radius: 12px;
      margin-bottom: 10px;
      color: #e2e8f0;
    }

    .nav-item.active {
      background: #2563eb;
      color: white;
      font-weight: 700;
    }

    .about {
      margin-top: 80px;
      padding: 16px;
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.08);
      font-size: 13px;
      color: #dbeafe;
      line-height: 1.6;
    }

    .main {
      flex: 1;
      padding: 30px;
    }

    .header {
      background: white;
      padding: 24px 28px;
      border-radius: 20px;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
      margin-bottom: 24px;
    }

    .header h1 {
      margin: 0;
      font-size: 30px;
    }

    .header p {
      margin: 8px 0 0;
      color: #475569;
      font-size: 16px;
    }

    .status-dot {
      display: inline-block;
      width: 10px;
      height: 10px;
      background: #22c55e;
      border-radius: 50%;
      margin: 0 8px 0 16px;
    }

    .cards {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 18px;
      margin-bottom: 22px;
    }

    .card, .panel, .metrics {
      background: white;
      border-radius: 18px;
      padding: 22px;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
    }

    .card h3, .panel h3, .metrics h3 {
      margin-top: 0;
      font-size: 16px;
    }

    .value {
      font-size: 24px;
      font-weight: 800;
      margin-top: 12px;
    }

    .success {
      color: #16a34a;
    }

    .warning {
      color: #f59e0b;
    }

    .muted {
      color: #64748b;
      font-size: 14px;
    }

    .dashboard {
      display: grid;
      grid-template-columns: 1fr 1.5fr;
      gap: 18px;
      margin-bottom: 22px;
    }

    .risk-box {
      text-align: center;
      padding: 28px 0;
    }

    .risk-level {
      font-size: 42px;
      font-weight: 900;
      color: #f59e0b;
      margin: 20px 0 8px;
    }

    .score {
      display: inline-block;
      background: #eff6ff;
      color: #1d4ed8;
      padding: 8px 14px;
      border-radius: 999px;
      font-size: 14px;
      margin-bottom: 16px;
    }

    .recommendation {
      text-align: left;
      background: #f8fafc;
      border-radius: 14px;
      padding: 16px;
      line-height: 1.6;
      font-size: 14px;
    }

    .chart-placeholder {
      height: 260px;
      border-radius: 16px;
      background:
        linear-gradient(180deg, rgba(37,99,235,0.08), rgba(37,99,235,0.01)),
        repeating-linear-gradient(
          to bottom,
          transparent,
          transparent 48px,
          #e2e8f0 49px
        );
      display: flex;
      align-items: center;
      justify-content: center;
      color: #64748b;
      font-weight: 600;
    }

    .metric-grid {
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 14px;
    }

    .metric {
      background: #f8fafc;
      border-radius: 16px;
      padding: 16px;
      text-align: center;
    }

    .metric-number {
      font-size: 24px;
      font-weight: 800;
      margin: 8px 0;
    }

    .tag {
      display: inline-block;
      padding: 5px 10px;
      border-radius: 999px;
      font-size: 12px;
      background: #dcfce7;
      color: #15803d;
    }

    .tag.low {
      background: #fee2e2;
      color: #dc2626;
    }

    .actions {
      margin-top: 22px;
      display: flex;
      gap: 14px;
    }

    button {
      background: #2563eb;
      color: white;
      border: none;
      border-radius: 14px;
      padding: 14px 28px;
      font-size: 16px;
      font-weight: 700;
      cursor: pointer;
    }

    button:hover {
      background: #1d4ed8;
    }

    .secondary {
      background: white;
      color: #2563eb;
      border: 1px solid #cbd5e1;
    }

    .secondary:hover {
      background: #f8fafc;
    }

    details {
      margin-top: 22px;
      background: white;
      border-radius: 16px;
      padding: 18px;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
    }

    summary {
      cursor: pointer;
      font-weight: 700;
      color: #334155;
    }

    pre {
      background: #0f172a;
      color: #dbeafe;
      padding: 18px;
      border-radius: 14px;
      overflow-x: auto;
      white-space: pre-wrap;
      margin-top: 16px;
    }

    @media (max-width: 1100px) {
      .cards, .metric-grid, .dashboard {
        grid-template-columns: 1fr;
      }

      .sidebar {
        display: none;
      }
    }
  </style>
</head>

<body>
  <div class="page">
    <aside class="sidebar">
      <div class="brand">SHIELD</div>
      <div class="subtitle">Clinical Decision Support</div>

      <div class="nav-item active">Dashboard</div>
      <div class="nav-item">Patient Context</div>
      <div class="nav-item">Observations</div>
      <div class="nav-item">HRV Analysis</div>
      <div class="nav-item">FHIR Connection</div>

      <div class="about">
        <strong>About SHIELD</strong><br />
        AI-powered HRV analysis system for clinical decision support.
      </div>
    </aside>

    <main class="main">
      <section class="header">
        <h1>SHIELD HRV Risk Prediction System</h1>
        <p>
          SMART on FHIR Integration
          <span class="status-dot"></span>
          <span id="topStatus">Connecting...</span>
        </p>
      </section>

      <section class="cards">
        <div class="card">
          <h3>FHIR Connection</h3>
          <div class="value success" id="connectionStatus">Connecting</div>
          <p class="muted">SMART on FHIR Server</p>
        </div>

        <div class="card">
          <h3>Patient Information</h3>
          <p class="muted">Patient ID</p>
          <div class="value" id="patientId">Waiting...</div>
        </div>

        <div class="card">
          <h3>Latest Observation</h3>
          <p class="muted">Observation ID</p>
          <div class="value" id="observationId">obs-HRV-003</div>
        </div>

        <div class="card">
          <h3>Data Status</h3>
          <div class="value" id="dataStatus">Loading</div>
          <p class="muted">Observation(s)</p>
        </div>
      </section>

      <section class="dashboard">
        <div class="panel">
          <h3>HRV Risk Assessment</h3>
          <div class="risk-box">
            <div class="risk-level">Moderate</div>
            <div class="score">Risk Score: 0.62 / 1.00</div>

            <div class="recommendation">
              <strong>AI Clinical Recommendation</strong><br />
              Patient shows moderate HRV risk. Continue monitoring and consider lifestyle assessment.
            </div>
          </div>
        </div>

        <div class="panel">
          <h3>HRV Trends</h3>
          <div class="chart-placeholder">
            HRV / ECG trend preview
          </div>
        </div>
      </section>

      <section class="metrics">
        <h3>HRV Key Metrics</h3>

        <div class="metric-grid">
          <div class="metric">
            Heart Rate
            <div class="metric-number">72</div>
            <span class="tag">Normal</span>
          </div>

          <div class="metric">
            SDNN
            <div class="metric-number">45.6</div>
            <span class="tag low">Low</span>
          </div>

          <div class="metric">
            RMSSD
            <div class="metric-number">28.3</div>
            <span class="tag low">Low</span>
          </div>

          <div class="metric">
            LF/HF Ratio
            <div class="metric-number">2.35</div>
            <span class="tag low">High</span>
          </div>

          <div class="metric">
            pNN50
            <div class="metric-number">12.5%</div>
            <span class="tag low">Low</span>
          </div>
        </div>
      </section>

      <div class="actions">
        <button id="go">Start HRV Analysis</button>
        <button class="secondary" onclick="location.reload()">Refresh Data</button>
      </div>

      <details>
        <summary>Technical Details</summary>
        <pre id="info">Initializing...</pre>
      </details>
    </main>
  </div>

  <script>
    /**********************************************************
     * 下游 SHIELD App
     **********************************************************/
    const SHINY_URL = "https://hrv-app-v4-0.onrender.com/";

    // 指定的 Observation ID
    const OBS_ID = "obs-HRV-003";

    let accessToken = null;
    let fhirBase = null;
    let pid = null;
    let OBS_URL = null;

    function setError(message) {
      document.getElementById("topStatus").textContent = "Error";
      document.getElementById("connectionStatus").textContent = "Error";
      document.getElementById("connectionStatus").className = "value warning";
      document.getElementById("dataStatus").textContent = "Error";
      document.getElementById("info").textContent = "❌ Error:\n" + message;
    }

    /**********************************************************
     * SMART OAuth Ready
     **********************************************************/
    FHIR.oauth2.ready()
      .then(client => {
        accessToken = client.state.tokenResponse.access_token;
        fhirBase = client.state.serverUrl;
        pid = client.patient.id;

        if (!pid) {
          throw new Error("No patient context (launch/patient missing)");
        }

        document.getElementById("topStatus").textContent = "Connected";
        document.getElementById("connectionStatus").textContent = "Connected";
        document.getElementById("patientId").textContent = pid;
        document.getElementById("observationId").textContent = OBS_ID;
        document.getElementById("dataStatus").textContent = "Searching";

        document.getElementById("info").textContent =
          "✅ SMART OAuth Ready\n\n" +
          "FHIR Server:\n" + fhirBase + "\n\n" +
          "Selected Patient:\nPatient/" + pid + "\n\n" +
          "Request:\n" +
          `GET Observation?subject=Patient/${pid}&_id=${OBS_ID}\n\n` +
          "Response:\n";

        return client.request(
          `Observation?subject=Patient/${pid}&_id=${OBS_ID}`
        );
      })
      .then(bundle => {
        if (!bundle.entry || bundle.entry.length === 0) {
          throw new Error(
            `Observation _id=${OBS_ID} not found under Patient/${pid}`
          );
        }

        if (bundle.entry.length !== 1) {
          throw new Error(
            `Unexpected result: ${bundle.entry.length} Observations returned`
          );
        }

        const obs = bundle.entry[0].resource;

        if (obs.id !== OBS_ID) {
          throw new Error("Returned Observation ID does not match requested _id");
        }

        if (obs.subject?.reference !== `Patient/${pid}`) {
          throw new Error("Observation subject does not match selected patient");
        }

        OBS_URL = `${fhirBase}/Observation/${OBS_ID}`;

        document.getElementById("dataStatus").textContent = "1";
        document.getElementById("info").textContent +=
          JSON.stringify(obs, null, 2) +
          "\n\n✅ Confirmed Observation:\n" +
          OBS_URL;
      })
      .catch(err => {
        setError(err.message);
        console.error("SMART Error:", err);
      });

    /**********************************************************
     * 傳遞給 SHIELD APP
     **********************************************************/
    document.getElementById("go").onclick = () => {
      if (!OBS_URL || !pid) {
        alert("Observation not ready");
        return;
      }

      const url =
        SHINY_URL +
        "?token=" + encodeURIComponent(accessToken) +
        "&pid=" + encodeURIComponent(pid) +
        "&obs=" + encodeURIComponent(OBS_URL) +
        "&fhir=" + encodeURIComponent(fhirBase);

      window.location.href = url;
    };
  </script>
</body>
</html>
