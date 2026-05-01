import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from flask import Flask
from models import db

# Import modular route files
from routes.auth import init_auth_routes
from routes.student import init_student_routes
from routes.analytics import init_analytics_routes
from routes.admin import init_admin_routes

# Load environment variables
load_dotenv()

app = Flask(__name__)

# --- CONFIGURATION ---
# Use Render's DATABASE_URL or a local fallback
app.secret_key = os.getenv("SECRET_KEY", "super-secret-dev-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Supabase/PostgreSQL Connection Drop Fix
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

app.config['UPLOAD_FOLDER'] = 'static/uploads/events'

# --- INITIALIZATION ---
# Bind Database
db.init_app(app)

# Bind all the routes to the app
init_auth_routes(app)
init_student_routes(app)
init_analytics_routes(app)
init_admin_routes(app)

# ── PRODUCTION DEPLOYMENT FIX ── 
# On Render/Gunicorn, the '__main__' block does not run.
# Moving these commands here ensures tables and folders are created at startup.
with app.app_context():
    db.create_all()
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

if __name__ == '__main__':
    # For local development only
    app.run(debug=True, port=5000)