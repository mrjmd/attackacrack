from app import create_app
from extensions import db
from flask_migrate import upgrade
from logging_config import get_logger

logger = get_logger(__name__)

def run_reset():
    """
    Drops all database tables and recreates them based on the
    latest migration script. This is for a clean start.
    """
    logger.info("Starting Database Reset")
    
    app = create_app()
    
    with app.app_context():
        logger.info("Dropping all database tables...")
        # The session.close() and drop_all() ensure all connections are closed
        # before we try to drop the tables, avoiding hangs.
        db.session.close()
        db.drop_all()
        logger.info("Tables dropped.")

        logger.info("Recreating all tables from migration history...")
        # The 'head' argument tells migrate to apply all migrations up to the latest one.
        upgrade()
        logger.info("Tables recreated successfully.")
        
    logger.info("Database Reset Complete")

if __name__ == '__main__':
    # A simple confirmation step to prevent accidental data loss.
    confirm = input("Are you sure you want to completely wipe all data and reset the database? (yes/no): ")
    if confirm.lower() == 'yes':
        run_reset()
    else:
        logger.info("Reset cancelled.")
