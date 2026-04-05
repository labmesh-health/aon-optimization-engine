import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import random
from fpdf import FPDF

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="AON Optimization Engine", layout="wide")
st.title("⚙️ PBRTQC / AON Optimization Engine")
st.markdown("Build, validate, and document patient-based real-time quality control parameters.")

# --- SIDEBAR: PHASE 2 CONFIGURATION ---
st.sidebar.header("📝 1. Report Metadata")
org_name = st.sidebar.text_input("Organization / Laboratory", value="Roche Diagnostics India")
assay_name = st.sidebar.text_input("Assay Name", value="AST_KRL")
unit = st.sidebar.text_input("Unit", value="U/L")

st.sidebar.markdown("---")
st.sidebar.header("📐 2. AON Parameters")
algorithm = st.sidebar.selectbox("Algorithm", ["Simple Moving Average (SMA)", "Moving Median", "EWMA"])
st.sidebar.caption("Compare multiple block sizes simultaneously (comma-separated):")
block_sizes_input = st.sidebar.text_input("Block Sizes / Windows (N)", value="10, 25, 50, 100")

st.sidebar.markdown("**Algorithmic Truncation Limits**")
trunc_min = st.sidebar.number_input("Lower Truncation Limit", value=18.0, step=0.1)
trunc_max = st.sidebar.number_input("Upper Truncation Limit", value=45.0, step=0.1)

st.sidebar.markdown("**Control Limits (Alarms)**")
control_limit_z = st.sidebar.number_input("Z-Score Multiplier", value=3.0, step=0.1)

st.sidebar.markdown("---")
st.sidebar.header("🎯 3. Simulation Settings")
sim_runs = st.sidebar.number_input("Simulations per Bias", min_value=5, max_value=100, value=20)
samples_before = st.sidebar.number_input("Samples before bias injection", value=150, step=10)
samples_after = st.sidebar.number_input("Samples after bias injection", value=150, step=10)

st.sidebar.markdown("**Systematic Bias Range (%)**")
b_col1, b_col2, b_col3 = st.sidebar.columns(3)
with b_col1: bias_min = st.number_input("Min", value=-30, step=1)
with b_col2: bias_max = st.number_input("Max", value=30, step=1)
with b_col3: bias_step = st.number_input("Step", value=5, step=1)

# Generate Bias List (Excluding 0)
biases = [b for b in range(int(bias_min), int(bias_max) + 1, int(bias_step)) if b != 0]
st.sidebar.caption(f"Testing Biases: {biases}")

# --- MAIN SCREEN: PHASE 1 DATA INGESTION ---
st.header("Step 1: Upload & Map Data")
uploaded_file = st.file_uploader("Upload Historical LIS/Middleware Data (CSV)", type=['csv'])

