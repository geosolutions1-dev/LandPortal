# migrate_status.py
import sqlite3

conn = sqlite3.connect('instance/land_administration.db')
cursor = conn.cursor()

# Add new columns if they don't exist
try:
    cursor.execute("ALTER TABLE applications ADD COLUMN is_paid BOOLEAN DEFAULT 0")
    print("Added is_paid column")
except:
    print("is_paid column already exists")

try:
    cursor.execute("ALTER TABLE applications ADD COLUMN submitted_at TIMESTAMP")
    print("Added submitted_at column")
except:
    print("submitted_at column already exists")

# Update existing applications
cursor.execute("UPDATE applications SET status = 'payment_made' WHERE status = 'pending' AND id IN (SELECT application_id FROM payments WHERE status = 'completed')")
cursor.execute("UPDATE applications SET is_paid = 1 WHERE id IN (SELECT application_id FROM payments WHERE status = 'completed')")
cursor.execute("UPDATE applications SET submitted_at = updated_at WHERE is_paid = 1 AND submitted_at IS NULL")

conn.commit()
conn.close()
print("Migration completed!")