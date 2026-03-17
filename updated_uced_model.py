import pandas as pd
import gurobipy as gp 
from gurobipy import GRB

# 1. SETUP MODEL
model = gp.Model("UCED")

# 2. DATA - THERMAL FLEET
nonrenewable_gen = {
    'coal1': {'max_capacity': 1800, 'min_stable_capacity': 900, 'marginal_cost': 46, 'ramp_up': 300, 'ramp_down': 300},
    'coal2': {'max_capacity': 750, 'min_stable_capacity': 405, 'marginal_cost': 60, 'ramp_up': 200, 'ramp_down': 200},
    'gas1':  {'max_capacity': 280, 'min_stable_capacity': 180, 'marginal_cost': 80, 'ramp_up': 100, 'ramp_down': 100},
    'gas2':  {'max_capacity': 420, 'min_stable_capacity': 279, 'marginal_cost': 50, 'ramp_up': 150, 'ramp_down': 150},
    'gas3':  {'max_capacity': 560, 'min_stable_capacity': 360, 'marginal_cost': 30, 'ramp_up': 200, 'ramp_down': 200},
}

## 2b. DATA - STORAGE
bess = {
    'capacity_mwh': 2000,    # A 4-hour battery (500 MW * 4 hrs)
    'charge_rate_mw': 500,   
    'discharge_rate_mw': 500,
    'efficiency': 0.85       # 85% round-trip efficiency
}


# 3. DATA - RENEWABLES & DEMAND

'''
hours = range(24)

solar_avail = [0, 0, 0, 0, 0, 0, 100, 800, 2000, 3200, 3800, 4000, 3800, 3500, 3000, 1800, 500, 0, 0, 0, 0, 0, 0, 0]
wind_avail = [3800, 3100, 2100, 900, 1300, 2000, 2100, 1800, 1500, 1700, 1900, 2050, 1825, 1205, 1400, 1600, 2000, 2400, 2600, 2970, 3400, 3800, 4100, 4300]

demand = [1750, 1500, 1250, 1000, 1390, 1780, 2170, 2560, 2950, 2797, 2645, 2492, 
          2340, 2634, 2928, 3222, 3516, 3810, 3466, 3123, 2780, 2436, 2093, 1750]
'''

#3.1. Load Data from CSV files

df_scada = pd.read_csv('/Users/szag_2304/Desktop/Project/UCED-model/scada_solar_wind.csv')
df_scada['time'] = pd.to_datetime(df_scada['time'])                             # Convert 'time' column to datetime
df_hourly_scada = df_scada.resample('H', on='time').mean()                             # Resample minute interval data to hourly frequency using mean aggregation

# DATA - RENEWABLES
solar_avail = df_hourly_scada['solar_generation'].tolist()
wind_avail = df_hourly_scada['wind_generation'].tolist()

# DATA - DEMAND
df_utility = pd.read_csv('/Users/szag_2304/Desktop/Project/UCED-model/utility_demand_data.csv')
df_utility['time'] = pd.to_datetime(df_utility['time'])                             # Convert 'time' column to datetime
df_hourly_utility = df_utility.resample('H', on='time').mean()                             # Resample minute interval data to hourly frequency using mean aggregation
demand = df_hourly_utility['load_demand'].tolist()

# DATA - MARKET EXPORT AND IMPORT PRICES

hours = range(len(demand))  # Assuming demand, solar_avail, and wind_avail all have the same length

# 24-hour dynamic prices for buying power from the grid
base_import = [40, 35, 35, 35, 40, 50, 60, 55, 45, 35, 25, 20, 15, 20, 30, 50, 80, 120, 150, 100, 80, 60, 50, 45]

dynamic_import = [base_import[t % 24] for t in hours]  # Repeat the 24-hour pattern if we have more than 24 hours of data

# Let's keep the $10/MWh spread so exporting is slightly less profitable than importing costs
dynamic_export = [p - 10 for p in dynamic_import]

# Update the market dictionary
market = {
    'import_price': dynamic_import,
    'export_price': dynamic_export,
    'max_mw': 800
}

# 4. DECISION VARIABLES
# Thermal Generation (Continuous) and Commitment (Binary)
gen = model.addVars(nonrenewable_gen.keys(), hours, lb=0, name="gen")
u = model.addVars(nonrenewable_gen.keys(), hours, vtype=GRB.BINARY, name="u")

# Renewable energy used (Continuous)
ren_used = model.addVars(['solar', 'wind'], hours, lb=0, name="ren_used")

# Battery Storage 
soc = model.addVars(hours, lb=0, ub=bess['capacity_mwh'], name="soc")
charge = model.addVars(hours, lb=0, ub=bess['charge_rate_mw'], name="charge")
discharge = model.addVars(hours, lb=0, ub=bess['discharge_rate_mw'], name="discharge")
is_charging = model.addVars(hours, vtype=GRB.BINARY, name="is_charging")
is_discharging = model.addVars(hours, vtype=GRB.BINARY, name="is_discharging")

