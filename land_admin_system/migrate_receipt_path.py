# migrate_receipt_path.py
import sqlite3

conn = sqlite3.connect('instance/land_administration.db')
cursor = conn.cursor()

# Add receipt_path column if it doesn't exist
try:
    cursor.execute("ALTER TABLE payments ADD COLUMN receipt_path TEXT")
    print("✅ Added receipt_path column to payments table")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("✅ receipt_path column already exists")
    else:
        print(f"Error: {e}")

conn.commit()
conn.close()