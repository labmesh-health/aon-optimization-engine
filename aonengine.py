import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import random
import os
import tempfile
from fpdf import FPDF

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="PBRTQC / AON Optimization Engine", layout="wide", initial_sidebar_state="expanded")

# --- PROFESSIONAL BLUE COLOR SCHEME ---
PROFESSIONAL_BLUE = (0, 75, 125)  # Professional Dark Blue
LIGHT_BLUE_BG = (220, 240, 250)    # Professional Very Light Blue

# --- Define standard Interpretive Flair colors for the PDF report ---
INTERPRETATION_COLORS = {
    "Breach": (150, 0, 0),         # Professional Red for limit breaches
    "Green": (0, 150, 0),          # Professional Green
    "Grey": (150, 150, 150),        # Professional Grey
}

# --- CUSTOM CSS FOR DASHBOARD UX ---
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
    </style>
    """, unsafe_allow_html=True)

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
        self.set_fill_color(*LIGHT_BLUE_BG) 
        self.set_draw_color(0, 0, 0) 

    def header(self):
        if self.logo_path and os.path.exists(self.logo_path):
            self.image(self.logo_path, 10, 8, 30) 
        else:
             self.set_draw_color(*INTERPRETATION_COLORS["Grey"])
             self.rect(10, 8, 30, 20)
             self.set_xy(11, 10)
             self.set_font("helvetica", 'I', 8)
             self.cell(28, 16, "Place Website Logo here", align='C')
             self.set_text_color(0)
             self.set_draw_color(0) 

        self.set_font("helvetica", 'B', 12)
        self.set_text_color(*PROFESSIONAL_BLUE)
        self.set_xy(10, 8) 
        self.cell(0, 10, self.org_name, ln=True, align='R')
        self.set_font("helvetica", 'B', 20)
        self.set_text_color(0)
        self.cell(0, 15, "PBRTQC Performance Verification Report", ln=True, align='C')
        self.set_font("helvetica", 'I', 10)
        now = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        self.cell(0, 8, f"Report Generated: {now}", ln=True, align='R')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", 'I', 8)
        self.set_text_color(*INTERPRETATION_COLORS["Grey"])
        self.cell(0, 10, "© 2024 LabMesh. All Rights Reserved. A general quality improvement tool. Clinical decisions remain with the laboratory.", ln=True, align='C')
        self.set_x(-20)
        self.cell(20, 10, f"Page {self.page_no()}/{{nb}}", ln=True, align='R')

    def section_title(self, label):
        self.ln(5)
        self.set_font("helvetica", 'B', 14)
        self.set_text_color(*PROFESSIONAL_BLUE)
        self.cell(0, 10, label, ln=True)
        self.set_text_color(0) 
        self.ln(3)

    def dynamic_intro_flair(self):
        intro_text = f"Executive Summary: Performance verification of the {self.algorithm_type} implementation for Assay {self.assay} ({self.unit}). Using {self.grouping_mode} grouping, standard simulation parameters were applied to the laboratory's historic dataset. Baseline statistics and control limits (UCL/LCL) match standard verification practices for Average Number of patient results until Error Detection (ANPed). Monte Carlo simulation performance verified per IFCC and quality specifications."
        self.multi_cell(0, 5, intro_text)
        self.ln(5)

    def professional_parameter_card(self, label, value):
        self.set_font("helvetica", 'B', 10)
        self.cell(40, 6, label + ":", border='L, T', fill=True)
        self.set_font("helvetica", '', 10)
        self.cell(0, 6, str(value), border='R, T', ln=True)

    def professional_aon_scorecard(self, stat_row, bias_impact_data_all, trunc_min, trunc_max, algorithm, operating_mode, control_limit_z):
        N = stat_row['Window / Block Size (N)']
        self.set_font("helvetica", 'B', 12)
        self.cell(0, 10, f"AON Scorecard: Block Size (Window) N={N}", ln=True)
        self.ln(2)

        self.set_fill_color(*LIGHT_BLUE_BG)
        self.professional_parameter_card("Algorithm used", algorithm)
        self.professional_parameter_card("Grouping period", operating_mode)
        self.professional_parameter_card("Control Z-Score", control_limit_z)
        self.professional_parameter_card("Algorithmic Truncation Range", f"{trunc_min} to {trunc_max} ({self.unit})")
        self.cell(0, 0, "", border='T', ln=True) 
        self.ln(3)

        self.set_font("helvetica", 'B', 10)
        self.set_text_color(*PROFESSIONAL_BLUE)
        self.set_fill_color(*LIGHT_BLUE_BG) 

        cols = ["Property (Verification Stats binned population)", "Value"]
        property_w = 100
        value_w = 90
        
        self.cell(property_w, 8, cols[0], border=1, fill=True, align='L')
        self.cell(value_w, 8, cols[1], border=1, fill=True, align='L', ln=True)
        self.set_text_color(0) 
        self.set_font("helvetica", '', 10)

        data_rows = [
            ("Target Mean Average", f"{stat_row['Target Mean']:.3f} {self.unit}"),
            ("Baseline Standard Deviation", f"{stat_row['Baseline SD']:.3f}"),
            ("Upper Control Limit (UCL)", f"{stat_row['Upper Control Limit (UCL)']:.3f} {self.unit}"),
            ("Lower Control Limit (LCL)", f"{stat_row['Lower Control Limit (LCL)']:.3f} {self.unit}"),
            ("Simulated Max Theoretical Shift (Mean + Max Bias)", f"{bias_impact_data_all[0]['Shifted Theoretical Mean']:.3f} {self.unit}") 
        ]
        
        for prop, val in data_rows:
            self.cell(property_w, 8, prop, border=1)
            self.cell(value_w, 8, str(val), border=1, ln=True)
        self.ln(5)

        self.interpretaion_notes(N, stat_row['Target Mean'], stat_row['Upper Control Limit (UCL)'], algorithm)

    def multi_block_results_table(self, results_df):
        self.interpretaion_notes(0,0,0,0) 

        self.set_fill_color(*PROFESSIONAL_BLUE) 
        self.set_text_color(*LIGHT_BLUE_BG) 
        self.set_font("helvetica", 'B', 10)

        col_widths = [30, 25, 45, 30, 30]
        headers = ["Window (W)", "Bias (%)", "Median NPed", "Min NPed", "Max NPed"]
        
        for i, col in enumerate(headers):
             self.cell(col_widths[i], 8, col, border=1, align='C', fill=True)

        self.set_text_color(0) 
        self.set_font("helvetica", '', 10)
        self.ln()

        for index, row in results_df.iterrows():
            if index % 2 == 0:
                 self.set_fill_color(245, 245, 245)
                 alternating_fill = True
            else:
                 alternating_fill = False

            current_median = row['Median NPed']

            self.cell(col_widths[0], 8, str(row['Block Size (N)']), border=1, align='C', fill=alternating_fill)
            self.cell(col_widths[1], 8, f"{row['Bias (%)']}%", border=1, align='C', fill=alternating_fill)

            if current_median < 50:
                 self.set_text_color(*INTERPRETATION_COLORS["Green"])
            elif current_median > 200:
                 self.set_text_color(*INTERPRETATION_COLORS["Breach"])
            else:
                 self.set_text_color(0) 

            self.cell(col_widths[2], 8, f"{current_median:.0f}", border=1, align='C', fill=alternating_fill)
            self.set_text_color(0) 

            self.cell(col_widths[3], 8, f"{row['Min NPed']:.0f}", border=1, align='C', fill=alternating_fill)
            self.cell(col_widths[4], 8, f"{row['Max NPed']:.0f}", border=1, align='C', fill=alternating_fill)
            self.ln()
        self.ln(5)

    def data_summary_flair(self, assay, unit, instruments_used, total_data_points, org):
        self.interpretaion_notes(0,0,0,0) 
        self.section_title("Real-World Data Verification (historic dataset overview)")
        summary_text = f"The verification was performed on real-world historic data ({total_data_points} points after clinical filtering). Historic results were collected from assay {assay} ({unit}), operated across {len(instruments_used)} different analytical modules at the {org} facility. This comprehensive historic data verified performance for multiple independent binned average grouping (W) standards, matching the IFCC real-time PBRTQC operational model."
        self.multi_cell(0, 5, summary_text)
        self.ln(5)
        
        self.interpretaion_notes(0,0,0,0) 
        self.set_font("helvetica", 'B', 10)
        self.cell(0, 8, f"Modules Used ({len(instruments_used)} independent systems):", ln=True)
        self.set_font("helvetica", '', 10)
        instrum_list_text = ", ".join(instruments_used[:10]) + ("..." if len(instruments_used) > 10 else "")
        self.multi_cell(0, 5, instrum_list_text)
        self.ln(5)

    def interpretaion_notes(self, N, target, ucl, algorithm_type):
        if N == 0:
            notes = "Verification Notes: All clinical decisions are the sole responsibility of the laboratory. NPed is the Median Number of Patient Results until Error Detection *within* a group based on Monte Carlo simulations. The tool provides a general verification of the historic data. Results may not apply to new patient populations or analyzer conditions. Interpretation color-coding (Green/Red) uses standard laboratory improvement targets. For official validation, a clinically relevant detection speed (ANPed) target should be compared to the actual Median ANPed performance results based on biological variation specifications and clinical assay goals."
            self.set_text_color(0)
            self.set_font("helvetica", 'I', 10)
            self.multi_cell(0, 5, notes)
            self.ln(5)
        elif N > 0:
             notes = f"Verification Interpretation (Window {N}): This scorecard verifies statistics matching the selected grouping mode. Real-time performance is verifiable inside the comparison table."
             self.set_text_color(0)
             self.set_font("helvetica", 'I', 10)
             self.multi_cell(0, 5, notes)
             self.ln(3)

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
                st.session_state['data_usage_flair'] = {
                    "assay": selected_test,
                    "instruments": selected_insts,
                    "total_points": len(df_clean)
                }
                st.sidebar.success(f"✅ Ready! {len(df_clean)} records retained.")

# ==========================================
# MAIN CANVAS: DASHBOARD & SIMULATION
# ==========================================
if 'clean_data' not in st.session_state:
    st.title("⚙️ PBRTQC Optimization Engine")
    st.info("👈 Please upload and cleanse your data in the sidebar to unlock the dashboard.")
else:
    st.title("🎛️ AON Simulation Dashboard")
    
    total_rows_flair = st.session_state['data_usage_flair']['total_points']
    default_max_n_flair = 50 
    
    # --- CONFIGURATION SECTION ---
    with st.expander("🛠️ Simulation & AON Configurations", expanded=True):
        col_meta, col_aon, col_sim = st.columns(3)
        
        with col_meta:
            st.markdown("##### 📝 Report Metadata")
            org_name = st.text_input("Organization", value="Roche Diagnostics India")
            assay_name = st.text_input("Assay Name", value=st.session_state['data_usage_flair']['assay'])
            unit = st.text_input("Unit", value="U/L")
            
        with col_aon:
            st.markdown("##### 📐 AON Parameters")
            algorithm = st.selectbox("Algorithm", ["Simple Moving Average (SMA)", "Moving Median", "EWMA"])
            operating_mode = st.radio("Operating Mode", ["Continuous (Rolling)", "Batch (Binning)"], horizontal=True)
            block_sizes_input = st.text_input("Block Sizes (comma-separated)", value="10, 25, 50, 100")
            
            st.markdown("**Algorithmic Truncation Limits**")
            st.caption("Filters normal population to reduce noise.")
            c_trunc1, c_trunc2 = st.columns(2)
            with c_trunc1: trunc_min = st.number_input("Lower Truncation Limit", value=5.0, step=0.1)
            with c_trunc2: trunc_max = st.number_input("Upper Truncation Limit", value=60.0, step=0.1)
            control_limit_z = st.number_input("Control Limits Z-Score", value=3.0, step=0.1)

        with col_sim:
            st.markdown("##### 🎯 Simulation Settings")
            c_sim1, c_sim2 = st.columns(2)
            with c_sim1: samples_before = st.number_input("Samples Before", value=150, step=10)
            with c_sim2: samples_after = st.number_input("Samples After", value=500, step=10)
            
            try:
                max_n_continuous_flair = max([int(n.strip()) for n in block_sizes_input.split(',') if n.strip().isdigit()])
            except:
                max_n_continuous_flair = default_max_n_flair 
                
            continuous_recommendation_samples_after_flair = max_n_continuous_flair * 5
            safe_dataset_continuous_flair = int(total_rows_flair * 0.4)
            if continuous_recommendation_samples_after_flair > safe_dataset_continuous_flair:
                continuous_recommendation_samples_after_flair = safe_dataset_continuous_flair
                continuous_safey_check_recommend_flair = f" (data limited)"
            else:
                 continuous_safey_check_recommend_flair = ""

            st.caption(f"💡 **Tip:** Set 'Samples After' to at least **{continuous_recommendation_samples_after_flair}**{continuous_safey_check_recommend_flair} (based on max N={max_n_continuous_flair} and dataset size).")

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
            
            block_sizes = [int(n.strip()) for n in block_sizes_input.split(',') if n.strip().isdigit()]
            all_results = []
            baseline_stats = []
            
            base_mask = (df[v_col] >= trunc_min) & (df[v_col] <= trunc_max)
            df_trunc = df[base_mask].copy()
            
            for n in block_sizes:
                if "Simple" in algorithm:
                    baseline_ma = df_trunc[v_col].rolling(window=n).mean()
                elif "Median" in algorithm:
                    baseline_ma = df_trunc[v_col].rolling(window=n).median()
                else:
                    baseline_ma = df_trunc[v_col].ewm(span=n, adjust=False).mean()
                
                if "Batch" in operating_mode:
                    baseline_ma = baseline_ma[n-1::n]
                    
                target_mean = baseline_ma.mean()
                ma_sd = baseline_ma.std()
                ucl = target_mean + (control_limit_z * ma_sd)
                lcl = target_mean - (control_limit_z * ma_sd)
                
                # --- KEY FIX FOR THE PDF ---
                # The PDF code looks for these EXACT keys. Do not change these strings.
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
                
                # Pre-Flight Warning
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
                            
                            if "Batch" in operating_mode:
                                ma_sim = ma_sim[n-1::n]
                                
                            trunc_start_idx = valid_mask[:start_idx].sum()
                            
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
            
            # Baseline Cards (Using custom HTML for shadowing and colors)
            st.subheader("📊 Baseline Limits per Window")
            card_cols = st.columns(len(baseline_stats))
            for i, stat in enumerate(baseline_stats):
                with card_cols[i]:
                    card_html = f"""
                    <div style="
                        background-color: white;
                        border-radius: 8px;
                        box-shadow: 0 4px 10px rgba(0,0,0,0.08);
                        overflow: hidden;
                        text-align: center;
                        border: 1px solid #e9ecef;
                        margin-bottom: 10px;
                        font-family: sans-serif;
                    ">
                        <div style="
                            background-color: #004b7d;
                            color: white;
                            padding: 10px;
                            font-size: 14px;
                            font-weight: 600;
                        ">
                            Window (N={stat['Block Size (N)']}) Mean
                        </div>
                        <div style="padding: 15px 10px;">
                            <div style="font-size: 32px; font-weight: 700; color: #1f2937;">
                                {stat['Target Mean']:.2f}
                            </div>
                            <div style="font-size: 13px; color: #6c757d; margin-top: 8px;">
                                <span style="color:#dc3545; font-weight:600;">UCL:</span> {stat['UCL']:.2f} &nbsp;|&nbsp; 
                                <span style="color:#198754; font-weight:600;">LCL:</span> {stat['LCL']:.2f}
                            </div>
                        </div>
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)
            
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
                            marker_color='#004b7d'
                        ))
                        fig_bar.update_layout(title=f"MA Validation (N={primary_n})", template="plotly_white")
                        st.plotly_chart(fig_bar, use_container_width=True)

            with tab_data:
                st.markdown("#### Bias Impact Analysis")
                st.markdown("Theoretical shifts for the primary window to confirm if limits are breached.")
                
                bias_impact_data_all = []
                if len(baseline_stats) > 0:
                    primary_stat = baseline_stats[0]
                    p_mean = primary_stat["Target Mean"]
                    p_lcl = primary_stat["LCL"]
                    p_ucl = primary_stat["UCL"]
                    
                    for bias in biases:
                        shifted_mean = p_mean * (1 + (bias / 100.0))
                        will_alarm = "Yes 🔴" if (shifted_mean > p_ucl or shifted_mean < p_lcl) else "No 🟢"
                        bias_impact_data_all.append({
                            "Bias (%)": f"{bias}%",
                            "Shifted Theoretical Mean": shifted_mean, 
                            "Display Mean": f"{shifted_mean:.3f}",
                            "LCL": f"{p_lcl:.3f}",
                            "UCL": f"{p_ucl:.3f}",
                            "Breaches Limits?": will_alarm
                        })
                    
                    display_df = pd.DataFrame(bias_impact_data_all).drop(columns=['Shifted Theoretical Mean']).rename(columns={'Display Mean': 'Shifted Mean'})
                    st.dataframe(display_df, use_container_width=True)

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
                    
                    pdf.dynamic_intro_flair()
                    pdf.data_summary_flair(
                        assay=assay_name, 
                        unit=unit, 
                        instruments_used=st.session_state['data_usage_flair']['instruments'], 
                        total_data_points=st.session_state['data_usage_flair']['total_points'], 
                        org=org_name
                    )

                    pdf.professional_aon_scorecard(
                        stat_row=baseline_stats[0], 
                        bias_impact_data_all=bias_impact_data_all,
                        trunc_min=trunc_min, 
                        trunc_max=trunc_max, 
                        algorithm=algorithm, 
                        operating_mode=operating_mode, 
                        control_limit_z=control_limit_z
                    )
                    
                    pdf.section_title("Simulation Error Detection Results (ANPed)")
                    
                    primary_results_df = res_df[res_df['Block Size (N)'] == str(primary_stat['Block Size (N)'])]
                    pdf.multi_block_results_table(primary_results_df)
                    
                    pdf_bytes = pdf.output()
                    
                    st.download_button(
                        label="📄 Download LabMesh Verification Report (PDF)",
                        data=bytes(pdf_bytes),
                        file_name=f"LabMesh_AON_Report_{assay_name.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        type="primary"
                    )