# Market Import/Export (Continuous)
import_mw = model.addVars(hours, lb=0, ub=market['max_mw'], name="import_mw")
export_mw = model.addVars(hours, lb=0, ub=market['max_mw'], name="export_mw")
is_importing = model.addVars(hours, vtype=GRB.BINARY, name="is_importing")
is_exporting = model.addVars(hours, vtype=GRB.BINARY, name="is_exporting")

# 5. OBJECTIVE FUNCTION

cost_thermal = gp.quicksum(gen[i, t] * nonrenewable_gen[i]['marginal_cost'] for i in nonrenewable_gen for t in hours)
cost_import = gp.quicksum(import_mw[t] * market['import_price'][t] for t in hours)
revenue_export = gp.quicksum(export_mw[t] * market['export_price'][t] for t in hours)

model.setObjective(
    cost_thermal + cost_import - revenue_export,
    GRB.MINIMIZE
)

# 6. CONSTRAINTS
# Load Balance: Total Gen + Total Ren = Demand
model.addConstrs((gen.sum('*', t) + ren_used.sum('*', t) - charge[t] + discharge[t] == demand[t] - import_mw[t] + export_mw[t] for t in hours), name="LoadBalance")

# Thermal Limits
for i in nonrenewable_gen:
    for t in hours:
        model.addConstr(gen[i, t] <= nonrenewable_gen[i]['max_capacity'] * u[i, t], name=f"MaxCap_{i}_{t}")
        model.addConstr(gen[i, t] >= nonrenewable_gen[i]['min_stable_capacity'] * u[i, t], name=f"MinCap_{i}_{t}")

# Ramping Constraints
# We start the loop at t=1 so we can safely look backward to t-1
for i in nonrenewable_gen:
    for t in hours[1:]:  # Start from 1 to avoid t-1 issues
        # 1. Ramp Up Limit
        model.addConstr(
            gen[i, t] <= gen[i, t-1] + 
                         (nonrenewable_gen[i]['ramp_up'] * u[i, t-1]) + 
                         (nonrenewable_gen[i]['min_stable_capacity'] * (1 - u[i, t-1])),
            name=f"RampUp_{i}_{t}"
        )
        
        # 2. Ramp Down Limit
        model.addConstr(
            gen[i, t] >= gen[i, t-1] - 
                         (nonrenewable_gen[i]['ramp_down'] * u[i, t-1]) - 
                         (nonrenewable_gen[i]['max_capacity'] * (1 - u[i, t])),
            name=f"RampDown_{i}_{t}"
        )

# Battery Constraints
for t in hours:
    if t == 0:
        model.addConstr(soc[t] == 0, name=f"BatterySOC_{t}")
    else:
        model.addConstr(soc[t] == soc[t-1] + charge[t] * bess['efficiency'] - discharge[t],
        name=f"BatterySOC_{t}")
    model.addConstr(is_charging[t] + is_discharging[t] <= 1, name=f"BatteryChargeDischarge_{t}")
    model.addConstr(charge[t] <= bess['charge_rate_mw'] * is_charging[t], name=f"BatteryChargeLimit_{t}")
    model.addConstr(discharge[t] <= bess['discharge_rate_mw'] * is_discharging[t], name=f"BatteryDischargeLimit_{t}")


# Renewable Limits
for t in hours:
    model.addConstr(ren_used['solar', t] <= solar_avail[t], name=f"SolarLimit_{t}")
    model.addConstr(ren_used['wind', t] <= wind_avail[t], name=f"WindLimit_{t}")

# Market Import/Export Constraints
for t in hours:
    model.addConstr(is_importing[t] + is_exporting[t] <= 1, name=f"MarketImportExport_{t}")
    model.addConstr(import_mw[t] <= market['max_mw'] * is_importing[t], name=f"MarketImportLimit_{t}")
    model.addConstr(export_mw[t] <= market['max_mw'] * is_exporting[t], name=f"MarketExportLimit_{t}")

# 7. SOLVE
model.optimize()

# Total Demand
total_demand = sum(demand[t] for t in hours)
print(f"\nTotal Daily Demand: {total_demand} MWh")

print("\n" + "="*50)

# 8. RESULTS PRINTING
if model.status == GRB.OPTIMAL:
    print("\n" + "="*50)
    print(f"OPTIMAL SOLUTION FOUND. Total Cost: ${model.objVal:,.2f}")
    print("="*50)
    # Check Hour 12 (Peak)
    h = 12
    print(f"HOUR {h} SUMMARY (Demand: {demand[h]} MW)")
    for i in nonrenewable_gen:
        print(f"  {i:6}: {gen[i,h].X:7.2f} MW [Status: {int(u[i,h].X)}]")
    print(f"  Solar : {ren_used['solar', h].X:7.2f} MW")
    print(f"  Wind  : {ren_used['wind', h].X:7.2f} MW")

    print(f"  Solar : {ren_used['solar', h].X:7.2f} MW (Available: {solar_avail[h]} MW)")
    print(f"  Wind  : {ren_used['wind', h].X:7.2f} MW (Available: {wind_avail[h]} MW)")
    print(f"  Battery Charge: {charge[h].X:7.2f} MW")
    print(f"  Battery Discharge: {discharge[h].X:7.2f} MW")
    print(f"  Market Import: {import_mw[h].X:7.2f} MW")
    print(f"  Market Export: {export_mw[h].X:7.2f} MW")

    print("\n" + "="*50)

    # Calculate and print the spilled energy
    spilled_wind = wind_avail[h] - ren_used['wind', h].X
    spilled_solar = solar_avail[h] - ren_used['solar', h].X
    
    print(f"  -> Wind Spilled : {spilled_wind:7.2f} MW")
    print(f"  -> Solar Spilled: {spilled_solar:7.2f} MW")
