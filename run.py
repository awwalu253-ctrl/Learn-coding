# run.py
import os
from backend import create_app

# Create the app instance
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    print("=" * 60)
    print("🚀 Awwalu Devs - Learning Management System")
    print("=" * 60)
    print(f"🔧 Running on port: {port}")
    print(f"🐛 Debug mode: {debug}")
    print("=" * 60)
    
    # Bind to all interfaces
    app.run(debug=debug, host='0.0.0.0', port=port)