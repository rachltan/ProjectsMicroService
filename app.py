import os
import json
import pandas as pd
import pymssql
from flask import Flask, jsonify
from flask_cors import CORS

# --- Flask setup ---
def create_app():
    app = Flask(__name__)
    CORS(app)

    # Azure SQL configuration
    AZURE_SQL_SERVER = os.getenv("AZURE_SQL_SERVER", "msitmproject.database.windows.net")
    AZURE_SQL_DATABASE = os.getenv("AZURE_SQL_DATABASE", "MSITM_Project_Datbase")
    AZURE_SQL_USERNAME = os.getenv("AZURE_SQL_USERNAME", "CloudSAffa4d29c")
    AZURE_SQL_PASSWORD = os.getenv("AZURE_SQL_PASSWORD", "Msitm1234%")

    # Local fallback CSVs
    CSV_BRAND_DETAIL = "data/stg_brand_detail.csv"

    # --- Helper: connect to Azure SQL safely ---
    def _query_azure(query):
        try:
            conn = pymssql.connect(
                server=AZURE_SQL_SERVER,
                user=AZURE_SQL_USERNAME,
                password=AZURE_SQL_PASSWORD,
                database=AZURE_SQL_DATABASE
            )
            df = pd.read_sql(query, conn)
            conn.close()
            return df
        except Exception as e:
            print(f"⚠️ Azure SQL connection failed: {e}")
            return None

    # --- Helper: load fallback CSV ---
    def _load_csv(path):
        try:
            df = pd.read_csv(path)
            print(f"✅ Loaded fallback CSV: {path}")
            return df
        except Exception as e:
            print(f"⚠️ CSV load failed: {e}")
            return pd.DataFrame()

    # -------------------------------------------------------------
    # ROUTE: Top 10 Companies (dashboard)
    # -------------------------------------------------------------
    @app.route("/api/top10companies", methods=["GET"])
    def api_top10companies():
        query = """
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
            b.category,
            b.sector,
            b.target_state
        FROM Ranked AS r
        LEFT JOIN dbo.brand_detail AS b
            ON LOWER(r.brand_name) = LOWER(b.brand_name)
        WHERE r.rn = 1
        ORDER BY r.spend_amount DESC;
        """

        df = _query_azure(query)

        # If Azure fails, fallback to CSVs
        if df is None or df.empty:
            df = _load_csv(CSV_BRAND_DETAIL)
            df = df.head(10)
            source = "CSV fallback"
        else:
            source = "Azure SQL"

        data = df.to_dict(orient="records")
        return jsonify({"success": True, "source": source, "data": data})

    # -------------------------------------------------------------
    # ROUTE: Brand Info (autofill by brand name)
    # -------------------------------------------------------------
    @app.route("/api/brandinfo/<brand_name>", methods=["GET"])
    def api_brandinfo(brand_name):
        query = f"""
        SELECT TOP 1
            brand_name,
            category,
            sector,
            target_state
        FROM dbo.brand_detail
        WHERE LOWER(brand_name) = LOWER('{brand_name}')
        """

        df = _query_azure(query)
        source = "Azure SQL"

        # fallback to local CSV if Azure query fails
        if df is None or df.empty:
            df = _load_csv(CSV_BRAND_DETAIL)
            df = df[df["brand_name"].str.lower() == brand_name.lower()]
            source = "CSV fallback"

        if df is None or df.empty:
            return jsonify({"success": False, "message": f"No info found for {brand_name}."})

        result = df.to_dict(orient="records")[0]
        return jsonify({"success": True, "source": source, "data": result})

    # -------------------------------------------------------------
    # ROOT TEST ENDPOINT
    # -------------------------------------------------------------
    @app.route("/", methods=["GET"])
    def index():
        return jsonify({"message": "Projects Microservice API is running."})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 2000)))
