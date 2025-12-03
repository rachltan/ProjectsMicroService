import os
import pandas as pd
from flask import Flask, jsonify, render_template
from flask_cors import CORS
from sqlalchemy import create_engine, text

# --------------------------------------------
# Flask App Factory
# --------------------------------------------
def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    CORS(app)

    # ----------------------------------------
    # Database Connection (Azure SQL)
    # ----------------------------------------
    AZURE_SERVER = "msitmproject.database.windows.net"
    AZURE_DATABASE = "MSITM_Project_Datbase"
    AZURE_USERNAME = os.getenv("AZURE_USERNAME", "YOUR_USERNAME_HERE")  # replace if needed
    AZURE_PASSWORD = os.getenv("AZURE_PASSWORD", "YOUR_PASSWORD_HERE")  # replace if needed

    conn_str = (
        f"mssql+pymssql://{AZURE_USERNAME}:{AZURE_PASSWORD}"
        f"@{AZURE_SERVER}/{AZURE_DATABASE}"
    )

    # Create SQLAlchemy engine
    try:
        engine = create_engine(conn_str)
    except Exception as e:
        print(f"⚠️ Failed to initialize SQLAlchemy engine: {e}")
        engine = None

    # ----------------------------------------
    # Helper: Load fallback CSV data
    # ----------------------------------------
    def load_csv_fallback():
        try:
            brand_detail = pd.read_csv("data/stg_brand_detail.csv")
            top10 = pd.read_csv("data/stg_daily_spend_top10.csv")

            merged = (
                top10.merge(
                    brand_detail,
                    on="brand_name",
                    how="left"
                )
                .drop_duplicates(subset=["brand_name"])
                .sort_values("spend_amount", ascending=False)
                .head(10)
            )
            merged["source"] = "csv-fallback"
            return merged.to_dict(orient="records")
        except Exception as e:
            print(f"⚠️ CSV Fallback Error: {e}")
            return []

    # ----------------------------------------
    # API: Get Top 10 Companies by Spend
    # ----------------------------------------
    @app.route("/api/top10companies", methods=["GET"])
    def get_top10companies():
        query = text("""
        WITH LatestMonth AS (
            SELECT MAX(month_start_date) AS latest_date
            FROM dbo.top10monthly
        ),
        Ranked AS (
            SELECT
                t.brand_name,
                t.total_spend AS spend_amount,
                t.month_start_date,
                ROW_NUMBER() OVER (PARTITION BY t.brand_name ORDER BY t.monthly_rank ASC) AS rn
            FROM dbo.top10monthly AS t
            CROSS JOIN LatestMonth AS lm
            WHERE t.month_start_date = lm.latest_date
        )
        SELECT TOP 10
            r.brand_name,
            r.spend_amount,
            r.month_start_date,
            b.target_state,
            b.sector,
            b.category
        FROM Ranked AS r
        LEFT JOIN dbo.stg_brand_detail AS b
            ON LOWER(r.brand_name) = LOWER(b.brand_name)
        WHERE r.rn = 1
        ORDER BY r.spend_amount DESC;
        """)

        try:
            if engine:
                with engine.connect() as conn:
                    df = pd.read_sql(query, conn)
                    if df.empty:
                        raise ValueError("Empty result set")
                    df["source"] = "azure-sql"
                    return jsonify(df.to_dict(orient="records"))
            else:
                raise ConnectionError("No active SQLAlchemy engine")

        except Exception as e:
            print(f"⚠️ Azure SQL connection failed: {e}")
            fallback_data = load_csv_fallback()
            return jsonify({
                "source": "csv-fallback",
                "error": str(e),
                "data": fallback_data
            })

    # ----------------------------------------
    # Frontend Routes (Templates)
    # ----------------------------------------
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/top10companies")
    def top10_page():
        return render_template("top10companies.html")


    return app


# --------------------------------------------
# Run Flask Locally
# --------------------------------------------
if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
