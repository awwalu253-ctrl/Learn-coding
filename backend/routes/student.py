# backend/routes/student.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import or_
from ..extensions import db
from ..models.user import User, CourseEnrollment
from ..models.course import Course
from ..models.note import Note, StudentProgress
from ..models.quiz import QuizGroup, QuizAnswer, QuizQuestion
from ..models.assignment import Assignment, AssignmentSubmission
from ..models.notification import Notification, RejectionMessage
from ..models.announcement import Announcement
from ..utils.decorators import student_required
from ..utils.helpers import allowed_file, save_uploaded_file
from ..services.notification_service import create_notification

student_bp = Blueprint('student', __name__)

# ============================================================================
# DASHBOARD
# ============================================================================

@student_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    
    if current_user.is_suspended:
        flash(f'Your account has been suspended. Reason: {current_user.suspension_reason or "No reason provided."}', 'error')
        return redirect(url_for('auth.logout'))
    
    if not current_user.is_approved:
        flash('Your account is pending approval. Please wait for an admin to approve your account.', 'warning')
        return redirect(url_for('student.pending_approval'))
    
    approved_courses = current_user.get_enrolled_courses()
    pending_courses = current_user.get_pending_courses()
    
    progress_data = []
    for course in approved_courses:
        progress_data.append({
            'course': course,
            'progress': course.get_progress_for_student(current_user.id)
        })
    
    # Get quiz results
    quiz_results = []
    if approved_courses:
        approved_course_ids = [c.id for c in approved_courses]
        quiz_answers = QuizAnswer.query.filter(
            QuizAnswer.student_id == current_user.id,
            QuizAnswer.quiz_group_id.in_(
                db.session.query(QuizGroup.id).filter(QuizGroup.course_id.in_(approved_course_ids))
            )
        ).all()
        
        quiz_groups_taken = set()
        for ans in quiz_answers:
            if ans.quiz_group_id not in quiz_groups_taken:
                quiz_groups_taken.add(ans.quiz_group_id)
                score = ans.quiz_group.get_student_score(current_user.id)
                if score:
                    quiz_results.append({
                        'title': ans.quiz_group.title,
                        'score': score
                    })
    
    # Get announcements
    announcements = Announcement.query.order_by(
        Announcement.is_pinned.desc(), 
        Announcement.created_at.desc()
    ).limit(5).all()
    
    # Get upcoming deadlines
    upcoming_deadlines = []
    if approved_courses:
        course_ids = [c.id for c in approved_courses]
        upcoming_deadlines = Assignment.query.filter(
            Assignment.course_id.in_(course_ids),
            Assignment.due_date >= datetime.utcnow()
        ).order_by(Assignment.due_date.asc()).limit(5).all()
    
    # Get recent activities
    recent_activities = []
    
    # Add quiz activities
    for ans in QuizAnswer.query.filter_by(student_id=current_user.id).order_by(QuizAnswer.answered_at.desc()).limit(5).all():
        if ans.quiz_group:
            recent_activities.append({
                'icon': 'fa-puzzle-piece',
                'color': 'gold',
                'text': f'You completed quiz: <strong>{ans.quiz_group.title}</strong>',
                'time': ans.answered_at
            })
    
    # Add assignment activities
    for sub in AssignmentSubmission.query.filter_by(student_id=current_user.id).order_by(AssignmentSubmission.submitted_at.desc()).limit(5).all():
        if sub.assignment:
            recent_activities.append({
                'icon': 'fa-tasks',
                'color': 'green',
                'text': f'You submitted assignment: <strong>{sub.assignment.title}</strong>',
                'time': sub.submitted_at
            })
    
    # Sort by time
    recent_activities.sort(key=lambda x: x['time'], reverse=True)
    
    pending_count = len(pending_courses)
    
    avg_progress = 0
    if progress_data:
        total_progress = sum(data['progress'] for data in progress_data)
        avg_progress = total_progress // len(progress_data)
    
    return render_template('student/dashboard.html', 
                         approved_courses=approved_courses,
                         pending_courses=pending_courses,
                         pending_count=pending_count,
                         progress_data=progress_data,
                         quiz_results=quiz_results[:5],
                         announcements=announcements,
                         upcoming_deadlines=upcoming_deadlines,
                         recent_activities=recent_activities[:10],
                         has_approved_courses=bool(approved_courses),
                         has_pending_courses=bool(pending_courses),
                         avg_progress=avg_progress)


# ============================================================================
# COURSES
# ============================================================================

