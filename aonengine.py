import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import random
import os
import tempfile
from fpdf import FPDF
from PIL import Image

# --- PAGE CONFIGURATION & BRANDING ---
APP_NAME = "LabMesh AoN Optimization Engine"
st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="expanded")

# --- PROFESSIONAL BLUE COLOR SCHEME ---
PROFESSIONAL_BLUE = (0, 75, 125)  
LIGHT_BLUE_BG = (220, 240, 250)    

# --- Define standard Interpretive Flair colors for the PDF report ---
INTERPRETATION_COLORS = {
    "Breach": (150, 0, 0),         
    "Green": (0, 150, 0),          
    "Grey": (150, 150, 150),        
}

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    div[data-testid="metric-container"] {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 5% 5% 5% 10%;
        border-radius: 5px;
    }
    div.stButton > button {
        background-color: #004b7d;
        color: white;
        border-radius: 5px;
        transition: 0.3s;
    }
    div.stButton > button:hover {
        background-color: #0060a0;
        color: white;
    }
    .app-title {
        margin-top: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# APP HEADER & LOGO 
# ==========================================
col_logo, col_title = st.columns([1.5, 10]) 
with col_logo:
    if os.path.exists("logo.png"):
        st.image(Image.open("logo.png"), width=150) 
    else:
        st.markdown("<h2>🧪</h2>", unsafe_allow_html=True)
with col_title:
    st.markdown(f'<h1 class="app-title">{APP_NAME}</h1>', unsafe_allow_html=True)
st.markdown("---")

# ==========================================
# SUBCLASS FPDF FOR PROFESSIONAL REPORTS
# ==========================================
class PDFReport(FPDF):
    def __init__(self, org_name, assay, unit, algorithm_type, grouping_mode, logo_path=None):
        super().__init__()
        self.org_name = org_name
        self.assay = assay
        self.unit = unit
        self.algorithm_type = algorithm_type
        self.grouping_mode = grouping_mode
        self.logo_path = logo_path
        self.set_auto_page_break(auto=True, margin=15)
        self.alias_nb_pages()

    def header(self):
        if self.logo_path and os.path.exists(self.logo_path):
            self.image(self.logo_path, 10, 8, 45) 
            
        self.set_y(15) 
        self.set_font("helvetica", 'B', 18)
        self.set_text_color(*PROFESSIONAL_BLUE)
        self.cell(0, 10, "PBRTQC Performance Verification", ln=True, align='R')
        self.set_font("helvetica", 'I', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, f"Generated for: {self.org_name}", ln=True, align='R')
        self.ln(15) 

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, "© 2026 LabMesh. All Rights Reserved. A general quality improvement tool. Clinical decisions remain with the laboratory.", 0, 0, 'C')
        self.set_x(-20)
        self.cell(20, 10, f"Page {self.page_no()}/{{nb}}", 0, 0, 'R')

    def section_title(self, label):
        self.ln(5)
        self.set_font("helvetica", 'B', 12)
        self.set_text_color(*PROFESSIONAL_BLUE)
        self.cell(0, 10, label, ln=True)
        self.set_text_color(0, 0, 0) 
        self.ln(2)

# ==========================================
# SIDEBAR: PHASE 1 - DATA INGESTION & PREP
# ==========================================
st.sidebar.title("📂 1. Data Ingestion")
st.sidebar.markdown("Upload and cleanse your historical data first.")

uploaded_file = st.sidebar.file_uploader(
    "Upload LIS/Middleware Data (CSV)", 
    type=['csv'],
    help="Upload your raw data extract. The file should be in CSV format and contain at least: Date/Time, Instrument Name, Test ID, and Result Value."
)

