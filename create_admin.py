from app import app
from models import db, Admin, School
from werkzeug.security import generate_password_hash

def setup_admin():
    with app.app_context():
        print("\n--- Create Admin Account ---")
        
        # Prompts updated to match the website UI exactly
        email = input("Admin ID (Email format, e.g. admin@gmail.com): ").strip()
        password = input("Master Password: ").strip()
        
        print("\nSelect Role:")
        print("1) school_admin")
        print("2) university_admin")
        print("3) university_head")
        role_choice = input("Enter 1, 2, or 3: ").strip()
        
        role_map = {'1': 'school_admin', '2': 'university_admin', '3': 'university_head'}
        role = role_map.get(role_choice, 'university_head')

        school_id = None
        if role == 'school_admin':
            schools = School.query.all()
            if not schools:
                print("\n⚠️ No schools found in the database. Please add schools via Supabase first.")
                return
            print("\nSelect School:")
            for s in schools:
                print(f"{s.school_id}) {s.name}")
            school_id = input("Enter School ID: ").strip()

        # Check if ID already exists
        existing = Admin.query.filter_by(admin_email=email).first()
        if existing:
            print("\n⚠️ An admin with this ID already exists!")
            return

        hashed_pw = generate_password_hash(password)
        new_admin = Admin(admin_email=email, password_hash=hashed_pw, role=role, school_id=school_id)
        
        db.session.add(new_admin)
        db.session.commit()
        print(f"\n✅ Success! Created {role} account for {email}")

if __name__ == "__main__":
    setup_admin()