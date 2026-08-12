import os
import sqlite3

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

DATABASE_PATH = os.getenv("DATABASE_PATH", "shipments.db")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")

conn = sqlite3.connect(DATABASE_PATH)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS shipments(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_id TEXT,
    status TEXT,
    location TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    username TEXT PRIMARY KEY,
    password TEXT
)
""")

# Seed default shipments if empty
cursor.execute("SELECT COUNT(*) FROM shipments")
if cursor.fetchone()[0] == 0:
    cursor.executemany(
        "INSERT INTO shipments (shipment_id,status,location) VALUES (?,?,?)",
        [
            ('SHP102','In Transit','Kolkata'),
            ('SHP103','Delayed','Delhi'),
            ('SHP104','Delivered','Mumbai')
        ]
    )

# Ensure admin user is not stored in users table
cursor.execute("DELETE FROM users WHERE username=?", (ADMIN_USERNAME,))

# Seed a default user (for testing)
cursor.execute("SELECT COUNT(*) FROM users")
if cursor.fetchone()[0] == 0:
    cursor.execute(
        "INSERT INTO users (username,password) VALUES (?,?)",
        ("user1", generate_password_hash("userpass")),
    )

conn.commit()
conn.close()

print("Database created and seeded successfully")