@student_bp.route('/courses')
@login_required
def courses():
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    
    if current_user.is_suspended:
        flash(f'Your account has been suspended.', 'error')
        return redirect(url_for('auth.logout'))
    
    if not current_user.is_approved:
        return redirect(url_for('student.pending_approval'))
    
    approved_courses = current_user.get_enrolled_courses()
    pending_courses = current_user.get_pending_courses()
    
    enrolled_course_ids = [c.id for c in approved_courses] + [c.id for c in pending_courses]
    
    rejections = RejectionMessage.query.filter_by(student_id=current_user.id).all()
    rejected_course_ids = [r.course_id for r in rejections]
    
    if enrolled_course_ids or rejected_course_ids:
        exclude_ids = enrolled_course_ids + rejected_course_ids
        available_courses = Course.query.filter(~Course.id.in_(exclude_ids)).all()
    else:
        available_courses = Course.query.all()
    
    return render_template('student/courses.html', 
                         approved_courses=approved_courses,
                         pending_courses=pending_courses,
                         available_courses=available_courses,
                         rejections=rejections)


# ============================================================================
# PENDING APPROVAL
# ============================================================================

@student_bp.route('/pending-approval')
@login_required
def pending_approval():
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    
    if current_user.is_suspended:
        flash(f'Your account has been suspended.', 'error')
        return redirect(url_for('auth.logout'))
    
    if current_user.is_approved:
        return redirect(url_for('student.dashboard'))
    
    pending_courses = current_user.get_pending_courses()
    rejected_courses = current_user.get_rejected_courses()
    
    return render_template('student/pending_approval.html', 
                         pending_courses=pending_courses,
                         pending_count=len(pending_courses),
                         rejected_courses=rejected_courses,
                         username=current_user.username)


# ============================================================================
# ANNOUNCEMENTS
# ============================================================================

@student_bp.route('/announcements')
@login_required
def announcements():
    if not current_user.is_approved:
        return redirect(url_for('student.pending_approval'))
    
    enrolled_course_ids = [c.id for c in current_user.get_enrolled_courses()]
    
    announcements = Announcement.query.filter(
        or_(
            Announcement.course_id.is_(None),
            Announcement.course_id.in_(enrolled_course_ids)
        )
    ).order_by(
        Announcement.is_pinned.desc(), 
        Announcement.created_at.desc()
    ).all()
    
    return render_template('student/announcements.html', announcements=announcements)


# ============================================================================
# NOTIFICATIONS
# ============================================================================

@student_bp.route('/notifications')
@login_required
def notifications_page():
    """Student notifications page"""
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).all()
    
    return render_template('student/notifications.html', notifications=notifications)


# ============================================================================
# MESSAGES
# ============================================================================

@student_bp.route('/messages')
@login_required
def messages_page():
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    
    return render_template('student/messages.html')


# ============================================================================
# CALENDAR
# ============================================================================

@student_bp.route('/calendar')
@login_required
def calendar_page():
    """Student calendar page"""
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    
    enrolled_courses = current_user.get_enrolled_courses()
    course_ids = [c.id for c in enrolled_courses]
    
    assignments = Assignment.query.filter(
        Assignment.course_id.in_(course_ids)
    ).order_by(Assignment.due_date.asc()).all()
    
    quizzes = QuizGroup.query.filter(
        QuizGroup.course_id.in_(course_ids)
    ).all()
    
    return render_template('student/calendar.html',
                         assignments=assignments,
                         quizzes=quizzes)


# ============================================================================
# PROGRESS
# ============================================================================

