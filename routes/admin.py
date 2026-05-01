import pandas as pd
from datetime import datetime, timedelta
from flask import request, jsonify, render_template, session, redirect, url_for, flash, abort, Response
from icalendar import Calendar, Event as IcalEvent
from models import db, Event, Participant, EventRegistration, School
from utils import admin_required

def init_admin_routes(app):
    @app.route('/admin/dashboard')
    @admin_required
    def admin_dashboard():
        role = session.get('role')
        
        # 🚨 SECURE BLOCK: Reject University Head from accessing the console
        if role not in ['school_admin', 'university_admin']:
            flash("Access denied. Only event organizers can access the Management Console.", "error")
            return redirect(url_for('profile'))

        school_id = session.get('school_id')
        school = db.session.get(School, school_id) if school_id else None

        # Determine which events this admin is allowed to link to as "Parent Events"
        if role == 'university_admin':
            # University Admins can see/link to ANY event
            existing_events = Event.query.order_by(Event.event_date.desc()).all()
            my_events = Event.query.order_by(Event.event_date.desc()).all()
        else:
            # School Admins can link to University-wide events OR their own School's events
            existing_events = Event.query.filter(
                (Event.organizing_school_id == school_id) | (Event.organizing_school_id == None)
            ).order_by(Event.event_date.desc()).all()
            
            # They only manage their own events in the table
            my_events = Event.query.filter_by(organizing_school_id=school_id).order_by(Event.event_date.desc()).all()

        # --- DYNAMIC CATEGORY LOGIC ---
        # 1. Fetch all unique categories from the database
        db_categories_tuples = db.session.query(Event.category).filter(Event.category != None).distinct().all()
        db_categories = [row[0] for row in db_categories_tuples if row[0] and str(row[0]).strip()]
        
        # 2. Define a baseline of default categories so the list is never empty
        default_categories = [
            'Technical', 'Sports', 'Workshop', 'Academic', 
            'Literary', 'Music', 'Dance', 'Theatre', 
            'Fine Arts', 'Media & Production', 'Business & Entrepreneurship',
            'Gaming', 'Heritage'
        ]
        
        # 3. Combine them, remove duplicates, and sort alphabetically
        all_categories = sorted(list(set(db_categories + default_categories)))

        return render_template(
            'admin_dashboard.html', 
            school=school, 
            existing_events=existing_events, 
            my_events=my_events,
            all_categories=all_categories  # <-- Passes the dynamic list to the HTML
        )

    @app.route('/api/events', methods=['POST'])
    @admin_required
    def api_create_event():
        # 🚨 SECURE BLOCK: Prevent University Head from POSTing data to create an event
        role = session.get('role')
        if role not in ['school_admin', 'university_admin']:
            flash("Access denied. Only event organizers can create events.", "error")
            return redirect(url_for('profile'))

        try:
            data = request.form
            
            # 1. Parse Event Date securely
            event_date_str = data.get('event_date')
            event_date = None
            if event_date_str:
                try:
                    event_date = datetime.strptime(event_date_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    try:
                        event_date = datetime.strptime(event_date_str, '%Y-%m-%d')
                    except ValueError:
                        pass
            
            # 2. Extract Parent Event ID
            parent_id_str = data.get('parent_event_id')
            parent_id = int(parent_id_str) if parent_id_str and parent_id_str.strip() != "" else None

            # 3. Create the Event (Category automatically saves whatever the user types!)
            new_event = Event(
                title=data.get('event_name') or data.get('title'),
                category=data.get('category'),
                event_date=event_date,
                venue=data.get('venue'),
                description=data.get('description'),
                incharge_club=data.get('organizer') or data.get('incharge_club'),
                organizing_school_id=data.get('organizing_school_id') or session.get('school_id'),
                parent_event_id=parent_id 
            )
            db.session.add(new_event)
            db.session.flush()

            image_file = request.files.get('event_image')
            if image_file and image_file.filename:
                import os
                from werkzeug.utils import secure_filename
                if '.' in image_file.filename:
                    ext = image_file.filename.rsplit('.', 1)[1].lower()
                    if ext in ['png', 'jpg', 'jpeg']:
                        filename = secure_filename(image_file.filename)
                        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                        unique_filename = f"{timestamp}_{filename}"
                        save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                        image_file.save(save_path)
                        new_event.image_url = f"/{save_path.replace(os.sep, '/')}"

            # 4. Handle Participant Roster Upload (Excel/CSV)
            file = request.files.get('roster_file')
            if file and file.filename:
                df = pd.read_excel(file) if file.filename.endswith('.xlsx') else pd.read_csv(file)
                df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
                
                for _, row in df.iterrows():
                    email = str(row.get('email', '')).strip()
                    if not email or email == 'nan': continue
                    
                    participant = Participant.query.filter_by(email=email).first()
                    if not participant:
                        participant = Participant(
                            name=str(row.get('name', 'Unknown')),
                            email=email,
                            roll_number=str(row.get('roll_number', '')),
                            department=str(row.get('department', '')),
                            year_of_study=str(row.get('year', ''))
                        )
                        db.session.add(participant)
                        db.session.flush()

                    reg = EventRegistration(
                        event_id=new_event.event_id,
                        participant_id=participant.participant_id,
                        team_name=str(row.get('team_name', '')),
                        rank_position=row.get('rank') if pd.notna(row.get('rank')) else None,
                        points_awarded=int(row.get('points', 0)) if pd.notna(row.get('points')) else 0
                    )
                    db.session.add(reg)

            db.session.commit()
            flash("Event and participants saved successfully!", "success")
            return redirect(url_for('admin_dashboard'))

        except Exception as e:
            db.session.rollback()
            flash(f"Error saving event: {str(e)}", "error")
            return redirect(url_for('admin_dashboard'))

    @app.route('/api/event/<int:event_id>/export', methods=['GET'])
    def export_event_ics(event_id):
        event = db.session.get(Event, event_id)
        if not event:
            abort(404)
            
        cal = Calendar()
        ical_event = IcalEvent()
        
        ical_event.add('summary', event.title)
        if event.event_date:
            ical_event.add('dtstart', event.event_date)
            ical_event.add('dtend', event.event_date + timedelta(hours=2))
        ical_event.add('location', event.venue or 'TBA')
        ical_event.add('description', event.description or '')
        
        cal.add_component(ical_event)
        return Response(
            cal.to_ical(),
            mimetype="text/calendar",
            headers={"Content-Disposition": f"attachment; filename=event_{event_id}.ics"}
        )

    @app.route('/api/events/<int:event_id>', methods=['DELETE'])
    @admin_required
    def delete_event(event_id):
        role = session.get('role')
        if role not in ['school_admin', 'university_admin']:
            return jsonify({"error": "Access denied"}), 403

        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({"error": "Event not found"}), 404
            
        db.session.delete(event)
        db.session.commit()
        return jsonify({"message": "Event deleted successfully."}), 200
    @app.route('/admin/download-roster-template')
    def download_roster_template():
        # Generates a simple CSV template for admins to download
        csv_content = "First Name,Last Name,Email,Register ID,Phone,Department,Course,Branch,Year of Study\nJohn,Doe,john.doe@example.com,24UG001,9876543210,School of Engineering,B.Tech,CS&AI,1"
        
        return Response(
            csv_content,
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=event_roster_template.csv"}
        )
