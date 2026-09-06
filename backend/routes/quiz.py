# backend/routes/quiz.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from ..extensions import db
from ..models.quiz import QuizGroup, QuizQuestion, QuizAnswer
from ..models.course import Course
from ..models.user import User, CourseEnrollment
from ..utils.decorators import admin_required, student_required

quiz_bp = Blueprint('quiz', __name__)

# ============================================================================
# STUDENT ROUTES
# ============================================================================

@quiz_bp.route('/student/quizzes')
@login_required
def student_quizzes():
    """Student quiz listing page"""
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    
    approved_courses = current_user.get_enrolled_courses()
    course_ids = [c.id for c in approved_courses]
    quizzes = QuizGroup.query.filter(QuizGroup.course_id.in_(course_ids)).all()
    
    quiz_data = []
    for quiz in quizzes:
        score = quiz.get_student_score(current_user.id)
        quiz_data.append({
            'quiz': quiz,
            'score': score,
            'has_attempted': score is not None
        })
    
    return render_template('student/quizzes.html', quiz_data=quiz_data)


@quiz_bp.route('/student/quizzes/<int:quiz_id>/take', methods=['GET', 'POST'])
@login_required
def take_quiz(quiz_id):
    """Take a quiz"""
    if current_user.is_admin():
        flash('Admins cannot take quizzes.', 'warning')
        return redirect(url_for('admin.dashboard'))
    
    quiz = QuizGroup.query.get_or_404(quiz_id)
    
    if not current_user.is_enrolled_in_course(quiz.course_id):
        flash('You are not enrolled in this course.', 'error')
        return redirect(url_for('student_quizzes'))
    
    # Check if already taken
    existing_answers = QuizAnswer.query.filter_by(
        student_id=current_user.id,
        quiz_group_id=quiz.id
    ).first()
    
    if existing_answers:
        flash('You have already taken this quiz.', 'info')
        return redirect(url_for('student_quizzes'))
    
    questions = quiz.questions
    
    if request.method == 'POST':
        correct_count = 0
        total = len(questions)
        
        for question in questions:
            selected = request.form.get(f'question_{question.id}')
            if selected:
                is_correct = selected == question.correct_option
                if is_correct:
                    correct_count += 1
                
                answer = QuizAnswer(
                    student_id=current_user.id,
                    quiz_group_id=quiz.id,
                    question_id=question.id,
                    selected_option=selected,
                    is_correct=is_correct
                )
                db.session.add(answer)
            else:
                # If no answer selected, mark as incorrect but still create an answer
                answer = QuizAnswer(
                    student_id=current_user.id,
                    quiz_group_id=quiz.id,
                    question_id=question.id,
                    selected_option='',
                    is_correct=False
                )
                db.session.add(answer)
        
        db.session.commit()
        
        score_percentage = int((correct_count / total) * 100) if total > 0 else 0
        
        # Send notification
        from ..services.notification_service import create_notification
        create_notification(
            user_id=current_user.id,
            title='📝 Quiz Completed!',
            message=f'You completed "{quiz.title}" with a score of {score_percentage}%',
            type='success',
            link=url_for('quiz.quiz_result', quiz_id=quiz.id),
            icon='fa-check-circle',
            icon_color='green'
        )
        
        return render_template('quiz/result.html', 
                             quiz=quiz, 
                             total=total, 
                             correct=correct_count, 
                             score=score_percentage)
    
    return render_template('quiz/take.html', quiz=quiz, questions=questions)


@quiz_bp.route('/student/quizzes/<int:quiz_id>/result')
@login_required
def quiz_result(quiz_id):
    """View quiz result"""
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    
    quiz = QuizGroup.query.get_or_404(quiz_id)
    
    if not current_user.is_enrolled_in_course(quiz.course_id):
        flash('You are not enrolled in this course.', 'error')
        return redirect(url_for('student_quizzes'))
    
    answers = QuizAnswer.query.filter_by(
        student_id=current_user.id,
        quiz_group_id=quiz.id
    ).all()
    
    if not answers:
        flash('You have not taken this quiz yet.', 'info')
        return redirect(url_for('student_quizzes'))
    
    correct = sum(1 for a in answers if a.is_correct)
    total = len(answers)
    score = int((correct / total) * 100) if total > 0 else 0
    
    return render_template('quiz/result.html', 
                         quiz=quiz, 
                         total=total, 
                         correct=correct, 
                         score=score)


