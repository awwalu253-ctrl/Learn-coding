# add_column.py
from backend import create_app
from backend.extensions import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        # Rollback any pending transaction
        db.session.rollback()
        
        # Add last_login column
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS last_login TIMESTAMP'))
        db.session.commit()
        print("✅ Added last_login column to user table")
        
        # Add any other missing columns just in case
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS phone VARCHAR(20)'))
        db.session.commit()
        print("✅ Added phone column")
        
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS dob TIMESTAMP'))
        db.session.commit()
        print("✅ Added dob column")
        
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS profile_picture VARCHAR(200)'))
        db.session.commit()
        print("✅ Added profile_picture column")
        
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS suspension_reason TEXT'))
        db.session.commit()
        print("✅ Added suspension_reason column")
        
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS suspended_at TIMESTAMP'))
        db.session.commit()
        print("✅ Added suspended_at column")
        
        print("All columns added successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        db.session.rollback()

print("Done!")