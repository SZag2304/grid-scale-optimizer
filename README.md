# grid-scale-optimizer
Interactive Streamlit web app for grid optimization and battery arbitrage, powered by Python, Pandas, and Gurobi MILP.

# ⚡ Grid-Scale UCED & Battery Arbitrage Optimizer

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Gurobi](https://img.shields.io/badge/Optimization-Gurobi_MILP-red.svg)
![Streamlit](https://img.shields.io/badge/Dashboard-Streamlit-FF4B4B.svg)
![Pandas](https://img.shields.io/badge/Data-Pandas-150458.svg)

## 📖 Executive Summary
This project is a **Production-Grade Unit Commitment and Economic Dispatch (UCED) model** built to maximize the commercial value of a hybrid energy portfolio. 

Using **Mixed-Integer Linear Programming (MILP)**, the model dynamically schedules a fleet of thermal generators, renewable assets (Wind/Solar), and a 2000 MWh Battery Energy Storage System (BESS) against Day-Ahead wholesale electricity prices. The accompanying Streamlit dashboard allows asset managers to interact with the model live, balancing operational constraints (physics) with financial performance (OPEX vs. CAPEX).

## 🎯 Business Value & Use Case
* **Energy Arbitrage:** Automatically identifies optimal battery charge/discharge cycles based on dynamic price spreads, turning market volatility into revenue.
* **Asset Valuation:** Calculates true System Cost by layering daily operational expenditure (OPEX) against the annualized capital expenditure (CAPEX) of the lithium-ion battery.
* **Curtailment Mitigation:** Quantifies spilled wind and solar energy, providing data-driven insights for future transmission or storage investments.

---

## 📸 Interactive Dashboard
*(Add a screenshot or GIF of your Streamlit app running here. Example: `![Streamlit Dashboard](demo.png)`)*

---

## 🛠️ Technical Highlights & Constraints Modeled

### 1. Battery Physics & Storage Logic
* Formulated **Big-M mutual exclusivity constraints** to prevent simultaneous charging and discharging.
* Integrated round-trip efficiency losses (85%) into the State of Charge (SoC) tracking to accurately reflect thermal energy loss.

### 2. Thermal Fleet Constraints
* Enforced **Min/Max Stable Capacities** for Coal and Gas assets using binary commitment variables.
* Modeled strict **Ramp-Up and Ramp-Down** limits, ensuring the mathematical dispatch respects the mechanical thermal stress of real-world boilers and turbines.

### 3. Automated Data Engineering pipelines
* Automated the ingestion of raw, high-frequency SCADA and Utility CSV data.
* Utilized `pandas` for dynamic temporal resampling (e.g., minute-level to hourly), allowing the model to dynamically scale its optimization horizon (24 hours, 48 hours, etc.) without breaking hardcoded loops.

---

## 🚀 How to Run Locally

**1. Clone the repository**
```bash
git clone [https://github.com/yourusername/UCED-optimizer.git](https://github.com/yourusername/UCED-optimizer.git)
cd UCED-optimizer
```
**2. Install the required dependencies**
```bash
pip install -r requirements.txt
```
**3. Launch the Streamlit Dashboard**
```bash
streamlit run ucedapp.py
```
(Note: A valid Gurobi license is required to solve MILP model. A free academic or web license can be obtained via Gurobi's website).

## 🔮 Future Roadmap

[ ] Ancillary Services: Integrate secondary market bidding for Frequency Regulation (Spinning Reserves).

[ ] Start-up Costs: Introduce thermal start-up penalties and minimum up/down time constraints.

[ ] Stochastic Forecasting: Replace perfect-foresight renewable data with XGBoost machine learning predictions to model real-world forecast uncertainty.
