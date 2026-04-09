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
APP_NAME = "LabMesh AON Formatter"
st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="expanded")

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

# --- BRANDING HEADER ---
# Ensure your logo file (e.g., 'logo.png') is in the same directory as this script.
try:
    logo_img = Image.open("logo.png")
    col1, col2 = st.columns([1, 8])
    with col1:
        st.image(logo_img, width=80)
    with col2:
        st.title(APP_NAME)
except FileNotFoundError:
    st.title(f"🧪 {APP_NAME}")
    st.caption("*(Note: 'logo.png' not found in directory. Add it to display the LabMesh logo here.)*")

st.markdown("Build, validate, and document patient-based real-time quality control parameters.")
st.markdown("---")

# ==========================================
# SUBCLASS FPDF FOR PROFESSIONAL REPORTS
# ==========================================
PROFESSIONAL_BLUE = (0, 75, 125)
LIGHT_BLUE_BG = (220, 240, 250)
INTERPRETATION_COLORS = {"Breach": (150, 0, 0), "Green": (0, 150, 0), "Grey": (150, 150, 150)}

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
             self.cell(28, 16, "LabMesh Logo", align='C')
             self.set_text_color(0)
             self.set_draw_color(0) 

        self.set_font("helvetica", 'B', 12)
        self.set_text_color(*PROFESSIONAL_BLUE)
        self.set_xy(10, 8) 
        self.cell(0, 10, self.org_name, ln=True, align='R')
        self.set_font("helvetica", 'B', 20)
        self.set_text_color(0)
        self.cell(0, 15, f"{APP_NAME}: Verification Report", ln=True, align='C')
        self.set_font("helvetica", 'I', 10)
        now = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        self.cell(0, 8, f"Report Generated: {now}", ln=True, align='R')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", 'I', 8)
        self.set_text_color(*INTERPRETATION_COLORS["Grey"])
        self.cell(0, 10, "© 2026 LabMesh. All Rights Reserved. A general quality improvement tool. Clinical decisions remain with the laboratory.", ln=True, align='C')
        self.set_x(-20)
        self.cell(20, 10, f"Page {self.page_no()}/{{nb}}", ln=True, align='R')

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
    st.info("👈 Please upload and cleanse your data in the sidebar to unlock the dashboard.")
else:
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
            
            # --- DYNAMIC RECOMMENDATION LOGIC ---
            try:
                max_n = max([int(n.strip()) for n in block_sizes_input.split(',') if n.strip().isdigit()])
            except:
                max_n = 50
                
            ideal_after = max_n * 5
            total_rows = len(st.session_state['clean_data'])
            
            if ideal_after > (total_rows * 0.4):
                ideal_after = int(total_rows * 0.4)
                
            st.caption(f"💡 **Tip:** Set 'Samples After' to at least **{ideal_after}** (based on max N={max_n} and your {total_rows}-row dataset) to ensure the simulation has enough runway.")
            # ------------------------------------

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
                
                # --- PRE-FLIGHT WARNING ---
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
                            marker_color='#004b7d' # Updated to LabMesh Blue
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
                
                if not res_df.empty and len(baseline_stats) > 0:
                     # Create the PDF object
                    pdf = PDFReport(org_name, assay_name, unit, algorithm, operating_mode, logo_path="logo.png")
                    pdf.add_page()
                    
                    # Section 1: Parameters
                    pdf.set_font("helvetica", 'B', 12)
                    pdf.set_text_color(*PROFESSIONAL_BLUE)
                    pdf.cell(0, 10, "1. AON Parameters", ln=True)
                    pdf.set_text_color(0)
                    pdf.set_font("helvetica", '', 11)
                    pdf.cell(0, 8, f"Block Size (N): {primary_stat['Block Size (N)']}", ln=True)
                    pdf.cell(0, 8, f"Truncation Limits: {trunc_min} to {trunc_max} {unit}", ln=True)
                    pdf.cell(0, 8, f"Z-Score: {control_limit_z}", ln=True)
                    pdf.ln(5)
                    
                    # Section 2: Baseline Stats
                    pdf.set_font("helvetica", 'B', 12)
                    pdf.set_text_color(*PROFESSIONAL_BLUE)
                    pdf.cell(0, 10, "2. Baseline Statistics", ln=True)
                    pdf.set_text_color(0)
                    pdf.set_font("helvetica", '', 11)
                    pdf.cell(0, 8, f"Target Mean: {primary_stat['Target Mean']:.3f} {unit}", ln=True)
                    pdf.cell(0, 8, f"Lower Control Limit (LCL): {primary_stat['LCL']:.3f} {unit}", ln=True)
                    pdf.cell(0, 8, f"Upper Control Limit (UCL): {primary_stat['UCL']:.3f} {unit}", ln=True)
                    pdf.ln(5)
                    
                    # Section 3: Data Table with Header Color
                    pdf.set_font("helvetica", 'B', 12)
                    pdf.set_text_color(*PROFESSIONAL_BLUE)
                    pdf.cell(0, 10, "3. Error Detection Results (ANPed)", ln=True)
                    
                    # Table Header - Colored
                    pdf.set_font("helvetica", 'B', 10)
                    pdf.set_fill_color(*PROFESSIONAL_BLUE)
                    pdf.set_text_color(255, 255, 255) # White text
                    pdf.cell(40, 8, "Bias (%)", border=1, align='C', fill=True)
                    pdf.cell(40, 8, "Median NPed", border=1, align='C', fill=True)
                    pdf.cell(40, 8, "Min NPed", border=1, align='C', fill=True)
                    pdf.cell(40, 8, "Max NPed", border=1, align='C', fill=True, ln=True)
                    
                    # Table Data - Normal
                    pdf.set_font("helvetica", '', 10)
                    pdf.set_text_color(0) # Back to black text
                    for _, row in primary_df.iterrows():
                        pdf.cell(40, 8, f"{row['Bias (%)']}%", border=1, align='C')
                        pdf.cell(40, 8, f"{row['Median NPed']:.0f}", border=1, align='C')
                        pdf.cell(40, 8, f"{row['Min NPed']:.0f}", border=1, align='C')
                        pdf.cell(40, 8, f"{row['Max NPed']:.0f}", border=1, align='C', ln=True)
                        
                    pdf_bytes = pdf.output()
                    
                    st.download_button(
                        label="📄 Download LabMesh Verification Report (PDF)",
                        data=bytes(pdf_bytes),
                        file_name=f"LabMesh_AON_Report_{assay_name.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        type="primary"
                    )
