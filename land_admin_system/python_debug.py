# fix_engagements_table.py
import sqlite3

conn = sqlite3.connect('instance/land_administration.db')
cursor = conn.cursor()

# Check current table structure
cursor.execute("PRAGMA table_info(engagements)")
columns = cursor.fetchall()
print("Current columns:", [col[1] for col in columns])

# Add missing columns if needed
try:
    cursor.execute("ALTER TABLE engagements ADD COLUMN sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    print("Added sent_at column")
except:
    print("sent_at column already exists")

try:
    cursor.execute("ALTER TABLE engagements ADD COLUMN status TEXT DEFAULT 'sent'")
    print("Added status column")
except:
    print("status column already exists")

conn.commit()
conn.close()
print("Migration complete!")