import sqlite3

conn = sqlite3.connect("shipments.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
username TEXT PRIMARY KEY,
password TEXT
)
""")

conn.commit()
conn.close()