if uploaded_file:
    df_raw = pd.read_csv(uploaded_file)
    actual_columns = df_raw.columns.tolist()
    
    with st.expander("Column Mapping", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1: 
            date_col = st.selectbox("Date Column", actual_columns, index=0)
            date_format = st.selectbox("Date Format", [
                "Auto-detect", "YYYYMMDDHHMMSS (Dense)", "YYYY-MM-DD HH:MM:SS", "DD/MM/YYYY HH:MM:SS", "MM/DD/YYYY HH:MM:SS"
            ])
        with col2: inst_col = st.selectbox("Instrument Column", actual_columns, index=0)
        with col3: test_col = st.selectbox("Test ID Column", actual_columns, index=0)
        with col4: val_col = st.selectbox("Result Value Column", actual_columns, index=0)

    st.markdown("---")
    st.header("Step 2: Filter & Gross Cleanse")
    unique_tests = sorted(df_raw[test_col].dropna().astype(str).unique())
    selected_test = st.selectbox("Select Test to Analyze", ["-- Select --"] + unique_tests)
    
    if selected_test != "-- Select --":
        df_test = df_raw[df_raw[test_col].astype(str) == selected_test].copy()
        unique_inst = sorted(df_test[inst_col].dropna().astype(str).unique())
        
        # MULTI-SELECT UPGRADE
        selected_insts = st.multiselect("Select Instrument(s) to Analyze", unique_inst, default=unique_inst[0] if len(unique_inst) > 0 else None)
        
        if selected_insts:
            # Filter for multiple instruments
            df_inst = df_test[df_test[inst_col].astype(str).isin(selected_insts)].copy()
            
            c1, c2 = st.columns(2)
            with c1: gross_min = st.number_input("Minimum Possible Physiological Value", value=0.0)
            with c2: gross_max = st.number_input("Maximum Possible Physiological Value", value=500.0)
            
            if st.button("Apply Gross Cleansing", type="primary"):
                original_count = len(df_inst)
                df_inst[val_col] = pd.to_numeric(df_inst[val_col], errors='coerce')
                df_clean = df_inst.dropna(subset=[val_col])
                df_clean = df_clean[(df_clean[val_col] >= gross_min) & (df_clean[val_col] <= gross_max)]
                
                if date_format == "YYYYMMDDHHMMSS (Dense)":
                    df_clean[date_col] = pd.to_datetime(df_clean[date_col].astype(str).str.split('.').str[0], format='%Y%m%d%H%M%S', errors='coerce')
                elif date_format == "YYYY-MM-DD HH:MM:SS":
                    df_clean[date_col] = pd.to_datetime(df_clean[date_col].astype(str), format='%Y-%m-%d %H:%M:%S', errors='coerce')
                elif date_format == "DD/MM/YYYY HH:MM:SS":
                    df_clean[date_col] = pd.to_datetime(df_clean[date_col].astype(str), format='%d/%m/%Y %H:%M:%S', errors='coerce')
                elif date_format == "MM/DD/YYYY HH:MM:SS":
                    df_clean[date_col] = pd.to_datetime(df_clean[date_col].astype(str), format='%m/%d/%Y %H:%M:%S', errors='coerce')
                else:
                    df_clean[date_col] = pd.to_datetime(df_clean[date_col], errors='coerce')
                
                df_clean = df_clean.dropna(subset=[date_col]).sort_values(by=date_col, ascending=True)
                final_count = len(df_clean)
                
                st.session_state['clean_data'] = df_clean
                st.session_state['val_col'] = val_col
                st.success(f"✅ Data Cleansing Complete! Retained {final_count} pure historical records from {len(selected_insts)} instrument(s).")

# --- PHASE 3, 4, & 5: MULTI-WINDOW SIMULATION ENGINE ---
if 'clean_data' in st.session_state:
    st.markdown("---")
    st.header("Step 3: Run IFCC-Compliant MA Simulations")
    
    if st.button("🚀 Run Multi-Window Simulation Engine", type="primary"):
        with st.spinner("Simulating multiple block sizes and calculating limits..."):
            df = st.session_state['clean_data'].copy()
            v_col = st.session_state['val_col']
            
            block_sizes = [int(n.strip()) for n in block_sizes_input.split(',')]
            all_results = []
            baseline_stats = []
            
            base_mask = (df[v_col] >= trunc_min) & (df[v_col] <= trunc_max)
            df_trunc = df[base_mask].copy()
            
            for n in block_sizes:
                # Calculate Baseline MA Stats for this N (Replicates the Huvaros Cards)
                if "Simple" in algorithm:
                    baseline_ma = df_trunc[v_col].rolling(window=n).mean()
                elif "Median" in algorithm:
                    baseline_ma = df_trunc[v_col].rolling(window=n).median()
                else:
                    baseline_ma = df_trunc[v_col].ewm(span=n, adjust=False).mean()
                    
                target_mean = baseline_ma.mean()
                ma_sd = baseline_ma.std()
                ucl = target_mean + (control_limit_z * ma_sd)
                lcl = target_mean - (control_limit_z * ma_sd)
                
                baseline_stats.append({
                    "Window / Block Size (N)": n,
                    "Target Mean": f"{target_mean:.3f}",
                    "Lower Control Limit (LCL)": f"{lcl:.3f}",
                    "Upper Control Limit (UCL)": f"{ucl:.3f}"
                })
                
                # Run Simulations for this N
                for bias in biases:
                    nped_list = []
                    for _ in range(sim_runs):
                        safe_start_min = max(n, samples_before)
                        safe_start_max = len(df) - samples_after
                        if safe_start_max <= safe_start_min:
                            continue 
                            
                        start_idx = random.randint(safe_start_min, safe_start_max)
                        sim_vals = df[v_col].values.copy()
                        sim_vals[start_idx:] = sim_vals[start_idx:] * (1 + (bias / 100.0))
                        
                        valid_mask = (sim_vals >= trunc_min) & (sim_vals <= trunc_max)
                        valid_vals = sim_vals[valid_mask]
                        
                        if len(valid_vals) >= n:
                            valid_series = pd.Series(valid_vals)
                            if "Simple" in algorithm:
                                ma_sim = valid_series.rolling(window=n).mean()
                            elif "Median" in algorithm:
                                ma_sim = valid_series.rolling(window=n).median()
                            else:
                                ma_sim = valid_series.ewm(span=n, adjust=False).mean()
                            
                            breach_idx = ma_sim[(ma_sim > ucl) | (ma_sim < lcl)].index
                            
                            if len(breach_idx) > 0:
                                samples_to_detect = int(breach_idx[0] - (start_idx * (len(valid_vals)/len(sim_vals))))
                                if samples_to_detect > 0:
                                    nped_list.append(samples_to_detect)
                    
                    if nped_list:
                        all_results.append({
                            "Block Size (N)": str(n),
                            "Bias (%)": bias,
                            "Median NPed": np.median(nped_list),
                            "Min NPed": np.min(nped_list),
                            "Max NPed": np.max(nped_list)
                        })

            # --- VISUALIZATIONS & DATA TABLES ---
            st.success("✅ Multi-Window Simulations Complete!")
            
            # Display the Control Limits Table (Replicating Huvaros Dashboard Cards)
            st.subheader("1. Control Limits per Algorithm Window")
            st.markdown("These are the strict limits calculated from your healthy baseline data. The algorithm uses these fixed thresholds to catch errors.")
            st.dataframe(pd.DataFrame(baseline_stats), use_container_width=True)
            
            # Display Bias Impact Table (Answering the user's specific request)
            st.subheader("2. Bias Impact Analysis (Primary Window)")
            st.markdown("This table illustrates what happens to the mean when the systematic biases are injected, and confirms if the shift is severe enough to breach the control limits.")
            primary_n = block_sizes[0]
            p_mean = float(baseline_stats[0]["Target Mean"])
            p_lcl = float(baseline_stats[0]["Lower Control Limit (LCL)"])
            p_ucl = float(baseline_stats[0]["Upper Control Limit (UCL)"])
            
            bias_impact_data = []
            for bias in biases:
                shifted_mean = p_mean * (1 + (bias / 100.0))
                will_alarm = "Yes 🔴" if (shifted_mean > p_ucl or shifted_mean < p_lcl) else "No (Shift too small) 🟢"
                bias_impact_data.append({
                    "Injected Bias Limit (%)": f"{bias}%",
                    "Shifted Theoretical Mean": f"{shifted_mean:.3f}",
                    "Fixed LCL": f"{p_lcl:.3f}",
                    "Fixed UCL": f"{p_ucl:.3f}",
                    "Breaches Limits?": will_alarm
                })
            st.dataframe(pd.DataFrame(bias_impact_data), use_container_width=True)

            # Draw the Plotly Charts
            res_df = pd.DataFrame(all_results)
            if not res_df.empty:
                st.subheader("3. Error Detection Performance")
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    fig_line = px.line(
                        res_df, x="Bias (%)", y="Median NPed", color="Block Size (N)", markers=True,
                        title="Bias Detection Curves (Comparing Block Sizes)",
                        labels={"Median NPed": "Results needed for bias detection"}
                    )
                    fig_line.update_layout(template="plotly_white", yaxis=dict(range=[0, min(100, res_df["Median NPed"].max() + 10)]))
                    st.plotly_chart(fig_line, use_container_width=True)
                
                with col2:
                    primary_df = res_df[res_df["Block Size (N)"] == str(primary_n)].sort_values("Bias (%)")
                    fig_bar = go.Figure()
                    fig_bar.add_trace(go.Bar(
                        x=primary_df["Bias (%)"], y=primary_df["Median NPed"],
                        name=f'N={primary_n}',
                        error_y=dict(
                            type='data', symmetric=False,
                            array=primary_df["Max NPed"] - primary_df["Median NPed"],
                            arrayminus=primary_df["Median NPed"] - primary_df["Min NPed"],
                            visible=True
                        ),
                        marker_color='royalblue'
                    ))
                    fig_bar.update_layout(title=f"MA Validation (N={primary_n})", template="plotly_white")
                    st.plotly_chart(fig_bar, use_container_width=True)
