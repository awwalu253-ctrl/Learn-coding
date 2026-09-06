# backend/routes/assignment.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, current_app, abort
from flask_login import login_required, current_user
from datetime import datetime
import os
from ..extensions import db
from ..models.assignment import Assignment, AssignmentSubmission
from ..models.course import Course
from ..models.user import User, CourseEnrollment
from ..utils.decorators import admin_required
from ..utils.helpers import allowed_file, save_uploaded_file, validate_assignment_file

assignment_bp = Blueprint('assignment', __name__)

# ============================================================================
# HELPER FUNCTION FOR FILE SERVING
# ============================================================================

def get_upload_folder():
    """Get the absolute upload folder path"""
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    
    # If it's a relative path, make it absolute
    if upload_folder and not os.path.isabs(upload_folder):
        # Try multiple approaches to find the correct path
        base_paths = [
            os.path.dirname(current_app.root_path),  # Project root
            current_app.root_path,  # App root
            os.path.join(os.path.dirname(current_app.root_path), 'frontend', 'static'),  # Frontend static
            os.path.join(os.path.dirname(current_app.root_path), 'frontend'),  # Frontend
        ]
        
        for base in base_paths:
            test_path = os.path.join(base, upload_folder)
            if os.path.exists(test_path):
                return test_path
            
            # Also check without the uploads part
            test_path2 = os.path.join(base, 'static', 'uploads')
            if os.path.exists(test_path2):
                return test_path2
    
    return upload_folder


def find_file_in_paths(filename, subfolder='assignments'):
    """Find a file in multiple possible locations"""
    upload_folder = get_upload_folder()
    
    possible_paths = [
        # With subfolder
        os.path.join(upload_folder, subfolder) if upload_folder else None,
        # Without subfolder
        upload_folder,
        # Absolute paths
        os.path.join('/tmp', 'uploads', subfolder),
        os.path.join('/tmp', 'uploads'),
        # Relative to project
        os.path.join(os.path.dirname(current_app.root_path), 'frontend', 'static', 'uploads', subfolder),
        os.path.join(os.path.dirname(current_app.root_path), 'frontend', 'static', 'uploads'),
        os.path.join(current_app.root_path, '..', 'frontend', 'static', 'uploads', subfolder),
    ]
    
    # Also try the exact path from the database (might include subfolder already)
    if '/' in filename or '\\' in filename:
        # The filename might already include the subfolder path
        possible_paths.insert(0, os.path.dirname(os.path.join(upload_folder, filename)) if upload_folder else None)
    
    for path in possible_paths:
        if not path:
            continue
        full_path = os.path.join(path, filename)
        if os.path.exists(full_path):
            return path, filename
    
    # Try just the filename without subfolder in the main upload folder
    if upload_folder:
        full_path = os.path.join(upload_folder, filename)
        if os.path.exists(full_path):
            return upload_folder, filename
    
    return None, None


# ============================================================================
# STUDENT ROUTES
# ============================================================================

@assignment_bp.route('/student/assignments')
@login_required
def student_assignments():
    """Student assignment listing page"""
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    
    if not current_user.is_approved:
        flash('Your account is pending approval.', 'warning')
        return redirect(url_for('student.pending_approval'))
    
    approved_courses = current_user.get_enrolled_courses()
    course_ids = [c.id for c in approved_courses]
    assignments = Assignment.query.filter(Assignment.course_id.in_(course_ids)).all()
    
    assignment_data = []
    for assignment in assignments:
        submission = assignment.get_submission_for_student(current_user.id)
        assignment_data.append({
            'assignment': assignment,
            'submission': submission,
            'is_submitted': submission is not None,
            'is_graded': submission and submission.is_graded,
            'is_past_due': assignment.is_past_due()
        })
    
    return render_template('student/assignments.html', assignment_data=assignment_data)


