"""
DataLens — Analysis Engine
Handles: KPI computation, chart data, forecasting, insights, top-performers
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from utils import clean_column, parse_dates_robust, COLUMN_ROLES


def build_analysis(df: pd.DataFrame, schema: dict) -> dict:
    """
    Master analysis function. Returns a rich dict consumed by the dashboard template.
    """
    role_to_col = {
        role: col
        for col, role in schema.items()
        if role != "ignore" and col in df.columns
    }

    # Auto-clean every mapped column
    for role, col in role_to_col.items():
        df[col] = clean_column(df[col], role)

    result = {
        "kpis": {},
        "charts": {},
        "insights": [],
        "forecast": {},
        "quality": {},
        "top_performers": {},
    }

    # ── DATA QUALITY ──────────────────────────────────────────────────────
    mapped_cols = list(schema.keys())
    missing = df[mapped_cols].isnull().sum()
    result["quality"] = {
        "total_rows": len(df),
        "missing_values": int(missing.sum()),
        "missing_by_col": {k: int(v) for k, v in missing.items() if v > 0},
        "completeness": round(
            (1 - missing.sum() / max(len(df) * len(schema), 1)) * 100, 1
        ),
    }

    # ── CORE KPIS ─────────────────────────────────────────────────────────
    rev_col = role_to_col.get("revenue")
    total_rev = 0.0
    if rev_col:
        total_rev = df[rev_col].sum()
        result["kpis"]["revenue"] = round(total_rev, 2)
        result["kpis"]["avg_order_value"] = round(total_rev / max(len(df), 1), 2)

    qty_col = role_to_col.get("quantity")
    if qty_col:
        result["kpis"]["total_units"] = int(df[qty_col].sum())

    profit_col = role_to_col.get("profit")
    if profit_col:
        result["kpis"]["total_profit"] = round(df[profit_col].sum(), 2)
        if rev_col and total_rev > 0:
            result["kpis"]["profit_margin"] = round(
                (df[profit_col].sum() / total_rev) * 100, 1
            )

    result["kpis"]["total_orders"] = len(df)

    # ── DIMENSION CHARTS ──────────────────────────────────────────────────
    dim_roles = [
        "product_name", "category", "sub_category", "region",
        "salesperson", "customer_segment", "channel", "payment_method", "status",
    ]
    metric_col = rev_col or role_to_col.get("quantity")
    for dim in dim_roles:
        col = role_to_col.get(dim)
        if col and metric_col:
            grp = df.groupby(col)[metric_col].sum().sort_values(ascending=False)
            result["charts"][dim] = {
                "labels": grp.index.tolist()[:15],
                "values": [round(v, 2) for v in grp.values.tolist()[:15]],
                "metric": metric_col,
            }

    # ── TIME SERIES + FORECAST ────────────────────────────────────────────
    date_col = role_to_col.get("date")
    if date_col and metric_col:
        try:
            temp = df.copy()
            temp[date_col] = parse_dates_robust(temp[date_col].astype(str))
            temp = temp.dropna(subset=[date_col])
            temp["period"] = temp[date_col].dt.to_period("M")
            ts = temp.groupby("period")[metric_col].sum().reset_index()
            ts["period"] = ts["period"].astype(str)
            result["charts"]["time_series"] = {
                "labels": ts["period"].tolist(),
                "values": [round(v, 2) for v in ts[metric_col].tolist()],
                "metric": metric_col,
            }
            # Store date range for the date-range filter
            result["date_range"] = {
                "min": temp[date_col].min().strftime("%Y-%m-%d"),
                "max": temp[date_col].max().strftime("%Y-%m-%d"),
            }
            # Forecast
            if len(ts) >= 3:
                X = np.array(range(len(ts))).reshape(-1, 1)
                y = ts[metric_col].values
                model = LinearRegression().fit(X, y)
                next_val = model.predict([[len(ts)]])[0]
                recent_avg = y[-3:].mean()
                growth = ((next_val - recent_avg) / recent_avg * 100) if recent_avg else 0
                result["forecast"] = {
                    "next_period": round(next_val, 2),
                    "growth_rate": round(growth, 2),
                    "trend": "up" if growth > 0 else "down",
                    "confidence": "Linear Regression on monthly aggregates",
                }
        except Exception:
            pass

    # ── TOP PERFORMERS ────────────────────────────────────────────────────
    for dim in ["product_name", "salesperson", "region", "customer_name"]:
        col = role_to_col.get(dim)
        if col and rev_col:
            top = df.groupby(col)[rev_col].sum().sort_values(ascending=False).head(5)
            result["top_performers"][dim] = {
                "names": top.index.tolist(),
                "values": [round(v, 2) for v in top.values.tolist()],
            }

    # ── INSIGHTS ─────────────────────────────────────────────────────────
    insights = []
    if rev_col and "product_name" in role_to_col:
        top = df.groupby(role_to_col["product_name"])[rev_col].sum()
        best = top.idxmax()
        pct = round(top.max() / max(top.sum(), 1) * 100, 1)
        insights.append(
            f"🏆 <b>{best}</b> is your top product, driving {pct}% of total revenue."
        )
    if rev_col and "region" in role_to_col:
        top = df.groupby(role_to_col["region"])[rev_col].sum()
        best_region = top.idxmax()
        insights.append(
            f"🌍 <b>{best_region}</b> is your highest-revenue region "
            f"with ${top.max():,.0f} in sales."
        )
    if "profit_margin" in result["kpis"]:
        m = result["kpis"]["profit_margin"]
        if m > 30:
            insights.append(
                f"✅ Profit margin of <b>{m}%</b> is healthy — industry avg ~20-25%."
            )
        elif m > 15:
            insights.append(
                f"⚠️ Profit margin of <b>{m}%</b> is moderate. Review cost structure."
            )
        else:
            insights.append(
                f"🔴 Profit margin of <b>{m}%</b> is low. Immediate review recommended."
            )
    if rev_col and "salesperson" in role_to_col:
        sp = df.groupby(role_to_col["salesperson"])[rev_col].sum()
        spread = sp.max() / max(sp.min() + 1, 1)
        if spread > 5:
            insights.append(
                f"📊 Sales team performance is highly uneven — top rep earns "
                f"{round(spread, 1)}× more than the lowest."
            )
    if result.get("forecast") and result["forecast"].get("growth_rate") is not None:
        g = result["forecast"]["growth_rate"]
        arrow = "📈" if g > 0 else "📉"
        insights.append(
            f"{arrow} Revenue forecast shows <b>{g:+.1f}%</b> change next period."
        )
    if not insights:
        insights.append(
            "📌 Map Revenue, Product, Region, and Date columns for richer insights."
        )
    result["insights"] = insights
    return result


def build_comparison(df_a: pd.DataFrame, schema_a: dict,
                     df_b: pd.DataFrame, schema_b: dict,
                     label_a: str = "Dataset A",
                     label_b: str = "Dataset B") -> dict:
    """
    Runs build_analysis on both datasets and stitches a side-by-side
    comparison dict for the compare template.
    """
    a = build_analysis(df_a.copy(), schema_a)
    b = build_analysis(df_b.copy(), schema_b)

    # Build unified time-series overlay for the comparison chart
    ts_a = a["charts"].get("time_series", {})
    ts_b = b["charts"].get("time_series", {})

    # KPI delta helpers
    def delta(key):
        va = a["kpis"].get(key, 0) or 0
        vb = b["kpis"].get(key, 0) or 0
        pct = round((vb - va) / max(abs(va), 1) * 100, 1)
        return {"a": va, "b": vb, "pct": pct, "dir": "up" if pct >= 0 else "down"}

    kpi_compare = {
        "revenue": delta("revenue"),
        "total_orders": delta("total_orders"),
        "avg_order_value": delta("avg_order_value"),
        "total_profit": delta("total_profit"),
    }

    return {
        "a": a,
        "b": b,
        "label_a": label_a,
        "label_b": label_b,
        "kpi_compare": kpi_compare,
        "ts_a": ts_a,
        "ts_b": ts_b,
    }
