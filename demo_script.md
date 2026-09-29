# ⏱️ 5-Minute Judge Demo Script: PolarSync AI
### Smart India Hackathon 2026 | Problem Statement: SIH26061
**NCPOR, Ministry of Earth Sciences** | **Idea Title:** `PolarSync AI` | **Team:** `anvaya`

---

## 🎯 Demo Preparation (Before Judges Arrive)
1. Double-click `run_demo.bat` (or run `.\run_demo.ps1`).
2. Verify that the browser opens `http://localhost:8501`.
3. Have this demo script open on a second window or tablet.

---

## 🎙️ Minute-by-Minute Pitch & Click Path

### Minute 0:00 – 0:45 | The Hook & Station Setup
- **What to Say:**
  > *"Respected Judges, Indian research stations like Maitri and Bharati in Antarctica face temperatures below -50°C, months of continuous darkness during Polar Night, and delivered diesel costs exceeding ₹320 per Liter. Today, we present **PolarSync AI**, an offline-first, production-grade smart energy management system built to guarantee polar survival, slash diesel reliance, and prevent blackouts."*
- **What to Click:**
  1. Point to the top metric cards: **Renewable Generation (kW)**, **Battery SOC (%)**, **H2 Tank Pressure (bar)**, **PEM Fuel Cell (kW)**, **Station Habitat Temp (20.0°C)**, and **Antarctic Wind Chill Index**.
  2. Point out the **1-Click Operational Presets** (Summer Midnight Sun, Winter Polar Night, Cat-5 Polar Blizzard, Safety Shield Test, Satellite Blackout) designed for judges to test scenarios instantly!

---

### Minute 0:45 – 1:30 | Live Power Flow Sankey & 7-Day Dispatch Stack
- **What to Say:**
  > *"Here on the main cockpit, you are seeing our dynamic Plotly power flow Sankey diagram in real-time. Notice how our physics-informed digital twin models air-density boosted wind turbines and solar PV routing into the 400V microgrid bus, with excess power actively producing green hydrogen in our 60 kW PEM electrolyzer."*
- **What to Click:**
  1. Hover cursor over the links on the **Sankey diagram** to show live kW values flowing between generation, storage, and loads.
  2. Click on the tab **"7-Day Dispatch Stack (168h)"**: show how wind and hydrogen fuel cell CHP co-generation displace diesel across multi-day polar depressions.
  3. Click on the tab **"24-Hour Conformal Forecast Bands"**: show the $q_{10}, q_{50}, q_{90}$ conformal prediction intervals with guaranteed 90% coverage.

---

### Minute 1:30 – 2:30 | The Blizzard Test: Storm-Prep Mode (Judge Favorite!)
- **What to Say:**
  > *"Now let's stress-test the system with an extreme polar blizzard. In Antarctica, a Category 4 blizzard brings 120 km/h winds, plunging temperatures to -55°C, causing turbine feathering and severe heating surges. Watch how PolarSync AI autonomously reacts."*
- **What to Click:**
  1. Scroll down to **Tab "🌪️ D: Storm-Prep Mode"**.
  2. Move the **Blizzard Severity Slider** to **Category 4**.
  3. Click **"⚡ TRIGGER POLAR BLIZZARD"**.
  4. Show the live changes:
     - Banner turns Red: `BLIZZARD EMERGENCY ACTIVE`.
     - Outside wind speed spikes above 25 m/s $\rightarrow$ Turbines safely feather to prevent mechanical damage.
     - Battery BESS pre-charges to 100%.
     - Building thermal mass pre-heats to 22.5°C using thermal capacitance as an energy buffer.
     - Field survey drones and snowmobiles are recalled and docked.

---

### Minute 2:30 – 3:15 | Deterministic Safety Shield & Explainability Copilot
- **What to Say:**
  > *"In life-or-death polar conditions, AI cannot be a black box. If an AI hallucinates or tries to cut life support to save fuel, our **Deterministic Safety Shield** intercepts and vetoes it."*
- **What to Click:**
  1. Click **Tab "🛡️ E: Safety Shield"**:
     - Show the **Live Veto Table**: point out `RULE_01` (Tier 1 Life Support Inviolable) and `RULE_02` (Battery Cryogenic SOC Floor).
  2. Click **Tab "🧠 F: Explainability XAI"**:
     - Point out the **SHAP Feature Attributions Bar Chart** showing exact drivers of the current dispatch.
     - Show the **Offline Ask Why Box**: type *"Why did the diesel start?"* and click Enter $\rightarrow$ Show the instant, local, zero-cloud technical explanation.

---

### Minute 3:15 – 4:00 | Chaos Fault Injection & Edge-Only Fallback
- **What to Say:**
  > *"What happens when polar storms sever satellite communication? Let's break the system live."*
- **What to Click:**
  1. Click **Tab "💥 G: Chaos Console"**.
  2. Check **"📡 Satellite Outage (Edge-Only Mode)"** and click **"Apply Chaos Faults"**.
  3. Point to the top status banner: system instantly falls back to **EDGE-AUTONOMOUS MODE**, executing full physics twin and local inference on the edge node without internet!
  4. Click **"Clear All Faults"** to show instant recovery.

---

### Minute 4:00 – 4:30 | Hardware-in-the-Loop Lite & Federated Learning
- **What to Say:**
  > *"PolarSync AI is built for real deployment. We support Hardware-in-the-Loop over MQTT and multi-station federated learning across India's three polar stations."*
- **What to Click:**
  1. Click **Tab "🔌 K: HIL Lite MQTT"**:
     - Toggle **"Enable Real Hardware Telemetry (ESP32 via MQTT)"**.
     - Show real pack voltage, current, and temperature packets arriving at 1 Hz from the edge microcontroller bridge.
  2. Click **Tab "🌐 J: Federated Learning"**:
     - Show the collaborative FedAvg network connecting **Maitri (Antarctica)**, **Bharati (Antarctica)**, and **Himadri (Arctic)**.
     - Point out: **99.8% bandwidth savings** ($<50\text{ KB}$ weights transferred) with **+18.4% model accuracy gain**.

---

### Minute 4:30 – 5:00 | 4-Way Annual Benchmark & Final Impact
- **What to Say:**
  > *"To prove our claims, we simulated a full 8,760-hour polar year across four controllers on identical weather."*
- **What to Click:**
  1. Click **Tab "🏆 4-Way Annual Benchmark"**.
  2. Walk the judges through the table:
     - **Pure RL Failed:** Suffered **341,141 kWh of blackout** without our safety shield!
     - **Rule-Based Heuristic:** Started generator 668 times and cycled battery 375 times.
     - **PolarSync Hierarchical:** Delivered **28.6% fuel savings (21,191 Liters saved)**, saved **₹67.8 Lakhs**, cut generator wear by **72%**, and guaranteed **0.0 kWh unserved life-support energy**.
- **Closing Punchline:**
  > *"PolarSync AI isn't just an energy optimizer—it is an autonomous life-support preservation shield for Indian polar exploration. Thank you!"*
