# backend/config.py
import os
import logging
from dotenv import load_dotenv

# Load .env from root directory
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'awwaludevs-secret-key-change-in-production')
    
    # Database
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL:
        if 'supabase.co' in DATABASE_URL or 'pooler.supabase.com' in DATABASE_URL:
            print("🔗 Connecting to Supabase PostgreSQL...")
            if 'sslmode' not in DATABASE_URL:
                DATABASE_URL += '?sslmode=require'
            print("✅ Supabase connection configured")
        elif os.environ.get('RENDER'):
            if 'sslmode' not in DATABASE_URL:
                DATABASE_URL += '?sslmode=require'
            print("🔗 Connecting to Render PostgreSQL...")
        
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
        
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_size': 10,
            'pool_recycle': 300,
            'pool_pre_ping': True,
            'connect_args': {
                'connect_timeout': 10
            }
        }
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///../database/awwaludevs.db'
        print("⚠️ Using SQLite (local development)")
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload
    if os.environ.get('RENDER'):
        UPLOAD_FOLDER = '/tmp/uploads'
    else:
        UPLOAD_FOLDER = '../frontend/static/uploads'
    
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'txt', 'zip'}
    
    # Ensure directories exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(os.path.join(UPLOAD_FOLDER, 'assignments'), exist_ok=True)
    os.makedirs(os.path.join(UPLOAD_FOLDER, 'notes'), exist_ok=True)
    os.makedirs(os.path.join(UPLOAD_FOLDER, 'profile_pictures'), exist_ok=True)
    
    if not os.environ.get('RENDER'):
        os.makedirs(os.path.join(os.path.dirname(__file__), '../database'), exist_ok=True)
    
    # Logging
    if os.environ.get('RENDER'):
        logging.basicConfig(level=logging.INFO)


# ============================================
# ADD THIS FUNCTION - FIXES THE WARNING
# ============================================
def ensure_columns():
    """Ensure all required columns exist - runs on startup"""
    from sqlalchemy import text, inspect
    from sqlalchemy.exc import ProgrammingError
    from flask import current_app
    from .extensions import db
    
    with current_app.app_context():
        try:
            db.session.rollback()
        except:
            pass
            
        try:
            inspector = inspect(db.engine)
            
            # Check if user table exists
            if 'user' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('user')]
                print(f"📋 Existing user columns: {', '.join(columns)}")
                
                # Add missing columns
                missing_columns = []
                
                if 'last_login' not in columns:
                    missing_columns.append('last_login TIMESTAMP')
                if 'phone' not in columns:
                    missing_columns.append('phone VARCHAR(20)')
                if 'dob' not in columns:
                    missing_columns.append('dob TIMESTAMP')
                if 'profile_picture' not in columns:
                    missing_columns.append('profile_picture VARCHAR(200)')
                if 'suspension_reason' not in columns:
                    missing_columns.append('suspension_reason TEXT')
                if 'suspended_at' not in columns:
                    missing_columns.append('suspended_at TIMESTAMP')
                if 'is_suspended' not in columns:
                    missing_columns.append('is_suspended BOOLEAN DEFAULT FALSE')
                
                for col_def in missing_columns:
                    col_name = col_def.split()[0]
                    try:
                        db.session.execute(text(f'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS {col_def}'))
                        db.session.commit()
                        print(f"✅ Added {col_name} to user")
                    except Exception as e:
                        print(f"⚠️ Could not add {col_name}: {e}")
                        db.session.rollback()
            
            # Check announcement table
            if 'announcement' in inspector.get_table_names():
                ann_columns = [col['name'] for col in inspector.get_columns('announcement')]
                if 'course_id' not in ann_columns:
                    try:
                        db.session.execute(text('ALTER TABLE "announcement" ADD COLUMN IF NOT EXISTS course_id INTEGER REFERENCES course(id)'))
                        db.session.commit()
                        print("✅ Added course_id to announcement")
                    except Exception as e:
                        print(f"⚠️ Could not add course_id: {e}")
                        db.session.rollback()
            
            # Check assignment table
            if 'assignment' in inspector.get_table_names():
                assign_columns = [col['name'] for col in inspector.get_columns('assignment')]
                for col in ['file_path', 'file_name', 'file_size']:
                    if col not in assign_columns:
                        try:
                            col_type = 'VARCHAR(200)' if col == 'file_path' else 'VARCHAR(100)' if col == 'file_name' else 'VARCHAR(20)'
                            db.session.execute(text(f'ALTER TABLE assignment ADD COLUMN IF NOT EXISTS {col} {col_type}'))
                            db.session.commit()
                            print(f"✅ Added {col} to assignment")
                        except Exception as e:
                            print(f"⚠️ Could not add {col}: {e}")
                            db.session.rollback()
            
            print("✅ All columns verified!")
                
        except ProgrammingError as e:
            db.session.rollback()
            print(f"⚠️ Programming error during migration: {e}")
        except Exception as e:
            db.session.rollback()
            print(f"⚠️ Auto-migration warning: {e}")