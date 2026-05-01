from datetime import datetime, timezone, timedelta
from flask import request, render_template, redirect, url_for, jsonify
from sqlalchemy import or_, func, distinct, text, case
from models import db, Event, EventRegistration, Participant, School, ViewOjasLeaderboard, ViewMonthlyTrend, ViewCategoryDist

# Define Indian Standard Time (UTC + 5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def init_analytics_routes(app):
    @app.route('/university')
    def university_events():
        now = datetime.now(timezone.utc)
        upcoming_events = Event.query.filter(Event.organizing_school_id == None, Event.event_date >= now).order_by(Event.event_date.asc()).all()
        past_events = Event.query.filter(Event.organizing_school_id == None, Event.event_date < now).order_by(Event.event_date.desc()).all()

        ojas_event = db.session.get(Event, 1)
        ojas_sub_events_count = Event.query.filter_by(parent_event_id=1).count()
        ojas_participants_count = db.session.query(func.count(distinct(EventRegistration.participant_id))).join(Event, EventRegistration.event_id == Event.event_id).join(Participant, EventRegistration.participant_id == Participant.participant_id).filter((Event.parent_event_id == 1) | (Event.event_id == 1), Participant.roll_number != None, ~Participant.email.ilike('%admin%'), ~Participant.email.ilike('%test%')).scalar()
        leaderboard = db.session.execute(text('SELECT school_id, school_name, COALESCE(total_points, 0) AS total_points FROM "ViewOjasLeaderboard" ORDER BY total_points DESC')).fetchall()
        ojas_winner = leaderboard[0].school_name if leaderboard else "TBD"
        ojas_sub_events = Event.query.filter_by(parent_event_id=1).all()
        ojas_details = []
        for sub in ojas_sub_events:
            winner_reg = EventRegistration.query.filter_by(event_id=sub.event_id, rank_position=1).first()
            winner_name = "TBA"
            if winner_reg:
                participant = db.session.get(Participant, winner_reg.participant_id)
                if participant: winner_name = participant.name
            org_school = "Central University"
            if sub.organizing_school_id:
                school_record = db.session.get(School, sub.organizing_school_id)
                if school_record: org_school = school_record.name
            ojas_details.append({'title': sub.title, 'date': sub.event_date.strftime('%b %d, %Y') if sub.event_date else 'TBA', 'organizing_school': org_school, 'winner': winner_name})
        return render_template('university_events.html', upcoming_events=upcoming_events, past_events=past_events, leaderboard=leaderboard, ojas_event=ojas_event, ojas_sub_events_count=ojas_sub_events_count, ojas_participants_count=ojas_participants_count, ojas_winner=ojas_winner, ojas_details=ojas_details)

    @app.route('/edit_event/<int:event_id>', methods=['GET', 'POST'])
    def edit_event(event_id):
        event_to_edit = Event.query.get_or_404(event_id)
        if request.method == 'POST':
            try:
                data = request.form
                event_to_edit.title = data.get('event_name') or data.get('title') or event_to_edit.title
                event_to_edit.category = data.get('category') or event_to_edit.category
                event_to_edit.venue = data.get('venue') or event_to_edit.venue
                event_to_edit.incharge_club = data.get('organizer') or data.get('incharge_club') or event_to_edit.incharge_club
                event_to_edit.description = data.get('description') or event_to_edit.description
                if data.get('organizing_school_id'): event_to_edit.organizing_school_id = int(data.get('organizing_school_id'))
                if data.get('parent_event_id') and str(data.get('parent_event_id')).strip() != "": event_to_edit.parent_event_id = int(data.get('parent_event_id'))
                else: event_to_edit.parent_event_id = None
                date_str = data.get('event_date')
                if date_str:
                    try: event_to_edit.event_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
                    except: pass
                db.session.commit()
                return redirect(url_for('university_events'))
            except Exception as e:
                db.session.rollback()
                return redirect(url_for('university_events'))
        schools = School.query.all()
        return render_template('edit_event.html', event=event_to_edit, schools=schools)

    @app.route('/school')
    def school_events():
        school_id = request.args.get('school_id')
        schools = School.query.all()
        now = datetime.now(timezone.utc)
        if school_id:
            selected_school = db.session.get(School, school_id)
            upcoming_events = Event.query.filter(Event.organizing_school_id == school_id, Event.event_date >= now).order_by(Event.event_date.asc()).all()
            past_events = Event.query.filter(Event.organizing_school_id == school_id, Event.event_date < now).order_by(Event.event_date.desc()).all()
        else:
            selected_school = None
            upcoming_events = Event.query.filter(Event.organizing_school_id != None, Event.event_date >= now).order_by(Event.event_date.asc()).all()
            past_events = Event.query.filter(Event.organizing_school_id != None, Event.event_date < now).order_by(Event.event_date.desc()).all()
        return render_template('school_events.html', schools=schools, selected_school=selected_school, upcoming_events=upcoming_events, past_events=past_events, school_analytics={})

    # ═══ Student Heatmap API ═══
    @app.route('/api/student_heatmap')
    def api_student_heatmap():
        roll_number = request.args.get('roll_number', '').strip()
        if not roll_number:
            return jsonify({'error': 'Please enter a valid Roll Number.'})
        participant = Participant.query.filter(Participant.roll_number.ilike(f"%{roll_number}%")).first()
        if not participant:
            return jsonify({'error': f'Roll No "{roll_number}" not found.'})
        try:
            registrations = db.session.query(
                Event.title, Event.event_date, Event.category, EventRegistration.points_awarded
            ).join(EventRegistration).filter(
                EventRegistration.participant_id == participant.participant_id
            ).order_by(Event.event_date.desc()).all()

            from collections import Counter
            month_counts, category_counts, event_list = Counter(), Counter(), []
            for r in registrations:
                if r.event_date:
                    month_counts[r.event_date.strftime('%b %Y')] += 1
                if r.category:
                    category_counts[r.category] += 1
                event_list.append({
                    'title': r.title,
                    'date': r.event_date.strftime('%d %b, %Y') if r.event_date else 'TBA',
                    'category': r.category or 'General',
                    'points': r.points_awarded or 0
                })

            return jsonify({
                'success': True,
                'name': participant.name,
                'dept': participant.department or 'N/A',
                'heatmap_labels': list(month_counts.keys())[::-1],
                'heatmap_data': list(month_counts.values())[::-1],
                'radar_labels': list(category_counts.keys()),
                'radar_data': list(category_counts.values()),
                'events': event_list
            })
        except Exception:
            db.session.rollback()
            return jsonify({'error': 'Database synchronization error.'})

    # ═══ University Analytics ═══
    @app.route('/university/analytics')
    def university_analytics():
        selected_year = request.args.get('academic_year', '2025-26')
        def fetch_chart(view_name, l_col, v_col):
            try:
                rows = db.session.execute(text(f"SELECT * FROM {view_name} WHERE academic_year = :y"), {"y": selected_year}).fetchall()
                return [str(getattr(r, l_col)) for r in rows], [float(getattr(r, v_col) or 0) for r in rows]
            except:
                db.session.rollback()
                return [], []

        try:
            kpi_row = db.session.execute(text("SELECT * FROM view_university_macro_kpis")).fetchone()
        except:
            db.session.rollback()
            kpi_row = None

        # 🟢 CHANGED: h1 now represents University-wide Reach (Target Audience)
        try:
            h1_data = db.session.query(
                Participant.year_of_study,
                func.count(EventRegistration.registration_id).label('total_regs')
            ).join(EventRegistration, Participant.participant_id == EventRegistration.participant_id)\
             .join(Event, EventRegistration.event_id == Event.event_id)\
             .group_by(Participant.year_of_study).all()
            
            h1l = [f"{row[0]} Year" if row[0] else "Unknown" for row in h1_data]
            h1v = [int(row[1]) for row in h1_data]
        except Exception:
            db.session.rollback()
            h1l, h1v = [], []
        h2l, h2v = fetch_chart('view_impact_participation_rate', 'school_name', 'participation_rate')
        h3l, h3v = fetch_chart('view_horizon_monthly_trend', 'month_name', 'event_count')
        h4l, h4v = fetch_chart('view_horizon_venue_dist', 'venue', 'event_count')
        d1l, d1v = fetch_chart('view_dynamics_leaderboard', 'school_name', 'total_points')
        d2l, d2v = fetch_chart('view_dynamics_school_event_count', 'school_name', 'event_count')

        try:
            d3_data = db.session.execute(text('SELECT * FROM view_dynamics_top_clubs WHERE academic_year = :y LIMIT 10'), {"y": selected_year}).fetchall()
            d3_rows = [{'club': r.club_name, 'count': r.event_count} for r in d3_data]
        except:
            db.session.rollback()
            d3_rows = []

        try:
            d4_data = db.session.execute(text('SELECT * FROM view_dynamics_category_school WHERE academic_year = :y'), {"y": selected_year}).fetchall()
            d4s = sorted(list(set(r.school_name for r in d4_data)))
            d4c = sorted(list(set(r.category for r in d4_data)))
            d4m = {s: {c: 0 for c in d4c} for s in d4s}
            for r in d4_data: d4m[r.school_name][r.category] = r.event_count
            d4d = [{'label': c, 'data': [d4m[s][c] for s in d4s]} for c in d4c]
        except:
            db.session.rollback()
            d4s, d4d = [], []

        j1l, j1v = fetch_chart('view_journey_registration_growth', 'reg_month', 'cumulative_count')

        try:
            j2_data = db.session.execute(text('SELECT * FROM view_journey_participant_school WHERE academic_year = :y'), {"y": selected_year}).fetchall()
            j2l, j2i, j2e = [r.school_name for r in j2_data], [r.internal_count for r in j2_data], [r.external_count for r in j2_data]
        except:
            db.session.rollback()
            j2l, j2i, j2e = [], [], []

        # 🟢 NEW: University Participation Retention Funnel
        try:
            loyalty_sq = db.session.query(
                EventRegistration.participant_id,
                func.count(EventRegistration.registration_id).label('attendance_count')
            ).group_by(EventRegistration.participant_id).subquery()

            retention_data = db.session.query(
                loyalty_sq.c.attendance_count,
                func.count(loyalty_sq.c.participant_id)
            ).group_by(loyalty_sq.c.attendance_count).all()

            buckets = {"1 Event": 0, "2 Events": 0, "3-4 Events": 0, "5+ Events": 0}
            for count, p_count in retention_data:
                if count == 1: buckets["1 Event"] += p_count
                elif count == 2: buckets["2 Events"] += p_count
                elif 3 <= count <= 4: buckets["3-4 Events"] += p_count
                else: buckets["5+ Events"] += p_count

            j3l, j3v = list(buckets.keys()), list(buckets.values())
        except Exception:
            db.session.rollback()
            j3l, j3v = [], []
        j4l, j4v = fetch_chart('view_journey_top_participants', 'name', 'total_points')
        e1l, e1v = fetch_chart('view_ecosystem_diet', 'category', 'event_count')
        # 🟢 NEW: Student Demand Index (Consumption)
        try:
            demand_data = db.session.query(
                Event.category,
                func.count(EventRegistration.registration_id).label('total_regs')
            ).join(EventRegistration, Event.event_id == EventRegistration.event_id)\
             .filter(Event.category.isnot(None))\
             .group_by(Event.category)\
             .order_by(text('total_regs DESC')).all()

            e2l, e2v = [r[0] for r in demand_data], [int(r[1]) for r in demand_data]
        except Exception:
            db.session.rollback()
            e2l, e2v = [], []
        e3l, e3v = fetch_chart('view_ecosystem_award_dist', 'rank_position', 'award_count')
        e4l, e4v = fetch_chart('view_ecosystem_school_diversity', 'school_name', 'unique_categories')

        return render_template('university_analytics.html',
            total_events=kpi_row.total_events if kpi_row else 0,
            total_footfall=kpi_row.total_registrations if kpi_row else 0,
            total_schools=kpi_row.ojas_engagement_index if kpi_row else 0,
            h1_labels=h1l, h1_values=h1v, h2_labels=h2l, h2_values=h2v,
            h3_labels=h3l, h3_values=h3v, h4_labels=h4l, h4_values=h4v,
            d1_labels=d1l, d1_values=d1v, d2_labels=d2l, d2_values=d2v,
            d3_rows=d3_rows, d4_schools=d4s, d4_datasets=d4d,
            j1_labels=j1l, j1_values=j1v,
            j2_labels=j2l, j2_internal=j2i, j2_external=j2e,
            j3_labels=j3l, j3_values=j3v, j4_labels=j4l, j4_values=j4v,
            e1_labels=e1l, e1_values=e1v, e2_labels=e2l, e2_values=e2v,
            e3_labels=e3l, e3_values=e3v, e4_labels=e4l, e4_values=e4v
        )

    # ═══ School Analytics (4-Tab Dashboard) ═══
    @app.route('/school/analytics')
    def school_analytics():
        sid = request.args.get('school_id')
        y = request.args.get('academic_year', '2025-26')
        schools = School.query.all()
        y_map = {
            '2023-24': ("2023-06-01", "2024-05-31"),
            '2024-25': ("2024-06-01", "2025-05-31"),
            '2025-26': ("2025-06-01", "2026-05-31")
        }
        sd, ed = y_map.get(y, ("2025-06-01", "2026-05-31"))

        # 🟢 Global Filter: Only School Events (Exclude University-level)
        base_q = Event.query.filter(Event.organizing_school_id.isnot(None), Event.event_date >= sd, Event.event_date <= ed)
        
        # Benchmark (Average across all schools)
        total_sch_e = base_q.count()
        total_sch_r = EventRegistration.query.join(Event).filter(
            Event.organizing_school_id.isnot(None), Event.event_date >= sd, Event.event_date <= ed
        ).count()
        univ_avg = round(total_sch_r / total_sch_e, 1) if total_sch_e > 0 else 0

        if sid and sid != "all":
            sel_s = db.session.get(School, sid)
            q_e = base_q.filter(Event.organizing_school_id == sid)
            q_r = db.session.query(EventRegistration).join(Event).join(Participant).filter(
                Event.organizing_school_id == sid, Event.event_date >= sd, Event.event_date <= ed
            )
        else:
            sel_s = None
            q_e = base_q
            q_r = db.session.query(EventRegistration).join(Event).join(Participant).filter(
                Event.organizing_school_id.isnot(None), Event.event_date >= sd, Event.event_date <= ed
            )

        e_count = q_e.count()
        r_count = q_r.count()
        intensity = round(r_count / e_count, 1) if e_count > 0 else 0

        # Data fetching with strict school-only filters
        yos_l, yos_d, cat_l, cat_d, jL, jE, jR, bL, bD = [], [], [], [], [], [], [], [], []
        try:
            yos_raw = q_r.with_entities(Participant.year_of_study, func.count(EventRegistration.registration_id)).group_by(Participant.year_of_study).all()
            yos_l, yos_d = [f"{r[0]} Year" if r[0] else "Unknown" for r in yos_raw], [r[1] for r in yos_raw]
            
            cat_raw = q_e.with_entities(Event.category, func.count(Event.event_id)).filter(Event.category.isnot(None)).group_by(Event.category).all()
            cat_l, cat_d = [r[0] for r in cat_raw], [r[1] for r in cat_raw]

            # Department stats
            dept_raw = q_r.with_entities(Participant.department, func.count(EventRegistration.registration_id)).group_by(Participant.department).all()
            dept_l, dept_d = [r[0] if r[0] else "Other" for r in dept_raw], [r[1] for r in dept_raw]

            # Cumulative Growth Journey
            e_dict = {row.m.strftime('%Y-%m'): row.e for row in q_e.with_entities(func.date_trunc('month', Event.event_date).label('m'), func.count(Event.event_id).label('e')).group_by('m').all() if row.m}
            r_dict = {row.m.strftime('%Y-%m'): row.r for row in q_r.with_entities(func.date_trunc('month', Event.event_date).label('m'), func.count(EventRegistration.registration_id).label('r')).group_by('m').all() if row.m}
            all_m = sorted(list(set(list(e_dict.keys()) + list(r_dict.keys()))))
            ce, cr = 0, 0
            
            # 🟢 Force graph line if only one month exists
            if len(all_m) == 1:
                prev_month = (datetime.strptime(all_m[0], '%Y-%m') - timedelta(days=28)).strftime('%b %Y')
                jL.append(prev_month); jE.append(0); jR.append(0)

            for m in all_m:
                jL.append(datetime.strptime(m, '%Y-%m').strftime('%b %Y'))
                ce += e_dict.get(m, 0); cr += r_dict.get(m, 0)
                jE.append(ce); jR.append(cr)

            # Benchmark Logic
            bench_q = db.session.query(School.name, func.count(Event.event_id)).outerjoin(Event, (Event.organizing_school_id == School.school_id) & (Event.event_date >= sd) & (Event.event_date <= ed)).group_by(School.name).order_by(func.count(Event.event_id).desc()).all()
            bL, bD = [r[0] for r in bench_q], [r[1] for r in bench_q]
        except:
            db.session.rollback()

        # Top Students with Row-to-List conversion to prevent JSON error
        try:
            ts_raw = q_r.with_entities(Participant.name, Participant.roll_number, func.sum(EventRegistration.points_awarded).label('pts')).group_by(Participant.name, Participant.roll_number).order_by(text('pts DESC')).limit(10).all()
            top_students = [list(r) for r in ts_raw]
        except:
            db.session.rollback()
            top_students = []

        return render_template('school_analytics.html',
            schools=schools,
            selected_school=sel_s,
            selected_year=y,
            total_events=e_count,
            total_participants=r_count,
            intensity=intensity,
            univ_avg=univ_avg,
            top_students=top_students,
            cat_labels=cat_l,
            cat_data=cat_d,
            yos_labels=yos_l,
            yos_data=yos_d,
            dept_labels=dept_l,
            dept_data=dept_d,
            journey_labels=jL,
            journey_events=jE,
            journey_regs=jR,
            bench_labels=bL,
            bench_data=bD
        )