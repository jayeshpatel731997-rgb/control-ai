from pathlib import Path

import plotly.express as px
import streamlit as st

from src.data_loader import load_supply_data
from src.decision_engine import generate_decisions
from src.risk_engine import calculate_risk


DATA_PATH = Path(__file__).parent / "data" / "sample_supply_data.csv"
RISK_ORDER = ["HIGH", "MEDIUM", "LOW"]
RISK_COLORS = {"HIGH": "#D92D20", "MEDIUM": "#F79009", "LOW": "#12B76A"}
TIMING_COLORS = {"critical": "#D92D20", "warning": "#F79009", "safe": "#12B76A"}


def main() -> None:
    st.set_page_config(page_title="Control Tower AI", layout="wide")
    _inject_styles()

    st.title("Control Tower AI")
    st.caption("Real-Time Supply Chain Risk & Decision System")

    try:
        source_df = load_supply_data(DATA_PATH)
    except FileNotFoundError:
        st.error(f"Supply data file was not found: {DATA_PATH}")
        return
    except ValueError as exc:
        st.error(str(exc))
        return

    decision_df = generate_decisions(calculate_risk(source_df))
    filtered_df = _apply_sidebar_filters(decision_df)

    if filtered_df.empty:
        st.warning("No supply records match the selected filters.")
        return

    _render_alert_panel(filtered_df)
    _render_kpis(filtered_df)
    _render_sku_drilldown(filtered_df)
    _render_charts(filtered_df)
    _render_table(filtered_df)
    _render_decision_cards(filtered_df)


def _apply_sidebar_filters(df):
    st.sidebar.header("Filters")

    locations = st.sidebar.multiselect("Location", sorted(df["location"].unique()))
    categories = st.sidebar.multiselect("Category", sorted(df["category"].unique()))
    suppliers = st.sidebar.multiselect("Supplier", sorted(df["supplier"].unique()))
    risks = st.sidebar.multiselect("Overall Risk", RISK_ORDER)

    filtered_df = df.copy()
    if locations:
        filtered_df = filtered_df[filtered_df["location"].isin(locations)]
    if categories:
        filtered_df = filtered_df[filtered_df["category"].isin(categories)]
    if suppliers:
        filtered_df = filtered_df[filtered_df["supplier"].isin(suppliers)]
    if risks:
        filtered_df = filtered_df[filtered_df["overall_risk"].isin(risks)]

    return filtered_df


