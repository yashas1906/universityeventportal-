from datetime import datetime, timezone, timedelta
from itertools import groupby
from flask import request, render_template, session, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash
from models import db, Event, Participant, EventRegistration, Admin, School
from utils import login_required
from sqlalchemy import func, distinct, text
import traceback

# Define Indian Standard Time (UTC + 5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def init_student_routes(app):
    @app.route('/')
    @app.route('/explore')
    def explore():
        now = datetime.now(timezone.utc)
        upcoming_events = Event.query.filter(Event.event_date >= now).order_by(Event.event_date.asc()).all()
        past_events = Event.query.filter(Event.event_date < now).order_by(Event.event_date.desc()).all()

        # OJAS Specific Data
        ojas_event = db.session.get(Event, 1)
        ojas_sub_events_count = Event.query.filter_by(parent_event_id=1).count()
        
        ojas_participants_count = db.session.query(func.count(distinct(EventRegistration.participant_id)))\
            .join(Event, EventRegistration.event_id == Event.event_id)\
            .join(Participant, EventRegistration.participant_id == Participant.participant_id)\
            .filter(
                (Event.parent_event_id == 1) | (Event.event_id == 1),
                Participant.roll_number != None,
                ~Participant.email.ilike('%admin%'),
                ~Participant.email.ilike('%test%')
            ).scalar()

        # Fetch Leaderboard Data
        try:
            leaderboard_query = text('SELECT school_name, total_points FROM view_ojas_leaderboard ORDER BY total_points DESC')
            leaderboard_result = db.session.execute(leaderboard_query).fetchall()
            leaderboard = [{"school_name": row.school_name, "total_points": row.total_points} for row in leaderboard_result]
        except:
            leaderboard = []

        # FETCH DETAILED OJAS BREAKDOWN FOR THE MODAL
        ojas_sub_events = Event.query.filter_by(parent_event_id=1).all()
        ojas_details = []
        for sub in ojas_sub_events:
            winner_reg = EventRegistration.query.filter_by(event_id=sub.event_id, rank_position=1).first()
            winner_name = "TBA"
            if winner_reg:
                winner_p = db.session.get(Participant, winner_reg.participant_id)
                if winner_p:
                    school_name = "Unknown School"
                    if winner_p.department:
                        s = School.query.filter(School.name.ilike(f"%{winner_p.department}%")).first()
                        if s: school_name = s.name
                    winner_name = f"{winner_p.name} ({school_name})"

            org_school = db.session.get(School, sub.organizing_school_id) if sub.organizing_school_id else None
            org_name = org_school.name if org_school else "University-Wide"
            
            ojas_details.append({
                "title": sub.title,
                "organizing_school": org_name,
                "date": sub.event_date.strftime('%d %b %Y') if sub.event_date else "TBA",
                "winner": winner_name
            })

        return render_template('explore.html', upcoming=upcoming_events, past=past_events,
                               ojas_event=ojas_event, ojas_sub_events_count=ojas_sub_events_count,
                               ojas_participants_count=ojas_participants_count, leaderboard=leaderboard,
                               ojas_details=ojas_details)

    @app.route('/calendar')
    def calendar():
        # Order by date is crucial for grouping
        events = Event.query.order_by(Event.event_date.desc()).all()
        now = datetime.now(timezone.utc)
        
        # Extract unique categories for the filter pills
        db_categories_tuples = db.session.query(Event.category).filter(Event.category != None).distinct().all()
        categories = sorted([row[0] for row in db_categories_tuples if row[0] and str(row[0]).strip()])

        # Grouping Logic
        grouped_events = []
        
        # We need a key function for groupby. 
        def get_date_key(ev):
             # Convert to IST before grouping so midnight UTC boundaries don't mess up dates
             return ev.event_date.astimezone(IST).date() if ev.event_date else None

        for date_key, group in groupby(events, key=get_date_key):
            if date_key is None:
                 continue # Skip events with no date for the calendar view
                 
            # Prepare the date block information
            date_info = {
                "day_of_week": date_key.strftime('%a').upper(), # MON, TUE
                "day_num": date_key.strftime('%d'),             # 27, 24
                "month_short": date_key.strftime('%b').upper(), # APR
                "raw_date": date_key # Used for sorting/filtering later if needed
            }
            
            # Prepare the events for this specific date
            day_events = []
            for ev in group:
                if ev.event_date < now:
                    time_bucket = 'past'
                # Use IST for the "today" check
                elif ev.event_date.astimezone(IST).date() == datetime.now(IST).date():
                    time_bucket = 'today'
                else:
                    time_bucket = 'upcoming'

                # Explicitly convert to IST timezone before formatting the display string
                local_time = ev.event_date.astimezone(IST) if ev.event_date else None

                day_events.append({
                    "id": ev.event_id,
                    "title": ev.title,
                    "category": ev.category,
                    "date": ev.event_date.strftime('%Y-%m-%dT%H:%M:%S'),
                    "display_time": local_time.strftime('%I:%M %p').lstrip('0') if local_time else "TBA",
                    "venue": ev.venue,
                    "incharge_club": ev.incharge_club,
                    "time_bucket": time_bucket
                })
                
            grouped_events.append({
                "date_info": date_info,
                "events": day_events
            })

        return render_template('calendar.html', grouped_events=grouped_events, categories=categories)

    @app.route('/profile')
    @login_required
    def profile():
        role = session.get('role')
        if role in ['school_admin', 'university_admin', 'university_head']:
            admin_id = session.get('admin_id')
            admin = db.session.get(Admin, admin_id)
            if not admin:
                flash("Admin record not found.", "error")
                return redirect(url_for('auth'))
            school = db.session.get(School, admin.school_id) if admin.school_id else None
            return render_template('profile.html', is_admin=True, admin=admin, school=school)

        email = session.get('email')
        participant = Participant.query.filter_by(email=email).first()
        regs = EventRegistration.query.filter_by(participant_id=participant.participant_id).all() if participant else []
        trophy_events = [r for r in regs if r.rank_position is not None]
        now = datetime.now(timezone.utc)
        return render_template('profile.html', is_admin=False, participant=participant, participated_events=regs, trophy_events=trophy_events, now=now)

    @app.route('/api/profile/update', methods=['POST'])
    @login_required
    def update_profile():
        role = session.get('role')
        data = request.form
        
        if role in ['school_admin', 'university_admin', 'university_head']:
            admin_id = session.get('admin_id')
            admin = db.session.get(Admin, admin_id)
            if admin:
                admin.admin_email = data.get('admin_email', admin.admin_email).strip()
                new_pw = data.get('password', '').strip()
                if new_pw:  
                    admin.password_hash = generate_password_hash(new_pw)
                db.session.commit()
                flash("Administrator credentials updated!", "success")
            return redirect(url_for('profile'))

        email = session.get('email')
        participant = Participant.query.filter_by(email=email).first()
        
        if participant:
            # Safely catch empty inputs or the literal string "None"
            def clean_val(key):
                v = data.get(key, '').strip()
                return None if not v or v.lower() == 'none' else v

            participant.name = clean_val('name') or participant.name
            participant.phone_number = clean_val('phone_number')
            participant.department = clean_val('department') # Academic School
            participant.course = clean_val('course')         # Course
            participant.branch = clean_val('branch')         # Branch
            participant.year_of_study = clean_val('year_of_study')

            new_roll = clean_val('roll_number')
            if new_roll and new_roll != participant.roll_number:
                taken = Participant.query.filter(
                    Participant.roll_number == new_roll,
                    Participant.participant_id != participant.participant_id
                ).first()
                if taken:
                    flash("Roll number already assigned to another student.", "error")
                    return redirect(url_for('profile'))
                participant.roll_number = new_roll
            elif not new_roll:
                participant.roll_number = None

            try:
                db.session.commit()
                flash("Profile updated successfully!", "success")
            except Exception as e:
                db.session.rollback()
                flash(f"Database error: {str(e)}", "error")
        else:
            flash("Student record not found.", "error")
            
        return redirect(url_for('profile'))

    @app.route('/api/register', methods=['POST'])
    def api_register():
        # Ensure the user is logged in as a student
        if 'role' not in session or session['role'] != 'student':
            return jsonify({'error': 'Unauthorized. Please log in.'}), 403

        data = request.get_json()
        event_id = data.get('event_id')
        reg_format = data.get('format', 'solo')
        team_name = data.get('team_name')
        participants_data = data.get('participants', [])

        if not event_id or not participants_data:
            return jsonify({'error': 'Invalid registration data received.'}), 400

        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({'error': 'Event not found.'}), 404

        registered_count = 0

        try:
            for p_data in participants_data:
                roll_no = p_data.get('roll_number', '').strip().upper()
                name = p_data.get('name', '').strip()

                if not roll_no or not name:
                    continue # Skip if empty row

                # 1. Find the participant by Roll Number, or create them if they are new
                participant = Participant.query.filter_by(roll_number=roll_no).first()
                
                if not participant:
                    is_internal = (p_data.get('affiliation') == 'Internal')
                    participant = Participant(
                        name=name,
                        roll_number=roll_no,
                        email=f"temp_{roll_no}@placeholder.com", # Added a temp email since email is required and unique
                        department=p_data.get('department'),
                        year_of_study=p_data.get('year'),
                        is_internal=is_internal
                    )
                    db.session.add(participant)
                    db.session.flush() # Assigns an ID without fully committing yet
                else:
                    # Optional: Update existing participant if they left these blank previously
                    if not participant.department and p_data.get('department'): 
                        participant.department = p_data.get('department')
                    if not participant.year_of_study and p_data.get('year'): 
                        participant.year_of_study = p_data.get('year')

                # 2. Prevent Double Registration
                existing_reg = EventRegistration.query.filter_by(
                    event_id=event_id, 
                    participant_id=participant.participant_id
                ).first()

                if existing_reg:
                    db.session.rollback()
                    return jsonify({'error': f'{name} ({roll_no}) is already registered for this event.'}), 400

                # 3. Create the Event Registration
                new_reg = EventRegistration(
                    event_id=event_id,
                    participant_id=participant.participant_id,
                    team_name=team_name if reg_format == 'group' else None
                )
                db.session.add(new_reg)
                registered_count += 1

            # Commit everything to the database at once
            db.session.commit()
            return jsonify({'success': True, 'message': f'Successfully registered {registered_count} participants.'})

        except Exception as e:
            db.session.rollback()
            print(f"Registration Error: {traceback.format_exc()}")
            return jsonify({'error': 'A database error occurred during registration.'}), 500
