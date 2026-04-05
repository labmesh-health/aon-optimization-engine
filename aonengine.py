import streamlit as st
import pandas as pd
import numpy as np

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

st.sidebar.markdown("---")
st.sidebar.header("🎯 3. Simulation Bias")
st.sidebar.caption("Enter comma-separated percentages (e.g., -10, -5, 5, 10)")
bias_input = st.sidebar.text_input("Systematic Errors to Simulate (%)", value="-10, -5, -2, 2, 5, 10")

# --- MAIN SCREEN: PHASE 1 DATA INGESTION ---
st.header("Step 1: Upload & Map Data")
uploaded_file = st.file_uploader("Upload Historical LIS/Middleware Data (CSV)", type=['csv'])

if uploaded_file:
    # Load raw data
    df_raw = pd.read_csv(uploaded_file)
    actual_columns = df_raw.columns.tolist()
    
    with st.expander("Column Mapping", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1: date_col = st.selectbox("Date Column", actual_columns, index=0)
        with col2: inst_col = st.selectbox("Instrument Column", actual_columns, index=0)
        with col3: test_col = st.selectbox("Test ID Column", actual_columns, index=0)
        with col4: val_col = st.selectbox("Result Value Column", actual_columns, index=0)

    st.markdown("---")
    st.header("Step 2: Filter & Gross Cleanse")
    
    # Dynamically populate tests and instruments based on user mapping
    unique_tests = sorted(df_raw[test_col].dropna().astype(str).unique())
    selected_test = st.selectbox("Select Test to Analyze", ["-- Select --"] + unique_tests)
    
    if selected_test != "-- Select --":
        # Filter by test
        df_test = df_raw[df_raw[test_col].astype(str) == selected_test].copy()
        
        unique_inst = sorted(df_test[inst_col].dropna().astype(str).unique())
        selected_inst = st.selectbox("Select Instrument to Analyze", ["-- Select --"] + unique_inst)
        
        if selected_inst != "-- Select --":
            # Filter by instrument
            df_inst = df_test[df_test[inst_col].astype(str) == selected_inst].copy()
            
            st.subheader("Absolute Clinical Limits (Garbage Filter)")
            st.markdown("Remove obvious artifacts, negative values, and literal analyzer error codes *before* running any simulations.")
            
            c1, c2 = st.columns(2)
            with c1: gross_min = st.number_input("Minimum Possible Physiological Value", value=0.0)
            with c2: gross_max = st.number_input("Maximum Possible Physiological Value", value=1000.0)
            
            if st.button("Apply Gross Cleansing", type="primary"):
                original_count = len(df_inst)
                
                # 1. Force values to numeric (turns "Error", "---", text to NaN)
                df_inst[val_col] = pd.to_numeric(df_inst[val_col], errors='coerce')
                
                # 2. Drop NaNs and apply gross limits
                df_clean = df_inst.dropna(subset=[val_col])
                df_clean = df_clean[(df_clean[val_col] >= gross_min) & (df_clean[val_col] <= gross_max)]
                
                # 3. Sort by Date strictly
                df_clean[date_col] = pd.to_datetime(df_clean[date_col], errors='coerce')
                df_clean = df_clean.dropna(subset=[date_col]).sort_values(by=date_col, ascending=True)
                
                final_count = len(df_clean)
                
                st.success("✅ Data Cleansing Complete!")
                m1, m2, m3 = st.columns(3)
                m1.metric("Original Rows", original_count)
                m2.metric("Garbage Rows Dropped", original_count - final_count)
                m3.metric("Clean Baseline Data", final_count)
                
                # Save the clean dataset to Streamlit's session state for the Simulation Engine
                st.session_state['clean_data'] = df_clean
                st.session_state['val_col'] = val_col
                
                st.info("The data is now clean and locked in memory. We are ready to run the MA Simulations.")