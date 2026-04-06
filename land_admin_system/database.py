# database.py
import sqlite3
import os
from werkzeug.security import generate_password_hash
from datetime import datetime

# Use Render's writable temporary directory
DB_PATH = os.environ.get('DATABASE_PATH', '/tmp/land_administration.db')

def init_db():
    """Initialize the database with all tables and default admin user"""
    
    print(f"Initializing database at: {DB_PATH}")
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            national_id TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            password TEXT NOT NULL,
            user_type TEXT DEFAULT 'applicant',
            is_verified BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
    # Create applications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_number TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            service_type TEXT NOT NULL,
            property_location TEXT NOT NULL,
            property_size REAL,
            title_deed_number TEXT,
            applicant_notes TEXT,
            status TEXT DEFAULT 'draft',
            is_paid BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP,
            submitted_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Create appointments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            appointment_date DATE NOT NULL,
            appointment_time TIME NOT NULL,
            engagement_mode TEXT NOT NULL,
            meeting_link TEXT,
            status TEXT DEFAULT 'scheduled',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (application_id) REFERENCES applications(id)
        )
    ''')
    
    # Create documents table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            document_type TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            verified BOOLEAN DEFAULT 0,
            FOREIGN KEY (application_id) REFERENCES applications(id)
        )
    ''')
    
    # Create payments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            payment_method TEXT NOT NULL,
            transaction_id TEXT UNIQUE,
            status TEXT DEFAULT 'pending',
            payment_date TIMESTAMP,
            receipt_path TEXT,
            FOREIGN KEY (application_id) REFERENCES applications(id)
        )
    ''')
    
    # Create engagements table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS engagements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            engagement_type TEXT NOT NULL,
            recipient TEXT NOT NULL,
            subject TEXT,
            message TEXT,
            status TEXT DEFAULT 'pending',
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (application_id) REFERENCES applications(id)
        )
    ''')
    
    # Create activity logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Insert default admin user if not exists
    try:
        cursor.execute('SELECT * FROM users WHERE email = ?', ('admin@land.gov',))
        if not cursor.fetchone():
            hashed_password = generate_password_hash('admin123')
            cursor.execute('''
                INSERT INTO users (national_id, full_name, email, phone, password, user_type, is_verified)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('ADMIN001', 'System Administrator', 'admin@land.gov', '+233200000000', hashed_password, 'admin', 1))
            print("✅ Default admin user created!")
    except Exception as e:
        print(f"Error creating admin: {e}")
    
    conn.commit()
    conn.close()
    print(f"✅ Database initialized successfully at {DB_PATH}")

def get_db():
    """Get database connection with row factory"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
