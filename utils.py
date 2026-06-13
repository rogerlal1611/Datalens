"""
DataLens — Utility functions
Handles: date parsing, fuzzy matching, column role detection,
         data cleaning, schema validation
"""

import re
import numpy as np
import pandas as pd
from difflib import SequenceMatcher
from dateutil import parser as dateutil_parser
import warnings

warnings.filterwarnings("ignore")

# ── COLUMN ROLE DEFINITIONS ────────────────────────────────────────────────

COLUMN_ROLES = {
    "product_name":    {"label": "Product Name",       "icon": "📦", "group": "dimension"},
    "category":        {"label": "Category / Type",    "icon": "🏷️", "group": "dimension"},
    "sub_category":    {"label": "Sub-Category",       "icon": "🔖", "group": "dimension"},
    "region":          {"label": "Region / Location",  "icon": "🌍", "group": "dimension"},
    "salesperson":     {"label": "Salesperson / Rep",  "icon": "👤", "group": "dimension"},
    "customer_name":   {"label": "Customer Name",      "icon": "🧑‍💼", "group": "dimension"},
    "customer_segment":{"label": "Customer Segment",   "icon": "🎯", "group": "dimension"},
    "channel":         {"label": "Sales Channel",      "icon": "📡", "group": "dimension"},
    "payment_method":  {"label": "Payment Method",     "icon": "💳", "group": "dimension"},
    "status":          {"label": "Order Status",       "icon": "✅", "group": "dimension"},
    "date":            {"label": "Date / Timestamp",   "icon": "📅", "group": "time"},
    "revenue":         {"label": "Revenue / Sales",    "icon": "💰", "group": "metric"},
    "quantity":        {"label": "Quantity / Units",   "icon": "🔢", "group": "metric"},
    "profit":          {"label": "Profit / Margin",    "icon": "📈", "group": "metric"},
    "cost":            {"label": "Cost / Expense",     "icon": "💸", "group": "metric"},
    "discount":        {"label": "Discount %",         "icon": "🏷",  "group": "metric"},
    "rating":          {"label": "Rating / Score",     "icon": "⭐", "group": "metric"},
    "order_id":        {"label": "Order ID",           "icon": "🔑", "group": "identifier"},
    "customer_id":     {"label": "Customer ID",        "icon": "🪪",  "group": "identifier"},
    "ignore":          {"label": "Ignore this column", "icon": "🚫", "group": "none"},
}

_HINTS = {
    # revenue
    "revenue": "revenue", "sale": "revenue", "sales": "revenue",
    "amount": "revenue", "price": "revenue", "total": "revenue",
    "income": "revenue", "earning": "revenue", "net_sale": "revenue",
    "gross_sale": "revenue", "net_amount": "revenue", "gross_amount": "revenue",
    "turnover": "revenue", "billing": "revenue", "invoice_amount": "revenue",
    "value": "revenue", "gmv": "revenue",
    # profit
    "profit": "profit", "margin": "profit", "gain": "profit",
    "net_profit": "profit", "gross_profit": "profit", "ebitda": "profit",
    # cost
    "cost": "cost", "expense": "cost", "spend": "cost",
    "expenditure": "cost", "overhead": "cost", "cogs": "cost",
    # quantity
    "qty": "quantity", "quantity": "quantity", "unit": "quantity",
    "sold": "quantity", "count": "quantity", "volume": "quantity",
    "num_order": "quantity", "number_of": "quantity", "pieces": "quantity",
    # discount
    "discount": "discount", "disc": "discount", "rebate": "discount",
    "promo": "discount", "offer": "discount",
    # date
    "date": "date", "time": "date", "month": "date", "year": "date",
    "day": "date", "period": "date", "week": "date", "timestamp": "date",
    "created_at": "date", "order_date": "date", "purchase_date": "date",
    # product
    "product": "product_name", "item": "product_name", "sku": "product_name",
    "goods": "product_name", "article": "product_name", "model": "product_name",
    "product_name": "product_name", "product_title": "product_name",
    # category
    "category": "category", "type": "category", "class": "category",
    "group": "category", "division": "category", "family": "category",
    # sub_category
    "sub_category": "sub_category", "subcat": "sub_category",
    "sub_type": "sub_category", "subcategory": "sub_category",
    # region
    "region": "region", "area": "region", "city": "region",
    "country": "region", "state": "region", "territory": "region",
    "location": "region", "zone": "region", "branch": "region",
    "market": "region", "geography": "region",
    # salesperson
    "rep": "salesperson", "agent": "salesperson", "employee": "salesperson",
    "salesperson": "salesperson", "sales_rep": "salesperson",
    "account_manager": "salesperson", "executive": "salesperson",
    "staff": "salesperson", "seller": "salesperson",
    # customer
    "customer": "customer_name", "client": "customer_name",
    "buyer": "customer_name", "account": "customer_name",
    "consumer": "customer_name",
    # segment
    "segment": "customer_segment", "tier": "customer_segment",
    "plan": "customer_segment", "membership": "customer_segment",
    # channel
    "channel": "channel", "source": "channel", "medium": "channel",
    "platform": "channel", "store": "channel", "outlet": "channel",
    "marketplace": "channel",
    # payment
    "payment": "payment_method", "pay_method": "payment_method",
    "transaction_type": "payment_method", "pay_type": "payment_method",
    # status
    "status": "status", "stage": "status",
    "order_status": "status", "fulfillment": "status",
    # rating
    "rating": "rating", "score": "rating", "review": "rating",
    "feedback": "rating", "stars": "rating", "nps": "rating",
    # identifiers
    "order_id": "order_id", "invoice": "order_id", "transaction_id": "order_id",
    "ref": "order_id", "reference": "order_id", "ticket": "order_id",
    "customer_id": "customer_id", "user_id": "customer_id",
    "client_id": "customer_id", "member_id": "customer_id",
}


