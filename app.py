import os
import pandas as pd
import pymssql
from flask import Flask, jsonify, render_template
from flask_cors import CORS

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    CORS(app)

    # --- Azure SQL credentials ---
    AZURE_SQL_SERVER = os.getenv("AZURE_SQL_SERVER", "msitmproject.database.windows.net")
    AZURE_SQL_DATABASE = os.getenv("AZURE_SQL_DATABASE", "MSITM_Project_Datbase")
    AZURE_SQL_USERNAME = os.getenv("AZURE_SQL_USERNAME", "CloudSAffa4d29c")
    AZURE_SQL_PASSWORD = os.getenv("AZURE_SQL_PASSWORD", "Msitm1234%")

    CSV_BRAND_DETAIL = "data/stg_brand_detail.csv"

    # ------------------ Helpers ------------------
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

    def _load_csv(path):
        try:
            return pd.read_csv(path)
        except Exception as e:
            print(f"⚠️ CSV load failed: {e}")
            return pd.DataFrame()

    # ------------------ API ROUTES ------------------
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
                d.STATE_ABBR AS target_state
            FROM Ranked AS r
            LEFT JOIN ingest.stg_daily_spend AS d
                ON LOWER(r.brand_name) = LOWER(d.BRAND_NAME)
            WHERE r.rn = 1
            ORDER BY r.spend_amount DESC;
            """


        df = _query_azure(query)
        if df is None or df.empty:
            df = _load_csv(CSV_BRAND_DETAIL)
            df = df.head(10)
            source = "CSV fallback"
        else:
            source = "Azure SQL"

        data = df.to_dict(orient="records")
        return jsonify({"success": True, "source": source, "data": data})

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

        if df is None or df.empty:
            df = _load_csv(CSV_BRAND_DETAIL)
            df = df[df["brand_name"].str.lower() == brand_name.lower()]
            source = "CSV fallback"

        if df.empty:
            return jsonify({"success": False, "message": f"No info found for {brand_name}."})
        return jsonify({"success": True, "source": source, "data": df.to_dict(orient="records")[0]})

    # ------------------ UI ROUTES ------------------
    @app.route("/", methods=["GET"])
    def root():
        return render_template("index.html")

    @app.route("/top10companies", methods=["GET"])
    def top10_page():
        return render_template("top10companies.html")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5003)), debug=False)
