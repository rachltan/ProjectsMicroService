import pandas as pd
# import pymssql
# # run in terminal : nc -vz msitmproject.database.windows.net 1433
# conn = pymssql.connect(
#   server='msitmproject.database.windows.net',
#   user='CloudSAffa4d29c',
#   password='Msitm1234%',
#   database='MSITM_Project_Datbase',
#   port=1433
# )

import pandas as pd
from sqlalchemy import create_engine

server = "msitmproject.database.windows.net"
database = "MSITM_Project_Datbase"
user = "CloudSAffa4d29c"
password = "Msitm1234%"

engine = create_engine(f"mssql+pymssql://{user}:{password}@{server}:1433/{database}")

query = "SELECT TOP 10 * FROM ingest.stg_daily_spend"
df = pd.read_sql(query, engine)

print(df.head())
df.head(10).to_csv("stg_daily_spend_top10.csv", index=False)


query2 = "SELECT TOP 10 * FROM ingest.stg_brand_detail"
df2 = pd.read_sql(query2, engine)

print(df2.head())
df2.head(10).to_csv("stg_brand_detail.csv", index=False)

# query1 = "SELECT * FROM ingest.stg_daily_spend"
# df = pd.read_sql(query1, conn)

# # print first 5 rows for display
# print(df.head())

# # save only the first 10 rows to CSV
# df.head(10).to_csv("stg_daily_spend_top10.csv", index=False)

# print("CSV created: stg_daily_spend_top10.csv")


# query2 = "SELECT * FROM ingest.stg_brand_detail"
# df = pd.read_sql(query2, conn)

# # print first 5 rows for display
# print(df.head())

# # save only the first 10 rows to CSV
# df.head(10).to_csv("brands.csv", index=False)

# print("CSV created: brands.csv")