@student_bp.route('/progress')
@login_required
def progress_page():
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    
    if not current_user.is_approved:
        return redirect(url_for('student.pending_approval'))
    
    enrolled_courses = current_user.get_enrolled_courses()
    course_progress = []
    total_progress = 0
    
    for course in enrolled_courses:
        progress = course.get_progress_for_student(current_user.id)
        course_progress.append({
            'course': course,
            'progress': progress
        })
        total_progress += progress
    
    avg_progress = (total_progress // len(enrolled_courses)) if enrolled_courses else 0
    
    return render_template('student/progress.html',
                         enrolled_courses=enrolled_courses,
                         course_progress=course_progress,
                         avg_progress=avg_progress)


# ============================================================================
# ACHIEVEMENTS
# ============================================================================

@student_bp.route('/achievements')
@login_required
def achievements_page():
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    
    if not current_user.is_approved:
        return redirect(url_for('student.pending_approval'))
    
    achievements = []
    
    # First Quiz Achievement
    quiz_count = QuizAnswer.query.filter_by(student_id=current_user.id).count()
    if quiz_count > 0:
        achievements.append({
            'name': 'First Quiz',
            'icon': 'fa-puzzle-piece',
            'description': 'Completed your first quiz',
            'earned': True,
            'date': QuizAnswer.query.filter_by(student_id=current_user.id).first().answered_at if quiz_count > 0 else None
        })
    else:
        achievements.append({
            'name': 'First Quiz',
            'icon': 'fa-puzzle-piece',
            'description': 'Complete your first quiz',
            'earned': False,
            'date': None
        })
    
    # Perfect Score Achievement
    answers = QuizAnswer.query.filter_by(student_id=current_user.id).all()
    if answers:
        correct = sum(1 for a in answers if a.is_correct)
        total = len(answers)
        if total > 0 and (correct / total) * 100 >= 100:
            achievements.append({
                'name': 'Perfect Score',
                'icon': 'fa-star',
                'description': 'Got 100% on a quiz',
                'earned': True,
                'date': answers[-1].answered_at
            })
        else:
            achievements.append({
                'name': 'Perfect Score',
                'icon': 'fa-star',
                'description': 'Get 100% on a quiz',
                'earned': False,
                'date': None
            })
    
    # Course Master Achievement
    enrolled_courses = current_user.get_enrolled_courses()
    completed_courses = 0
    for course in enrolled_courses:
        if course.get_progress_for_student(current_user.id) >= 100:
            completed_courses += 1
    if completed_courses >= 1:
        achievements.append({
            'name': 'Course Master',
            'icon': 'fa-graduation-cap',
            'description': 'Completed a course',
            'earned': True,
            'date': None
        })
    else:
        achievements.append({
            'name': 'Course Master',
            'icon': 'fa-graduation-cap',
            'description': 'Complete all modules in a course',
            'earned': False,
            'date': None
        })
    
    # Assignment Submitted Achievement
    submissions = AssignmentSubmission.query.filter_by(student_id=current_user.id).count()
    if submissions > 0:
        achievements.append({
            'name': 'Assignment Submitted',
            'icon': 'fa-tasks',
            'description': f'Submitted {submissions} assignment(s)',
            'earned': True,
            'date': AssignmentSubmission.query.filter_by(student_id=current_user.id).first().submitted_at
        })
    else:
        achievements.append({
            'name': 'Assignment Submitted',
            'icon': 'fa-tasks',
            'description': 'Submit your first assignment',
            'earned': False,
            'date': None
        })
    
    earned_count = sum(1 for a in achievements if a['earned'])
    
    return render_template('student/achievements.html',
                         achievements=achievements,
                         earned_count=earned_count,
                         total_achievements=len(achievements))


# ============================================================================
# EDIT PROFILE
# ============================================================================

@student_bp.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if current_user.is_admin():
        flash('Admins cannot edit student profiles here. Please use the admin panel.', 'warning')
        return redirect(url_for('admin.dashboard'))
    
    if not current_user.is_approved:
        flash('Your account is pending approval. You cannot edit your profile until approved.', 'warning')
        return redirect(url_for('student.pending_approval'))
    
    if current_user.is_suspended:
        flash('Your account is suspended. Please contact an admin.', 'error')
        logout_user()
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        phone = request.form.get('phone')
        dob = request.form.get('dob')
        
        if not username or not email:
            flash('Username and email are required.', 'error')
            return render_template('student/edit_profile.html')
        
        # Check if username exists
        existing_user = User.query.filter(User.username == username, User.id != current_user.id).first()
        if existing_user:
            flash('Username already taken.', 'error')
            return render_template('student/edit_profile.html')
        
        # Check if email exists
        existing_email = User.query.filter(User.email == email, User.id != current_user.id).first()
        if existing_email:
            flash('Email already registered.', 'error')
            return render_template('student/edit_profile.html')
        
        current_user.username = username
        current_user.email = email
        current_user.phone = phone if phone else None
        
        if dob:
            try:
                current_user.dob = datetime.strptime(dob, '%Y-%m-%d')
            except ValueError:
                flash('Invalid date format.', 'error')
                return render_template('student/edit_profile.html')
        
        # Handle profile picture upload
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename:
                if allowed_file(file.filename):
                    # Delete old picture
                    if current_user.profile_picture:
                        old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_user.profile_picture)
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
    
    return render_template('student/edit_profile.html')