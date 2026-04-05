import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import random
from fpdf import FPDF

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="AON Optimization Engine", layout="wide")
st.title("⚙️ PBRTQC / AON Optimization Engine")
st.markdown("Build, validate, and document patient-based real-time quality control parameters.")

# --- SIDEBAR: PHASE 2 CONFIGURATION ---
st.sidebar.header("📝 1. Report Metadata")
org_name = st.sidebar.text_input("Organization / Laboratory", value="My Laboratory")
assay_name = st.sidebar.text_input("Assay Name", value="Potassium")
unit = st.sidebar.text_input("Unit", value="mmol/L")

st.sidebar.markdown("---")
st.sidebar.header("📐 2. AON Parameters")
algorithm = st.sidebar.selectbox("Algorithm", ["Simple Moving Average (SMA)", "Moving Median", "EWMA"])
block_size = st.sidebar.number_input("Block Size (N)", min_value=5, max_value=200, value=50, step=5)

st.sidebar.markdown("**Algorithmic Truncation Limits**")
st.sidebar.caption("These limits filter the 'normal' population for the moving average.")
trunc_min = st.sidebar.number_input("Lower Truncation Limit", value=3.5, step=0.1)
trunc_max = st.sidebar.number_input("Upper Truncation Limit", value=5.5, step=0.1)

st.sidebar.markdown("**Control Limits (Alarms)**")
st.sidebar.caption("Multiplier for the Moving Average Standard Deviation")
control_limit_z = st.sidebar.number_input("Z-Score Multiplier", value=3.0, step=0.1)

st.sidebar.markdown("---")
st.sidebar.header("🎯 3. Simulation Bias")
st.sidebar.caption("Enter comma-separated percentages (e.g., -10, -5, 5, 10)")
bias_input = st.sidebar.text_input("Systematic Errors (%)", value="-10, -5, -2, 2, 5, 10")
sim_runs = st.sidebar.number_input("Simulations per Bias", min_value=5, max_value=50, value=20)

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
                "Auto-detect", 
                "YYYYMMDDHHMMSS (Dense)", 
                "YYYY-MM-DD HH:MM:SS", 
                "DD/MM/YYYY HH:MM:SS", 
                "MM/DD/YYYY HH:MM:SS"
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
        selected_inst = st.selectbox("Select Instrument to Analyze", ["-- Select --"] + unique_inst)
        
        if selected_inst != "-- Select --":
            df_inst = df_test[df_test[inst_col].astype(str) == selected_inst].copy()
            
            st.subheader("Absolute Clinical Limits (Garbage Filter)")
            st.markdown("Remove obvious artifacts, negative values, and literal analyzer error codes *before* running any simulations.")
            
            c1, c2 = st.columns(2)
            with c1: gross_min = st.number_input("Minimum Possible Physiological Value", value=0.0)
            with c2: gross_max = st.number_input("Maximum Possible Physiological Value", value=100.0)
            
            if st.button("Apply Gross Cleansing", type="primary"):
                original_count = len(df_inst)
                df_inst[val_col] = pd.to_numeric(df_inst[val_col], errors='coerce')
                df_clean = df_inst.dropna(subset=[val_col])
                df_clean = df_clean[(df_clean[val_col] >= gross_min) & (df_clean[val_col] <= gross_max)]
                
                # --- DATE PARSING LOGIC ---
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
                
                st.success("✅ Data Cleansing Complete!")
                m1, m2, m3 = st.columns(3)
                m1.metric("Original Rows", original_count)
                m2.metric("Garbage Rows Dropped", original_count - final_count)
                m3.metric("Clean Baseline Data", final_count)

