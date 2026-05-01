from flask import request, render_template, session, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Admin, Participant

def init_auth_routes(app):
    @app.route('/auth', methods=['GET', 'POST'])
    def auth():
        if request.method == 'POST':
            return login()
        mode = request.args.get('mode', 'login') # Default to login
        return render_template('auth.html', mode=mode)

    @app.route('/login', methods=['POST'])
    def login():
        action = request.form.get('action')
        
        # --- STUDENT LOGIN & SIGNUP ---
        if action == 'student_login':
            email = request.form.get('email')
            password = request.form.get('password')
            mode = request.form.get('mode', 'login')
            
            if mode == 'signup':
                # Check if account already exists
                existing = Participant.query.filter_by(email=email).first()
                if existing:
                    flash("Account with this email already exists. Please log in.", "error")
                    return redirect(url_for('auth', mode='login'))
                
                # Process Sign Up
                first_name = request.form.get('first_name', '').strip()
                last_name = request.form.get('last_name', '').strip()
                full_name = f"{first_name} {last_name}".strip()
                if not full_name:
                    full_name = email.split('@')[0].capitalize()
                
                new_p = Participant(
                    name=full_name,
                    email=email,
                    password_hash=generate_password_hash(password), # Hash the new password
                    roll_number=request.form.get('roll_number', '').strip() or None,
                    phone_number=request.form.get('phone_number', '').strip() or None,
                    department=request.form.get('department', '').strip() or None,
                    course=request.form.get('course', '').strip() or None,
                    branch=request.form.get('branch', '').strip() or None,
                    year_of_study=request.form.get('year_of_study', '').strip() or None
                )
                db.session.add(new_p)
                db.session.commit()
                
                # Log them in automatically
                session['email'] = email
                session['role'] = 'student'
                flash("Successfully registered and logged in!", "success")
                return redirect(url_for('explore'))
                
            else:
                # Process Log In
                participant = Participant.query.filter_by(email=email).first()
                
                if not participant:
                    flash("Account not found. Please sign up.", "error")
                    return redirect(url_for('auth', mode='signup'))
                
                # Check if they signed up before passwords were required
                if not participant.password_hash:
                    flash("Your account requires a password update. Please contact administration.", "error")
                    return redirect(url_for('auth', mode='login'))
                    
                # Validate password
                if check_password_hash(participant.password_hash, password):
                    session['email'] = email
                    session['role'] = 'student'
                    flash("Successfully logged in.", "success")
                    return redirect(url_for('explore'))
                else:
                    flash("Invalid password.", "error")
                    return redirect(url_for('auth', mode='login'))

        # --- ADMIN LOGIN ---
        role = request.form.get('role') 
        email = request.form.get('admin_id')
        password = request.form.get('password')
        school_id = request.form.get('school_id')

        admin = Admin.query.filter_by(admin_email=email).first()
        if admin and check_password_hash(admin.password_hash, password) and admin.role == role:
            session['admin_id'] = admin.admin_id
            session['role'] = admin.role
            session['school_id'] = admin.school_id or school_id
            flash("Welcome back, Administrator.", "success")
            return redirect(url_for('admin_dashboard'))

        flash("Invalid admin credentials or role mismatch.", "error")
        return redirect(url_for('auth'))

    @app.route('/logout')
    def logout():
        session.clear()
        flash("You have been successfully logged out.", "info")
        return redirect(url_for('explore'))