import os
import pandas as pd
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from sqlalchemy import create_engine, text
import urllib
import traceback

# -----------------------------
# CONFIGURATION
# -----------------------------
AZURE_SERVER = "msitmproject.database.windows.net"
AZURE_DB = "MSITM_Project_Datbase"
AZURE_USER = os.getenv("AZURE_SQL_USER", "msitmadmindb")  # replace if needed
AZURE_PASS = os.getenv("AZURE_SQL_PASSWORD", "YOUR_PASSWORD_HERE")  # 🔒 secure this in env vars

# Fallback CSVs
CSV_FALLBACK_TOP10 = "data/stg_daily_spend_top10.csv"
CSV_FALLBACK_BRAND_DETAIL = "data/stg_brand_detail.csv"

# -----------------------------
# CREATE APP
# -----------------------------
def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="")
    CORS(app)

    # -----------------------------
    # ROUTES
    # -----------------------------

    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/api/top10companies", methods=["GET"])
    def get_top10companies():
        """
        Pulls the latest Top 10 unique brands by monthly spend.
        If Azure SQL fails, uses CSV fallback instead.
        """
        try:
            # Build Azure SQL connection using SQLAlchemy
            connection_string = (
                f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                f"SERVER={AZURE_SERVER};DATABASE={AZURE_DB};"
                f"UID={AZURE_USER};PWD={AZURE_PASS};Encrypt=yes;"
            )
            params = urllib.parse.quote_plus(connection_string)
            engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

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
                    d.STATE_ABBR AS target_state
                FROM (
                    SELECT DISTINCT brand_name, spend_amount, month_start_date
                    FROM Ranked
                    WHERE rn = 1
                ) AS r
                OUTER APPLY (
                    SELECT TOP 1 d.STATE_ABBR
                    FROM ingest.stg_daily_spend AS d
                    WHERE LOWER(d.BRAND_NAME) = LOWER(r.brand_name)
                    ORDER BY d.TRANS_DATE DESC
                ) AS d
                ORDER BY r.spend_amount DESC;
            """)

            df = pd.read_sql(query, engine)

            # Convert to JSON for frontend
            result = df.to_dict(orient="records")
            return jsonify({"source": "azure-sql", "data": result})

        except Exception as e:
            print("⚠️ Azure SQL connection failed:", e)
            traceback.print_exc()

            # -----------------------------
            # FALLBACK to CSV
            # -----------------------------
            try:
                if os.path.exists(CSV_FALLBACK_TOP10):
                    df = pd.read_csv(CSV_FALLBACK_TOP10)
                    result = df.head(10).to_dict(orient="records")
                    return jsonify({
                        "source": "csv-fallback",
                        "data": result,
                        "error": str(e)
                    })
                else:
                    return jsonify({
                        "error": "Azure SQL and CSV fallback both unavailable."
                    }), 500
            except Exception as e2:
                return jsonify({
                    "error": "Fallback CSV failed.",
                    "details": str(e2)
                }), 500

    return app


# -----------------------------
# ENTRY POINT
# -----------------------------
if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
