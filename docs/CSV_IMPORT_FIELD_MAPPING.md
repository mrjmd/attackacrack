# CSV Import & Field Mapping System Documentation

## Table of Contents
1. [Current System Capabilities](#current-system-capabilities)
2. [How to Use CSV Import (Production Ready)](#how-to-use-csv-import-production-ready)
3. [Field Handling Details](#field-handling-details)
4. [Future Enhancement Plan](#future-enhancement-plan)
5. [Implementation Roadmap](#implementation-roadmap)

---

## Current System Capabilities

### ✅ Production-Ready Features

The CSV import system is **fully functional in production** with the following capabilities:

#### Core Features
- **Smart Contact Enrichment**: Updates existing contacts without overwriting data
- **Automatic Deduplication**: Uses phone number as unique identifier
- **Campaign List Creation**: Automatically creates targetable lists from imports
- **Comprehensive Error Handling**: Detailed feedback on success/failure
- **Import History Tracking**: Complete audit trail of all imports
- **Flexible Data Storage**: Stores ANY CSV columns via JSON metadata

#### Technical Specifications
- **Max File Size**: 16MB
- **Supported Format**: CSV with headers
- **Required Field**: `phone` (must be unique)
- **Processing**: Synchronous (blocks during upload)
- **Transaction Safety**: Full rollback on errors

### Available Interfaces

1. **Primary (Recommended)**: `/campaigns/import-csv`
   - Professional UI with examples
   - Automatic campaign list creation
   - Best error handling and feedback

2. **Alternative**: `/import_csv`
   - Simpler legacy interface
   - Basic functionality

3. **Management Dashboard**: `/settings/imports`
   - View import history
   - Access import statistics

---

## How to Use CSV Import (Production Ready)

### Step 1: Prepare Your CSV

#### Required Format
```csv
phone,first_name,last_name,email,company,title,address,city,state,zip,notes
+16175551234,John,Smith,john@example.com,ABC Corp,CEO,123 Main St,Boston,MA,02134,High priority lead
+16175551235,Jane,Doe,jane@example.com,XYZ Inc,CTO,456 Oak Ave,Cambridge,MA,02139,Interested in services
```

#### Field Requirements
- **Required**: `phone` (with country code, e.g., +1 for US)
- **Optional Standard Fields**: `first_name`, `last_name`, `email`
- **Optional Metadata Fields**: ANY additional columns (stored in JSON)

### Step 2: Upload via Web Interface

1. Navigate to `https://[your-domain]/campaigns/import-csv`
2. Click "Choose File" and select your CSV
3. Optionally provide a campaign list name
4. Click "Import Contacts"
5. Review the results summary

### Step 3: Verify Import Results

The system will display:
- Total rows processed
- Successful imports
- Failed imports (with reasons)
- Duplicates found (enriched existing contacts)
- New contacts created

---

## Field Handling Details

### Currently Mapped Fields

| CSV Column | Database Field | Type | Notes |
|------------|---------------|------|-------|
| phone | Contact.phone | String | Required, unique identifier |
| first_name | Contact.first_name | String | Direct mapping |
| last_name | Contact.last_name | String | Direct mapping |
| email | Contact.email | String | Direct mapping, validated |
| *any other* | Contact.contact_metadata | JSON | Stored as key-value pairs |

### How Metadata Storage Works

All non-standard fields are automatically captured:

```python
# Example: CSV has additional columns
company → stored as contact_metadata['company']
title → stored as contact_metadata['title']
address → stored as contact_metadata['address']
custom_field → stored as contact_metadata['custom_field']
```

### Enrichment Logic

When importing a contact that already exists (by phone number):

1. **Preserves existing data** - Never overwrites populated fields
2. **Fills missing data** - Only updates NULL/empty fields
3. **Merges metadata** - Combines new metadata with existing
4. **Tracks changes** - Records what was updated in each import

Example:
```python
# Existing contact
{
  "first_name": "John",
  "last_name": null,
  "email": "john@old.com",
  "metadata": {"source": "website"}
}

# CSV row
{
  "phone": "+16175551234",
  "first_name": "Johnny",  # Won't overwrite "John"
  "last_name": "Smith",    # Will fill empty field
  "email": "john@new.com", # Won't overwrite existing
  "company": "ABC Corp"     # Will add to metadata
}

# Result after import
{
  "first_name": "John",     # Preserved
  "last_name": "Smith",     # Added (was null)
  "email": "john@old.com",  # Preserved
  "metadata": {
    "source": "website",    # Preserved
    "company": "ABC Corp"   # Added
  }
}
```

---

## Future Enhancement Plan

### Phase 1: Field Detection & Mapping UI (Priority: High)

#### Objectives
- Auto-detect CSV column types
- Interactive field mapping interface
- Preview data before import
- Save mapping templates

#### Features to Implement

1. **CSV Field Analyzer**
   - Detect data types (phone, email, address, date, currency)
   - Suggest field mappings based on column names
   - Sample first 100 rows for preview

2. **Mapping Interface**
   ```
   CSV Column     →  Maps To                    Action
   ─────────────────────────────────────────────────────
   phone          →  Contact.phone              ✓ Required
   company_name   →  Contact.company_name       ✓ Map
   job_title      →  Contact.job_title          ✓ Map
   street_address →  Property.address           ✓ Create Property
   deal_value     →  Skip                       ✗ Ignore
   ```

3. **Data Preview**
   - Show first 10 rows as they'll appear
   - Highlight validation errors
   - Display relationship creation plans

### Phase 2: Enhanced Field Support (Priority: High)

#### New Direct Contact Fields
```python
# Add to Contact model
company_name = db.Column(db.String(200), nullable=True)
job_title = db.Column(db.String(100), nullable=True)
company_website = db.Column(db.String(200), nullable=True)
linkedin_url = db.Column(db.String(200), nullable=True)
source = db.Column(db.String(50), nullable=True)
industry = db.Column(db.String(100), nullable=True)
company_size = db.Column(db.String(50), nullable=True)
```

#### Field Validation Rules
- **Phone**: Format validation, country code detection
- **Email**: RFC-compliant validation
- **Address**: Standardization via geocoding API
- **URL**: Protocol validation and normalization
- **Date**: Multiple format parsing

### Phase 3: Relationship Management (Priority: Medium)

#### Automatic Record Creation

1. **Property Creation from Address Fields**
   ```python
   if 'address' in csv_row:
       property = Property.create_or_update(
           address=standardize_address(csv_row['address']),
           contact_id=contact.id,
           property_type=csv_row.get('property_type', 'residential')
       )
   ```

2. **Job Creation from Job Fields**
   ```python
   if 'job_description' in csv_row:
       job = Job.create(
           description=csv_row['job_description'],
           property_id=property.id,
           status=csv_row.get('job_status', 'pending')
       )
   ```

3. **Tag Extraction**
   ```python
   if 'tags' in csv_row:
       tags = parse_tags(csv_row['tags'])  # "urgent, commercial, repeat"
       contact.add_tags(tags)
   ```

### Phase 4: Intelligent Mapping (Priority: Medium)

#### Smart Field Detection

Map common variations automatically:

| CSV Headers | Auto-Maps To |
|------------|--------------|
| "Company", "Company Name", "Business", "Organization" | company_name |
| "Title", "Job Title", "Position", "Role" | job_title |
| "Address", "Street", "Location", "Address Line 1" | property.address |
| "Cell", "Mobile", "Phone Number", "Tel" | phone |

#### Mapping Templates

```python
class CSVMappingTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))  # "QuickBooks Export", "Marketing List"
    mappings = db.Column(db.JSON)     # Field mapping configuration
    transformations = db.Column(db.JSON)  # Data transformation rules
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_default = db.Column(db.Boolean, default=False)
```

### Phase 5: Enterprise Features (Priority: Low)

#### Advanced Capabilities

1. **Conflict Resolution Strategies**
   - "Always keep existing"
   - "Always use new"
   - "Use newer by date"
   - "Manual review queue"

2. **Duplicate Detection Strategies**
   - Phone number (current)
   - Email address
   - Name + address combination
   - Fuzzy matching with similarity threshold

3. **Background Processing**
   ```python
   @celery.task
   def process_csv_import(file_path, mapping_config, user_id):
       # Process in background
       # Send progress updates via WebSocket
       # Email completion notification
   ```

4. **Import Analytics Dashboard**
   - Success/failure rates by import
   - Data quality metrics
   - Duplicate detection patterns
   - Field coverage analysis

---

## Implementation Roadmap

### Quick Wins (1-2 Days Each)

1. **Add Company/Title Fields**
   - Add database columns
   - Update import logic
   - Display in contact views

2. **CSV Template Download**
   - Provide example CSV
   - Include all supported fields
   - Add import instructions

3. **Better Error Messages**
   - Line-by-line error details
   - Suggested fixes
   - Partial import option

### Medium Projects (3-5 Days Each)

1. **Field Mapping UI**
   - Drag-and-drop interface
   - Column type detection
   - Mapping preview

2. **Property/Job Creation**
   - Parse address fields
   - Create related records
   - Handle duplicates

3. **Background Processing**
   - Celery task for imports
   - Progress tracking
   - Email notifications

### Large Projects (1-2 Weeks Each)

1. **Complete Mapping System**
   - Full UI/UX redesign
   - Template management
   - Transformation rules

2. **Advanced Duplicate Detection**
   - Multiple strategies
   - Fuzzy matching
   - Manual review queue

3. **Import Analytics Platform**
   - Comprehensive dashboard
   - Data quality metrics
   - Historical analysis

---

## Database Schema for Enhanced System

### New Tables Required

```sql
-- Mapping Templates
CREATE TABLE csv_mapping_template (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    mappings JSONB NOT NULL,
    transformations JSONB,
    validation_rules JSONB,
    created_by INTEGER REFERENCES user(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_default BOOLEAN DEFAULT FALSE,
    is_public BOOLEAN DEFAULT FALSE
);

-- Import Sessions with Enhanced Tracking
CREATE TABLE import_session (
    id SERIAL PRIMARY KEY,
    file_name VARCHAR(255),
    file_size INTEGER,
    total_rows INTEGER,
    processed_rows INTEGER DEFAULT 0,
    successful_rows INTEGER DEFAULT 0,
    failed_rows INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',
    mapping_template_id INTEGER REFERENCES csv_mapping_template(id),
    error_log JSONB,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_by INTEGER REFERENCES user(id)
);

-- Field Mapping History
CREATE TABLE field_mapping_history (
    id SERIAL PRIMARY KEY,
    import_session_id INTEGER REFERENCES import_session(id),
    csv_column VARCHAR(100),
    mapped_to VARCHAR(100),
    transformation_applied VARCHAR(100),
    sample_values JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Contact Model Enhancements

```python
class Contact(db.Model):
    # Existing fields...
    
    # New standard fields for common business data
    company_name = db.Column(db.String(200), nullable=True, index=True)
    job_title = db.Column(db.String(100), nullable=True)
    department = db.Column(db.String(100), nullable=True)
    company_website = db.Column(db.String(200), nullable=True)
    linkedin_url = db.Column(db.String(200), nullable=True)
    twitter_handle = db.Column(db.String(50), nullable=True)
    
    # Enhanced tracking
    source = db.Column(db.String(50), nullable=True)  # 'csv', 'api', 'manual', 'web_form'
    source_details = db.Column(db.JSON, nullable=True)  # Additional source metadata
    data_quality_score = db.Column(db.Float, nullable=True)  # 0-100 score
    last_enriched_at = db.Column(db.DateTime, nullable=True)
    
    # Relationship improvements
    primary_property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=True)
    
    # Indexes for performance
    __table_args__ = (
        db.Index('idx_company_name', 'company_name'),
        db.Index('idx_source', 'source'),
        db.Index('idx_imported_at', 'imported_at'),
    )
```

---

## API Documentation for Future Development

### Import Endpoint (Future)

```python
POST /api/v1/import/csv
Content-Type: multipart/form-data

Parameters:
- file: CSV file (required)
- mapping_template_id: ID of saved mapping template (optional)
- create_campaign_list: boolean (optional, default: true)
- background: boolean (optional, default: false for <1000 rows)
- validation_mode: 'strict' | 'lenient' | 'none' (optional, default: 'lenient')

Response:
{
    "import_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "processing",
    "preview": {
        "total_rows": 5000,
        "sample_data": [...],
        "detected_mappings": {...},
        "validation_errors": [...]
    },
    "websocket_channel": "import_550e8400"  // For real-time updates
}
```

### Mapping Template Endpoint (Future)

```python
POST /api/v1/import/mapping-templates
Content-Type: application/json

{
    "name": "QuickBooks Customer Export",
    "mappings": {
        "Customer": "company_name",
        "Primary Contact": "first_name",
        "Email": "email",
        "Phone": "phone",
        "Billing Address": "property.address"
    },
    "transformations": {
        "Phone": "normalize_phone_number",
        "Billing Address": "parse_address"
    },
    "validation_rules": {
        "Email": "email_validator",
        "Phone": "phone_validator"
    }
}
```

---

## Testing the Current System

### Test Data Set

Create a test CSV with various scenarios:

```csv
phone,first_name,last_name,email,company,title,address,notes,custom_field_1,custom_field_2
+16175551234,John,Smith,john@example.com,ABC Corp,CEO,123 Main St,Existing customer,Value1,Value2
+16175551235,Jane,,jane@example.com,XYZ Inc,CTO,456 Oak Ave,New lead,,Value3
+16175551234,Johnny,Smith,john@newcompany.com,DEF Corp,President,789 Elm St,Updated info,Value4,Value5
,Invalid,Row,invalid@example.com,No Phone Inc,Manager,321 Pine St,Should fail,,
+16175551236,,,nophone@example.com,,,,,Minimal data,Value6
```

### Expected Results

1. **Row 1**: Creates new contact with all fields
2. **Row 2**: Creates new contact, last_name is empty
3. **Row 3**: Enriches existing contact (same phone as Row 1)
4. **Row 4**: Fails - missing required phone field
5. **Row 5**: Creates minimal contact with metadata

### Validation Checklist

- [ ] File uploads successfully
- [ ] Progress indicator shows (if implemented)
- [ ] Success/failure counts are accurate
- [ ] Existing contacts are enriched, not duplicated
- [ ] Metadata fields are stored in contact_metadata
- [ ] Campaign list is created with correct members
- [ ] Error messages are clear and actionable
- [ ] Import history is recorded

---

## Security Considerations

### Current Security Measures

1. **File Validation**
   - File size limits (16MB)
   - CSV format validation
   - Secure filename sanitization

2. **Data Protection**
   - SQL injection prevention via SQLAlchemy
   - XSS protection in templates
   - CSRF tokens on forms

3. **Access Control**
   - Login required for imports
   - User tracking on all imports
   - Audit trail maintained

### Future Security Enhancements

1. **Enhanced Validation**
   - Virus scanning for uploads
   - Content-type verification
   - Malicious CSV detection

2. **Rate Limiting**
   - Limit imports per user per hour
   - Prevent DoS via large files

3. **Data Privacy**
   - PII detection and masking
   - GDPR compliance features
   - Data retention policies

---

## Performance Optimization

### Current Performance

- **Small Files (<1000 rows)**: 2-5 seconds
- **Medium Files (1000-5000 rows)**: 10-30 seconds
- **Large Files (5000-10000 rows)**: 30-60 seconds
- **Maximum**: ~10,000 rows before timeout risk

### Optimization Strategies

1. **Batch Processing**
   ```python
   # Current: One-by-one
   for row in csv:
       process_row(row)
       db.session.commit()
   
   # Optimized: Batch commits
   batch = []
   for row in csv:
       batch.append(process_row(row))
       if len(batch) >= 100:
           db.session.bulk_insert_mappings(Contact, batch)
           db.session.commit()
           batch = []
   ```

2. **Background Processing**
   - Move large imports to Celery
   - Provide real-time progress updates
   - Allow concurrent imports

3. **Database Optimization**
   - Add indexes on phone, email
   - Use upsert for deduplication
   - Optimize metadata queries

---

## Monitoring & Maintenance

### Key Metrics to Track

1. **Import Success Rate**
   - Successful rows / Total rows
   - Target: >95%

2. **Processing Speed**
   - Rows per second
   - Target: >100 rows/second

3. **Data Quality**
   - Fields filled percentage
   - Invalid data percentage
   - Duplicate rate

4. **System Health**
   - Memory usage during imports
   - Database connection pool
   - Disk space for temp files

### Maintenance Tasks

- **Daily**: Review failed imports
- **Weekly**: Clean up temp files
- **Monthly**: Analyze import patterns
- **Quarterly**: Review and optimize mapping templates

---

## Troubleshooting Guide

### Common Issues and Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Import times out | File too large | Use smaller batches or implement background processing |
| Duplicates created | Phone format varies | Normalize phone numbers before import |
| Missing data | Incorrect column names | Check CSV headers match expected format |
| Import fails silently | Server error | Check application logs for stack trace |
| Metadata not saved | JSON parsing error | Validate special characters in CSV |

### Debug Mode

Enable detailed logging for troubleshooting:

```python
# In config.py
IMPORT_DEBUG = True
IMPORT_LOG_LEVEL = 'DEBUG'

# In import service
if app.config.get('IMPORT_DEBUG'):
    logger.debug(f"Processing row: {row}")
    logger.debug(f"Extracted metadata: {metadata}")
```

---

## Conclusion

The current CSV import system is **production-ready** and handles the core requirements well. The enhancement plan provides a clear path to building an enterprise-grade field mapping system that can handle complex business relationships and data transformations.

### Immediate Actions Available

1. Use `/campaigns/import-csv` for production imports
2. Prepare CSVs with phone numbers and any additional fields
3. Monitor import results and gather user feedback

### Recommended Next Steps

1. Test current system with production data
2. Document specific field requirements from users
3. Implement Phase 1 (Field Detection & Mapping UI)
4. Add company_name and job_title as direct fields
5. Build Property creation from address fields

---

*Document created: January 2025*  
*Last updated: Current*  
*Status: Current system production-ready, enhancement plan documented*