if uploaded_file:
    df_raw = pd.read_csv(uploaded_file)
    actual_columns = df_raw.columns.tolist()
    
    with st.sidebar.expander("⚙️ Column Mapping", expanded=False):
        date_col = st.selectbox("Date Column", actual_columns, index=0, help="Select the column containing the timestamp for each test result.")
        date_format = st.selectbox("Date Format", ["Auto-detect", "YYYYMMDDHHMMSS (Dense)", "YYYY-MM-DD HH:MM:SS", "DD/MM/YYYY HH:MM:SS", "MM/DD/YYYY HH:MM:SS"], help="If 'Auto-detect' fails, manually specify how the dates are formatted in your file.")
        inst_col = st.selectbox("Instrument Column", actual_columns, index=0, help="Select the column that identifies which analyzer performed the test.")
        test_col = st.selectbox("Test ID Column", actual_columns, index=0, help="Select the column that contains the name or ID of the assay (e.g., AST, K, Na).")
        val_col = st.selectbox("Result Value Column", actual_columns, index=0, help="Select the column containing the actual numeric result of the test.")

    st.sidebar.markdown("---")
    st.sidebar.subheader("🧹 2. Gross Cleansing")
    
    unique_tests = sorted(df_raw[test_col].dropna().astype(str).unique())
    selected_test = st.sidebar.selectbox("Select Test", ["-- Select --"] + unique_tests)
    
    if selected_test != "-- Select --":
        df_test = df_raw[df_raw[test_col].astype(str) == selected_test].copy()
        unique_inst = sorted(df_test[inst_col].dropna().astype(str).unique())
        selected_insts = st.sidebar.multiselect("Select Instrument(s)", unique_inst, default=unique_inst[0] if len(unique_inst) > 0 else None)
        
        if selected_insts:
            gross_min = st.sidebar.number_input("Min Physiological Value", value=0.0, help="Absolute lowest possible value for this assay. Anything lower is considered a gross error and is deleted before AON analysis.")
            gross_max = st.sidebar.number_input("Max Physiological Value", value=500.0, help="Absolute highest possible value for this assay. Anything higher is considered a gross error and is deleted.")
            
            if st.sidebar.button("Apply Gross Cleansing", type="primary", use_container_width=True):
                df_inst = df_test[df_test[inst_col].astype(str).isin(selected_insts)].copy()
                df_inst[val_col] = pd.to_numeric(df_inst[val_col], errors='coerce')
                df_clean = df_inst.dropna(subset=[val_col])
                df_clean = df_clean[(df_clean[val_col] >= gross_min) & (df_clean[val_col] <= gross_max)]
                
                if date_format == "YYYYMMDDHHMMSS (Dense)":
                    df_clean[date_col] = pd.to_datetime(df_clean[date_col].astype(str).str.split('.').str[0], format='%Y%m%d%H%M%S', errors='coerce')
                else:
                    df_clean[date_col] = pd.to_datetime(df_clean[date_col], errors='coerce')
                
                df_clean = df_clean.dropna(subset=[date_col]).sort_values(by=date_col, ascending=True)
                
                st.session_state['clean_data'] = df_clean
                st.session_state['val_col'] = val_col
                st.session_state['data_usage_flair'] = {"assay": selected_test, "total_points": len(df_clean)}
                st.sidebar.success(f"✅ Ready! {len(df_clean)} records retained.")

# ==========================================
# MAIN CANVAS: DASHBOARD & SIMULATION
# ==========================================
if 'clean_data' not in st.session_state:
    st.info("👈 Please upload and cleanse your data in the sidebar to unlock the dashboard.")
