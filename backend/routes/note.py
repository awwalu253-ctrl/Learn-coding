# backend/routes/note.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory
from flask_login import login_required, current_user
from datetime import datetime
from ..extensions import db
from ..models.note import Note, Tag, StudentProgress
from ..models.course import Course
from ..utils.decorators import admin_required, student_required
from ..utils.helpers import allowed_file, save_uploaded_file, get_upload_path
import os

note_bp = Blueprint('note', __name__)

# ============================================================================
# STUDENT ROUTES
# ============================================================================

@note_bp.route('/<int:note_id>')
@login_required
def view(note_id):
    """View a single note"""
    note = Note.query.get_or_404(note_id)
    
    if current_user.is_admin():
        return render_template('course/note.html', note=note)
    
    if not current_user.is_enrolled_in_course(note.course_id):
        flash('You do not have access to this note.', 'error')
        return redirect(url_for('student.dashboard'))
    
    # Mark as read
    progress = StudentProgress.query.filter_by(
        student_id=current_user.id,
        note_id=note.id
    ).first()
    
    if not progress:
        progress = StudentProgress(
            student_id=current_user.id,
            note_id=note.id,
            course_id=note.course_id,
            is_read=True,
            read_at=datetime.utcnow()
        )
        db.session.add(progress)
    elif not progress.is_read:
        progress.is_read = True
        progress.read_at = datetime.utcnow()
    
    db.session.commit()
    
    return render_template('course/note.html', note=note)

# ============================================================================
# ADMIN ROUTES
# ============================================================================

@note_bp.route('/admin/notes')
@login_required
@admin_required
def manage_notes():
    """Manage all notes"""
    if current_user.is_super_admin():
        notes = Note.query.order_by(Note.created_at.desc()).all()
    else:
        course_ids = [c.id for c in current_user.managed_courses]
        notes = Note.query.filter(Note.course_id.in_(course_ids)).order_by(Note.created_at.desc()).all()
    
    courses = Course.query.all()
    tags = Tag.query.all()
    return render_template('admin/manage_notes.html', notes=notes, courses=courses, tags=tags)

@note_bp.route('/admin/notes/post', methods=['GET', 'POST'])
@login_required
@admin_required
def post_note():
    """Post a new note"""
    if current_user.is_super_admin():
        courses = Course.query.all()
    else:
        courses = current_user.managed_courses
    
    tags = Tag.query.all()
    
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        course_id = request.form.get('course_id')
        tag_id = request.form.get('tag_id')
        
        if not title or not content or not course_id:
            flash('Title, content, and course are required.', 'error')
            return render_template('admin/post_note.html', courses=courses, tags=tags)
        
        course = Course.query.get(course_id)
        if not current_user.is_super_admin() and course not in current_user.managed_courses:
            flash('You do not have permission for this course.', 'error')
            return render_template('admin/post_note.html', courses=courses, tags=tags)
        
        # Handle file upload
        file_path = None
        file_name = None
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename and allowed_file(file.filename):
                file_path, file_name = save_uploaded_file(file, 'notes')
        
        note = Note(
            title=title,
            content=content,
            course_id=course_id,
            tag_id=tag_id if tag_id else None,
            author_id=current_user.id,
            file_path=file_path,
            file_name=file_name
        )
        db.session.add(note)
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
                title=f'📝 New Note: {title}',
                message=f'A new note "{title}" has been posted in {course.name}.',
                type='info',
                link=url_for('note.view', note_id=note.id),
                icon='fa-file-alt',
                icon_color='blue'
            )
        
        flash(f'Note "{title}" posted successfully!', 'success')
        return redirect(url_for('note.manage_notes'))
    
    return render_template('admin/post_note.html', courses=courses, tags=tags)

