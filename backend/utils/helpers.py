# backend/utils/helpers.py
import os
import uuid
from datetime import datetime
from flask import current_app
from werkzeug.utils import secure_filename

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def get_upload_path(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    unique_name = f"{uuid.uuid4().hex[:12]}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    return f"{unique_name}.{ext}" if ext else unique_name

def validate_assignment_file(file):
    if not file or file.filename == '':
        return None, "No file selected"
    
    if not allowed_file(file.filename):
        return None, f"File type not allowed"
    
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    
    if size > current_app.config['MAX_CONTENT_LENGTH']:
        return None, f"File too large"
    
    return True, None

def save_uploaded_file(file, subfolder=''):
    if not file or not file.filename:
        return None, None
    
    filename = secure_filename(file.filename)
    unique_filename = get_upload_path(filename)
    
    upload_dir = current_app.config['UPLOAD_FOLDER']
    if subfolder:
        upload_dir = os.path.join(upload_dir, subfolder)
        os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, unique_filename)
    file.save(file_path)
    
    return unique_filename, filename