# --- PHASE 3, 4, 5 & 6: THE SIMULATION ENGINE AND REPORTING ---
if 'clean_data' in st.session_state:
    st.markdown("---")
    st.header("Step 3: Run IFCC-Compliant MA Simulations")
    
    if st.button("🚀 Run Simulation Engine", type="primary"):
        with st.spinner("Calculating Baseline and Simulating Errors..."):
            df = st.session_state['clean_data'].copy()
            v_col = st.session_state['val_col']
            
            # 1. Baseline Profiling (Apply Algorithmic Truncation to normal data)
            base_mask = (df[v_col] >= trunc_min) & (df[v_col] <= trunc_max)
            df_trunc = df[base_mask].copy()
            
            # Calculate Baseline MA Stats
            if "Simple" in algorithm:
                baseline_ma = df_trunc[v_col].rolling(window=block_size).mean()
            elif "Median" in algorithm:
                baseline_ma = df_trunc[v_col].rolling(window=block_size).median()
            else:
                baseline_ma = df_trunc[v_col].ewm(span=block_size, adjust=False).mean()
                
            target_mean = baseline_ma.mean()
            ma_sd = baseline_ma.std()
            ucl = target_mean + (control_limit_z * ma_sd)
            lcl = target_mean - (control_limit_z * ma_sd)
            
            # 2. Simulation Loop
            biases = [float(b.strip()) for b in bias_input.split(',')]
            results_data = []
            
            for bias in biases:
                nped_list = []
                for _ in range(sim_runs):
                    # Pick a random injection point
                    start_idx = random.randint(block_size * 2, len(df) - (block_size * 5))
                    
                    # Create a simulated shifted array
                    sim_vals = df[v_col].values.copy()
                    sim_vals[start_idx:] = sim_vals[start_idx:] * (1 + (bias / 100.0))
                    
                    # IFCC RULE: Apply truncation limits AFTER bias is injected
                    valid_mask = (sim_vals >= trunc_min) & (sim_vals <= trunc_max)
                    valid_vals = sim_vals[valid_mask]
                    
                    # Calculate MA on the truncated shifted data
                    if len(valid_vals) >= block_size:
                        valid_series = pd.Series(valid_vals)
                        if "Simple" in algorithm:
                            ma_sim = valid_series.rolling(window=block_size).mean()
                        elif "Median" in algorithm:
                            ma_sim = valid_series.rolling(window=block_size).median()
                        else:
                            ma_sim = valid_series.ewm(span=block_size, adjust=False).mean()
                        
                        # Find the first index where MA breaches UCL or LCL
                        breach_idx = ma_sim[(ma_sim > ucl) | (ma_sim < lcl)].index
                        
                        # Calculate NPed (Samples to detection)
                        if len(breach_idx) > 0:
                            # Rough estimation of total samples (including truncated) elapsed
                            samples_to_detect = int(breach_idx[0] - (start_idx * (len(valid_vals)/len(sim_vals))))
                            if samples_to_detect > 0:
                                nped_list.append(samples_to_detect)
                
                # Aggregate results for this bias
                if nped_list:
                    results_data.append({
                        "Bias (%)": bias,
                        "Median NPed": np.median(nped_list),
                        "Max NPed": np.max(nped_list),
                        "Min NPed": np.min(nped_list)
                    })

            # --- PHASE 5: VISUALIZATION ---
            st.success("Simulations Complete!")
            
            res_df = pd.DataFrame()
            if results_data:
                res_df = pd.DataFrame(results_data).sort_values("Bias (%)")
                
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=res_df["Bias (%)"],
                    y=res_df["Median NPed"],
                    name='Median NPed',
                    error_y=dict(
                        type='data',
                        symmetric=False,
                        array=res_df["Max NPed"] - res_df["Median NPed"],
                        arrayminus=res_df["Median NPed"] - res_df["Min NPed"],
                        visible=True
                    ),
                    marker_color='royalblue'
                ))
                
                fig.update_layout(
                    title="MA Validation Chart (Bias vs. Samples to Detection)",
                    xaxis_title="Systematic Error / Bias (%)",
                    yaxis_title="Patient Results Needed for Error Detection",
                    template="plotly_white"
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
            # Display Metrics Summary
            st.subheader("Baseline AON Metrics")
            m1, m2, m3 = st.columns(3)
            m1.metric("Target Mean", f"{target_mean:.3f}")
            m2.metric("Upper Control Limit (UCL)", f"{ucl:.3f}")
            m3.metric("Lower Control Limit (LCL)", f"{lcl:.3f}")

            # --- PHASE 6: IFCC COMPLIANT PDF REPORT GENERATION ---
            if not res_df.empty:
                st.markdown("---")
                st.header("Step 4: Export Validation Report")
                st.markdown("Generate an IFCC-compliant documentation report for your laboratory Quality Management System.")
                
                # Function to generate PDF
                def create_pdf(org, assay, unit_label, algo, n, t_min, t_max, z, mean, sd, u_lim, l_lim, results_df):
                    pdf = FPDF()
                    pdf.add_page()
                    
                    # Header
                    pdf.set_font("helvetica", 'B', 16)
                    pdf.cell(0, 10, "PBRTQC / AON Performance Verification Report", ln=True, align='C')
                    pdf.ln(5)
                    
                    # Section 1: Metadata
                    pdf.set_font("helvetica", 'B', 12)
                    pdf.cell(0, 10, "1. Report Metadata", ln=True)
                    pdf.set_font("helvetica", '', 11)
                    pdf.cell(0, 8, f"Organization / Laboratory: {org}", ln=True)
                    pdf.cell(0, 8, f"Assay: {assay}", ln=True)
                    pdf.cell(0, 8, f"Unit: {unit_label}", ln=True)
                    pdf.ln(5)
                    
                    # Section 2: AON Parameters
                    pdf.set_font("helvetica", 'B', 12)
                    pdf.cell(0, 10, "2. Selected AON Parameters", ln=True)
                    pdf.set_font("helvetica", '', 11)
                    pdf.cell(0, 8, f"Algorithm: {algo}", ln=True)
                    pdf.cell(0, 8, f"Block Size (N): {n}", ln=True)
                    pdf.cell(0, 8, f"Lower Truncation Limit: {t_min} {unit_label}", ln=True)
                    pdf.cell(0, 8, f"Upper Truncation Limit: {t_max} {unit_label}", ln=True)
                    pdf.ln(5)
                    
                    # Section 3: Baseline Statistics
                    pdf.set_font("helvetica", 'B', 12)
                    pdf.cell(0, 10, "3. Baseline Statistics & Control Limits", ln=True)
                    pdf.set_font("helvetica", '', 11)
                    pdf.cell(0, 8, f"Target Mean: {mean:.3f} {unit_label}", ln=True)
                    pdf.cell(0, 8, f"Moving Average Standard Deviation: {sd:.3f}", ln=True)
                    pdf.cell(0, 8, f"Control Limit Z-Score: {z}", ln=True)
                    pdf.cell(0, 8, f"Lower Control Limit (LCL): {l_lim:.3f} {unit_label}", ln=True)
                    pdf.cell(0, 8, f"Upper Control Limit (UCL): {u_lim:.3f} {unit_label}", ln=True)
                    pdf.ln(5)
                    
                    # Section 4: Simulation Results
                    pdf.set_font("helvetica", 'B', 12)
                    pdf.cell(0, 10, "4. Simulation Error Detection Results (ANPed)", ln=True)
                    pdf.set_font("helvetica", 'I', 10)
                    pdf.cell(0, 8, "Number of patient results affected before error detection (Median & 95th Percentile range)", ln=True)
                    pdf.set_font("helvetica", '', 10)
                    
                    # Simple Table Header
                    pdf.set_font("helvetica", 'B', 10)
                    pdf.cell(40, 8, "Injected Bias (%)", border=1)
                    pdf.cell(40, 8, "Median NPed", border=1)
                    pdf.cell(40, 8, "Min NPed", border=1)
                    pdf.cell(40, 8, "Max NPed", border=1, ln=True)
                    
                    # Table Data
                    pdf.set_font("helvetica", '', 10)
                    for index, row in results_df.iterrows():
                        pdf.cell(40, 8, f"{row['Bias (%)']}%", border=1)
                        pdf.cell(40, 8, f"{row['Median NPed']:.0f}", border=1)
                        pdf.cell(40, 8, f"{row['Min NPed']:.0f}", border=1)
                        pdf.cell(40, 8, f"{row['Max NPed']:.0f}", border=1, ln=True)
                    
                    # Output PDF as bytearray
                    return pdf.output()

                # Generate the PDF bytes
                pdf_bytes = create_pdf(org_name, assay_name, unit, algorithm, block_size, 
                                       trunc_min, trunc_max, control_limit_z, 
                                       target_mean, ma_sd, ucl, lcl, res_df)
                
                # Streamlit Download Button
                st.download_button(
                    label="📄 Download IFCC Compliance Report (PDF)",
                    data=bytes(pdf_bytes),
                    file_name=f"AON_Report_{assay_name.replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    type="primary"
                )
