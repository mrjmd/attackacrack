from app import create_app
from crm_database import db
import sqlalchemy

app = create_app()
with app.app_context():
    inspector = sqlalchemy.inspect(db.engine)
    tables = inspector.get_table_names()
    print('campaign_templates:', 'campaign_templates' in tables)
    print('ab_test_results:', 'ab_test_results' in tables)
    print('\nAll tables:', sorted(tables))