def fuzzy_match(col, candidates, threshold=0.6):
    col = col.lower()
    best_score, best_match = 0, None
    for c in candidates:
        score = SequenceMatcher(None, col, c).ratio()
        if score > best_score:
            best_score, best_match = score, c
    return best_match if best_score >= threshold else None


def guess_role(col_name: str) -> str:
    col = col_name.lower().replace(" ", "_").replace("-", "_")
    if col in COLUMN_ROLES:
        return col
    for hint, role in _HINTS.items():
        if hint in col:
            return role
    match = fuzzy_match(col, list(_HINTS.keys()), threshold=0.72)
    if match:
        return _HINTS[match]
    return "ignore"


# ── DATE PARSING ──────────────────────────────────────────────────────────

def parse_dates_robust(series: pd.Series) -> pd.Series:
    result = pd.to_datetime(series, errors="coerce")
    null_count = result.isnull().sum()
    if null_count == 0:
        return result
    formats = [
        "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d",
        "%d-%m-%Y", "%m-%d-%Y",
        "%d %b %Y", "%b %d %Y",
        "%Y%m%d",
    ]
    for fmt in formats:
        attempt = pd.to_datetime(series, format=fmt, errors="coerce")
        if attempt.isnull().sum() < null_count:
            result, null_count = attempt, attempt.isnull().sum()
        if null_count == 0:
            break
    if null_count > 0:
        def try_parse(val):
            try:
                return dateutil_parser.parse(str(val))
            except Exception:
                return pd.NaT
        result = result.fillna(series.apply(try_parse))
    return result


# ── CLEANING ──────────────────────────────────────────────────────────────

def clean_column(series: pd.Series, role: str) -> pd.Series:
    if role in {"revenue", "profit", "cost", "quantity", "rating"}:
        s = series.astype(str).str.strip()
        s = s.str.replace(r"[£$€¥₹,\s]", "", regex=True)
        s = s.str.replace(r"\((\d+\.?\d*)\)", r"-\1", regex=True)
        return pd.to_numeric(s, errors="coerce").fillna(0)

    if role == "discount":
        bool_map = {"true": 1, "false": 0, "yes": 1, "no": 0}
        s = series.astype(str).str.strip().str.lower()
        if s.isin(bool_map).mean() > 0.5:
            return s.map(bool_map).fillna(0)
        s = s.str.replace("%", "", regex=False)
        s = s.str.replace(r"[£$€,\s]", "", regex=True)
        return pd.to_numeric(s, errors="coerce").fillna(0)

    if role == "date":
        return parse_dates_robust(series.astype(str))

    if role in {"product_name", "category", "sub_category", "region",
                "salesperson", "customer_name", "customer_segment",
                "channel", "payment_method", "status"}:
        s = series.astype(str).str.strip().str.title()
        return s.replace({"Nan": np.nan, "None": np.nan, "": np.nan}).fillna("Unknown")

    return series


# ── SCHEMA VALIDATION ────────────────────────────────────────────────────

def validate_schema(df: pd.DataFrame, schema: dict) -> dict:
    warnings_out = {}
    metric_roles = {"revenue", "profit", "cost", "quantity", "discount", "rating"}
    dimension_roles = {
        "product_name", "category", "sub_category", "region",
        "salesperson", "customer_name", "customer_segment",
        "channel", "payment_method", "status",
    }
    for col, role in schema.items():
        if col not in df.columns or role == "ignore":
            continue
        series = df[col].dropna()
        if len(series) == 0:
            warnings_out[col] = "Column is entirely empty."
            continue
        if role in metric_roles:
            cleaned = series.astype(str).str.replace(r"[£$€,\s]", "", regex=True)
            numeric = pd.to_numeric(cleaned, errors="coerce")
            fail_pct = numeric.isnull().sum() / len(numeric) * 100
            if fail_pct > 40:
                warnings_out[col] = (
                    f"Assigned as '{COLUMN_ROLES[role]['label']}' but "
                    f"{fail_pct:.0f}% of values are non-numeric. "
                    f"Sample: {series.iloc[:3].tolist()}"
                )
        if role == "date":
            parsed = parse_dates_robust(series.astype(str).head(50))
            fail_pct = parsed.isnull().sum() / len(parsed) * 100
            if fail_pct > 40:
                warnings_out[col] = (
                    f"Assigned as 'Date' but {fail_pct:.0f}% couldn't be parsed. "
                    f"Sample: {series.iloc[:3].tolist()}"
                )
        if role in dimension_roles:
            nc = pd.to_numeric(
                series.astype(str).str.replace(r"[£$€,]", "", regex=True),
                errors="coerce",
            )
            if nc.notnull().sum() / len(series) > 0.9:
                warnings_out[col] = (
                    f"Assigned as '{COLUMN_ROLES[role]['label']}' but most values look "
                    f"numeric. Did you mean Revenue or Quantity?"
                )
    return warnings_out
