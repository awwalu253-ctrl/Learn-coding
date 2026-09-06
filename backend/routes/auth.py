# backend/routes/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
import os
from ..extensions import db
from ..models.user import User, CourseEnrollment
from ..models.course import Course
from ..models.announcement import Announcement
from ..services.notification_service import create_notification
from ..utils.decorators import student_required
from ..utils.helpers import allowed_file, save_uploaded_file

auth_bp = Blueprint('auth', __name__)

# ============================================================================
# HOME & INDEX ROUTES
# ============================================================================

@auth_bp.route('/')
def home():
    """Home page - redirects to index"""
    if current_user.is_authenticated:
        if current_user.is_admin():
            return redirect(url_for('admin.dashboard'))
        elif current_user.is_approved:
            return redirect(url_for('student.dashboard'))
        else:
            return redirect(url_for('auth.pending_approval'))
    return redirect(url_for('auth.index'))

@auth_bp.route('/index')
def index():
    """Main landing page"""
    return render_template('index.html')

# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    if current_user.is_authenticated:
        if current_user.is_admin():
            return redirect(url_for('admin.dashboard'))
        elif current_user.is_approved:
            return redirect(url_for('student.dashboard'))
        else:
            return redirect(url_for('auth.pending_approval'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json
        
        if user and user.check_password(password):
            # Check if user is suspended
            if user.is_suspended:
                if is_ajax:
                    return jsonify({'error': f'Account suspended. Reason: {user.suspension_reason or "No reason provided."}'}), 403
                flash(f'Account suspended. Reason: {user.suspension_reason or "No reason provided."}', 'error')
                return render_template('login.html')
            
            # Check if student account is approved
            if not user.is_approved and user.role == 'student':
                if is_ajax:
                    return jsonify({'error': 'Your account is pending approval.'}), 403
                flash('Your account is pending approval. Please wait for admin approval.', 'warning')
                return render_template('login.html')
            
            # Login successful
            login_user(user)
            
            # Update last login time
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            if is_ajax:
                if user.is_admin():
                    return jsonify({'redirect': url_for('admin.dashboard')})
                return jsonify({'redirect': url_for('student.dashboard')})
            
            # Redirect based on role
            if user.is_admin():
                return redirect(url_for('admin.dashboard'))
            elif not user.is_approved:
                return redirect(url_for('auth.pending_approval'))
            else:
                return redirect(url_for('student.dashboard'))
        else:
            if is_ajax:
                return jsonify({'error': 'Invalid username or password.'}), 401
            flash('Invalid username or password.', 'error')
    
    return render_template('login.html')

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """User registration page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    courses = Course.query.all()
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        selected_courses = request.form.getlist('courses')
        phone = request.form.get('phone', '').strip()
        
        # Validation
        if not username or not email or not password:
            flash('Please fill in all required fields.', 'error')
            return render_template('signup.html', courses=courses)
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('signup.html', courses=courses)
        
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('signup.html', courses=courses)
        
        if not selected_courses:
            flash('Please select at least one course.', 'error')
            return render_template('signup.html', courses=courses)
        
        # Check if username exists
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
            return render_template('signup.html', courses=courses)
        
        # Check if email exists
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return render_template('signup.html', courses=courses)
        
        try:
            # Create new student
            student = User(
                username=username,
                email=email,
                role='student',
                is_approved=False,
                phone=phone if phone else None
            )
            student.set_password(password)
            db.session.add(student)
            db.session.flush()  # Get the ID
            
            # Add course enrollments
            for course_id in selected_courses:
                course = Course.query.get(course_id)
                if course:
                    enrollment = CourseEnrollment(
                        student_id=student.id,
                        course_id=course_id,
                        status='pending'
                    )
                    db.session.add(enrollment)
            
            db.session.commit()
            
            # Send notifications to admins
            try:
                admins = User.query.filter(User.role.in_(['admin', 'super_admin'])).all()
                for admin in admins:
                    create_notification(
                        user_id=admin.id,
                        title='📝 New Student Registration',
                        message=f'New student "{username}" has registered and is pending approval.',
                        type='info',
                        link=url_for('admin.manage_students'),
                        icon='fa-user-plus',
                        icon_color='gold'
                    )
            except Exception as e:
                print(f"Notification error: {e}")
                # Continue anyway
            
            flash('Account created successfully! Please wait for admin approval.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Signup error: {e}")
            flash('An error occurred during registration. Please try again.', 'error')
            return render_template('signup.html', courses=courses)
    
    return render_template('signup.html', courses=courses)

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.index'))

# ============================================================================
# PENDING APPROVAL ROUTE
# ============================================================================

@auth_bp.route('/pending-approval')
@login_required
def pending_approval():
    """Student pending approval page"""
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    
    if current_user.is_approved:
        return redirect(url_for('student.dashboard'))
    
    if current_user.is_suspended:
        flash(f'Your account has been suspended. Reason: {current_user.suspension_reason or "No reason provided."}', 'error')
        return redirect(url_for('auth.logout'))
    
    pending_courses = current_user.get_pending_courses()
    rejected_courses = current_user.get_rejected_courses()
    approved_courses = current_user.get_enrolled_courses()
    
    return render_template('student/pending_approval.html', 
                         pending_courses=pending_courses,
                         pending_count=len(pending_courses),
                         rejected_courses=rejected_courses,
                         approved_courses=approved_courses,
                         username=current_user.username)

# ============================================================================
# PROFILE ROUTES
# ============================================================================

@auth_bp.route('/profile')
@login_required
def profile():
    """User profile page"""
    if current_user.is_suspended:
        flash('Your account is suspended.', 'error')
        return redirect(url_for('auth.logout'))
    
    return render_template('profile.html')

@auth_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit user profile"""
    if current_user.is_suspended:
        flash('Your account is suspended.', 'error')
        return redirect(url_for('auth.logout'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        phone = request.form.get('phone')
        dob = request.form.get('dob')
        
        # Validate
        if not username or not email:
            flash('Username and email are required.', 'error')
            return render_template('edit_profile.html')
        
        # Check if username exists
        existing_user = User.query.filter(User.username == username, User.id != current_user.id).first()
        if existing_user:
            flash('Username already taken.', 'error')
            return render_template('edit_profile.html')
        
        # Check if email exists
        existing_email = User.query.filter(User.email == email, User.id != current_user.id).first()
        if existing_email:
            flash('Email already registered.', 'error')
            return render_template('edit_profile.html')
        
        # Update user
        current_user.username = username
        current_user.email = email
        current_user.phone = phone if phone else None
        
        if dob:
            try:
                current_user.dob = datetime.strptime(dob, '%Y-%m-%d')
            except ValueError:
                flash('Invalid date format.', 'error')
                return render_template('edit_profile.html')
        
        # Handle profile picture upload
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename:
                if allowed_file(file.filename):
                    # Delete old picture
                    if current_user.profile_picture:
                        old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profile_pictures', current_user.profile_picture)
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    
                    # Save new picture
                    file_path, file_name = save_uploaded_file(file, 'profile_pictures')
                    current_user.profile_picture = file_path
                    flash('Profile picture updated!', 'success')
                else:
                    flash('Invalid file format. Please upload JPG, PNG, or GIF.', 'error')
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('edit_profile.html')

@auth_bp.route('/profile/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change password page"""
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not current_user.check_password(current_password):
            flash('Current password is incorrect.', 'error')
            return render_template('change_password.html')
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return render_template('change_password.html')
        
        if len(new_password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('change_password.html')
        
        current_user.set_password(new_password)
        db.session.commit()
        
        # Send notification
        create_notification(
            user_id=current_user.id,
            title='🔑 Password Changed',
            message='Your password has been successfully changed.',
            type='success',
            icon='fa-key',
            icon_color='green'
        )
        
        flash('Password changed successfully!', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('change_password.html')

@auth_bp.route('/profile/toggle-dark-mode', methods=['POST'])
@login_required
def toggle_dark_mode():
    """Toggle dark mode"""
    current_user.dark_mode = not current_user.dark_mode
    db.session.commit()
    return jsonify({'dark_mode': current_user.dark_mode})

# ============================================================================
# HEALTH CHECK ROUTE
# ============================================================================

@auth_bp.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'database': 'connected'
    })

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@auth_bp.app_errorhandler(404)
def not_found(error):
    """404 error handler"""
    return render_template('404.html'), 404

@auth_bp.app_errorhandler(500)
def server_error(error):
    """500 error handler"""
    return render_template('500.html'), 500

# ============================================================================
# HELPER ROUTES FOR TEMPLATES
# ============================================================================

@auth_bp.route('/maintenance')
def maintenance():
    """Maintenance page"""
    return render_template('maintenance.html')

@auth_bp.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    """Serve uploaded files"""
    from flask import send_from_directory
    return send_from_directory(os.path.join(current_app.config['UPLOAD_FOLDER'], 'profile_pictures'), filename)