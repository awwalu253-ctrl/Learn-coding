# run.py
import os
from backend import create_app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    print("=" * 60)
    print("🚀 Awwalu Devs - Learning Management System")
    print("=" * 60)
    print("📚 Default Admin Credentials:")
    print("   Username: admin")
    print("   Password: admin123")
    print("=" * 60)
    
    app.run(debug=debug, host='0.0.0.0', port=port)