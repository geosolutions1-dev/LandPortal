# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
from datetime import datetime, timedelta
import hashlib
import os
import uuid
from database import init_db, get_db
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['UPLOAD_FOLDER'] = 'static/uploads/documents'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
app.config['SESSION_COOKIE_SECURE'] = True if os.environ.get('FLASK_ENV') == 'production' else False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/uploads/profiles', exist_ok=True)

# Database path for Render - use /tmp for writable storage
DATABASE_PATH = os.environ.get('DATABASE_PATH', '/tmp/land_administration.db')

def get_db():
    """Get database connection with row factory"""
    import sqlite3
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Initialize database
init_db()

# ========== Helper Functions ==========
def generate_application_number():
    return f"LND-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

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
        print(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

# ========== Context Processor ==========
@app.context_processor
def inject_datetime():
    return {'datetime': datetime}

# ========== Routes ==========
@app.route('/')
def index():
    return render_template('index.html')

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
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
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

            # Determine user type
            SECRET_ADMIN_CODE = 'ADMIN2024!'
            user_type = 'admin' if admin_code == SECRET_ADMIN_CODE else 'applicant'

            # Create new user
            hashed_password = generate_password_hash(password)
            conn.execute('''
                INSERT INTO users (national_id, full_name, email, phone, password, user_type, is_verified)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (national_id, full_name, email, phone, hashed_password, user_type, 1))
            conn.commit()
            conn.close()

            flash(f'Registration successful! You are registered as a {user_type}. Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            print(f"Registration error: {e}")
            flash('Registration failed. Please try again.', 'danger')
            return render_template('register.html')

    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    conn = get_db()

    stats = {}
    if session['user_type'] == 'admin':
        stats['total_applications'] = conn.execute('SELECT COUNT(*) FROM applications').fetchone()[0] or 0
        stats['pending_applications'] = conn.execute('SELECT COUNT(*) FROM applications WHERE status = "pending"').fetchone()[0] or 0
        stats['total_users'] = conn.execute('SELECT COUNT(*) FROM users WHERE user_type = "applicant"').fetchone()[0] or 0
        stats['total_revenue'] = conn.execute('SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = "completed"').fetchone()[0] or 0
        stats['completed_applications'] = conn.execute('SELECT COUNT(*) FROM applications WHERE status = "completed"').fetchone()[0] or 0
    else:
        stats['my_applications'] = conn.execute('SELECT COUNT(*) FROM applications WHERE user_id = ?', (user_id,)).fetchone()[0] or 0
        stats['pending_apps'] = conn.execute('SELECT COUNT(*) FROM applications WHERE user_id = ? AND status = "pending"', (user_id,)).fetchone()[0] or 0
        stats['upcoming_appointments'] = conn.execute('''
            SELECT COUNT(*) FROM appointments a 
            JOIN applications app ON a.application_id = app.id 
            WHERE app.user_id = ? AND a.status = "scheduled" AND a.appointment_date >= ?
        ''', (user_id, datetime.now().date())).fetchone()[0] or 0

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
        try:
            service_type = request.form.get('service_type')
            property_location = request.form.get('property_location')
            property_size = request.form.get('property_size')
            title_deed_number = request.form.get('title_deed_number')
            appointment_date = request.form.get('appointment_date')
            appointment_time = request.form.get('appointment_time')
            engagement_mode = request.form.get('engagement_mode')
            meeting_link = request.form.get('meeting_link') if engagement_mode == 'zoom' else None
            applicant_notes = request.form.get('applicant_notes')

            application_number = generate_application_number()
            conn = get_db()

            cursor = conn.execute('''
                INSERT INTO applications (application_number, user_id, service_type, property_location, property_size, title_deed_number, status, applicant_notes, is_paid)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (application_number, session['user_id'], service_type, property_location, property_size, title_deed_number,
                  'draft', applicant_notes, 0))

            application_id = cursor.lastrowid

            conn.execute('''
                INSERT INTO appointments (application_id, appointment_date, appointment_time, engagement_mode, meeting_link)
                VALUES (?, ?, ?, ?, ?)
            ''', (application_id, appointment_date, appointment_time, engagement_mode, meeting_link))

            conn.commit()
            conn.close()

            flash(f'Application draft created! Please complete payment to submit your application.', 'info')
            return redirect(url_for('upload_documents', app_id=application_id))
        except Exception as e:
            print(f"Booking error: {e}")
            flash('Error creating application. Please try again.', 'danger')
            return redirect(url_for('book_appointment'))

    return render_template('book_appointment.html')

@app.route('/upload_documents/<int:app_id>', methods=['GET', 'POST'])
@login_required
def upload_documents(app_id):
    conn = get_db()
    application = conn.execute('SELECT * FROM applications WHERE id = ? AND user_id = ?',
                               (app_id, session['user_id'])).fetchone()

    if not application:
        flash('Application not found', 'danger')
        return redirect(url_for('my_applications'))

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
        conn.close()

        if uploaded_files:
            flash(f'{len(uploaded_files)} document(s) uploaded successfully!', 'success')
        else:
            flash('No documents were uploaded. You can proceed to payment.', 'info')

        return redirect(url_for('make_payment', app_id=app_id))

    conn.close()
    return render_template('upload_documents.html', application=application)

@app.route('/make_payment/<int:app_id>', methods=['GET', 'POST'])
@login_required
def make_payment(app_id):
    conn = get_db()
    application = conn.execute('SELECT * FROM applications WHERE id = ? AND user_id = ?',
                               (app_id, session['user_id'])).fetchone()

    if not application:
        flash('Application not found', 'danger')
        return redirect(url_for('my_applications'))

    amount = 200.00  # Fixed fee for all services

    if request.method == 'POST':
        payment_method = request.form.get('payment_method')
        transaction_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"

        conn.execute('''
            INSERT INTO payments (application_id, amount, payment_method, transaction_id, status, payment_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (app_id, amount, payment_method, transaction_id, 'completed', datetime.now()))

        conn.execute('''
            UPDATE applications 
            SET status = 'payment_made', 
                is_paid = 1, 
                submitted_at = ?,
                updated_at = ? 
            WHERE id = ?
        ''', (datetime.now(), datetime.now(), app_id))

        conn.commit()
        conn.close()

        send_email(
            session['user_email'],
            f'Application Submitted - {application["application_number"]}',
            f'Your application has been submitted. Amount Paid: GHC {amount:,.2f}'
        )

        flash('Payment completed! Your application has been submitted successfully.', 'success')
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
        SELECT a.*,
               (SELECT COUNT(*) FROM documents WHERE application_id = a.id) as doc_count,
               (SELECT status FROM payments WHERE application_id = a.id ORDER BY id DESC LIMIT 1) as payment_status,
               (SELECT appointment_date FROM appointments WHERE application_id = a.id LIMIT 1) as appointment_date,
               (SELECT appointment_time FROM appointments WHERE application_id = a.id LIMIT 1) as appointment_time
        FROM applications a 
        WHERE a.user_id = ? 
        ORDER BY a.created_at DESC
    ''', (session['user_id'],)).fetchall()
    conn.close()

    return render_template('my_applications.html', applications=applications)

@app.route('/application_detail/<int:app_id>')
@login_required
def application_detail(app_id):
    conn = get_db()
    application = conn.execute('''
        SELECT a.*, u.full_name, u.email, u.phone
        FROM applications a 
        JOIN users u ON a.user_id = u.id 
        WHERE a.id = ?
    ''', (app_id,)).fetchone()

    if not application or (session['user_type'] != 'admin' and application['user_id'] != session['user_id']):
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))

    documents = conn.execute('SELECT * FROM documents WHERE application_id = ?', (app_id,)).fetchall()
    appointment = conn.execute('SELECT * FROM appointments WHERE application_id = ?', (app_id,)).fetchone()
    payment = conn.execute('SELECT * FROM payments WHERE application_id = ?', (app_id,)).fetchone()
    engagements = conn.execute('SELECT * FROM engagements WHERE application_id = ? ORDER BY sent_at DESC', (app_id,)).fetchall()
    conn.close()

    return render_template('application_detail.html',
                           application=dict(application),
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
    application = conn.execute('SELECT a.*, u.email, u.phone FROM applications a JOIN users u ON a.user_id = u.id WHERE a.id = ?', (app_id,)).fetchone()
    conn.close()

    recipient = application['email'] if engagement_type == 'email' else application['phone']
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
@app.route('/admin/manage_applications')
@login_required
@admin_required
def manage_applications():
    conn = get_db()
    applications = conn.execute('''
        SELECT a.*, u.full_name, u.email, u.phone
        FROM applications a
        JOIN users u ON a.user_id = u.id
        WHERE a.is_paid = 1
        ORDER BY a.created_at DESC
    ''').fetchall()
    conn.close()
    return render_template('admin/manage_applications.html', applications=applications)

@app.route('/admin/update_status/<int:app_id>', methods=['POST'])
@login_required
@admin_required
def update_status(app_id):
    status = request.form.get('status')
    conn = get_db()
    conn.execute('UPDATE applications SET status = ?, updated_at = ? WHERE id = ?', (status, datetime.now(), app_id))
    conn.commit()
    conn.close()
    flash('Application status updated successfully!', 'success')
    return jsonify({'success': True})

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
    return render_template('admin/reports.html')

@app.route('/profile-content')
@login_required
def profile_content():
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    return render_template('profile.html', user=user)

@app.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    try:
        data = request.get_json()
        conn = get_db()
        conn.execute('UPDATE users SET full_name = ?, email = ?, phone = ? WHERE id = ?',
                    (data.get('full_name'), data.get('email'), data.get('phone'), session['user_id']))
        conn.commit()
        conn.close()
        session['user_name'] = data.get('full_name')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/static/uploads/documents/<path:filename>')
def serve_document(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)