def _render_alert_panel(df) -> None:
    alerts_df = df[df["overall_risk"].isin(["HIGH", "MEDIUM"])].sort_values(
        "estimated_stockout_loss",
        ascending=False,
    )

    st.subheader("Priority Alerts")
    if alerts_df.empty:
        st.success("No high or medium priority alerts in the current view.")
        return

    for _, row in alerts_df.head(8).iterrows():
        risk_class = row["overall_risk"].lower()
        issue = _short_issue(row)
        st.markdown(
            f"""
            <div class="alert-row {risk_class}">
                <div>
                    <strong>{row["sku"]}</strong>
                    <span class="muted"> | {row["location"]}</span>
                    <div class="alert-issue">{issue}</div>
                </div>
                <div class="alert-side">
                    <span class="risk-pill {risk_class}">{row["overall_risk"]}</span>
                    <span>{_format_money(row["estimated_stockout_loss"])}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_kpis(df) -> None:
    total_skus = df["sku"].nunique()
    high_risk_skus = int((df["overall_risk"] == "HIGH").sum())
    average_days = df["days_of_supply"].replace(float("inf"), 0).mean()
    stockout_loss = df["estimated_stockout_loss"].sum()
    critical_stockouts = int((df["stockout_timing"] == "critical").sum())

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total SKUs", f"{total_skus:,}")
    col2.metric("High Risk SKUs", f"{high_risk_skus:,}")
    col3.metric("Avg Days to Stockout", f"{average_days:,.1f}", f"{critical_stockouts} critical")
    col4.metric("Estimated Stockout Loss", _format_money(stockout_loss))


def _render_sku_drilldown(df) -> None:
    st.subheader("SKU Drill-Down")
    ranked_df = df.assign(_risk_rank=df["overall_risk"].map({"HIGH": 0, "MEDIUM": 1, "LOW": 2}))
    sku_options = [
        f"{row.sku} - {row.product_name}"
        for row in ranked_df.sort_values(
            ["_risk_rank", "estimated_stockout_loss"],
            ascending=[True, False],
        ).itertuples()
    ]

    selected_label = st.selectbox("Select SKU", sku_options)
    selected_sku = selected_label.split(" - ", 1)[0]
    row = df[df["sku"] == selected_sku].iloc[0]
    timing_class = row["stockout_timing"]
    warning_text = (
        "Stockout is projected before supplier lead time."
        if row["days_to_stockout"] < row["lead_time_days"]
        else "Stockout timing is currently inside the planned coverage window."
    )

    st.markdown(
        f"""
        <div class="drilldown-summary {timing_class}">
            <div>
                <strong>{row["product_name"]}</strong>
                <span class="muted"> | {row["location"]} | {row["supplier"]}</span>
            </div>
            <div>{warning_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    chart_left, chart_right = st.columns(2)
    inventory_chart = px.bar(
        x=["Current Inventory", "Reorder Point", "Safety Stock"],
        y=[row["current_inventory"], row["reorder_point"], row["safety_stock"]],
        color=["Current Inventory", "Reorder Point", "Safety Stock"],
        color_discrete_sequence=["#2563EB", "#D92D20", "#667085"],
        labels={"x": "", "y": "Units"},
    )
    inventory_chart.update_layout(showlegend=False, margin=dict(l=10, r=10, t=20, b=10))
    chart_left.plotly_chart(inventory_chart, width="stretch")

    coverage_chart = px.bar(
        x=["Avg Daily Demand", "Days of Supply", "Lead Time"],
        y=[row["avg_daily_demand"], row["days_of_supply"], row["lead_time_days"]],
        color=["Avg Daily Demand", "Days of Supply", "Lead Time"],
        color_discrete_sequence=["#2563EB", TIMING_COLORS[timing_class], "#475467"],
        labels={"x": "", "y": "Value"},
    )
    coverage_chart.update_layout(showlegend=False, margin=dict(l=10, r=10, t=20, b=10))
    chart_right.plotly_chart(coverage_chart, width="stretch")

    detail1, detail2, detail3, detail4 = st.columns(4)
    detail1.metric("Supplier OTIF", f"{row['supplier_otif']:.0%}")
    detail2.metric("Shipment Delay", f"{row['shipment_delay_days']:.0f} days")
    detail3.metric("Days to Stockout", _format_days(row["days_to_stockout"]))
    detail4.metric("Lead Time", f"{row['lead_time_days']:.0f} days")


def _render_charts(df) -> None:
    st.subheader("Risk Signals")
    left, right = st.columns(2)

    category_counts = _risk_count(df, "category")
    fig_category = px.bar(
        category_counts,
        x="category",
        y="count",
        color="overall_risk",
        barmode="group",
        category_orders={"overall_risk": RISK_ORDER},
        color_discrete_map=RISK_COLORS,
        labels={"category": "Category", "count": "SKUs", "overall_risk": "Risk"},
    )
    fig_category.update_layout(margin=dict(l=10, r=10, t=20, b=10), legend_title_text="")
    left.plotly_chart(fig_category, width="stretch")

    location_counts = _risk_count(df, "location")
    fig_location = px.bar(
        location_counts,
        x="location",
        y="count",
        color="overall_risk",
        barmode="group",
        category_orders={"overall_risk": RISK_ORDER},
        color_discrete_map=RISK_COLORS,
        labels={"location": "Location", "count": "SKUs", "overall_risk": "Risk"},
    )
    fig_location.update_layout(margin=dict(l=10, r=10, t=20, b=10), legend_title_text="")
    right.plotly_chart(fig_location, width="stretch")

    top_loss = df.sort_values("estimated_stockout_loss", ascending=False).head(10)
    fig_loss = px.bar(
        top_loss,
        x="estimated_stockout_loss",
        y="sku",
        color="overall_risk",
        orientation="h",
        category_orders={"overall_risk": RISK_ORDER},
        color_discrete_map=RISK_COLORS,
        hover_data=["product_name", "location", "supplier"],
        labels={"estimated_stockout_loss": "Estimated Stockout Loss", "sku": "SKU"},
    )
    fig_loss.update_layout(
        yaxis={"categoryorder": "total ascending"},
        margin=dict(l=10, r=10, t=20, b=10),
        legend_title_text="",
    )
    st.plotly_chart(fig_loss, width="stretch")


def _render_table(df) -> None:
    st.subheader("Supply Risk Table")
    table_columns = [
        "sku",
        "product_name",
        "location",
        "supplier",
        "current_inventory",
        "reorder_point",
        "days_of_supply",
        "days_to_stockout",
        "stockout_timing",
        "stockout_risk",
        "supplier_risk",
        "logistics_risk",
        "overall_risk",
        "estimated_stockout_loss",
    ]

    display_df = df[table_columns].assign(
        _risk_rank=df["overall_risk"].map({"HIGH": 0, "MEDIUM": 1, "LOW": 2})
    )
    display_df = display_df.sort_values(
        by=["_risk_rank", "estimated_stockout_loss"],
        ascending=[True, False],
    ).drop(columns="_risk_rank")

    styled_df = display_df.style.apply(_style_risk_table, axis=1).format(
        {
            "days_of_supply": "{:.1f}",
            "days_to_stockout": _format_days,
            "estimated_stockout_loss": "${:,.0f}",
        }
    )

    st.dataframe(
        styled_df,
        width="stretch",
        hide_index=True,
        column_config={
            "days_of_supply": st.column_config.NumberColumn("days_of_supply", format="%.1f"),
            "estimated_stockout_loss": st.column_config.NumberColumn(
                "estimated_stockout_loss",
                format="$%.0f",
            ),
        },
    )


def _render_decision_cards(df) -> None:
    st.subheader("Top Decisions")
    ranked_df = df.assign(
        risk_rank=df["overall_risk"].map({"HIGH": 0, "MEDIUM": 1, "LOW": 2})
    ).sort_values(["risk_rank", "estimated_stockout_loss"], ascending=[True, False])

    for _, row in ranked_df.head(5).iterrows():
        risk_class = row["overall_risk"].lower()
        timing_class = row["stockout_timing"]
        icon = {"HIGH": "🚨", "MEDIUM": "⚠️", "LOW": "✅"}[row["overall_risk"]]
        st.markdown(
            f"""
            <div class="decision-card {risk_class}">
                <div class="decision-header">
                    <span>{icon} {row["sku"]} - {row["product_name"]}</span>
                    <span class="risk-pill {risk_class}">{row["overall_risk"]} URGENCY</span>
                </div>
                <div class="decision-meta">{row["location"]} | {row["supplier"]}</div>
                <div class="decision-grid">
                    <div><span class="label">Time to stockout</span><strong class="{timing_class}">{_format_days(row["days_to_stockout"])}</strong></div>
                    <div><span class="label">Lead time</span><strong>{row["lead_time_days"]:.0f} days</strong></div>
                    <div><span class="label">Loss exposure</span><strong>{_format_money(row["estimated_stockout_loss"])}</strong></div>
                </div>
                <p><strong>Issue:</strong> {row["issue_summary"]}</p>
                <p><strong>Recommended action:</strong> {row["recommended_action"]}</p>
                <p><strong>Business impact:</strong> {row["business_impact"]}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _risk_count(df, group_column: str):
    return (
        df.groupby([group_column, "overall_risk"], observed=True)
        .size()
        .reset_index(name="count")
    )


def _format_money(value: float) -> str:
    return f"${value:,.0f}"


def _format_days(value: float) -> str:
    if value == float("inf"):
        return "No active demand"
    return f"{value:,.1f} days"


def _short_issue(row) -> str:
    if row["stockout_timing"] == "critical":
        return f"Projected stockout in {_format_days(row['days_to_stockout'])}, before {row['lead_time_days']:.0f}-day lead time."
    if row["stockout_risk"] == "HIGH":
        return "Inventory is below reorder point."
    if row["supplier_risk"] == "HIGH":
        return "Supplier OTIF is below 85%."
    if row["logistics_risk"] == "HIGH":
        return "Shipment delay exceeds two days."
    return "Risk signals require replenishment review."


def _style_risk_table(row) -> list[str]:
    styles = []
    for column in row.index:
        if column in {"overall_risk", "stockout_risk", "supplier_risk", "logistics_risk"}:
            styles.append(_cell_color(row[column].lower()))
        elif column in {"days_to_stockout", "stockout_timing"}:
            styles.append(_cell_color(row["stockout_timing"]))
        else:
            styles.append("")
    return styles


def _cell_color(status: str) -> str:
    colors = {
        "high": "#FEE4E2",
        "critical": "#FEE4E2",
        "medium": "#FEF0C7",
        "warning": "#FEF0C7",
        "low": "#DCFAE6",
        "safe": "#DCFAE6",
    }
    return f"background-color: {colors.get(status, '#ffffff')}; font-weight: 700;"


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
        }
        [data-testid="stMetric"] {
            background: #151923 !important;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 1.05rem 1rem;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.28);
        }
        [data-testid="stMetric"] [data-testid="stMetricLabel"],
        [data-testid="stMetric"] [data-testid="stMetricLabel"] p {
            color: #cbd5e1 !important;
        }
        [data-testid="stMetric"] [data-testid="stMetricValue"],
        [data-testid="stMetric"] [data-testid="stMetricValue"] div {
            color: #ffffff !important;
        }
        [data-testid="stMetric"] [data-testid="stMetricDelta"],
        [data-testid="stMetric"] [data-testid="stMetricDelta"] div,
        [data-testid="stMetric"] [data-testid="stMetricDelta"] svg {
            color: #f59e0b !important;
            fill: #f59e0b !important;
        }
        .alert-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            border: 1px solid #334155;
            border-left: 6px solid #98a2b3;
            border-radius: 8px;
            padding: 0.85rem 1rem;
            margin-bottom: 0.55rem;
            background: #1f2937;
            color: #ffffff;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
        }
        .alert-row.high { border-left-color: #ef4444; }
        .alert-row.medium { border-left-color: #f59e0b; }
        .alert-issue {
            color: #e2e8f0;
            margin-top: 0.15rem;
        }
        .alert-side {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            font-weight: 700;
            white-space: nowrap;
        }
        .drilldown-summary {
            border: 1px solid #334155;
            border-left: 6px solid #22c55e;
            border-radius: 8px;
            padding: 0.9rem 1rem;
            margin-bottom: 0.85rem;
            background: #1f2937;
            color: #ffffff;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
        }
        .drilldown-summary.critical { border-left-color: #ef4444; }
        .drilldown-summary.warning { border-left-color: #f59e0b; }
        .drilldown-summary.safe { border-left-color: #22c55e; }
        .muted {
            color: #cbd5e1;
        }
        .decision-card {
            border: 1px solid #334155;
            border-left: 6px solid #98a2b3;
            border-radius: 8px;
            padding: 1rem 1.1rem;
            margin-bottom: 0.75rem;
            background: #1f2937;
            color: #ffffff;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.24);
        }
        .decision-card.high { border-left-color: #ef4444; }
        .decision-card.medium { border-left-color: #f59e0b; }
        .decision-card.low { border-left-color: #22c55e; }
        .decision-card p {
            color: #e2e8f0;
        }
        .decision-card p strong {
            color: #ffffff;
        }
        .decision-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            font-weight: 700;
            color: #ffffff;
        }
        .decision-meta {
            margin-top: 0.2rem;
            color: #cbd5e1;
            font-size: 0.9rem;
        }
        .decision-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.75rem;
            margin-top: 0.85rem;
            margin-bottom: 0.85rem;
        }
        .decision-grid div {
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 0.65rem;
            background: #151923;
        }
        .decision-grid strong {
            color: #ffffff;
        }
        .label {
            display: block;
            color: #cbd5e1;
            font-size: 0.78rem;
            margin-bottom: 0.2rem;
        }
        .critical { color: #ef4444 !important; }
        .warning { color: #f59e0b !important; }
        .safe { color: #22c55e !important; }
        .risk-pill {
            border-radius: 999px;
            padding: 0.25rem 0.55rem;
            font-size: 0.75rem;
            letter-spacing: 0;
            color: #ffffff;
            white-space: nowrap;
        }
        .risk-pill.high { background: #ef4444; }
        .risk-pill.medium { background: #f59e0b; }
        .risk-pill.low { background: #22c55e; color: #052e16; }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
