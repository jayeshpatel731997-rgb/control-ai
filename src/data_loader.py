from pathlib import Path
from typing import IO

import pandas as pd


REQUIRED_COLUMNS = {
    "sku",
    "product_name",
    "category",
    "location",
    "supplier",
    "current_inventory",
    "reorder_point",
    "safety_stock",
    "avg_daily_demand",
    "lead_time_days",
    "supplier_otif",
    "shipment_delay_days",
    "unit_cost",
    "selling_price",
}


def load_supply_data(path: str | Path | IO[bytes]) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing_columns = REQUIRED_COLUMNS.difference(df.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Supply data is missing required columns: {missing}")

    return df
