import pandas as pd


HIGH_RISK_ACTION = "Expedite inventory, escalate supplier, or transfer stock from another DC."
MEDIUM_RISK_ACTION = "Monitor closely and review replenishment plan within 48 hours."
LOW_RISK_ACTION = "No immediate action required."


def generate_decisions(df: pd.DataFrame) -> pd.DataFrame:
    decision_df = df.copy()
    decision_df["issue_summary"] = decision_df.apply(_summarize_issue, axis=1)
    decision_df["recommended_action"] = decision_df["overall_risk"].map(
        {
            "HIGH": HIGH_RISK_ACTION,
            "MEDIUM": MEDIUM_RISK_ACTION,
            "LOW": LOW_RISK_ACTION,
        }
    )
    decision_df["business_impact"] = decision_df["estimated_stockout_loss"].apply(_business_impact)
    return decision_df


def _summarize_issue(row: pd.Series) -> str:
    issues = []

    if row["stockout_risk"] == "HIGH":
        issues.append("inventory is below reorder point")
    elif row["stockout_risk"] == "MEDIUM":
        issues.append("days of supply is close to lead-time coverage")

    if row["supplier_risk"] == "HIGH":
        issues.append("supplier OTIF is below 85%")
    elif row["supplier_risk"] == "MEDIUM":
        issues.append("supplier OTIF needs attention")

    if row["logistics_risk"] == "HIGH":
        issues.append("shipment delay exceeds two days")
    elif row["logistics_risk"] == "MEDIUM":
        issues.append("shipment is delayed")

    if not issues:
        return "Supply position is stable with no active risk signals."

    return "; ".join(issues).capitalize() + "."


def _business_impact(estimated_stockout_loss: float) -> str:
    if estimated_stockout_loss > 0:
        return f"Estimated avoided stockout loss: ${estimated_stockout_loss:,.0f}"

    return "Operational risk is currently controlled."
