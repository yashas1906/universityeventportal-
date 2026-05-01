from functools import wraps
from flask import session, flash, redirect, url_for

# In-Memory OTP Store
otp_store = {}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for('auth'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') not in ['school_admin', 'university_admin', 'university_head']:
            flash("Unauthorized access. Admin privileges required.", "error")
            return redirect(url_for('explore'))
        return f(*args, **kwargs)
    return decorated_function