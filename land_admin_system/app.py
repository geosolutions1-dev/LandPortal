# app.py
import email
from dbm import sqlite3

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file, \
    send_from_directory
from functools import wraps
from datetime import datetime, timedelta
import hashlib
import os
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from database import init_db, get_db
import json
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash



app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'
app.config['UPLOAD_FOLDER'] = 'static/uploads/documents'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/uploads/profiles', exist_ok=True)
from database import init_db, get_db, get_user_by_email, get_user_by_id, get_all_applications, get_statistics, log_activity

# Initialize database at startup

# app.py - Add these changes at the top
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
# Use environment variable for secret key in production
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

# Configuration for production
app.config['UPLOAD_FOLDER'] = 'static/uploads/documents'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['SESSION_COOKIE_SECURE'] = True if os.environ.get('FLASK_ENV') == 'production' else False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/uploads/profiles', exist_ok=True)

# Database path for Render (use persistent disk or external database)
# For Render free tier, we'll use local SQLite
# For production, consider using PostgreSQL
DATABASE_PATH = os.environ.get('DATABASE_PATH', 'instance/land_administration.db')
os.makedirs('instance', exist_ok=True)

def get_db():
    """Get database connection with row factory"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn




# Initialize database
init_db()


# Add this context processor to make datetime available in all templates
@app.context_processor
def inject_datetime():
    return {'datetime': datetime}

# ========== Helper Functions ==========
def generate_application_number():
    return f"LND-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()



import hashlib

# Helper function for password verification
def verify_password(password, hashed):
    """Verify password against SHA256 hash"""
    return hashlib.sha256(password.encode()).hexdigest() == hashed


# ========== Decorators ==========
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_type') != 'admin':
            flash('Admin access required', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)

    return decorated_function


# ========== Email Function ==========
def send_email(to_email, subject, body):
    try:
        # Configure your email settings here
        # This is a placeholder - configure with your SMTP server
        print(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


# ========== Routes ==========
@app.route('/')
def index():
    """Landing page showing all services"""
    return render_template('index.html')


from flask import request, session, redirect, url_for, flash, render_template
from werkzeug.security import check_password_hash
from datetime import datetime


# Then use the functions
def login():
    # ... use get_user_by_email(email) instead of direct query
    user = get_user_by_email(email)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        plain_password = request.form.get('password')

        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], plain_password):
            session['user_id'] = user['id']
            session['user_name'] = user['full_name']
            session['user_email'] = user['email']
            session['user_type'] = user['user_type']
            session['national_id'] = user['national_id']

            # Update last login
            conn = get_db()
            conn.execute('UPDATE users SET last_login = ? WHERE id = ?', (datetime.now(), user['id']))
            conn.commit()
            conn.close()

            flash(f'Welcome back, {user["full_name"]}!', 'success')

            # Both admin and applicant go to the same dashboard
            # The dashboard will show different content based on user_type
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')





# Option 1: Use werkzeug.security (Recommended)
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        national_id = request.form.get('national_id')
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        admin_code = request.form.get('admin_code')

        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('register.html')

        conn = get_db()

        # Check if user exists
        existing = conn.execute('SELECT * FROM users WHERE email = ? OR national_id = ?',
                                (email, national_id)).fetchone()
        if existing:
            flash('User with this email or national ID already exists', 'danger')
            conn.close()
            return render_template('register.html')

        # Determine user type based on admin code
        SECRET_ADMIN_CODE = 'ADMIN2024!'
        user_type = 'admin' if admin_code == SECRET_ADMIN_CODE else 'applicant'

        # Use werkzeug's generate_password_hash (stronger than SHA256)
        hashed_password = generate_password_hash(password)

        # Create new user
        conn.execute('''
            INSERT INTO users (national_id, full_name, email, phone, password, user_type, is_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (national_id, full_name, email, phone, hashed_password, user_type, 1))
        conn.commit()
        conn.close()

        flash(f'Registration successful! You are registered as a {user_type}. Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    conn = get_db()

    # Get statistics based on user type
    stats = {}
    if session['user_type'] == 'admin':
        # Admin statistics
        stats['total_applications'] = conn.execute('SELECT COUNT(*) FROM applications').fetchone()[0]
        stats['pending_applications'] = conn.execute('SELECT COUNT(*) FROM applications WHERE status = "pending"').fetchone()[0]
        stats['total_users'] = conn.execute('SELECT COUNT(*) FROM users WHERE user_type = "applicant"').fetchone()[0]
        stats['total_revenue'] = conn.execute('SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = "completed"').fetchone()[0]
        stats['completed_applications'] = conn.execute('SELECT COUNT(*) FROM applications WHERE status = "completed"').fetchone()[0]
    else:
        # Applicant statistics
        stats['my_applications'] = conn.execute('SELECT COUNT(*) FROM applications WHERE user_id = ?', (user_id,)).fetchone()[0]
        stats['pending_apps'] = conn.execute('SELECT COUNT(*) FROM applications WHERE user_id = ? AND status = "pending"', (user_id,)).fetchone()[0]
        stats['upcoming_appointments'] = conn.execute('''
            SELECT COUNT(*) FROM appointments a 
            JOIN applications app ON a.application_id = app.id 
            WHERE app.user_id = ? AND a.status = "scheduled" AND a.appointment_date >= ?
        ''', (user_id, datetime.now().date())).fetchone()[0]

    # Get recent applications
    if session['user_type'] == 'admin':
        recent_apps = conn.execute('''
            SELECT a.*, u.full_name, u.email 
            FROM applications a 
            JOIN users u ON a.user_id = u.id 
            ORDER BY a.created_at DESC LIMIT 5
        ''').fetchall()
    else:
        recent_apps = conn.execute('''
            SELECT * FROM applications 
            WHERE user_id = ? 
            ORDER BY created_at DESC LIMIT 5
        ''', (user_id,)).fetchall()

    conn.close()

    return render_template('dashboard.html', stats=stats, recent_apps=recent_apps)


@app.route('/book_appointment', methods=['GET', 'POST'])
@login_required
def book_appointment():
    if request.method == 'POST':
        service_type = request.form.get('service_type')
        property_location = request.form.get('property_location')
        property_size = request.form.get('property_size')
        title_deed_number = request.form.get('title_deed_number')
        appointment_date = request.form.get('appointment_date')
        appointment_time = request.form.get('appointment_time')
        engagement_mode = request.form.get('engagement_mode')
        meeting_link = request.form.get('meeting_link') if engagement_mode == 'zoom' else None
        applicant_notes = request.form.get('applicant_notes')

        # Create application in DRAFT status (not yet submitted)
        application_number = generate_application_number()
        conn = get_db()

        cursor = conn.execute('''
            INSERT INTO applications (application_number, user_id, service_type, property_location, property_size, title_deed_number, status, applicant_notes, is_paid)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (application_number, session['user_id'], service_type, property_location, property_size, title_deed_number,
              'draft', applicant_notes, 0))

        application_id = cursor.lastrowid

        # Create appointment
        conn.execute('''
            INSERT INTO appointments (application_id, appointment_date, appointment_time, engagement_mode, meeting_link)
            VALUES (?, ?, ?, ?, ?)
        ''', (application_id, appointment_date, appointment_time, engagement_mode, meeting_link))

        conn.commit()
        conn.close()

        flash(f'Application draft created! Please complete payment to submit your application. Application Number: {application_number}', 'info')
        return redirect(url_for('upload_documents', app_id=application_id))

    return render_template('book_appointment.html')


# Update the upload_documents route in app.py

@app.route('/upload_documents/<int:app_id>', methods=['GET', 'POST'])
@login_required
def upload_documents(app_id):
    conn = get_db()
    application = conn.execute('SELECT * FROM applications WHERE id = ? AND user_id = ?',
                               (app_id, session['user_id'])).fetchone()

    if not application:
        flash('Application not found', 'danger')
        return redirect(url_for('my_applications'))

    # Only allow document upload for draft applications
    if application['status'] != 'draft':
        flash('Documents can only be uploaded before payment.', 'warning')
        return redirect(url_for('make_payment', app_id=app_id))

    if request.method == 'POST':
        document_types = request.form.getlist('document_type[]')
        files = request.files.getlist('document_file[]')

        uploaded_files = []

        for doc_type, file in zip(document_types, files):
            if file and file.filename and doc_type:
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)

                if file_size > 10 * 1024 * 1024:
                    flash(f'File {file.filename} exceeds 10MB limit', 'warning')
                    continue

                filename = f"{application['application_number']}_{doc_type}_{uuid.uuid4().hex[:8]}_{file.filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                conn.execute('''
                    INSERT INTO documents (application_id, document_type, file_name, file_path)
                    VALUES (?, ?, ?, ?)
                ''', (app_id, doc_type, filename, filepath))
                uploaded_files.append(doc_type)

        conn.commit()

        if uploaded_files:
            conn.execute('UPDATE applications SET status = "draft", updated_at = ? WHERE id = ?',
                         (datetime.now(), app_id))
            conn.commit()
            flash(f'{len(uploaded_files)} document(s) uploaded successfully!', 'success')
        else:
            flash('No documents were uploaded. You can proceed to payment.', 'info')

        conn.close()
        return redirect(url_for('make_payment', app_id=app_id))

    conn.close()
    return render_template('upload_documents.html', application=application)


# In app.py, update the make_payment route:
@app.route('/make_payment/<int:app_id>', methods=['GET', 'POST'])
@login_required
def make_payment(app_id):
    conn = get_db()
    application = conn.execute('SELECT * FROM applications WHERE id = ? AND user_id = ?',
                               (app_id, session['user_id'])).fetchone()

    if not application:
        flash('Application not found', 'danger')
        return redirect(url_for('my_applications'))

    # Service fees in Ghana Cedis (GHC) - All services GHC 200.00
    service_fees = {
        'land_transfer': 200.00,
        'surveying_mapping': 200.00,
        'boundaries': 200.00,
        'land_search': 200.00,
        'title_deed': 200.00,
        'land_valuation': 200.00,
        'lease_registration': 200.00,
        'topographic_surveying': 200.00,
        'building_plan_approval': 200.00,
        'land_consolidation': 200.00,
        'land_subdivision': 200.00,
        'change_of_user': 200.00
    }

    amount = service_fees.get(application['service_type'], 200.00)

    if request.method == 'POST':
        payment_method = request.form.get('payment_method')
        transaction_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"

        # Insert payment record
        conn.execute('''
            INSERT INTO payments (application_id, amount, payment_method, transaction_id, status, payment_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (app_id, amount, payment_method, transaction_id, 'completed', datetime.now()))

        # Update application - mark as paid and change status to 'payment_made'
        conn.execute('''
            UPDATE applications 
            SET status = 'payment_made', 
                is_paid = 1, 
                submitted_at = ?,
                updated_at = ? 
            WHERE id = ?
        ''', (datetime.now(), datetime.now(), app_id))

        conn.commit()

        # Get updated application info
        updated_app = conn.execute('SELECT * FROM applications WHERE id = ?', (app_id,)).fetchone()
        conn.close()

        # Send confirmation email
        send_email(
            session['user_email'],
            f'Application Submitted Successfully - {application["application_number"]}',
            f'Your application has been submitted successfully!\n\n'
            f'Application Number: {application["application_number"]}\n'
            f'Service: {application["service_type"].replace("_", " ").title()}\n'
            f'Amount Paid: GHC {amount:,.2f}\n'
            f'Transaction ID: {transaction_id}\n\n'
            f'We will process your application and contact you shortly.'
        )

        flash(
            f'Payment completed! Your application has been submitted successfully. Application Number: {application["application_number"]}',
            'success')
        return redirect(url_for('my_applications'))

    conn.close()
    return render_template('make_payment.html', application=application, amount=amount)


@app.route('/my_applications')
@login_required
def my_applications():
    if session.get('user_type') == 'admin':
        flash('Admins can view all applications from the All Applications page.', 'info')
        return redirect(url_for('manage_applications'))

    conn = get_db()

    applications = conn.execute('''
        SELECT 
            a.*,
            (SELECT COUNT(*) FROM documents WHERE application_id = a.id) as doc_count,
            (SELECT status FROM payments WHERE application_id = a.id ORDER BY id DESC LIMIT 1) as payment_status,
            (SELECT appointment_date FROM appointments WHERE application_id = a.id LIMIT 1) as appointment_date,
            (SELECT appointment_time FROM appointments WHERE application_id = a.id LIMIT 1) as appointment_time
        FROM applications a 
        WHERE a.user_id = ? 
        ORDER BY a.created_at DESC
    ''', (session['user_id'],)).fetchall()

    conn.close()

    applications_list = []
    for app in applications:
        app_dict = dict(app)
        if app_dict.get('doc_count') is None:
            app_dict['doc_count'] = 0
        if app_dict.get('payment_status') is None:
            app_dict['payment_status'] = 'not_initiated'
        applications_list.append(app_dict)

    return render_template('my_applications.html', applications=applications_list)


@app.route('/application_detail/<int:app_id>')
@login_required
def application_detail(app_id):
    conn = get_db()

    # Get application with all details including notes
    application = conn.execute('''
        SELECT a.*, u.full_name, u.email, u.phone
        FROM applications a 
        JOIN users u ON a.user_id = u.id 
        WHERE a.id = ?
    ''', (app_id,)).fetchone()

    if not application or (session['user_type'] != 'admin' and application['user_id'] != session['user_id']):
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))

    # Convert to dictionary for easier manipulation
    app_dict = dict(application)

    # Debug print to check if notes are being retrieved
    print(f"Applicant Notes: {app_dict.get('applicant_notes')}")
    print(f"Notes exists: {'applicant_notes' in app_dict}")
    print(f"Notes value: {app_dict.get('applicant_notes', 'No notes found')}")

    # Get documents
    documents = conn.execute('SELECT * FROM documents WHERE application_id = ?', (app_id,)).fetchall()

    # Get appointment
    appointment = conn.execute('SELECT * FROM appointments WHERE application_id = ?', (app_id,)).fetchone()

    # Get payment
    payment = conn.execute('SELECT * FROM payments WHERE application_id = ?', (app_id,)).fetchone()

    # Get engagements
    engagements = conn.execute('SELECT * FROM engagements WHERE application_id = ? ORDER BY sent_at DESC',
                               (app_id,)).fetchall()

    conn.close()

    return render_template('application_detail.html',
                           application=app_dict,
                           documents=documents,
                           appointment=appointment,
                           payment=payment,
                           engagements=engagements)


@app.route('/send_engagement/<int:app_id>', methods=['POST'])
@login_required
def send_engagement(app_id):
    if session['user_type'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    engagement_type = request.form.get('engagement_type')
    message = request.form.get('message')

    conn = get_db()
    application = conn.execute(
        'SELECT a.*, u.email, u.phone, u.full_name FROM applications a JOIN users u ON a.user_id = u.id WHERE a.id = ?',
        (app_id,)).fetchone()

    if not application:
        return jsonify({'success': False, 'error': 'Application not found'}), 404

    # Determine recipient based on engagement type
    if engagement_type == 'email':
        recipient = application['email']
    elif engagement_type in ['whatsapp', 'phone', 'zoom']:
        recipient = application['phone']
    else:
        recipient = application['email']

    # Update application status to engagement_scheduled
    conn.execute('UPDATE applications SET status = "engagement_scheduled", updated_at = ? WHERE id = ?',
                 (datetime.now(), app_id))

    # Store engagement in database
    conn.execute('''
        INSERT INTO engagements (application_id, engagement_type, recipient, subject, message, status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (app_id, engagement_type, recipient, f'Update on Application {application["application_number"]}', message,
          'pending'))
    conn.commit()
    conn.close()

    # Here you would integrate actual email/WhatsApp sending
    print(f"Engagement sent to {recipient} via {engagement_type}: {message}")

    return jsonify({'success': True})

@app.route('/profile')
@login_required
def profile():
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    return render_template('profile.html', user=user)


@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))


# ========== Admin Routes ==========
@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    conn = get_db()

    # Statistics
    total_applications = conn.execute('SELECT COUNT(*) FROM applications').fetchone()[0]
    pending_applications = conn.execute('SELECT COUNT(*) FROM applications WHERE status = "pending"').fetchone()[0]
    total_users = conn.execute('SELECT COUNT(*) FROM users WHERE user_type = "applicant"').fetchone()[0]
    total_revenue = conn.execute('SELECT SUM(amount) FROM payments WHERE status = "completed"').fetchone()[0] or 0

    # Recent applications
    recent_apps = conn.execute('''
        SELECT a.*, u.full_name, u.email, u.phone
        FROM applications a
        JOIN users u ON a.user_id = u.id
        ORDER BY a.created_at DESC LIMIT 10
    ''').fetchall()

    conn.close()

    return render_template('admin/admin_dashboard.html',
                           total_applications=total_applications,
                           pending_applications=pending_applications,
                           total_users=total_users,
                           total_revenue=total_revenue,
                           recent_apps=recent_apps)


@app.route('/admin/manage_applications')
@login_required
@admin_required
def manage_applications():
    conn = get_db()
    # Only show applications that have been paid for (submitted)
    applications = conn.execute('''
        SELECT a.*, u.full_name, u.email, u.phone
        FROM applications a
        JOIN users u ON a.user_id = u.id
        WHERE a.is_paid = 1 OR a.status != 'draft'
        ORDER BY a.created_at DESC
    ''').fetchall()
    conn.close()
    return render_template('admin/manage_applications.html', applications=applications)



@app.route('/admin/update_status/<int:app_id>', methods=['POST'])
@login_required
@admin_required
def update_status(app_id):
    status = request.form.get('status')
    notes = request.form.get('notes')

    conn = get_db()
    conn.execute('UPDATE applications SET status = ?, updated_at = ? WHERE id = ?', (status, datetime.now(), app_id))
    conn.commit()

    # Get user email to notify
    app = conn.execute('SELECT a.*, u.email FROM applications a JOIN users u ON a.user_id = u.id WHERE a.id = ?',
                       (app_id,)).fetchone()
    conn.close()

    send_email(app['email'], f'Application Status Update - {app["application_number"]}',
               f'Your application status has been updated to: {status}\nNotes: {notes}')

    flash('Application status updated successfully!', 'success')
    return redirect(url_for('manage_applications'))


@app.route('/admin/manage_users')
@login_required
@admin_required
def manage_users():
    conn = get_db()
    users = conn.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('admin/manage_users.html', users=users)


@app.route('/admin/reports')
@login_required
@admin_required
def reports():
    conn = get_db()

    # Monthly applications
    monthly_apps = conn.execute('''
        SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as count
        FROM applications
        GROUP BY month
        ORDER BY month DESC
        LIMIT 6
    ''').fetchall()

    # Revenue by service type
    revenue_by_service = conn.execute('''
        SELECT a.service_type, COUNT(p.id) as count, SUM(p.amount) as total
        FROM payments p
        JOIN applications a ON p.application_id = a.id
        WHERE p.status = 'completed'
        GROUP BY a.service_type
    ''').fetchall()

    conn.close()

    return render_template('admin/reports.html', monthly_apps=monthly_apps, revenue_by_service=revenue_by_service)


# Add this to app.py after creating the application
@app.route('/skip_documents/<int:app_id>')
@login_required
def skip_documents(app_id):
    conn = get_db()
    conn.execute('UPDATE applications SET status = "documents_skipped", updated_at = ? WHERE id = ?',
                 (datetime.now(), app_id))
    conn.commit()
    conn.close()

    flash('Documents step skipped. Proceed to payment.', 'info')
    return redirect(url_for('make_payment', app_id=app_id))

# Add this to app.py

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Also add this to serve files from the static/uploads directory
@app.route('/static/uploads/documents/<path:filename>')
def serve_document(filename):
    """Serve documents from uploads folder"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# Add these routes to app.py

