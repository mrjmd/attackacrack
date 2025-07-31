from app import create_app
from extensions import db
from flask_migrate import upgrade

def run_reset():
    """
    Drops all database tables and recreates them based on the
    latest migration script. This is for a clean start.
    """
    print("--- Starting Database Reset ---")
    
    app = create_app()
    
    with app.app_context():
        print("Dropping all database tables...")
        # The session.close() and drop_all() ensure all connections are closed
        # before we try to drop the tables, avoiding hangs.
        db.session.close()
        db.drop_all()
        print("-> Tables dropped.")

        print("Recreating all tables from migration history...")
        # The 'head' argument tells migrate to apply all migrations up to the latest one.
        upgrade()
        print("-> Tables recreated successfully.")
        
    print("\n--- Database Reset Complete ---")

if __name__ == '__main__':
    # A simple confirmation step to prevent accidental data loss.
    confirm = input("Are you sure you want to completely wipe all data and reset the database? (yes/no): ")
    if confirm.lower() == 'yes':
        run_reset()
    else:
        print("Reset cancelled.")
