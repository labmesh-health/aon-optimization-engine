import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import random
from fpdf import FPDF

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="AON Optimization Engine", layout="wide", initial_sidebar_state="expanded")

# --- CUSTOM CSS FOR METRIC CARDS ---
st.markdown("""
    <style>
    div[data-testid="metric-container"] {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 5% 5% 5% 10%;
        border-radius: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# SIDEBAR: PHASE 1 - DATA INGESTION & PREP
# ==========================================
st.sidebar.title("📂 1. Data Ingestion")
st.sidebar.markdown("Upload and cleanse your historical data first.")

uploaded_file = st.sidebar.file_uploader("Upload LIS/Middleware Data (CSV)", type=['csv'])

if uploaded_file:
    df_raw = pd.read_csv(uploaded_file)
    actual_columns = df_raw.columns.tolist()
    
    with st.sidebar.expander("⚙️ Column Mapping", expanded=False):
        date_col = st.selectbox("Date Column", actual_columns, index=0)
        date_format = st.selectbox("Date Format", [
            "Auto-detect", "YYYYMMDDHHMMSS (Dense)", "YYYY-MM-DD HH:MM:SS", "DD/MM/YYYY HH:MM:SS", "MM/DD/YYYY HH:MM:SS"
        ])
        inst_col = st.selectbox("Instrument Column", actual_columns, index=0)
        test_col = st.selectbox("Test ID Column", actual_columns, index=0)
        val_col = st.selectbox("Result Value Column", actual_columns, index=0)

    st.sidebar.markdown("---")
    st.sidebar.subheader("🧹 2. Gross Cleansing")
    
    unique_tests = sorted(df_raw[test_col].dropna().astype(str).unique())
    selected_test = st.sidebar.selectbox("Select Test", ["-- Select --"] + unique_tests)
    
    if selected_test != "-- Select --":
        df_test = df_raw[df_raw[test_col].astype(str) == selected_test].copy()
        unique_inst = sorted(df_test[inst_col].dropna().astype(str).unique())
        selected_insts = st.sidebar.multiselect("Select Instrument(s)", unique_inst, default=unique_inst[0] if len(unique_inst) > 0 else None)
        
        if selected_insts:
            gross_min = st.sidebar.number_input("Min Physiological Value", value=0.0)
            gross_max = st.sidebar.number_input("Max Physiological Value", value=500.0)
            
            if st.sidebar.button("Apply Gross Cleansing", type="primary", use_container_width=True):
                df_inst = df_test[df_test[inst_col].astype(str).isin(selected_insts)].copy()
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
                
                st.session_state['clean_data'] = df_clean
                st.session_state['val_col'] = val_col
                st.sidebar.success(f"✅ Ready! {len(df_clean)} records retained.")

# ==========================================
# MAIN CANVAS: DASHBOARD & SIMULATION
# ==========================================
if 'clean_data' not in st.session_state:
    st.title("⚙️ PBRTQC Optimization Engine")
    st.info("👈 Please upload and cleanse your data in the sidebar to unlock the dashboard.")
else:
    st.title("🎛️ AON Simulation Dashboard")
    
    # --- CONFIGURATION SECTION ---
    with st.expander("🛠️ Simulation & AON Configurations", expanded=True):
        col_meta, col_aon, col_sim = st.columns(3)
        
        with col_meta:
            st.markdown("##### 📝 Report Metadata")
            org_name = st.text_input("Organization", value="Roche Diagnostics India")
            assay_name = st.text_input("Assay Name", value="AST_KRL")
            unit = st.text_input("Unit", value="U/L")
            
        with col_aon:
            st.markdown("##### 📐 AON Parameters")
            algorithm = st.selectbox("Algorithm", ["Simple Moving Average (SMA)", "Moving Median", "EWMA"])
            operating_mode = st.radio("Operating Mode", ["Continuous (Rolling)", "Batch (Binning)"], horizontal=True)
            block_sizes_input = st.text_input("Block Sizes (comma-separated)", value="10, 25, 50, 100")
            
            c_trunc1, c_trunc2 = st.columns(2)
            with c_trunc1: trunc_min = st.number_input("Lower Truncation Limit", value=5.0, step=0.1)
            with c_trunc2: trunc_max = st.number_input("Upper Truncation Limit", value=60.0, step=0.1)
            control_limit_z = st.number_input("Z-Score Multiplier", value=3.0, step=0.1)

        with col_sim:
            st.markdown("##### 🎯 Simulation Settings")
            c_sim1, c_sim2 = st.columns(2)
            with c_sim1: samples_before = st.number_input("Samples Before", value=150, step=10)
            with c_sim2: samples_after = st.number_input("Samples After", value=500, step=10)
            sim_runs = st.number_input("Simulations per Bias", min_value=5, max_value=100, value=20)
            
            st.markdown("**Bias Range (%)**")
            b_col1, b_col2, b_col3 = st.columns(3)
            with b_col1: bias_min = st.number_input("Min Bias", value=-30, step=1)
            with b_col2: bias_max = st.number_input("Max Bias", value=30, step=1)
            with b_col3: bias_step = st.number_input("Step", value=5, step=1)
            
            biases = [b for b in range(int(bias_min), int(bias_max) + 1, int(bias_step)) if b != 0]

    # --- SIMULATION TRIGGER ---
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚀 Run Multi-Window Simulation", type="primary", use_container_width=True):
        with st.spinner("Simulating multiple block sizes and calculating limits..."):
            df = st.session_state['clean_data'].copy()
            v_col = st.session_state['val_col']
            
            block_sizes = [int(n.strip()) for n in block_sizes_input.split(',')]
            all_results = []
            baseline_stats = []
            
            base_mask = (df[v_col] >= trunc_min) & (df[v_col] <= trunc_max)
            df_trunc = df[base_mask].copy()
            
            for n in block_sizes:
                # 1. Calculate Baseline MA Stats
                if "Simple" in algorithm:
                    baseline_ma = df_trunc[v_col].rolling(window=n).mean()
                elif "Median" in algorithm:
                    baseline_ma = df_trunc[v_col].rolling(window=n).median()
                else:
                    baseline_ma = df_trunc[v_col].ewm(span=n, adjust=False).mean()
                
                if operating_mode == "Batch (Binning)":
                    baseline_ma = baseline_ma[n-1::n]
                    
                target_mean = baseline_ma.mean()
                ma_sd = baseline_ma.std()
                ucl = target_mean + (control_limit_z * ma_sd)
                lcl = target_mean - (control_limit_z * ma_sd)
                
                baseline_stats.append({
                    "Block Size (N)": n,
                    "Target Mean": target_mean,
                    "LCL": lcl,
                    "UCL": ucl
                })
                
                # --- NEW: DYNAMIC PRE-FLIGHT WARNING ---
                max_bias_pct = max([abs(b) for b in biases]) / 100.0
                max_theoretical_shift = target_mean * max_bias_pct
                distance_to_ucl = ucl - target_mean
                
                if max_theoretical_shift < distance_to_ucl:
                    st.warning(f"""
                    ⚠️ **Pre-Flight Warning for Block Size N={n}: Your Truncation Limits are too wide!**
                    * **Baseline Noise (Distance to Control Limit):** {distance_to_ucl:.2f}
                    * **Max Error Shift (Mean × Max Bias):** {max_theoretical_shift:.2f}
                    
                    *The simulated error is mathematically invisible to the algorithm. Lower your Upper Truncation Limit to shrink the baseline noise.*
                    """)
                
                # 2. Run Simulations
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
                            
                            if operating_mode == "Batch (Binning)":
                                ma_sim = ma_sim[n-1::n]
                                
                            # Calculate exact index where bias starts in truncated array
                            trunc_start_idx = valid_mask[:start_idx].sum()
                            
                            # Search for breaches AFTER injection
                            ma_post_injection = ma_sim[ma_sim.index >= trunc_start_idx]
                            breaches = ma_post_injection[(ma_post_injection > ucl) | (ma_post_injection < lcl)].index
                            
                            if len(breaches) > 0:
                                samples_to_detect = int(breaches[0] - trunc_start_idx)
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

            # --- RENDER RESULTS UI ---
            st.markdown("---")
            
            # Baseline Cards
            st.subheader("📊 Baseline Limits per Window")
            card_cols = st.columns(len(baseline_stats))
            for i, stat in enumerate(baseline_stats):
                with card_cols[i]:
                    st.metric(label=f"Window (N={stat['Block Size (N)']}) Mean", value=f"{stat['Target Mean']:.2f}")
                    st.caption(f"**UCL:** {stat['UCL']:.2f} | **LCL:** {stat['LCL']:.2f}")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Tabbed Interface
            tab_charts, tab_data, tab_report = st.tabs(["📈 Interactive Charts", "📋 Data Tables", "📄 Export PDF Report"])
            res_df = pd.DataFrame(all_results)
            
            with tab_charts:
                if not res_df.empty:
                    c_chart1, c_chart2 = st.columns([2, 1])
                    with c_chart1:
                        fig_line = px.line(
                            res_df, x="Bias (%)", y="Median NPed", color="Block Size (N)", markers=True,
                            title="Bias Detection Curves (All Block Sizes)",
                            labels={"Median NPed": "Results needed for bias detection"}
                        )
                        # Auto-scales Y-axis (Removed clamping code)
                        fig_line.update_layout(template="plotly_white")
                        st.plotly_chart(fig_line, use_container_width=True)
                    
                    with c_chart2:
                        primary_n = str(block_sizes[0])
                        primary_df = res_df[res_df["Block Size (N)"] == primary_n].sort_values("Bias (%)")
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

            with tab_data:
                st.markdown("#### Bias Impact Analysis")
                st.markdown("Theoretical shifts for the primary window to confirm if limits are breached.")
                
                if len(baseline_stats) > 0:
                    primary_stat = baseline_stats[0]
                    p_mean = primary_stat["Target Mean"]
                    p_lcl = primary_stat["LCL"]
                    p_ucl = primary_stat["UCL"]
                    
                    bias_impact_data = []
                    for bias in biases:
                        shifted_mean = p_mean * (1 + (bias / 100.0))
                        will_alarm = "Yes 🔴" if (shifted_mean > p_ucl or shifted_mean < p_lcl) else "No 🟢"
                        bias_impact_data.append({
                            "Bias (%)": f"{bias}%",
                            "Shifted Mean": f"{shifted_mean:.3f}",
                            "LCL": f"{p_lcl:.3f}",
                            "UCL": f"{p_ucl:.3f}",
                            "Breaches Limits?": will_alarm
                        })
                    st.dataframe(pd.DataFrame(bias_impact_data), use_container_width=True)

            with tab_report:
                st.markdown("#### Generate IFCC Compliance Report")
                st.info("Exports parameters and data for the primary block size selected.")
                
                def create_pdf(org, assay, unit_label, algo, n, t_min, t_max, z, mean, u_lim, l_lim, results_df):
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("helvetica", 'B', 16)
                    pdf.cell(0, 10, "PBRTQC / AON Performance Verification Report", ln=True, align='C')
                    pdf.ln(5)
                    
                    pdf.set_font("helvetica", 'B', 12)
                    pdf.cell(0, 10, "1. Metadata & Parameters", ln=True)
                    pdf.set_font("helvetica", '', 11)
                    pdf.cell(0, 8, f"Lab: {org} | Assay: {assay} ({unit_label})", ln=True)
                    pdf.cell(0, 8, f"Algorithm: {algo} | Block Size (N): {n}", ln=True)
                    pdf.cell(0, 8, f"Truncation Limits: {t_min} to {t_max} | Z-Score: {z}", ln=True)
                    pdf.ln(5)
                    
                    pdf.set_font("helvetica", 'B', 12)
                    pdf.cell(0, 10, "2. Baseline Statistics", ln=True)
                    pdf.set_font("helvetica", '', 11)
                    pdf.cell(0, 8, f"Target Mean: {mean:.3f} | LCL: {l_lim:.3f} | UCL: {u_lim:.3f}", ln=True)
                    pdf.ln(5)
                    
                    pdf.set_font("helvetica", 'B', 12)
                    pdf.cell(0, 10, "3. Simulation Error Detection Results (ANPed)", ln=True)
                    pdf.set_font("helvetica", 'B', 10)
                    pdf.cell(40, 8, "Bias (%)", border=1)
                    pdf.cell(40, 8, "Median NPed", border=1)
                    pdf.cell(40, 8, "Min NPed", border=1)
                    pdf.cell(40, 8, "Max NPed", border=1, ln=True)
                    
                    pdf.set_font("helvetica", '', 10)
                    for _, row in results_df.iterrows():
                        pdf.cell(40, 8, f"{row['Bias (%)']}%", border=1)
                        pdf.cell(40, 8, f"{row['Median NPed']:.0f}", border=1)
                        pdf.cell(40, 8, f"{row['Min NPed']:.0f}", border=1)
                        pdf.cell(40, 8, f"{row['Max NPed']:.0f}", border=1, ln=True)
                    return pdf.output()

                if not res_df.empty and len(baseline_stats) > 0:
                    pdf_bytes = create_pdf(org_name, assay_name, unit, algorithm, primary_stat['Block Size (N)'], 
                                           trunc_min, trunc_max, control_limit_z, 
                                           primary_stat['Target Mean'], primary_stat['UCL'], primary_stat['LCL'], primary_df)
                    
                    st.download_button(
                        label="📄 Download IFCC Report (PDF)",
                        data=bytes(pdf_bytes),
                        file_name=f"AON_Report_{assay_name.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        type="primary"
                    )
