#!/bin/bash
# Test migrations on a fresh PostgreSQL database

echo "Testing migrations on fresh PostgreSQL database..."

# Set database URL for test database
export DATABASE_URL="postgresql://matt:dev_password@db:5432/test_migrations"

# Run migrations
echo "1. Running initial migration (c4c776fc75e9)..."
flask db upgrade c4c776fc75e9

# Check if user table exists
echo "2. Checking if user table was created..."
docker-compose exec db psql -U matt -d test_migrations -c "\d user" 2>&1 | grep -q "Table" && echo "   ✓ User table created" || echo "   ✗ User table not found"

echo "3. Running todos migration (5666d6960685)..."
flask db upgrade 5666d6960685

# Check if todos table exists
echo "4. Checking if todos table was created..."
docker-compose exec db psql -U matt -d test_migrations -c "\d todos" 2>&1 | grep -q "Table" && echo "   ✓ Todos table created" || echo "   ✗ Todos table not found"

echo "5. Running final migration (2792ed2d7978)..."
flask db upgrade 2792ed2d7978

echo "6. Checking final state..."
flask db current

echo "7. Listing all tables..."
docker-compose exec db psql -U matt -d test_migrations -c "\dt"

echo "Done! Test database will be kept for inspection."