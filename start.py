#!/usr/bin/env python3
"""
Simple startup script for Email Management Tool
Run with: python start.py
"""

import os
import sys
import subprocess
import time

def check_dependencies():
    """Check if required dependencies are available"""
    try:
        import flask
        import sqlalchemy
        import imapclient
        print("✓ Dependencies available")
        return True
    except ImportError as e:
        print(f"✗ Missing dependency: {e}")
        print("Run: pip install -r requirements.txt")
        return False

def check_env_file():
    """Check if .env file exists"""
    if os.path.exists('.env'):
        print("✓ Environment file found")
        return True
    else:
        print("⚠ No .env file found, using defaults")
        return False

def check_database():
    """Check if database exists"""
    if os.path.exists('email_manager.db'):
        print("✓ Database found")
        return True
    else:
        print("⚠ Database not found, will be created on first run")
        return False

def main():
    print("=" * 60)
    print("  EMAIL MANAGEMENT TOOL - QUICK START")
    print("=" * 60)
    print()

    # Pre-flight checks
    print("Checking system requirements...")
    deps_ok = check_dependencies()
    env_ok = check_env_file()
    db_ok = check_database()
    print()

    if not deps_ok:
        print("Please install dependencies first:")
        print("  pip install -r requirements.txt")
        sys.exit(1)

    # Start the application
    print("Starting Email Management Tool...")
    print()
    print("🌐 Web Dashboard: http://localhost:5001")
    print("👤 Default Login: admin / admin123")
    print("📧 SMTP Proxy: localhost:8587")
    print()
    print("Press Ctrl+C to stop")
    print("-" * 60)
    print()

    try:
        # Import and run the app
        from simple_app import app
        from simple_app import init_database

        # Initialize database if needed
        if not db_ok:
            print("Initializing database...")
            init_database()

        # Run the app
        debug = str(os.environ.get('FLASK_DEBUG', '1')).lower() in ('1', 'true', 'yes')
        host = os.environ.get('FLASK_HOST', '127.0.0.1')
        port = int(os.environ.get('FLASK_PORT', '5001'))

        app.run(debug=debug, use_reloader=False, host=host, port=port)

    except KeyboardInterrupt:
        print("\nApplication stopped by user")
    except Exception as e:
        print(f"\nError starting application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
