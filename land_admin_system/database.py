# database.py
import sqlite3
import os
from werkzeug.security import generate_password_hash
from datetime import datetime

# database.py - Update the database path
import os

DB_PATH = os.environ.get('DATABASE_PATH', 'instance/land_administration.db')


def init_db():
    """Initialize the database with all tables and default admin user"""

    # Ensure instance directory exists
    os.makedirs('instance', exist_ok=True)

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ... rest of your table creation code remains the same ...








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
    # In database.py, update the applications table creation:
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
            status TEXT DEFAULT 'draft',  -- draft, pending_payment, payment_made, under_review, approved, rejected, completed
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

    # Create engagements table (for tracking communications)
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
    admin_email = 'admin@land.gov'
    cursor.execute('SELECT * FROM users WHERE email = ?', (admin_email,))
    if not cursor.fetchone():
        # Create admin user with hashed password
        hashed_password = generate_password_hash('admin123')
        cursor.execute('''
            INSERT INTO users (national_id, full_name, email, phone, password, user_type, is_verified, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
        'ADMIN001', 'System Administrator', admin_email, '+233200000000', hashed_password, 'admin', 1, datetime.now()))
        print("✓ Default admin user created successfully!")
        print("  Email: admin@land.gov")
        print("  Password: admin123")

    # Insert a sample applicant user for testing (optional)
    test_email = 'applicant@example.com'
    cursor.execute('SELECT * FROM users WHERE email = ?', (test_email,))
    if not cursor.fetchone():
        hashed_password = generate_password_hash('applicant123')
        cursor.execute('''
            INSERT INTO users (national_id, full_name, email, phone, password, user_type, is_verified, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('APP001', 'Test Applicant', test_email, '+233211234567', hashed_password, 'applicant', 1, datetime.now()))
        print("✓ Test applicant user created successfully!")
        print("  Email: applicant@example.com")
        print("  Password: applicant123")

    # Commit changes and close connection
    conn.commit()
    conn.close()

    print("\n✓ Database initialized successfully!")
    print(f"  Database location: instance/land_administration.db")


def get_db():
    """Get database connection with row factory"""
    conn = sqlite3.connect('instance/land_administration.db')
    conn.row_factory = sqlite3.Row
    return conn


def get_user_by_email(email):
    """Get user by email"""
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()
    return user


def get_user_by_id(user_id):
    """Get user by ID"""
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return user


def get_application_by_number(app_number):
    """Get application by application number"""
    conn = get_db()
    app = conn.execute('SELECT * FROM applications WHERE application_number = ?', (app_number,)).fetchone()
    conn.close()
    return app


def get_applications_by_user(user_id):
    """Get all applications for a specific user"""
    conn = get_db()
    apps = conn.execute('SELECT * FROM applications WHERE user_id = ? ORDER BY created_at DESC', (user_id,)).fetchall()
    conn.close()
    return apps


def get_all_applications():
    """Get all applications for admin"""
    conn = get_db()
    apps = conn.execute('''
        SELECT a.*, u.full_name, u.email, u.phone 
        FROM applications a 
        JOIN users u ON a.user_id = u.id 
        ORDER BY a.created_at DESC
    ''').fetchall()
    conn.close()
    return apps


def update_application_status(app_id, status):
    """Update application status"""
    conn = get_db()
    conn.execute('UPDATE applications SET status = ?, updated_at = ? WHERE id = ?',
                 (status, datetime.now(), app_id))
    conn.commit()
    conn.close()


def get_all_users():
    """Get all users for admin"""
    conn = get_db()
    users = conn.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
    conn.close()
    return users


def get_statistics():
    """Get system statistics for admin dashboard"""
    conn = get_db()

    stats = {
        'total_applications': conn.execute('SELECT COUNT(*) FROM applications').fetchone()[0],
        'pending_applications': conn.execute('SELECT COUNT(*) FROM applications WHERE status = "pending"').fetchone()[
            0],
        'total_users': conn.execute('SELECT COUNT(*) FROM users WHERE user_type = "applicant"').fetchone()[0],
        'total_admins': conn.execute('SELECT COUNT(*) FROM users WHERE user_type = "admin"').fetchone()[0],
        'total_revenue':
            conn.execute('SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = "completed"').fetchone()[0],
        'total_documents': conn.execute('SELECT COUNT(*) FROM documents').fetchone()[0],
        'completed_applications':
            conn.execute('SELECT COUNT(*) FROM applications WHERE status = "completed"').fetchone()[0]
    }

    conn.close()
    return stats


def log_activity(user_id, action, details=None, ip_address=None):
    """Log user activity"""
    conn = get_db()
    conn.execute('''
        INSERT INTO activity_logs (user_id, action, details, ip_address)
        VALUES (?, ?, ?, ?)
    ''', (user_id, action, details, ip_address))
    conn.commit()
    conn.close()


if __name__ == '__main__':
    # Initialize the database when this script is run directly
    init_db()

    # Print some statistics
    conn = get_db()

    print("\n" + "=" * 50)
    print("DATABASE STATISTICS")
    print("=" * 50)

    user_count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    app_count = conn.execute('SELECT COUNT(*) FROM applications').fetchone()[0]
    doc_count = conn.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
    payment_count = conn.execute('SELECT COUNT(*) FROM payments').fetchone()[0]

    print(f"Total Users: {user_count}")
    print(f"Total Applications: {app_count}")
    print(f"Total Documents: {doc_count}")
    print(f"Total Payments: {payment_count}")

    # Get user breakdown
    admin_count = conn.execute('SELECT COUNT(*) FROM users WHERE user_type = "admin"').fetchone()[0]
    applicant_count = conn.execute('SELECT COUNT(*) FROM users WHERE user_type = "applicant"').fetchone()[0]

    print(f"\nUser Breakdown:")
    print(f"  Admins: {admin_count}")
    print(f"  Applicants: {applicant_count}")

    conn.close()