@quiz_bp.route('/student/quizzes/<int:quiz_id>/review')
@login_required
def quiz_review(quiz_id):
    """Review quiz answers"""
    if current_user.is_admin():
        flash('Admins cannot review quizzes.', 'warning')
        return redirect(url_for('admin.dashboard'))
    
    quiz = QuizGroup.query.get_or_404(quiz_id)
    
    if not current_user.is_enrolled_in_course(quiz.course_id):
        flash('You are not enrolled in this course.', 'error')
        return redirect(url_for('student_quizzes'))
    
    answers = QuizAnswer.query.filter_by(
        student_id=current_user.id,
        quiz_group_id=quiz.id
    ).all()
    
    if not answers:
        flash('You have not taken this quiz yet.', 'info')
        return redirect(url_for('student_quizzes'))
    
    questions = QuizQuestion.query.filter_by(quiz_group_id=quiz.id).order_by(QuizQuestion.order.asc()).all()
    
    question_reviews = []
    correct_count = 0
    
    for question in questions:
        answer = next((a for a in answers if a.question_id == question.id), None)
        
        if answer:
            is_correct = answer.is_correct
            if is_correct:
                correct_count += 1
        else:
            is_correct = False
        
        question_reviews.append({
            'question_id': question.id,
            'question_text': question.question_text,
            'option_a': question.option_a,
            'option_b': question.option_b,
            'option_c': question.option_c,
            'option_d': question.option_d,
            'correct': question.correct_option,
            'selected': answer.selected_option if answer else None,
            'is_correct': is_correct
        })
    
    total_questions = len(questions)
    score = int((correct_count / total_questions) * 100) if total_questions > 0 else 0
    
    return render_template('quiz/review.html',
                         quiz=quiz,
                         question_reviews=question_reviews,
                         correct_count=correct_count,
                         total_questions=total_questions,
                         score=score)


# ============================================================================
# ADMIN ROUTES
# ============================================================================

@quiz_bp.route('/admin/quizzes')
@login_required
@admin_required
def manage_quizzes():
    """Manage all quizzes"""
    if current_user.is_super_admin():
        quizzes = QuizGroup.query.order_by(QuizGroup.created_at.desc()).all()
    else:
        course_ids = [c.id for c in current_user.managed_courses]
        quizzes = QuizGroup.query.filter(QuizGroup.course_id.in_(course_ids)).order_by(QuizGroup.created_at.desc()).all()
    
    return render_template('admin/manage_quizzes.html', quizzes=quizzes)


@quiz_bp.route('/admin/quizzes/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_quiz_group():
    """Create a new quiz"""
    if current_user.is_super_admin():
        courses = Course.query.all()
    else:
        courses = current_user.managed_courses
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        course_id = request.form.get('course_id')
        time_limit = request.form.get('time_limit', 0)
        
        if not title or not course_id:
            flash('Title and course are required.', 'error')
            return render_template('admin/create_quiz_group.html', courses=courses)
        
        course = Course.query.get(course_id)
        if not current_user.is_super_admin() and course not in current_user.managed_courses:
            flash('You do not have permission for this course.', 'error')
            return render_template('admin/create_quiz_group.html', courses=courses)
        
        quiz_group = QuizGroup(
            title=title,
            description=description,
            course_id=course_id,
            author_id=current_user.id,
            time_limit=int(time_limit) if time_limit else 0
        )
        db.session.add(quiz_group)
        db.session.flush()  # Get the ID
        
        # Get questions from form - Only add complete questions
        questions = request.form.getlist('question_text')
        option_a = request.form.getlist('option_a')
        option_b = request.form.getlist('option_b')
        option_c = request.form.getlist('option_c')
        option_d = request.form.getlist('option_d')
        correct_option = request.form.getlist('correct_option')
        
        added_count = 0
        for i in range(len(questions)):
            if (questions[i] and option_a[i] and option_b[i] and 
                option_c[i] and option_d[i] and correct_option[i]):
                question = QuizQuestion(
                    question_text=questions[i],
                    option_a=option_a[i],
                    option_b=option_b[i],
                    option_c=option_c[i],
                    option_d=option_d[i],
                    correct_option=correct_option[i],
                    order=i,
                    quiz_group_id=quiz_group.id
                )
                db.session.add(question)
                added_count += 1
            elif questions[i]:
                flash(f'Question {i+1} was incomplete and was not added.', 'warning')
        
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
                title=f'📝 New Quiz: {title}',
                message=f'A new quiz "{title}" is available in {course.name}.',
                type='info',
                link=url_for('quiz.student_quizzes'),
                icon='fa-puzzle-piece',
                icon_color='gold'
            )
        
        flash(f'Quiz "{title}" created with {added_count} questions!', 'success')
        return redirect(url_for('quiz.manage_quizzes'))
    
    return render_template('admin/create_quiz_group.html', courses=courses)


