# ⚙️ PBRTQC / AON Optimization Engine

A Python/Streamlit web application designed to build, validate, and document Patient-Based Real-Time Quality Control (PBRTQC) and Average of Normals (AON) parameters.

## Overview
This tool is designed to replace legacy simulation software by providing an end-to-end pipeline to:
1. Ingest and cleanse historical LIS/Middleware data.
2. Run Monte Carlo-style simulations injecting positive and negative systematic errors (bias).
3. Calculate the Average Number of Patient results affected before error detection (ANPed).
4. Generate Bias Detection Curves and MA Validation Charts.
5. Export an IFCC-compliant PDF validation report for laboratory quality management systems.
