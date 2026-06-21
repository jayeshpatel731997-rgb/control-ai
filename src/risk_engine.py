import numpy as np
import pandas as pd


def calculate_risk(df: pd.DataFrame) -> pd.DataFrame:
    risk_df = df.copy()

    demand = risk_df["avg_daily_demand"].replace(0, np.nan)
    risk_df["days_to_stockout"] = (
        risk_df["current_inventory"].div(demand).replace([np.inf, -np.inf], np.nan).fillna(np.inf)
    )
    risk_df["days_of_supply"] = risk_df["days_to_stockout"]
    risk_df["inventory_gap"] = risk_df["current_inventory"] - risk_df["reorder_point"]
    risk_df["gross_margin_per_unit"] = risk_df["selling_price"] - risk_df["unit_cost"]

    risk_df["stockout_risk"] = np.select(
        [
            risk_df["current_inventory"] < risk_df["reorder_point"],
            risk_df["days_of_supply"] <= risk_df["lead_time_days"] + 3,
        ],
        ["HIGH", "MEDIUM"],
        default="LOW",
    )

    risk_df["supplier_risk"] = np.select(
        [
            risk_df["supplier_otif"] < 0.85,
            risk_df["supplier_otif"] < 0.92,
        ],
        ["HIGH", "MEDIUM"],
        default="LOW",
    )

    risk_df["logistics_risk"] = np.select(
        [
            risk_df["shipment_delay_days"] > 2,
            risk_df["shipment_delay_days"] > 0,
        ],
        ["HIGH", "MEDIUM"],
        default="LOW",
    )

    risk_columns = ["stockout_risk", "supplier_risk", "logistics_risk"]
    risk_df["overall_risk"] = np.select(
        [
            risk_df[risk_columns].eq("HIGH").any(axis=1),
            risk_df[risk_columns].eq("MEDIUM").any(axis=1),
        ],
        ["HIGH", "MEDIUM"],
        default="LOW",
    )

    shortage_units = (risk_df["reorder_point"] - risk_df["current_inventory"]).clip(lower=0)
    risk_df["estimated_stockout_loss"] = shortage_units * risk_df["gross_margin_per_unit"]
    risk_df["stockout_timing"] = np.select(
        [
            risk_df["days_to_stockout"] < risk_df["lead_time_days"],
            risk_df["days_to_stockout"] <= risk_df["lead_time_days"] + 3,
        ],
        ["critical", "warning"],
        default="safe",
    )

    return risk_df
