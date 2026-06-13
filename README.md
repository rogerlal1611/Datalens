# ◈ DataLens — Sales Intelligence Platform

> Upload any CSV or Excel sales file. Map your columns. Get instant forecasts, interactive charts, and PDF reports — no setup required.

## ✨ Features

| Feature | Details |
|---|---|
| **Universal data support** | Any CSV / XLSX / XLS file, any column structure |
| **Smart column detection** | Fuzzy-match auto-guesses 19 semantic roles |
| **Dark / Light mode** | Toggle saved to `localStorage` |
| **Date-range filter** | Filter every chart and KPI without reloading |
| **Interactive drill-down** | Click any bar or doughnut segment → detail modal |
| **Multi-file comparison** | Upload two datasets side-by-side with KPI deltas |
| **PDF export** | One-click printable report (requires `wkhtmltopdf`) |
| **Skeleton loaders** | Smooth loading animation while data processes |
| **Mobile responsive** | Full layout on phones and tablets |
| **SQLite sessions** | Server-side sessions via SQLAlchemy (multi-user safe) |
| **Revenue forecasting** | Linear Regression on monthly aggregates |
| **Data quality report** | Completeness score + missing-value breakdown |
| **404 / 500 error pages** | Styled error pages matching the main design |

## 🏗 Project Structure

```
datalens/
├── app.py            ← Application factory & entry point
├── routes.py         ← All Flask route handlers
├── analysis.py       ← Analysis engine (KPIs, charts, forecast)
├── utils.py          ← Column detection, date parsing, cleaning
├── models.py         ← SQLAlchemy UploadSession model
├── extensions.py     ← Shared db instance (avoids circular imports)
├── requirements.txt
├── .env.example      ← Copy to .env and fill in SECRET_KEY
├── .gitignore
├── uploads/          ← Runtime file storage (gitignored)
│   └── .gitkeep
├── instance/         ← SQLite DB lives here (gitignored)
├── static/css/
│   └── style.css     ← Full dark+light theme, all components
└── templates/
    ├── index.html       ← Upload page (single + compare tabs)
    ├── configure.html   ← Column mapping
    ├── dashboard.html   ← Main dashboard
    ├── compare.html     ← Side-by-side comparison
    ├── pdf_export.html  ← Print-friendly report
    ├── 404.html
    └── 500.html
```

## 🚀 Setup

```bash
git clone https://github.com/yourusername/datalens.git
cd datalens

# Create virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env and set a real SECRET_KEY

# Run
python app.py
```

Open: **http://localhost:5000**

## 📖 How to Use

1. **Upload** — Drag and drop a CSV or Excel file (max 50MB)
2. **Configure** — Review auto-detected column roles; correct mismatches
3. **Dashboard** — Explore KPIs, charts, and insights
4. **Filter** — Use the date picker to narrow the time range
5. **Drill down** — Click any chart bar/slice for a detail view
6. **Compare** — Use the "Compare Two Datasets" tab to upload a second file
7. **Export** — Click "Export PDF" in the nav bar

## 🗂 Supported Column Roles

`revenue` · `profit` · `cost` · `quantity` · `discount` · `date` · `product_name` · `category` · `sub_category` · `region` · `salesperson` · `customer_name` · `customer_segment` · `channel` · `payment_method` · `status` · `order_id` · `customer_id`

## 🛣 Roadmap

- [ ] LLM-powered natural language Q&A on uploaded data
- [ ] Facebook Prophet seasonal forecasting
- [ ] Multi-user authentication (Flask-Login)
- [ ] Docker + one-click Railway/Render deploy
- [ ] Unit test suite
