# Control Tower AI

Control Tower AI is a Streamlit dashboard for real-time supply chain risk monitoring and decision support. It scores SKU-level inventory, supplier, and logistics risk across distribution centers, then recommends actions to reduce stockout exposure.

## Features

- SKU-level risk scoring for stockout, supplier, logistics, and overall risk
- Sidebar filters for location, category, supplier, and risk level
- KPI cards for SKU count, high-risk SKUs, average days of supply, and estimated stockout loss
- Plotly charts for risk concentration by category, location, and stockout loss
- Decision cards for the highest-priority items
- Robust CSV validation and clear Streamlit error handling

## Tech Stack

- Streamlit
- Pandas
- NumPy
- Plotly

## How To Run

```bash
pip install -r requirements.txt
streamlit run app.py
```
