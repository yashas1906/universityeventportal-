from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import quoted_name

db = SQLAlchemy()

class School(db.Model):
    __tablename__ = 'schools'
    school_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)

class Admin(db.Model):
    __tablename__ = 'admins'
    admin_id = db.Column(db.Integer, primary_key=True)
    admin_email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False) 
    school_id = db.Column(db.Integer, db.ForeignKey('schools.school_id', ondelete='CASCADE'), nullable=True)

class Event(db.Model):
    __tablename__ = 'events'
    event_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50))
    event_date = db.Column(db.DateTime)
    venue = db.Column(db.String(150))
    description = db.Column(db.Text)
    incharge_club = db.Column(db.String(150))
    image_url = db.Column(db.String(500), nullable=True)
    organizing_school_id = db.Column(db.Integer, db.ForeignKey('schools.school_id', ondelete='SET NULL'), nullable=True)
    
    # Parent-Child Relationship (For Flagship Sub-events)
    parent_event_id = db.Column(db.Integer, db.ForeignKey('events.event_id', ondelete='CASCADE'), nullable=True)
    sub_events = db.relationship('Event', backref=db.backref('parent_event', remote_side=[event_id]), cascade="all, delete-orphan")

class Participant(db.Model):
    __tablename__ = 'participants'
    participant_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    phone_number = db.Column(db.String(20))
    is_internal = db.Column(db.Boolean, default=True)
    roll_number = db.Column(db.String(50), unique=True, nullable=True)
    
    # Academic Details
    department = db.Column(db.String(100)) # Academic School
    course = db.Column(db.String(100))     # Course (e.g., B.Tech)
    branch = db.Column(db.String(100))     # Branch (e.g., CS&AI)
    year_of_study = db.Column(db.String(20))
    password_hash = db.Column(db.String(255), nullable=True) # For student login

class EventRegistration(db.Model):
    __tablename__ = 'event_registrations'
    registration_id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.event_id', ondelete='CASCADE'))
    participant_id = db.Column(db.Integer, db.ForeignKey('participants.participant_id', ondelete='CASCADE'))
    team_name = db.Column(db.String(150))
    rank_position = db.Column(db.Integer)
    award_details = db.Column(db.String(255))
    points_awarded = db.Column(db.Integer, default=0)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

    event = db.relationship('Event', backref='registrations')
    participant = db.relationship('Participant', backref='registrations')

# --- SUPABASE ANALYTICS VIEWS ---
class ViewOjasLeaderboard(db.Model):
    __tablename__ = quoted_name('ViewOjasLeaderboard', True)  # Preserves PascalCase for Supabase
    school_id    = db.Column(db.Integer, primary_key=True)
    school_name  = db.Column(db.String)
    total_points = db.Column(db.Integer)

class ViewMonthlyTrend(db.Model):
    __tablename__ = 'view_monthly_trend'
    month_num = db.Column(db.Integer, primary_key=True)
    month_name = db.Column(db.String)
    event_count = db.Column(db.Integer)

class ViewCategoryDist(db.Model):
    __tablename__ = 'view_category_dist'
    category = db.Column(db.String, primary_key=True)
    event_count = db.Column(db.Integer)