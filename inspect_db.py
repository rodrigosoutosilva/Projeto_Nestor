import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'database', 'invest_app.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT id, nome, created_at FROM portfolios;")
rows = cursor.fetchall()
for row in rows:
    print(row)
