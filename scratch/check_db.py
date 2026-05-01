from app import app
from models import db
from sqlalchemy import text

def check_db():
    with app.app_context():
        print("--- Tables ---")
        result = db.session.execute(text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'")).fetchall()
        for r in result:
            print(r[0])
        
        print("\n--- Views ---")
        result = db.session.execute(text("SELECT viewname FROM pg_catalog.pg_views WHERE schemaname = 'public'")).fetchall()
        for r in result:
            print(r[0])

if __name__ == '__main__':
    check_db()