@assignment_bp.route('/student/assignments/<int:assignment_id>/submit', methods=['GET', 'POST'])
@login_required
def submit_assignment(assignment_id):
    """Submit an assignment"""
    if current_user.is_admin():
        flash('Admins cannot submit assignments.', 'warning')
        return redirect(url_for('admin.dashboard'))
    
    assignment = Assignment.query.get_or_404(assignment_id)
    
    if not current_user.is_enrolled_in_course(assignment.course_id):
        flash('You are not enrolled in this course.', 'error')
        return redirect(url_for('assignment.student_assignments'))
    
    if assignment.is_past_due():
        flash('This assignment is past due.', 'error')
        return redirect(url_for('assignment.student_assignments'))
    
    existing = assignment.get_submission_for_student(current_user.id)
    if existing:
        flash('You have already submitted this assignment.', 'info')
        return redirect(url_for('assignment.student_assignments'))
    
    if request.method == 'POST':
        content = request.form.get('content')
        
        if not content:
            flash('Please provide content or upload a file.', 'error')
            return render_template('student/submit_assignment.html', assignment=assignment)
        
        file_path = None
        file_name = None
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename and allowed_file(file.filename):
                file_path, file_name = save_uploaded_file(file, 'assignments')
        
        submission = AssignmentSubmission(
            student_id=current_user.id,
            assignment_id=assignment.id,
            content=content,
            file_path=file_path,
            file_name=file_name
        )
        db.session.add(submission)
        db.session.commit()
        
        # Send notification to admins
        from ..services.notification_service import create_notification
        admins = User.query.filter(User.role.in_(['admin', 'super_admin'])).all()
        for admin in admins:
            create_notification(
                user_id=admin.id,
                title='📋 New Assignment Submission',
                message=f'{current_user.username} submitted "{assignment.title}"',
                type='info',
                link=url_for('assignment.view_submissions', assignment_id=assignment.id),
                icon='fa-tasks',
                icon_color='green'
            )
        
        flash('Assignment submitted successfully!', 'success')
        return redirect(url_for('assignment.student_assignments'))
    
    return render_template('student/submit_assignment.html', assignment=assignment)


# backend/routes/assignment.py - Update view_submission route

@assignment_bp.route('/student/assignments/<int:assignment_id>/view-submission')
@login_required
def view_submission(assignment_id):
    """View a submission - students view their own, admins view any"""
    assignment = Assignment.query.get_or_404(assignment_id)
    submission_id = request.args.get('submission_id', type=int)
    
    # Admin viewing
    if current_user.is_admin():
        if submission_id:
            submission = AssignmentSubmission.query.get_or_404(submission_id)
            # Verify the submission belongs to this assignment
            if submission.assignment_id != assignment_id:
                flash('Submission does not belong to this assignment.', 'error')
                return redirect(url_for('assignment.view_submissions', assignment_id=assignment_id))
        else:
            # Try to get the student's submission (if admin is also a student in this course)
            submission = assignment.get_submission_for_student(current_user.id)
            if not submission:
                flash('No submission found.', 'info')
                return redirect(url_for('assignment.view_submissions', assignment_id=assignment_id))
        
        # Render with admin layout or same layout
        return render_template('student/view_submission.html', assignment=assignment, submission=submission)
    
    # Student viewing their own submission
    if not current_user.is_enrolled_in_course(assignment.course_id):
        flash('You are not enrolled in this course.', 'error')
        return redirect(url_for('student.dashboard'))
    
    submission = assignment.get_submission_for_student(current_user.id)
    if not submission:
        flash('You have not submitted this assignment.', 'info')
        return redirect(url_for('student_assignments'))
    
    return render_template('student/view_submission.html', assignment=assignment, submission=submission)

@assignment_bp.route('/admin/submissions/<int:submission_id>/view')
@login_required
@admin_required
def admin_view_submission(submission_id):
    """Admin view a specific submission"""
    submission = AssignmentSubmission.query.get_or_404(submission_id)
    assignment = submission.assignment
    
    if not current_user.is_super_admin() and assignment.course not in current_user.managed_courses:
        flash('You do not have permission to view this submission.', 'error')
        return redirect(url_for('assignment.manage_assignments'))
    
    return render_template('student/view_submission.html', assignment=assignment, submission=submission)


