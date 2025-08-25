# Password Hash Format Fix Documentation

## Issue Description

**Problem**: "ValueError: Invalid salt" error when trying to log in on local development environment.

**Root Cause**: Password hashes in the database were created with `scrypt` format (from Werkzeug's `generate_password_hash`), but the authentication service uses `flask_bcrypt` which expects bcrypt-formatted hashes.

## Symptoms

- Login fails with "Invalid email or password" even with correct credentials
- Error in logs: `ValueError: Invalid salt` from bcrypt
- Password hashes in database start with `scrypt:` instead of `$2b$` or `$2a$`

## Solution

### Quick Fix (Reset Admin Password)

```bash
# Reset the admin password to use bcrypt format
docker-compose exec web flask reset-admin --email admin@attackacrack.com --password 'admin123!'
```

### Check All Users

```bash
# List all users and their password hash formats
docker-compose exec web flask fix-passwords --list-users
```

### Fix All Users with Invalid Hashes

```bash
# Fix all users with non-bcrypt password hashes
docker-compose exec web flask fix-passwords

# Or fix a specific user
docker-compose exec web flask fix-passwords --email user@example.com --reset-password 'newpassword'
```

## Technical Details

### Password Hash Formats

- **Bcrypt** (correct): `$2b$12$...` or `$2a$12$...`
- **Scrypt** (incorrect): `scrypt:32768:8:1$...`
- **PBKDF2** (incorrect): `pbkdf2:sha256:...`

### The Fix Script

Located at `/scripts/fix_password_hashes.py`, this script provides:

1. **`flask fix-passwords`**: Fix password hashes for users
   - `--list-users`: Show all users and their hash formats
   - `--email`: Fix specific user
   - `--reset-password`: Set new password

2. **`flask reset-admin`**: Create or reset admin user
   - `--email`: Admin email (default: admin@attackacrack.com)
   - `--password`: New password
   - `--first-name`: First name
   - `--last-name`: Last name

### Why This Happened

The issue occurred because:
1. Initial database setup might have used Werkzeug's `generate_password_hash` 
2. The application was later updated to use `flask_bcrypt`
3. Existing password hashes were not migrated to the new format

### Prevention

- Always use `flask_bcrypt` for password hashing in this application
- When creating test users, use the auth service methods
- Regular password hash format checks in development

## Default Credentials (Local Development Only)

After running the fix:
- **Email**: admin@attackacrack.com
- **Password**: admin123!

**IMPORTANT**: Never use these credentials in production!

## Related Files

- `/services/auth_service_refactored.py` - Authentication service
- `/scripts/fix_password_hashes.py` - Password fix utility
- `/scripts/commands.py` - CLI command registration
- `/crm_database.py` - User model definition