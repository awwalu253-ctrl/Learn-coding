# backend/utils/file_utils.py
import os
from flask import current_app, send_from_directory, abort

def find_and_serve_file(filename, subfolder='assignments', as_attachment=True, download_name=None):
    """
    Find a file in multiple possible locations and serve it
    """
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    
    # Possible locations to check
    possible_paths = [
        upload_folder,
        os.path.join(upload_folder, subfolder),
        os.path.join(os.path.dirname(current_app.root_path), 'frontend', 'static', 'uploads'),
        os.path.join(os.path.dirname(current_app.root_path), 'frontend', 'static', 'uploads', subfolder),
        os.path.join(current_app.root_path, '..', 'frontend', 'static', 'uploads'),
        os.path.join(current_app.root_path, '..', 'frontend', 'static', 'uploads', subfolder),
        '/tmp/uploads',
        os.path.join('/tmp', 'uploads', subfolder)
    ]
    
    for path in possible_paths:
        if not path:
            continue
        full_path = os.path.join(path, filename)
        if os.path.exists(full_path):
            return send_from_directory(
                path,
                filename,
                as_attachment=as_attachment,
                download_name=download_name or filename
            )
    
    # If file not found
    current_app.logger.error(f"File not found: {filename} in paths: {possible_paths}")
    abort(404)