@quiz_bp.route('/admin/quizzes/<int:quiz_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_quiz_group(quiz_id):
    """Edit an existing quiz"""
    quiz = QuizGroup.query.get_or_404(quiz_id)
    
    if not current_user.is_super_admin() and quiz.course not in current_user.managed_courses:
        flash('You do not have permission to edit this quiz.', 'error')
        return redirect(url_for('quiz.manage_quizzes'))
    
    if current_user.is_super_admin():
        courses = Course.query.all()
    else:
        courses = current_user.managed_courses
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        course_id = request.form.get('course_id')
        time_limit = request.form.get('time_limit', 0)
        
        if not title or not course_id:
            flash('Title and course are required.', 'error')
            return render_template('admin/edit_quiz_group.html', quiz=quiz, courses=courses)
        
        quiz.title = title
        quiz.description = description
        quiz.course_id = course_id
        quiz.time_limit = int(time_limit) if time_limit else 0
        quiz.updated_at = datetime.utcnow()
        
        # Delete questions marked for removal
        delete_questions = request.form.getlist('delete_questions')
        for qid in delete_questions:
            if qid:
                q = QuizQuestion.query.get(qid)
                if q and q.quiz_group_id == quiz.id:
                    # Delete associated answers first
                    QuizAnswer.query.filter_by(question_id=q.id).delete()
                    db.session.delete(q)
        
        # Update existing questions
        question_ids = request.form.getlist('question_id')
        for qid in question_ids:
            if qid:
                q = QuizQuestion.query.get(qid)
                if q and q.quiz_group_id == quiz.id:
                    question_text = request.form.get(f'question_text_{qid}')
                    option_a = request.form.get(f'option_a_{qid}')
                    option_b = request.form.get(f'option_b_{qid}')
                    option_c = request.form.get(f'option_c_{qid}')
                    option_d = request.form.get(f'option_d_{qid}')
                    correct_option = request.form.get(f'correct_option_{qid}')
                    
                    # Only update if all fields are present
                    if question_text and option_a and option_b and option_c and option_d and correct_option:
                        q.question_text = question_text
                        q.option_a = option_a
                        q.option_b = option_b
                        q.option_c = option_c
                        q.option_d = option_d
                        q.correct_option = correct_option
                    else:
                        # If required fields are missing, skip this question
                        flash(f'Question {qid} has missing fields and was skipped.', 'warning')
                        # Don't delete it, just skip the update
        
        # Add new questions
        new_questions = request.form.getlist('new_question_text')
        new_option_a = request.form.getlist('new_option_a')
        new_option_b = request.form.getlist('new_option_b')
        new_option_c = request.form.getlist('new_option_c')
        new_option_d = request.form.getlist('new_option_d')
        new_correct_option = request.form.getlist('new_correct_option')
        
        # Get current max order
        existing_questions = QuizQuestion.query.filter_by(quiz_group_id=quiz.id).order_by(QuizQuestion.order.desc()).first()
        next_order = (existing_questions.order + 1) if existing_questions else 0
        
        added_count = 0
        for i in range(len(new_questions)):
            if (new_questions[i] and new_option_a[i] and new_option_b[i] and 
                new_option_c[i] and new_option_d[i] and new_correct_option[i]):
                question = QuizQuestion(
                    question_text=new_questions[i],
                    option_a=new_option_a[i],
                    option_b=new_option_b[i],
                    option_c=new_option_c[i],
                    option_d=new_option_d[i],
                    correct_option=new_correct_option[i],
                    order=next_order + i,
                    quiz_group_id=quiz.id
                )
                db.session.add(question)
                added_count += 1
            elif new_questions[i]:
                flash(f'New question {i+1} was incomplete and was not added.', 'warning')
        
        db.session.commit()
        
        if added_count > 0:
            flash(f'Quiz "{title}" updated successfully! Added {added_count} new questions.', 'success')
        else:
            flash(f'Quiz "{title}" updated successfully!', 'success')
        return redirect(url_for('quiz.manage_quizzes'))
    
    return render_template('admin/edit_quiz_group.html', quiz=quiz, courses=courses)


@quiz_bp.route('/admin/quizzes/<int:quiz_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_quiz_group(quiz_id):
    """Delete a quiz"""
    quiz = QuizGroup.query.get_or_404(quiz_id)
    
    if not current_user.is_super_admin() and quiz.course not in current_user.managed_courses:
        flash('You do not have permission to delete this quiz.', 'error')
        return redirect(url_for('quiz.manage_quizzes'))
    
    # Send notification to students
    from ..services.notification_service import create_notification
    students = User.query.filter(
        User.id.in_(
            db.session.query(CourseEnrollment.student_id).filter(
                CourseEnrollment.course_id == quiz.course_id,
                CourseEnrollment.status == 'approved'
            )
        )
    ).all()
    
    for student in students:
        create_notification(
            user_id=student.id,
            title=f'🗑️ Quiz Removed: {quiz.title}',
            message=f'The quiz "{quiz.title}" has been removed from {quiz.course.name}.',
            type='warning',
            link=url_for('student_quizzes'),
            icon='fa-trash',
            icon_color='red'
        )
    
    # Delete related records
    QuizAnswer.query.filter_by(quiz_group_id=quiz.id).delete()
    QuizQuestion.query.filter_by(quiz_group_id=quiz.id).delete()
    
    db.session.delete(quiz)
    db.session.commit()
    
    flash('Quiz deleted successfully.', 'success')
    return redirect(url_for('quiz.manage_quizzes'))


# ============================================================================
# API ENDPOINTS
# ============================================================================

@quiz_bp.route('/api/quizzes/<int:quiz_id>/results')
@login_required
@admin_required
def get_quiz_results(quiz_id):
    """Get quiz results as JSON"""
    quiz = QuizGroup.query.get_or_404(quiz_id)
    
    if not current_user.is_super_admin() and quiz.course not in current_user.managed_courses:
        return jsonify({'error': 'Unauthorized'}), 403
    
    answers = QuizAnswer.query.filter_by(quiz_group_id=quiz.id).all()
    
    # Group by student
    student_results = {}
    for answer in answers:
        if answer.student_id not in student_results:
            student_results[answer.student_id] = {'correct': 0, 'total': 0}
        student_results[answer.student_id]['total'] += 1
        if answer.is_correct:
            student_results[answer.student_id]['correct'] += 1
    
    results = []
    for student_id, data in student_results.items():
        student = User.query.get(student_id)
        if student:
            score = int((data['correct'] / data['total']) * 100) if data['total'] > 0 else 0
            results.append({
                'student_name': student.username,
                'correct': data['correct'],
                'total': data['total'],
                'score': score
            })
    
    results.sort(key=lambda x: x['score'], reverse=True)
    
    return jsonify({
        'quiz_title': quiz.title,
        'total_students': len(results),
        'results': results
    })

@quiz_bp.route('/admin/quizzes/<int:quiz_id>/view')
@login_required
@admin_required
def view_quiz(quiz_id):
    """View a quiz (read-only mode for admins)"""
    quiz = QuizGroup.query.get_or_404(quiz_id)
    
    if not current_user.is_super_admin() and quiz.course not in current_user.managed_courses:
        flash('You do not have permission to view this quiz.', 'error')
        return redirect(url_for('quiz.manage_quizzes'))
    
    questions = QuizQuestion.query.filter_by(quiz_group_id=quiz.id).order_by(QuizQuestion.order.asc()).all()
    
    return render_template('admin/view_quiz.html', 
                         quiz=quiz, 
                         questions=questions,
                         total_questions=len(questions))