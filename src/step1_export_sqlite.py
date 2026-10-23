"""
Step 1 - Copy the DeliveryLens database from SQL Server into one SQLite file.

Why: the chat assistant runs on Vercel, which cannot reach the SQL Server on your PC.
SQLite is a single read-only file that ships with the API. SQL Server stays the source.

Inputs : DeliveryLens database on your SQL Server (built in the DeliveryLens project),
         including the view vw_delivered_orders
Output : data/deliverylens.db   (8 tables + delivered_orders, indexed, ~60 MB)

The 32-character Olist IDs are replaced by whole numbers (same number = same order, seller...),
which halves the file size so it fits on GitHub and in a Vercel function.
Needs  : pip install pandas pyodbc
"""
from datetime import date, datetime
from pathlib import Path
import sqlite3
import pandas as pd
import pyodbc

# --- Block 1: settings ----------------------------------------------------
SERVER = "DESKTOP-0CCEUEQ"          # same server name as in the DeliveryLens project
DATABASE = "DeliveryLens"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "deliverylens.db"

# SQL Server object -> SQLite table. Review text is left out (Portuguese free text, large).
OBJECTS = {
    "customers": "SELECT * FROM customers",
    "sellers": "SELECT * FROM sellers",
    "products": "SELECT * FROM products",
    "category_en": "SELECT * FROM category_en",
    "orders": "SELECT * FROM orders",
    "order_items": "SELECT * FROM order_items",
    "payments": "SELECT * FROM payments",
    "reviews": "SELECT review_id, order_id, review_score, review_creation_date, review_answer_timestamp FROM reviews",
    "delivered_orders": "SELECT * FROM vw_delivered_orders",
}
INDEXES = [
    "CREATE INDEX ix_orders_customer ON orders(customer_id)",
    "CREATE INDEX ix_items_order ON order_items(order_id)",
    "CREATE INDEX ix_items_seller ON order_items(seller_id)",
    "CREATE INDEX ix_items_product ON order_items(product_id)",
    "CREATE INDEX ix_pay_order ON payments(order_id)",
    "CREATE INDEX ix_rev_order ON reviews(order_id)",
    "CREATE INDEX ix_do_seller ON delivered_orders(seller_id)",
    "CREATE INDEX ix_do_month ON delivered_orders(purchase_month)",
]

# --- Block 2: connect to SQL Server ----------------------------------------
drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
if not drivers:
    raise SystemExit("No SQL Server ODBC driver found. Install 'ODBC Driver 18 for SQL Server'.")
driver = sorted(drivers, key=lambda d: ("ODBC Driver" in d, d))[-1]
src = pyodbc.connect(f"DRIVER={{{driver}}};SERVER={SERVER};DATABASE={DATABASE};"
                     "Trusted_Connection=yes;TrustServerCertificate=yes;")

# --- Block 3: read everything ----------------------------------------------
tables = {name: pd.read_sql(sql, src) for name, sql in OBJECTS.items()}
src.close()

# --- Block 4: replace the long IDs with numbers (one numbering per ID type) ---
ID_COLS = ["order_id", "customer_id", "customer_unique_id", "seller_id", "product_id", "review_id"]
for col in ID_COLS:
    values = sorted(pd.unique(pd.concat([d[col] for d in tables.values() if col in d]).dropna()))
    number = {v: i + 1 for i, v in enumerate(values)}
    for d in tables.values():
        if col in d:
            d[col] = d[col].map(number).astype("Int64")

# --- Block 5: write SQLite --------------------------------------------------
OUT.parent.mkdir(exist_ok=True)
OUT.unlink(missing_ok=True)
dst = sqlite3.connect(OUT)
for name, df in tables.items():
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].dt.strftime("%Y-%m-%d %H:%M:%S")       # SQLite stores dates as ISO text
        elif df[c].dtype == object and len(df[c].dropna()) and isinstance(df[c].dropna().iloc[0], datetime):
            df[c] = pd.to_datetime(df[c]).dt.strftime("%Y-%m-%d %H:%M:%S")
        elif df[c].dtype == object and len(df[c].dropna()) and isinstance(df[c].dropna().iloc[0], date):
            df[c] = pd.to_datetime(df[c]).dt.strftime("%Y-%m-%d")  # DATE columns (purchase_month)
        elif df[c].dtype == object and len(df[c].dropna()) and type(df[c].dropna().iloc[0]).__name__ == "Decimal":
            df[c] = df[c].astype(float)                            # DECIMAL -> REAL
    df.to_sql(name, dst, index=False)
    print(f"{name:17s} {len(df):>8,} rows")

for ix in INDEXES:
    dst.execute(ix)
dst.commit()
dst.execute("VACUUM")
dst.close()
print(f"\nSaved {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e6:.1f} MB)")