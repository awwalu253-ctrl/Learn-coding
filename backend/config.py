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
    if not os.environ.get('RENDER'):
        os.makedirs(os.path.join(os.path.dirname(__file__), '../database'), exist_ok=True)
    
    # Logging
    if os.environ.get('RENDER'):
        logging.basicConfig(level=logging.INFO)