else:
    try:
        total_rows = st.session_state['data_usage_flair']['total_points']
        default_assay = st.session_state['data_usage_flair']['assay']
    except KeyError:
        total_rows = 1000 
        default_assay = "Assay"
        
    with st.expander("🛠️ Simulation & AON Configurations", expanded=True):
        col_meta, col_aon, col_sim = st.columns(3)
        
        with col_meta:
            st.markdown("##### 📝 Report Metadata")
            org_name = st.text_input("Organization", value="Roche Diagnostics India")
            assay_name = st.text_input("Assay Name", value=default_assay)
            unit = st.text_input("Unit", value="U/L")
            
        with col_aon:
            st.markdown("##### 📐 AON Parameters")
            algorithm = st.selectbox("Algorithm", ["Simple Moving Average (SMA)", "Moving Median", "EWMA"], help="SMA is the most common. EWMA gives more weight to recent results, detecting sudden shifts faster.")
            operating_mode = st.radio("Operating Mode", ["Continuous (Rolling)", "Batch (Binning)"], horizontal=True, help="Continuous checks after every result. Batch waits until 'N' results are collected, averages them, and checks once.")
            block_sizes_input = st.text_input("Block Sizes (comma-separated)", value="10, 25, 50, 100", help="The number of results (N) used to calculate the average. Smaller blocks detect large errors faster.")
            
            st.markdown("**Algorithmic Truncation Limits**")
            c_trunc1, c_trunc2 = st.columns(2)
            with c_trunc1: trunc_min = st.number_input("Lower Truncation Limit", value=5.0, step=0.1, help="Results below this value are ignored to isolate the 'normal' healthy population.")
            with c_trunc2: trunc_max = st.number_input("Upper Truncation Limit", value=60.0, step=0.1, help="CRITICAL: Results above this are ignored. Do not set this too high, or outliers will mask real errors!")
            control_limit_z = st.number_input("Control Limits Z-Score", value=3.0, step=0.1, help="Determines how wide your limits are. 3.0 is standard. Lowering it increases sensitivity but adds false alarms.")

        with col_sim:
            st.markdown("##### 🎯 Simulation Settings")
            c_sim1, c_sim2 = st.columns(2)
            with c_sim1: samples_before = st.number_input("Samples Before", value=150, step=10, help="The 'warm-up' period. The number of normal samples processed to establish a stable baseline *before* the error is injected.")
            with c_sim2: samples_after = st.number_input("Samples After", value=500, step=10, help="The 'runway'. The max number of samples the engine will process after injecting the error to see if an alarm triggers.")
            
            try:
                max_n = max([int(n.strip()) for n in block_sizes_input.split(',') if n.strip().isdigit()])
            except:
                max_n = 50
                
            ideal_after = max_n * 5
            if ideal_after > (total_rows * 0.4): ideal_after = int(total_rows * 0.4)
            st.caption(f"💡 **Tip:** Set 'Samples After' to at least **{ideal_after}** (based on max N={max_n} and your {total_rows}-row dataset) to ensure enough runway.")

            sim_runs = st.number_input("Simulations per Bias", min_value=5, max_value=100, value=20, help="How many times to repeat the Monte Carlo simulation to find the median detection speed.")
            
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
            
            block_sizes = [int(n.strip()) for n in block_sizes_input.split(',') if n.strip().isdigit()]
            all_results = []
            baseline_stats = []
            
            base_mask = (df[v_col] >= trunc_min) & (df[v_col] <= trunc_max)
            df_trunc = df[base_mask].copy()
            
            for n in block_sizes:
                if "Simple" in algorithm: baseline_ma = df_trunc[v_col].rolling(window=n).mean()
                elif "Median" in algorithm: baseline_ma = df_trunc[v_col].rolling(window=n).median()
                else: baseline_ma = df_trunc[v_col].ewm(span=n, adjust=False).mean()
                
                if "Batch" in operating_mode: baseline_ma = baseline_ma[n-1::n]
                    
                target_mean = baseline_ma.mean()
                ma_sd = baseline_ma.std()
                ucl = target_mean + (control_limit_z * ma_sd)
                lcl = target_mean - (control_limit_z * ma_sd)
                
                baseline_stats.append({
                    "Window / Block Size (N)": n,
                    "Block Size (N)": n,
                    "Target Mean": target_mean,
                    "Baseline SD": ma_sd,
                    "Lower Control Limit (LCL)": lcl,
                    "Upper Control Limit (UCL)": ucl,
                    "LCL": lcl,
                    "UCL": ucl
                })
                
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
                
                for bias in biases:
                    nped_list = []
                    for _ in range(sim_runs):
                        safe_start_min = max(n, samples_before)
                        safe_start_max = len(df) - samples_after
                        if safe_start_max <= safe_start_min: continue 
                            
                        start_idx = random.randint(safe_start_min, safe_start_max)
                        sim_vals = df[v_col].values.copy()
                        sim_vals[start_idx:] = sim_vals[start_idx:] * (1 + (bias / 100.0))
                        
                        valid_mask = (sim_vals >= trunc_min) & (sim_vals <= trunc_max)
                        valid_vals = sim_vals[valid_mask]
                        
                        if len(valid_vals) >= n:
                            valid_series = pd.Series(valid_vals)
                            if "Simple" in algorithm: ma_sim = valid_series.rolling(window=n).mean()
                            elif "Median" in algorithm: ma_sim = valid_series.rolling(window=n).median()
                            else: ma_sim = valid_series.ewm(span=n, adjust=False).mean()
                            
                            if "Batch" in operating_mode: ma_sim = ma_sim[n-1::n]
                                
                            trunc_start_idx = valid_mask[:start_idx].sum()
                            ma_post_injection = ma_sim[ma_sim.index >= trunc_start_idx]
                            breaches = ma_post_injection[(ma_post_injection > ucl) | (ma_post_injection < lcl)].index
                            
                            if len(breaches) > 0:
                                samples_to_detect = int(breaches[0] - trunc_start_idx)
                                if samples_to_detect > 0: nped_list.append(samples_to_detect)
                    
                    if nped_list:
                        all_results.append({
                            "Block Size (N)": str(n),
                            "Bias (%)": bias,
                            "Median NPed": np.median(nped_list),
                            "Min NPed": np.min(nped_list),
                            "Max NPed": np.max(nped_list)
                        })

            st.markdown("---")
            
            st.subheader("📊 Baseline Limits per Window")
            card_cols = st.columns(len(baseline_stats))
            for i, stat in enumerate(baseline_stats):
                with card_cols[i]:
                    card_html = f"""
                    <div style="background-color: white; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); overflow: hidden; text-align: center; border: 1px solid #e9ecef; margin-bottom: 10px; font-family: sans-serif;">
                        <div style="background-color: #004b7d; color: white; padding: 10px; font-size: 14px; font-weight: 600;">
                            Window (N={stat['Block Size (N)']}) Mean
                        </div>
                        <div style="padding: 15px 10px;">
                            <div style="font-size: 32px; font-weight: 700; color: #1f2937;">{stat['Target Mean']:.2f}</div>
                            <div style="font-size: 13px; color: #6c757d; margin-top: 8px;">
                                <span style="color:#dc3545; font-weight:600;">UCL:</span> {stat['UCL']:.2f} &nbsp;|&nbsp; 
                                <span style="color:#198754; font-weight:600;">LCL:</span> {stat['LCL']:.2f}
                            </div>
                        </div>
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            tab_charts, tab_data, tab_report = st.tabs(["📈 Interactive Charts", "📋 Data Tables", "📄 Export PDF Report"])
            res_df = pd.DataFrame(all_results)
            
            with tab_charts:
                if not res_df.empty:
                    c_chart1, c_chart2 = st.columns([2, 1])
                    with c_chart1:
                        fig_line = px.line(res_df, x="Bias (%)", y="Median NPed", color="Block Size (N)", markers=True, title="Bias Detection Curves (All Block Sizes)")
                        fig_line.update_layout(template="plotly_white", height=600)
                        st.plotly_chart(fig_line, use_container_width=True)
                        
                        # --- DYNAMIC CHART 1 SUMMARY ---
                        with st.expander("📝 Data Interpretation Notes: Multi-Window Curves", expanded=True):
                            st.markdown(f"**Observations from the simulated data:**")
                            st.markdown(f"* **Sensitivity vs. Speed:** Smaller block sizes (e.g., N={block_sizes[0]}) generally detect large shifts faster. Larger blocks tend to be better at confirming smaller, subtle shifts.")
                            # Check if the smallest bias was detected by any window
                            smallest_bias_mag = min([abs(b) for b in biases])
                            smallest_bias_results = res_df[res_df['Bias (%)'].abs() == smallest_bias_mag]
                            if not smallest_bias_results.empty:
                                min_detect_n = smallest_bias_results.loc[smallest_bias_results['Median NPed'].idxmin()]['Block Size (N)']
                                st.markdown(f"* **Small Bias Detection:** For the smallest simulated shift (±{smallest_bias_mag}%), window size **N={min_detect_n}** provided the fastest median detection.")
                            st.caption("*Disclaimer: These observations are based on Monte Carlo simulations of historic data. They do not constitute clinical guidance. Always compare ANPed targets to analytical quality specifications (e.g., allowable total error).*")

                    with c_chart2:
                        primary_n = str(block_sizes[0])
                        primary_df = res_df[res_df["Block Size (N)"] == primary_n].sort_values("Bias (%)")
                        fig_bar = go.Figure()
                        fig_bar.add_trace(go.Bar(
                            x=primary_df["Bias (%)"], y=primary_df["Median NPed"], name=f'N={primary_n}',
                            error_y=dict(type='data', array=primary_df["Max NPed"] - primary_df["Median NPed"], arrayminus=primary_df["Median NPed"] - primary_df["Min NPed"], visible=True),
                            marker_color='#004b7d'
                        ))
                        fig_bar.update_layout(title=f"MA Validation (N={primary_n})", template="plotly_white", height=600)
                        st.plotly_chart(fig_bar, use_container_width=True)
                        
                        # --- DYNAMIC CHART 2 SUMMARY ---
                        with st.expander(f"📝 Data Interpretation Notes: Primary Window (N={primary_n})", expanded=True):
                            st.markdown(f"**Observations from the simulated data:**")
                            
                            # Analyze the -5% / +5% (or smallest bias) behavior
                            smallest_bias = primary_df['Bias (%)'].abs().min()
                            small_bias_data = primary_df[primary_df['Bias (%)'].abs() == smallest_bias]
                            if not small_bias_data.empty:
                                median_val = small_bias_data['Median NPed'].max() # Use max of the +/- to be conservative
                                st.markdown(f"* **Subtle Shifts:** A small shift of ±{smallest_bias}% requires a median of **~{median_val:.0f}** patient results to trigger an alarm in this configuration.")
                            
                            # Analyze the larger shifts
                            largest_bias = primary_df['Bias (%)'].abs().max()
                            large_bias_data = primary_df[primary_df['Bias (%)'].abs() == largest_bias]
                            if not large_bias_data.empty:
                                median_val_large = large_bias_data['Median NPed'].min()
                                st.markdown(f"* **Critical Shifts:** A massive shift of ±{largest_bias}% is caught much faster, requiring a median of only **~{median_val_large:.0f}** patient results.")
                                
                            st.markdown(f"* **Variance:** The error bars (whiskers) indicate the minimum and maximum detection times observed during the {sim_runs} simulation runs. Wider bars mean less consistent detection.")
                            st.caption(f"*Disclaimer: The clinical significance of a ±{smallest_bias}% shift depends entirely on the biological variation of {assay_name}. Evaluate if {median_val:.0f} reported patients is an acceptable risk for your laboratory.*")

            with tab_data:
                st.markdown("#### Bias Impact Analysis")
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
                            "Bias (%)": f"{bias}%", "Shifted Mean": f"{shifted_mean:.3f}",
                            "LCL": f"{p_lcl:.3f}", "UCL": f"{p_ucl:.3f}", "Breaches Limits?": will_alarm
                        })
                    st.dataframe(pd.DataFrame(bias_impact_data), use_container_width=True)

            with tab_report:
                st.markdown("#### Generate Professional IFCC Compliance Report")
                st.info("Exports parameters, historic data context, and verified results into a professional PDF format.")
                
                if not res_df.empty and len(baseline_stats) > 0:
                    logo_file = "logo.png" if os.path.exists("logo.png") else None

                    pdf = PDFReport(
                        org_name=org_name, 
                        assay=assay_name, 
                        unit=unit, 
                        algorithm_type=algorithm, 
                        grouping_mode=operating_mode,
                        logo_path=logo_file
                    )
                    pdf.add_page()
                    
                    pdf.section_title("Executive Summary")
                    pdf.set_font("helvetica", '', 11)
                    pdf.multi_cell(0, 6, f"This document verifies the performance of the {algorithm} PBRTQC algorithm for {assay_name} ({unit}). The simulation was conducted in {operating_mode} mode using {total_rows} validated historical patient records. The results below outline the baseline statistical noise and the Median Number of Patient Results until Error Detection (ANPed) across various systematic bias shifts.")
                    
                    pdf.ln(5)
                    pdf.set_fill_color(240, 240, 240)
                    pdf.set_font("helvetica", 'B', 10)
                    pdf.cell(95, 8, f" Truncation Range: {trunc_min} - {trunc_max} {unit}", border=1, fill=True)
                    pdf.cell(95, 8, f" Control Limits Z-Score: {control_limit_z}", border=1, fill=True, ln=True)
                    
                    pdf.section_title(f"Baseline Statistics (Primary Window N={primary_stat['Block Size (N)']})")
                    pdf.set_font("helvetica", '', 11)
                    pdf.cell(0, 8, f"Target Mean: {primary_stat['Target Mean']:.3f} {unit}    |    Baseline SD: {primary_stat['Baseline SD']:.3f}", ln=True)
                    pdf.cell(0, 8, f"Upper Control Limit (UCL): {primary_stat['UCL']:.3f} {unit}", ln=True)
                    pdf.cell(0, 8, f"Lower Control Limit (LCL): {primary_stat['LCL']:.3f} {unit}", ln=True)
                    
                    pdf.section_title("Error Detection Performance (ANPed)")
                    
                    pdf.set_fill_color(*PROFESSIONAL_BLUE)
                    pdf.set_text_color(255, 255, 255)
                    pdf.set_font("helvetica", 'B', 10)
                    col_w = [30, 40, 40, 40]
                    pdf.cell(col_w[0], 8, "Block (N)", border=1, align='C', fill=True)
                    pdf.cell(col_w[1], 8, "Injected Bias (%)", border=1, align='C', fill=True)
                    pdf.cell(col_w[2], 8, "Median ANPed", border=1, align='C', fill=True)
                    pdf.cell(col_w[3], 8, "Range (Min - Max)", border=1, align='C', fill=True, ln=True)
                    
                    pdf.set_text_color(0, 0, 0)
                    pdf.set_font("helvetica", '', 10)
                    
                    for idx, row in res_df.iterrows():
                        fill = True if idx % 2 == 0 else False
                        if fill: pdf.set_fill_color(245, 245, 245)
                        
                        pdf.cell(col_w[0], 8, str(row['Block Size (N)']), border=1, align='C', fill=fill)
                        pdf.cell(col_w[1], 8, f"{row['Bias (%)']}%", border=1, align='C', fill=fill)
                        
                        if row['Median NPed'] < 50: pdf.set_text_color(*INTERPRETATION_COLORS["Green"])
                        elif row['Median NPed'] > 200: pdf.set_text_color(*INTERPRETATION_COLORS["Breach"])
                        else: pdf.set_text_color(0, 0, 0)
                            
                        pdf.cell(col_w[2], 8, f"{row['Median NPed']:.0f}", border=1, align='C', fill=fill)
                        
                        pdf.set_text_color(0, 0, 0)
                        pdf.cell(col_w[3], 8, f"{row['Min NPed']:.0f} - {row['Max NPed']:.0f}", border=1, align='C', fill=fill, ln=True)
                    
                    pdf_bytes = pdf.output()
                    
                    st.download_button(
                        label="📄 Download LabMesh Verification Report (PDF)",
                        data=bytes(pdf_bytes),
                        file_name=f"LabMesh_AON_Report_{assay_name.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        type="primary"
                    )