@app.route('/complete_engagement/<int:engagement_id>', methods=['POST'])
@login_required
def complete_engagement(engagement_id):
    if session['user_type'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    conn = get_db()
    conn.execute('UPDATE engagements SET status = "completed" WHERE id = ?', (engagement_id,))
    conn.commit()
    conn.close()

    return jsonify({'success': True})


@app.route('/mark_application_completed/<int:app_id>', methods=['POST'])
@login_required
def mark_application_completed(app_id):
    if session['user_type'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    conn = get_db()
    conn.execute('UPDATE applications SET status = "completed", updated_at = ? WHERE id = ?',
                 (datetime.now(), app_id))
    conn.commit()
    conn.close()

    return jsonify({'success': True})

@app.route('/profile-content')
@login_required
def profile_content():
    """Return profile modal content"""
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    return render_template('profile.html', user=user)


@app.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    """Update user profile"""
    try:
        data = request.get_json()
        full_name = data.get('full_name')
        email = data.get('email')
        phone = data.get('phone')

        conn = get_db()
        conn.execute('''
            UPDATE users 
            SET full_name = ?, email = ?, phone = ? 
            WHERE id = ?
        ''', (full_name, email, phone, session['user_id']))
        conn.commit()
        conn.close()

        # Update session values
        session['user_name'] = full_name
        session['user_email'] = email

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/my-applications')
@login_required
def api_my_applications():
    """API endpoint for paginated applications"""
    conn = get_db()

    applications = conn.execute('''
        SELECT 
            a.*,
            (SELECT COUNT(*) FROM documents WHERE application_id = a.id) as doc_count,
            (SELECT status FROM payments WHERE application_id = a.id ORDER BY id DESC LIMIT 1) as payment_status,
            (SELECT appointment_date FROM appointments WHERE application_id = a.id LIMIT 1) as appointment_date,
            (SELECT appointment_time FROM appointments WHERE application_id = a.id LIMIT 1) as appointment_time
        FROM applications a 
        WHERE a.user_id = ? 
        ORDER BY a.created_at DESC
    ''', (session['user_id'],)).fetchall()

    conn.close()

    # Convert to list of dicts
    applications_list = []
    for app in applications:
        app_dict = dict(app)
        if app_dict.get('doc_count') is None:
            app_dict['doc_count'] = 0
        if app_dict.get('payment_status') is None:
            app_dict['payment_status'] = 'not_initiated'
        applications_list.append(app_dict)

    return jsonify({'applications': applications_list})


@app.route('/admin/create-user', methods=['POST'])
@login_required
@admin_required
def create_user():
    """Create a new user (admin or applicant)"""
    try:
        data = request.get_json()
        full_name = data.get('full_name')
        national_id = data.get('national_id')
        email = data.get('email')
        phone = data.get('phone')
        user_type = data.get('user_type')
        password = data.get('password')

        # Validate password length
        if len(password) < 6:
            return jsonify({'success': False, 'error': 'Password must be at least 6 characters'})

        conn = get_db()

        # Check if user already exists
        existing = conn.execute('SELECT * FROM users WHERE email = ? OR national_id = ?',
                                (email, national_id)).fetchone()
        if existing:
            conn.close()
            return jsonify({'success': False, 'error': 'User with this email or national ID already exists'})

        # Hash password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        # Create user
        conn.execute('''
            INSERT INTO users (national_id, full_name, email, phone, password, user_type, is_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (national_id, full_name, email, phone, hashed_password, user_type, 1))
        conn.commit()
        conn.close()

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/admin/make-admin/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def make_admin(user_id):
    """Promote a user to admin"""
    try:
        conn = get_db()
        conn.execute('UPDATE users SET user_type = ? WHERE id = ?', ('admin', user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/admin/delete-user/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(user_id):
    """Delete a user"""
    try:
        # Prevent admin from deleting themselves
        if user_id == session['user_id']:
            return jsonify({'success': False, 'error': 'You cannot delete your own account'})

        conn = get_db()
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)