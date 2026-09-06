# fix_column.py
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL
database_url = os.environ.get('DATABASE_URL')

if not database_url:
    print("❌ DATABASE_URL not found in environment variables")
    exit(1)

# Ensure SSL for Supabase
if 'supabase.co' in database_url or 'pooler.supabase.com' in database_url:
    if 'sslmode' not in database_url:
        database_url += '?sslmode=require'

print(f"🔗 Connecting to database...")

try:
    # Create engine
    engine = create_engine(database_url)
    
    with engine.connect() as conn:
        # Add last_login column
        print("📝 Adding last_login column...")
        conn.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS last_login TIMESTAMP'))
        conn.commit()
        print("✅ Added last_login column")
        
        # Add other missing columns
        columns_to_add = [
            ('phone', 'VARCHAR(20)'),
            ('dob', 'TIMESTAMP'),
            ('profile_picture', 'VARCHAR(200)'),
            ('suspension_reason', 'TEXT'),
            ('suspended_at', 'TIMESTAMP'),
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                print(f"📝 Adding {col_name} column...")
                conn.execute(text(f'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS {col_name} {col_type}'))
                conn.commit()
                print(f"✅ Added {col_name} column")
            except Exception as e:
                print(f"⚠️ Could not add {col_name}: {e}")
                conn.rollback()
        
        # Check if is_suspended exists
        try:
            conn.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS is_suspended BOOLEAN DEFAULT FALSE'))
            conn.commit()
            print("✅ Added is_suspended column")
        except Exception as e:
            print(f"⚠️ Could not add is_suspended: {e}")
            conn.rollback()
        
        print("\n✅ All columns added successfully!")
        
        # Verify columns exist
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'user'
            ORDER BY ordinal_position
        """))
        
        columns = [row[0] for row in result]
        print(f"\n📋 Current columns in user table: {', '.join(columns)}")
        
except Exception as e:
    print(f"❌ Error: {e}")