# ============================================================================
# FILE DOWNLOAD ROUTES - FIXED
# ============================================================================

@assignment_bp.route('/student/assignments/<int:assignment_id>/download-file')
@login_required
def download_assignment_file(assignment_id):
    """Download the assignment file for students"""
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # Check if user is enrolled in the course
    if not current_user.is_admin() and not current_user.is_enrolled_in_course(assignment.course_id):
        flash('You are not enrolled in this course.', 'error')
        return redirect(url_for('assignment.student_assignments'))
    
    if not assignment.file_path:
        flash('No file attached to this assignment.', 'warning')
        return redirect(url_for('assignment.student_assignments'))
    
    # Get the upload folder
    upload_folder = get_upload_folder()
    
    if not upload_folder:
        flash('Upload folder not configured.', 'error')
        return redirect(url_for('assignment.student_assignments'))
    
    # Try to find the file
    file_path = assignment.file_path
    file_name = assignment.file_name or 'assignment_file'
    
    # Try different locations
    possible_locations = [
        os.path.join(upload_folder, 'assignments', file_path),
        os.path.join(upload_folder, file_path),
        os.path.join(upload_folder, 'assignments', os.path.basename(file_path)),
        os.path.join(upload_folder, os.path.basename(file_path)),
    ]
    
    # Try also with the path from the database (it might already include the subfolder)
    if '/' in file_path or '\\' in file_path:
        possible_locations.append(os.path.join(upload_folder, file_path.replace('assignments/', '')))
    
    # Check which location has the file
    found_path = None
    for location in possible_locations:
        if os.path.exists(location):
            found_path = location
            break
    
    if not found_path:
        # Log the error
        current_app.logger.error(f"File not found: {file_path} in upload folder: {upload_folder}")
        flash('File not found. It may have been moved or deleted.', 'error')
        return redirect(url_for('assignment.student_assignments'))
    
    # Serve the file
    try:
        return send_from_directory(
            os.path.dirname(found_path),
            os.path.basename(found_path),
            as_attachment=True,
            download_name=file_name
        )
    except Exception as e:
        current_app.logger.error(f"Error serving file: {e}")
        flash('Error downloading file.', 'error')
        return redirect(url_for('assignment.student_assignments'))


@assignment_bp.route('/student/submissions/<int:submission_id>/download')
@login_required
def download_submission_file(submission_id):
    """Download a student's submission file"""
    submission = AssignmentSubmission.query.get_or_404(submission_id)
    
    # Check permission
    if submission.student_id != current_user.id and not current_user.is_admin():
        flash('You do not have permission to download this file.', 'error')
        return redirect(url_for('assignment.student_assignments'))
    
    if not submission.file_path:
        flash('No file attached to this submission.', 'warning')
        return redirect(url_for('assignment.student_assignments'))
    
    # Get the upload folder
    upload_folder = get_upload_folder()
    
    if not upload_folder:
        flash('Upload folder not configured.', 'error')
        return redirect(url_for('assignment.student_assignments'))
    
    file_path = submission.file_path
    file_name = submission.file_name or 'submission_file'
    
    # Try different locations
    possible_locations = [
        os.path.join(upload_folder, 'assignments', file_path),
        os.path.join(upload_folder, file_path),
        os.path.join(upload_folder, 'assignments', os.path.basename(file_path)),
        os.path.join(upload_folder, os.path.basename(file_path)),
    ]
    
    found_path = None
    for location in possible_locations:
        if os.path.exists(location):
            found_path = location
            break
    
    if not found_path:
        flash('File not found.', 'error')
        return redirect(url_for('assignment.student_assignments'))
    
    try:
        return send_from_directory(
            os.path.dirname(found_path),
            os.path.basename(found_path),
            as_attachment=True,
            download_name=file_name
        )
    except Exception as e:
        current_app.logger.error(f"Error serving file: {e}")
        flash('Error downloading file.', 'error')
        return redirect(url_for('assignment.student_assignments'))