@note_bp.route('/admin/notes/<int:note_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_note(note_id):
    """Edit an existing note"""
    note = Note.query.get_or_404(note_id)
    
    if not current_user.is_super_admin() and note.course not in current_user.managed_courses:
        flash('You do not have permission to edit this note.', 'error')
        return redirect(url_for('note.manage_notes'))
    
    if current_user.is_super_admin():
        courses = Course.query.all()
    else:
        courses = current_user.managed_courses
    
    tags = Tag.query.all()
    
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        course_id = request.form.get('course_id')
        tag_id = request.form.get('tag_id')
        
        if not title or not content or not course_id:
            flash('Title, content, and course are required.', 'error')
            return render_template('admin/edit_note.html', note=note, courses=courses, tags=tags)
        
        note.title = title
        note.content = content
        note.course_id = course_id
        note.tag_id = tag_id if tag_id else None
        note.updated_at = datetime.utcnow()
        
        # Handle file upload
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename and allowed_file(file.filename):
                # Delete old file if exists
                if note.file_path:
                    old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'notes', note.file_path)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                file_path, file_name = save_uploaded_file(file, 'notes')
                note.file_path = file_path
                note.file_name = file_name
        
        db.session.commit()
        
        # Send notification to students
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
                title=f'📝 Note Updated: {title}',
                message=f'The note "{title}" in {note.course.name} has been updated.',
                type='info',
                link=url_for('note.view', note_id=note.id),
                icon='fa-edit',
                icon_color='blue'
            )
        
        flash(f'Note "{title}" updated successfully!', 'success')
        return redirect(url_for('note.manage_notes'))
    
    return render_template('admin/edit_note.html', note=note, courses=courses, tags=tags)

@note_bp.route('/admin/notes/<int:note_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_note(note_id):
    """Delete a note"""
    note = Note.query.get_or_404(note_id)
    
    if not current_user.is_super_admin() and note.course not in current_user.managed_courses:
        flash('You do not have permission to delete this note.', 'error')
        return redirect(url_for('note.manage_notes'))
    
    # Send notification to students
    from ..services.notification_service import create_notification
    students = User.query.filter(
        User.id.in_(
            db.session.query(CourseEnrollment.student_id).filter(
                CourseEnrollment.course_id == note.course_id,
                CourseEnrollment.status == 'approved'
            )
        )
    ).all()
    
    for student in students:
        create_notification(
            user_id=student.id,
            title=f'🗑️ Note Removed: {note.title}',
            message=f'The note "{note.title}" has been removed from {note.course.name}.',
            type='warning',
            link=url_for('student.courses'),
            icon='fa-trash',
            icon_color='red'
        )
    
    # Delete file if exists
    if note.file_path:
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'notes', note.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
    
    # Delete progress records
    StudentProgress.query.filter_by(note_id=note.id).delete()
    
    db.session.delete(note)
    db.session.commit()
    
    flash('Note deleted successfully.', 'success')
    return redirect(url_for('note.manage_notes'))

@note_bp.route('/admin/notes/bulk-delete', methods=['POST'])
@login_required
@admin_required
def bulk_delete_notes():
    """Bulk delete notes"""
    note_ids = request.form.getlist('note_ids')
    
    if not note_ids:
        flash('No notes selected.', 'warning')
        return redirect(url_for('note.manage_notes'))
    
    deleted_count = 0
    for note_id in note_ids:
        note = Note.query.get(note_id)
        if note:
            if current_user.is_super_admin() or note.course in current_user.managed_courses:
                if note.file_path:
                    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'notes', note.file_path)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                db.session.delete(note)
                deleted_count += 1
    
    db.session.commit()
    flash(f'{deleted_count} notes deleted successfully.', 'success')
    return redirect(url_for('note.manage_notes'))

# ============================================================================
# STUDENT NOTE INTERACTIONS
# ============================================================================

@note_bp.route('/student/notes/<int:note_id>/toggle-read', methods=['POST'])
@login_required
def toggle_note_read(note_id):
    """Toggle read status for a note"""
    note = Note.query.get_or_404(note_id)
    
    if current_user.is_admin():
        return jsonify({'error': 'Admins cannot track progress'}), 403
    
    if not current_user.is_enrolled_in_course(note.course_id):
        return jsonify({'error': 'Not enrolled'}), 403
    
    progress = StudentProgress.query.filter_by(
        student_id=current_user.id,
        note_id=note.id
    ).first()
    
    if not progress:
        progress = StudentProgress(
            student_id=current_user.id,
            note_id=note.id,
            course_id=note.course_id,
            is_read=True,
            read_at=datetime.utcnow()
        )
        db.session.add(progress)
    else:
        progress.is_read = not progress.is_read
        if progress.is_read:
            progress.read_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({'success': True, 'is_read': progress.is_read})

# ============================================================================
# FILE DOWNLOAD
# ============================================================================

@note_bp.route('/download/<filename>')
@login_required
def download_file(filename):
    """Download a file attached to a note"""
    return send_from_directory(
        os.path.join(current_app.config['UPLOAD_FOLDER'], 'notes'),
        filename,
        as_attachment=True
    )