else:
    print("Optimization was stopped or is infeasible.")

print("\n" + "="*50)


# For all hours, print a summary table of generation and costs
if model.status == GRB.OPTIMAL:
      # Calculate and print the spilled energy for each hour

    print(f"{'Hour':<5} | {'Demand':<8} | {'Solar':<8} | {'Solar Spilled':<8} | {'Wind':<8} | {'Wind Spilled':<8} | {'Coal1':<8} | {'Coal2':<8} | {'Gas1':<8} | {'Gas2':<8} | {'Gas3':<8} | {'SoC':<8} | {'Charge':<8} | {'Discharge':<8} | {'Import':<8} | {'Export':<8} | {'Cost'}")
    print("-" * 70)
    for t in hours:
        # Calculate hourly cost
        h_cost = sum(gen[i, t].X * nonrenewable_gen[i]['marginal_cost'] for i in nonrenewable_gen)
        spilled_wind_pd = wind_avail[t] - ren_used['wind', t].X
        spilled_solar_pd = solar_avail[t] - ren_used['solar', t].X
        print(f"{t:<5} | {demand[t]:<8} | {ren_used['solar',t].X:<8.0f} | {spilled_solar_pd:<13.0f} | {ren_used['wind',t].X:<8.0f} | {spilled_wind_pd:<12.0f} | {gen['coal1',t].X:<8.0f} | {gen['coal2',t].X:<8.0f} | {gen['gas1',t].X:<8.0f} | {gen['gas2',t].X:<8.0f} | {gen['gas3',t].X:<8.0f} | {soc[t].X:<8.0f} | {charge[t].X:<8.0f} | {discharge[t].X:<8.0f} | {import_mw[t].X:<8.0f} | {export_mw[t].X:<8.0f} | ${h_cost:,.0f}")


# --- FINANCIAL SUMMARY ---

    # CAPEX Calculation
    # For simplicity, let's assume the following CAPEX costs:
    capex_bess_permw = 300000  # $300,000 per MWh of battery capacity for 15 years lifespan
    capex_bess = capex_bess_permw * bess['capacity_mwh']  # Total CAPEX for the battery system
    capex_hourly = [capex_bess / (365 * 24 * 15) for t in hours]  # Distribute CAPEX over 15 years on an hourly basis

    # 1. Calculate Total CAPEX for the simulated hours
    total_capex = sum(capex_hourly[t] for t in hours)
    
    # 2. Calculate Total System Cost (Operations + CAPEX)
    total_system_cost = model.objVal + total_capex

    print("\n" + "="*50)
    print(" 📊 FINANCIAL DASHBOARD & ROI SUMMARY")
    print("="*50)
    # model.objVal can be negative if export revenue is higher than generation/import costs!
    print(f"Total Operational Cost (OPEX):  ${model.objVal:,.2f}")
    print(f"Total Battery Cost (CAPEX):     ${total_capex:,.2f}")
    print("-" * 50)
    print(f"TRUE SYSTEM COST (OPEX+CAPEX):  ${total_system_cost:,.2f}")
    print("="*50)


# Plotting results
import matplotlib.pyplot as plt

battery_charge = [charge[t].X for t in hours]
battery_discharge = [discharge[t].X for t in hours]
total_demand = [(demand[t] + battery_charge[t]) for t in hours]

if model.status == GRB.OPTIMAL:
    # Prepare data for plotting
    plot_data = {name: [gen[name, t].X for t in hours] for name in nonrenewable_gen}
    plot_data['Solar'] = [ren_used['solar', t].X for t in hours]
    plot_data['Wind'] = [ren_used['wind', t].X for t in hours]
    plot_data['Battery'] = [discharge[t].X - charge[t].X for t in hours]  # Net discharge (positive means discharging)
    
    # Stack them: Renewables first, then Thermal by cost
    order = ['Solar', 'Wind', 'Battery', 'gas3', 'coal1', 'gas2', 'coal2', 'gas1']
    y = [plot_data[name] for name in order if name in plot_data]

    plt.figure(figsize=(12, 6))
    plt.stackplot(hours, y, labels=order)
    plt.plot(hours, total_demand, color='black', linestyle='--', linewidth=2, label='Demand')
    
    plt.title("24-Hour Optimal Dispatch Stack")
    plt.xlabel("Hour of Day")
    plt.ylabel("Generation (MW)")
    plt.legend(loc='upper left')
    plt.grid(alpha=0.3)
    plt.show()