# ============================================================================
# ADMIN ROUTES
# ============================================================================

@assignment_bp.route('/admin/assignments')
@login_required
@admin_required
def manage_assignments():
    """Manage all assignments"""
    if current_user.is_super_admin():
        assignments = Assignment.query.order_by(Assignment.created_at.desc()).all()
    else:
        course_ids = [c.id for c in current_user.managed_courses]
        assignments = Assignment.query.filter(
            Assignment.course_id.in_(course_ids)
        ).order_by(Assignment.created_at.desc()).all()
    
    return render_template('admin/manage_assignments.html', assignments=assignments)


@assignment_bp.route('/admin/assignments/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_assignment():
    """Create a new assignment"""
    if current_user.is_super_admin():
        courses = Course.query.all()
    else:
        courses = current_user.managed_courses
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        course_id = request.form.get('course_id')
        due_date = request.form.get('due_date')
        max_score = request.form.get('max_score', 100)
        
        if not title or not description or not course_id or not due_date:
            flash('All fields are required.', 'error')
            return render_template('admin/create_assignment.html', courses=courses)
        
        course = Course.query.get(course_id)
        if not current_user.is_super_admin() and course not in current_user.managed_courses:
            flash('You do not have permission for this course.', 'error')
            return render_template('admin/create_assignment.html', courses=courses)
        
        try:
            due_date_obj = datetime.strptime(due_date, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DDTHH:MM', 'error')
            return render_template('admin/create_assignment.html', courses=courses)
        
        # Handle file upload
        file_path = None
        file_name = None
        file_size = None
        
        if 'assignment_file' in request.files:
            file = request.files['assignment_file']
            if file and file.filename:
                is_valid, error = validate_assignment_file(file)
                if not is_valid:
                    flash(error, 'error')
                    return render_template('admin/create_assignment.html', courses=courses)
                
                file_path, file_name = save_uploaded_file(file, 'assignments')
                upload_folder = get_upload_folder()
                if upload_folder:
                    full_path = os.path.join(upload_folder, 'assignments', file_path)
                    if os.path.exists(full_path):
                        file_size = f"{os.path.getsize(full_path) / 1024:.1f} KB"
        
        assignment = Assignment(
            title=title,
            description=description,
            course_id=course_id,
            author_id=current_user.id,
            due_date=due_date_obj,
            max_score=float(max_score) if max_score else 100,
            file_path=file_path,
            file_name=file_name,
            file_size=file_size
        )
        db.session.add(assignment)
        db.session.commit()
        
        # Send notifications to students
        from ..services.notification_service import create_notification
        students = User.query.filter(
            User.id.in_(
                db.session.query(CourseEnrollment.student_id).filter(
                    CourseEnrollment.course_id == course_id,
                    CourseEnrollment.status == 'approved'
                )
            )
        ).all()
        
        for student in students:
            create_notification(
                user_id=student.id,
                title=f'📝 New Assignment: {title}',
                message=f'A new assignment "{title}" has been posted in {course.name}. Due: {due_date_obj.strftime("%b %d, %Y")}',
                type='info',
                link=url_for('assignment.student_assignments'),
                icon='fa-tasks',
                icon_color='blue'
            )
        
        flash(f'Assignment "{title}" created successfully!', 'success')
        return redirect(url_for('assignment.manage_assignments'))
    
    return render_template('admin/create_assignment.html', courses=courses)


@assignment_bp.route('/admin/assignments/<int:assignment_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_assignment(assignment_id):
    """Edit an existing assignment"""
    assignment = Assignment.query.get_or_404(assignment_id)
    
    if not current_user.is_super_admin() and assignment.course not in current_user.managed_courses:
        flash('You do not have permission to edit this assignment.', 'error')
        return redirect(url_for('assignment.manage_assignments'))
    
    if current_user.is_super_admin():
        courses = Course.query.all()
    else:
        courses = current_user.managed_courses
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        course_id = request.form.get('course_id')
        due_date = request.form.get('due_date')
        max_score = request.form.get('max_score', 100)
        remove_file = request.form.get('remove_file') == 'on'
        
        if not title or not description or not course_id or not due_date:
            flash('All fields are required.', 'error')
            return render_template('admin/edit_assignment.html', assignment=assignment, courses=courses)
        
        try:
            due_date_obj = datetime.strptime(due_date, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Invalid date format.', 'error')
            return render_template('admin/edit_assignment.html', assignment=assignment, courses=courses)
        
        assignment.title = title
        assignment.description = description
        assignment.course_id = course_id
        assignment.due_date = due_date_obj
        assignment.max_score = float(max_score) if max_score else 100
        assignment.updated_at = datetime.utcnow()
        
        # Handle file upload
        if 'assignment_file' in request.files:
            file = request.files['assignment_file']
            if file and file.filename:
                # Delete old file
                upload_folder = get_upload_folder()
                if upload_folder and assignment.file_path:
                    old_path = os.path.join(upload_folder, 'assignments', assignment.file_path)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                    # Also check without subfolder
                    old_path2 = os.path.join(upload_folder, assignment.file_path)
                    if os.path.exists(old_path2):
                        os.remove(old_path2)
                
                is_valid, error = validate_assignment_file(file)
                if not is_valid:
                    flash(error, 'error')
                    return render_template('admin/edit_assignment.html', assignment=assignment, courses=courses)
                
                file_path, file_name = save_uploaded_file(file, 'assignments')
                if upload_folder:
                    full_path = os.path.join(upload_folder, 'assignments', file_path)
                    if os.path.exists(full_path):
                        file_size = f"{os.path.getsize(full_path) / 1024:.1f} KB"
                
                assignment.file_path = file_path
                assignment.file_name = file_name
                assignment.file_size = file_size
        
        # Handle file removal
        if remove_file and assignment.file_path:
            upload_folder = get_upload_folder()
            if upload_folder:
                old_path = os.path.join(upload_folder, 'assignments', assignment.file_path)
                if os.path.exists(old_path):
                    os.remove(old_path)
                old_path2 = os.path.join(upload_folder, assignment.file_path)
                if os.path.exists(old_path2):
                    os.remove(old_path2)
            assignment.file_path = None
            assignment.file_name = None
            assignment.file_size = None
        
        db.session.commit()
        
        flash(f'Assignment "{title}" updated successfully!', 'success')
        return redirect(url_for('assignment.manage_assignments'))
    
    return render_template('admin/edit_assignment.html', assignment=assignment, courses=courses)


@assignment_bp.route('/admin/assignments/<int:assignment_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_assignment(assignment_id):
    """Delete an assignment"""
    assignment = Assignment.query.get_or_404(assignment_id)
    
    if not current_user.is_super_admin() and assignment.course not in current_user.managed_courses:
        flash('You do not have permission to delete this assignment.', 'error')
        return redirect(url_for('assignment.manage_assignments'))
    
    # Send notification to students
    from ..services.notification_service import create_notification
    students = User.query.filter(
        User.id.in_(
            db.session.query(CourseEnrollment.student_id).filter(
                CourseEnrollment.course_id == assignment.course_id,
                CourseEnrollment.status == 'approved'
            )
        )
    ).all()
    
    for student in students:
        create_notification(
            user_id=student.id,
            title=f'🗑️ Assignment Removed: {assignment.title}',
            message=f'The assignment "{assignment.title}" has been removed from {assignment.course.name}.',
            type='warning',
            link=url_for('assignment.student_assignments'),
            icon='fa-trash',
            icon_color='red'
        )
    
    # Delete file if exists
    if assignment.file_path:
        upload_folder = get_upload_folder()
        if upload_folder:
            file_paths = [
                os.path.join(upload_folder, 'assignments', assignment.file_path),
                os.path.join(upload_folder, assignment.file_path)
            ]
            for file_path in file_paths:
                if os.path.exists(file_path):
                    os.remove(file_path)
    
    # Delete submissions
    AssignmentSubmission.query.filter_by(assignment_id=assignment.id).delete()
    
    db.session.delete(assignment)
    db.session.commit()
    
    flash('Assignment deleted successfully.', 'success')
    return redirect(url_for('assignment.manage_assignments'))


# ============================================================================
# SUBMISSION MANAGEMENT
# ============================================================================

@assignment_bp.route('/admin/assignments/<int:assignment_id>/submissions')
@login_required
@admin_required
def view_submissions(assignment_id):
    """View all submissions for an assignment"""
    assignment = Assignment.query.get_or_404(assignment_id)
    
    if not current_user.is_super_admin() and assignment.course not in current_user.managed_courses:
        flash('You do not have permission to view these submissions.', 'error')
        return redirect(url_for('assignment.manage_assignments'))
    
    submissions = AssignmentSubmission.query.filter_by(assignment_id=assignment_id).all()
    return render_template('admin/view_submissions.html', assignment=assignment, submissions=submissions)


@assignment_bp.route('/admin/submissions/<int:submission_id>/grade', methods=['GET', 'POST'])
@login_required
@admin_required
def grade_submission(submission_id):
    """Grade a submission"""
    submission = AssignmentSubmission.query.get_or_404(submission_id)
    assignment = submission.assignment
    
    if not current_user.is_super_admin() and assignment.course not in current_user.managed_courses:
        flash('You do not have permission to grade this submission.', 'error')
        return redirect(url_for('assignment.manage_assignments'))
    
    if request.method == 'POST':
        score = request.form.get('score')
        feedback = request.form.get('feedback')
        
        if not score:
            flash('Score is required.', 'error')
            return render_template('admin/grade_submission.html', submission=submission)
        
        submission.score = float(score)
        submission.feedback = feedback
        submission.is_graded = True
        
        db.session.commit()
        
        # Send notification to student
        from ..services.notification_service import create_notification
        create_notification(
            user_id=submission.student_id,
            title=f'📊 Assignment Graded: {assignment.title}',
            message=f'Your submission for "{assignment.title}" has been graded. Score: {score} out of {assignment.max_score}',
            type='success',
            link=url_for('assignment.student_assignments'),
            icon='fa-check-circle',
            icon_color='green'
        )
        
        flash(f'Submission graded with score {score}.', 'success')
        return redirect(url_for('assignment.view_submissions', assignment_id=assignment.id))
    
    return render_template('admin/grade_submission.html', submission=submission)


@assignment_bp.route('/admin/submissions/<int:submission_id>/download')
@login_required
@admin_required
def download_submission(submission_id):
    """Download a submission file"""
    submission = AssignmentSubmission.query.get_or_404(submission_id)
    
    if not submission.file_path:
        flash('No file attached to this submission.', 'warning')
        return redirect(url_for('assignment.view_submissions', assignment_id=submission.assignment_id))
    
    upload_folder = get_upload_folder()
    if not upload_folder:
        flash('Upload folder not configured.', 'error')
        return redirect(url_for('assignment.view_submissions', assignment_id=submission.assignment_id))
    
    file_path = submission.file_path
    file_name = submission.file_name or 'submission_file'
    
    possible_locations = [
        os.path.join(upload_folder, 'assignments', file_path),
        os.path.join(upload_folder, file_path),
        os.path.join(upload_folder, 'assignments', os.path.basename(file_path)),
        os.path.join(upload_folder, os.path.basename(file_path)),
    ]
    
    found_path = None
    for location in possible_locations:
        if os.path.exists(location):
            found_path = location
            break
    
    if not found_path:
        flash('File not found.', 'error')
        return redirect(url_for('assignment.view_submissions', assignment_id=submission.assignment_id))
    
    try:
        return send_from_directory(
            os.path.dirname(found_path),
            os.path.basename(found_path),
            as_attachment=True,
            download_name=file_name
        )
    except Exception as e:
        current_app.logger.error(f"Error serving file: {e}")
        flash('Error downloading file.', 'error')
        return redirect(url_for('assignment.view_submissions', assignment_id=submission.assignment_id))