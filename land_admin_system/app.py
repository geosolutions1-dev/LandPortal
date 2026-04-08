# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory, \
    send_file
from functools import wraps
from datetime import datetime, timedelta
import hashlib
import os
import uuid
from database import init_db, get_db
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from payment_slip import generate_payment_slip

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

    if session['user_type'] == 'admin':
        # Admin statistics
        stats = {
            'total_applications': conn.execute('SELECT COUNT(*) FROM applications').fetchone()[0] or 0,
            'pending_applications':
                conn.execute('SELECT COUNT(*) FROM applications WHERE status = "pending"').fetchone()[0] or 0,
            'total_users': conn.execute('SELECT COUNT(*) FROM users WHERE user_type = "applicant"').fetchone()[0] or 0,
            'total_revenue':
                conn.execute('SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = "completed"').fetchone()[
                    0] or 0,
            'completed_applications':
                conn.execute('SELECT COUNT(*) FROM applications WHERE status = "completed"').fetchone()[0] or 0
        }
        conn.close()
        return render_template('admin/admin_dashboard.html', stats=stats)

    else:
        # Applicant statistics
        stats = {
            'my_applications':
                conn.execute('SELECT COUNT(*) FROM applications WHERE user_id = ?', (user_id,)).fetchone()[0] or 0,
            'pending_apps': conn.execute('SELECT COUNT(*) FROM applications WHERE user_id = ? AND status = "pending"',
                                         (user_id,)).fetchone()[0] or 0,
            'approved_apps': conn.execute('SELECT COUNT(*) FROM applications WHERE user_id = ? AND status = "approved"',
                                          (user_id,)).fetchone()[0] or 0,
            'upcoming_appointments': conn.execute('''
                SELECT COUNT(*) FROM appointments a 
                JOIN applications app ON a.application_id = app.id 
                WHERE app.user_id = ? AND a.status = "scheduled" AND a.appointment_date >= ?
            ''', (user_id, datetime.now().date())).fetchone()[0] or 0
        }

        # Get recent applications
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

    # Check if this is a re-upload (documents requested by admin)
    is_reupload = request.args.get('reupload', False)

    # Get any requested documents from engagements
    requested_documents = []
    if is_reupload:
        requested_docs = conn.execute('''
            SELECT * FROM engagements 
            WHERE application_id = ? 
            AND engagement_type = 'document_request'
            AND status = 'pending'
            ORDER BY sent_at DESC
        ''', (app_id,)).fetchall()
        requested_documents = requested_docs

    if request.method == 'POST':
        document_types = request.form.getlist('document_type[]')
        other_doc_names = request.form.getlist('other_doc_name[]')
        files = request.files.getlist('document_file[]')

        uploaded_files = []

        for idx, (doc_type, file) in enumerate(zip(document_types, files)):
            if file and file.filename and doc_type:
                # If document type is "other", use the user-specified name
                if doc_type == 'other' and idx < len(other_doc_names) and other_doc_names[idx]:
                    actual_doc_type = other_doc_names[idx].strip().lower().replace(' ', '_')
                else:
                    actual_doc_type = doc_type

                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)

                if file_size > 10 * 1024 * 1024:
                    flash(f'File {file.filename} exceeds 10MB limit', 'warning')
                    continue

                filename = f"{application['application_number']}_{actual_doc_type}_{uuid.uuid4().hex[:8]}_{file.filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                conn.execute('''
                    INSERT INTO documents (application_id, document_type, file_name, file_path)
                    VALUES (?, ?, ?, ?)
                ''', (app_id, actual_doc_type.replace('_', ' ').title(), filename, filepath))
                uploaded_files.append(actual_doc_type)

        conn.commit()

        if uploaded_files:
            if is_reupload:
                # For re-upload (requested documents), update status back to payment_made
                # No payment required - just add documents
                conn.execute('UPDATE applications SET status = "payment_made", updated_at = ? WHERE id = ?',
                             (datetime.now(), app_id))
                # Mark requested documents as completed
                conn.execute('''
                    UPDATE engagements 
                    SET status = 'completed' 
                    WHERE application_id = ? AND engagement_type = 'document_request' AND status = 'pending'
                ''', (app_id,))
                flash(f'{len(uploaded_files)} document(s) uploaded successfully! Your application is now complete.',
                      'success')
            else:
                # Initial upload - proceed to payment
                conn.execute('UPDATE applications SET status = "documents_uploaded", updated_at = ? WHERE id = ?',
                             (datetime.now(), app_id))
                flash(f'{len(uploaded_files)} document(s) uploaded successfully!', 'success')

            conn.commit()
        else:
            if is_reupload:
                flash('Please upload the required documents.', 'warning')
                conn.close()
                return redirect(url_for('upload_documents', app_id=app_id, reupload=True))
            else:
                flash('No documents were uploaded. You can proceed to payment.', 'info')

        conn.close()

        # Redirect based on whether this is a re-upload or initial upload
        if is_reupload:
            # Go back to application details, not payment
            return redirect(url_for('application_detail', app_id=app_id))
        else:
            return redirect(url_for('make_payment', app_id=app_id))

    conn.close()
    return render_template('upload_documents.html',
                           application=application,
                           is_reupload=is_reupload,
                           requested_documents=requested_documents)




@app.route('/make_payment/<int:app_id>', methods=['GET', 'POST'])
@login_required
def make_payment(app_id):
    conn = get_db()
    application = conn.execute('SELECT * FROM applications WHERE id = ? AND user_id = ?',
                               (app_id, session['user_id'])).fetchone()

    if not application:
        flash('Application not found', 'danger')
        return redirect(url_for('my_applications'))

    amount = 200.00

    if request.method == 'POST':
        payment_method = request.form.get('payment_method')
        transaction_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"

        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()

        # Insert payment record
        conn.execute('''
            INSERT INTO payments (application_id, amount, payment_method, transaction_id, status, payment_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (app_id, amount, payment_method, transaction_id, 'completed', datetime.now()))

        # Update application
        conn.execute('''
            UPDATE applications 
            SET status = 'payment_made', 
                is_paid = 1, 
                submitted_at = ?,
                updated_at = ? 
            WHERE id = ?
        ''', (datetime.now(), datetime.now(), app_id))

        conn.commit()

        payment = conn.execute('SELECT * FROM payments WHERE transaction_id = ?', (transaction_id,)).fetchone()

        # Generate payment slip
        from payment_slip import generate_payment_slip
        slip_path = generate_payment_slip(dict(application), dict(payment), dict(user))

        # Get just the filename for the URL
        slip_filename = os.path.basename(slip_path)

        # Store the RELATIVE path for web access (not the full system path)
        relative_path = f"static/uploads/payments/{slip_filename}"

        # Save payment slip as a document
        conn.execute('''
            INSERT INTO documents (application_id, document_type, file_name, file_path, verified)
            VALUES (?, ?, ?, ?, ?)
        ''', (app_id, 'Payment Slip', slip_filename, relative_path, 1))

        # Update payment record
        conn.execute('UPDATE payments SET receipt_path = ? WHERE transaction_id = ?', (relative_path, transaction_id))
        conn.commit()
        conn.close()

        flash('Payment completed! Your payment slip has been added to your documents.', 'success')
        return redirect(url_for('application_detail', app_id=app_id))

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

    # Get documents
    documents = conn.execute('SELECT * FROM documents WHERE application_id = ?', (app_id,)).fetchall()

    # Get appointment
    appointment = conn.execute('SELECT * FROM appointments WHERE application_id = ?', (app_id,)).fetchone()

    # Get payment
    payment = conn.execute('SELECT * FROM payments WHERE application_id = ?', (app_id,)).fetchone()

    # Get engagements - ORDER BY sent_at DESC to show newest first
    engagements = conn.execute('''
        SELECT * FROM engagements 
        WHERE application_id = ? 
        ORDER BY sent_at DESC
    ''', (app_id,)).fetchall()

    print(f"Found {len(engagements)} engagements for app {app_id}")  # Debug log

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

    print(f"Sending {engagement_type} to application {app_id}: {message}")  # Debug log

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

    # Store engagement in database
    try:
        conn.execute('''
            INSERT INTO engagements (application_id, engagement_type, recipient, subject, message, status, sent_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (app_id, engagement_type, recipient, f'Update on Application {application["application_number"]}', message,
              'sent', datetime.now()))
        conn.commit()
        print(f"Engagement saved to database for app {app_id}")  # Debug log
    except Exception as e:
        print(f"Error saving engagement: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

    conn.close()

    # Here you would integrate actual email/WhatsApp sending
    print(f"Engagement sent to {recipient} via {engagement_type}: {message}")

    return jsonify({'success': True})

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


@app.route('/payment_slip/<int:app_id>')
@login_required
def payment_slip(app_id):
    """View and download payment slip"""
    import base64
    import qrcode
    from io import BytesIO

    conn = get_db()

    # Get application and payment details
    application = conn.execute('SELECT * FROM applications WHERE id = ?', (app_id,)).fetchone()
    payment = conn.execute('SELECT * FROM payments WHERE application_id = ? ORDER BY id DESC LIMIT 1',
                           (app_id,)).fetchone()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()

    if not application or (session['user_type'] != 'admin' and application['user_id'] != session['user_id']):
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))

    # Generate QR code for web display
    qr_data = f"App: {application['application_number']} | Receipt: RCP-{payment['transaction_id']}"
    qr_img = qrcode.make(qr_data)
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode('utf-8')

    conn.close()

    return render_template('payment_slip.html',
                           application=application,
                           payment=payment,
                           user=user,
                           qr_base64=qr_base64)


@app.route('/download_payment_slip/<int:payment_id>')
@login_required
def download_payment_slip(payment_id):
    """Download the payment slip PDF"""
    conn = get_db()

    # Get payment and verify access
    payment = conn.execute('SELECT * FROM payments WHERE id = ?', (payment_id,)).fetchone()
    if not payment:
        flash('Payment record not found', 'danger')
        return redirect(url_for('dashboard'))

    # Get application to verify ownership
    application = conn.execute('SELECT * FROM applications WHERE id = ?', (payment['application_id'],)).fetchone()

    # Check if user has access (admin or application owner)
    if session['user_type'] != 'admin' and application['user_id'] != session['user_id']:
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))

    # Check if receipt exists
    if not payment['receipt_path'] or not os.path.exists(payment['receipt_path']):
        flash('Payment slip not found', 'danger')
        return redirect(url_for('application_detail', app_id=application['id']))

    conn.close()

    # Send the PDF file
    return send_file(
        payment['receipt_path'],
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"payment_slip_{application['application_number']}.pdf"
    )

@app.route('/static/uploads/payments/<path:filename>')
def serve_payment_slip(filename):
    """Serve payment slip files"""
    return send_from_directory('static/uploads/payments', filename)


@app.route('/api/service-counts')
@login_required
@admin_required
def api_service_counts():
    """Get application counts by service type"""
    conn = get_db()

    counts = {}
    services = ['land_transfer', 'surveying_mapping', 'boundaries', 'land_search',
                'title_deed', 'land_valuation', 'lease_registration', 'topographic_surveying',
                'building_plan_approval', 'land_consolidation', 'land_subdivision', 'change_of_user']

    for service in services:
        count = \
        conn.execute('SELECT COUNT(*) FROM applications WHERE service_type = ? AND is_paid = 1', (service,)).fetchone()[
            0]
        counts[service] = count

    conn.close()
    return jsonify(counts)


@app.route('/api/admin-applications')
@login_required
@admin_required
def api_admin_applications():
    """API endpoint for admin applications with pagination"""
    conn = get_db()

    applications = conn.execute('''
        SELECT a.*, u.full_name, u.email, u.phone, 
               (SELECT engagement_mode FROM appointments WHERE application_id = a.id LIMIT 1) as engagement_mode
        FROM applications a
        JOIN users u ON a.user_id = u.id
        WHERE a.is_paid = 1
        ORDER BY a.created_at ASC
    ''').fetchall()

    conn.close()

    applications_list = []
    for app in applications:
        app_dict = dict(app)
        applications_list.append(app_dict)

    return jsonify({'applications': applications_list})


@app.route('/debug/engagements')
@login_required
@admin_required
def debug_engagements():
    """Debug page to check engagements"""
    conn = get_db()
    engagements = conn.execute('SELECT * FROM engagements ORDER BY id DESC LIMIT 20').fetchall()
    conn.close()

    output = "<h1>Recent Engagements</h1>"
    output += "<table border='1' cellpadding='5'>"
    output += "<tr><th>ID</th><th>App ID</th><th>Type</th><th>Recipient</th><th>Message</th><th>Status</th><th>Sent At</th></tr>"
    for eng in engagements:
        output += f"<tr>"
        output += f"<td>{eng['id']}</td>"
        output += f"<td>{eng['application_id']}</td>"
        output += f"<td>{eng['engagement_type']}</td>"
        output += f"<td>{eng['recipient']}</td>"
        output += f"<td>{eng['message'][:50]}</td>"
        output += f"<td>{eng['status']}</td>"
        output += f"<td>{eng['sent_at']}</td>"
        output += f"</tr>"
    output += "</table>"
    return output

@app.route('/profile')
@login_required
def profile():
    """User profile page"""
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    return render_template('profile.html', user=user)


@app.route('/admin/request_document/<int:app_id>', methods=['POST'])
@login_required
@admin_required
def request_document(app_id):
    """Admin requests a specific document from applicant"""
    document_type = request.form.get('document_type')
    message = request.form.get('message')

    conn = get_db()
    application = conn.execute(
        'SELECT a.*, u.email, u.phone FROM applications a JOIN users u ON a.user_id = u.id WHERE a.id = ?',
        (app_id,)).fetchone()

    if not application:
        return jsonify({'success': False, 'error': 'Application not found'}), 404

    # Store the document request as an engagement
    conn.execute('''
        INSERT INTO engagements (application_id, engagement_type, recipient, subject, message, status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (app_id, 'document_request', application['email'], f'Document Required: {document_type}', message, 'pending'))

    # Update application status
    conn.execute('UPDATE applications SET status = "documents_requested", updated_at = ? WHERE id = ?',
                 (datetime.now(), app_id))
    conn.commit()
    conn.close()

    # Send email notification
    send_email(
        application['email'],
        f'Document Required for Application {application["application_number"]}',
        f'Dear customer,\n\n{message}\n\nPlease login to upload the requested document.\n\nThank you.'
    )

    flash(f'Document request sent to applicant.', 'success')
    return jsonify({'success': True})




if __name__ == '__main__':
    app.run(debug=True)
