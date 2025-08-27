# Comprehensive CSV Import System Implementation Plan

## Executive Summary

The current CSV import system has critical flaws in statistics tracking, duplicate detection, and data persistence. This plan outlines a complete overhaul to create a robust, enterprise-grade import system with accurate tracking, configurable duplicate handling, and comprehensive reporting.

## Current State Analysis

### Critical Issues Identified

1. **Broken Statistics**
   - Current system counts CSV data extraction, not actual database operations
   - Shows "1788 imported, 1729 updated" but `contacts_updated` is never incremented in code
   - No distinction between contacts and properties in statistics
   - Statistics don't reflect actual database state

2. **Progress Bar Issues**
   - Numerator counts contacts (2 per row possible) while denominator counts rows
   - Results in progress exceeding 100% (e.g., 2500/2000 = 125%)
   - No meaningful progress indication for users

3. **Data Persistence Failure**
   - Campaign list associations created but not committed to database
   - Lists show 0 contacts despite "successful" import
   - Transaction scope issues with list member creation

4. **No Duplicate Detection**
   - Same CSV imported multiple times creates duplicates
   - No option to skip or merge existing records
   - No tracking of what was actually created vs updated

## Requirements Specification

### Functional Requirements

#### 1. Statistics Tracking
Track separately for contacts AND properties:
- **New**: Records created for first time
- **Updated**: Existing records modified
- **Skipped**: Existing records unchanged (based on strategy)
- **Failed**: Records that couldn't be processed

#### 2. Duplicate Handling Strategies
User-selectable before import:
- **Skip Mode**: Don't modify existing records
- **Replace Mode**: Overwrite all fields with new data
- **Merge Mode**: Only update empty/null fields

#### 3. Progress Tracking
During import:
- Simple progress bar (0-100% based on rows, not entities)
- Current row indicator (e.g., "Processing row 567 of 2181")

Post-import:
- Complete statistics breakdown
- Error log with row numbers
- Processing time and speed

#### 4. Expected Behavior
- First import: All records marked as "new"
- Second import (Skip mode): All marked as "skipped"
- Second import (Replace mode): All marked as "updated"
- Second import (Merge mode): Mix of "updated" and "skipped"

### Non-Functional Requirements

1. **Performance**: Process 10,000+ rows in under 5 minutes
2. **Memory**: Stay under 500MB for large files
3. **Reliability**: Continue processing despite individual row errors
4. **Usability**: Clear feedback at every stage

## Technical Design

### Data Model Changes

#### Enhanced CSVImport Table
```sql
ALTER TABLE csv_import ADD COLUMN contacts_new INTEGER DEFAULT 0;
ALTER TABLE csv_import ADD COLUMN contacts_updated INTEGER DEFAULT 0;
ALTER TABLE csv_import ADD COLUMN contacts_skipped INTEGER DEFAULT 0;
ALTER TABLE csv_import ADD COLUMN contacts_failed INTEGER DEFAULT 0;

ALTER TABLE csv_import ADD COLUMN properties_new INTEGER DEFAULT 0;
ALTER TABLE csv_import ADD COLUMN properties_updated INTEGER DEFAULT 0;
ALTER TABLE csv_import ADD COLUMN properties_skipped INTEGER DEFAULT 0;
ALTER TABLE csv_import ADD COLUMN properties_failed INTEGER DEFAULT 0;

ALTER TABLE csv_import ADD COLUMN duplicate_strategy VARCHAR(20) DEFAULT 'skip';
ALTER TABLE csv_import ADD COLUMN processing_time_seconds FLOAT;
ALTER TABLE csv_import ADD COLUMN error_log JSON;
ALTER TABLE csv_import ADD COLUMN campaign_list_id INTEGER REFERENCES campaign_list(id);
```

### Service Layer Design

#### Core Algorithm Changes

1. **Fix Statistics Tracking**
```python
def _process_contact(self, contact_data, strategy='skip'):
    existing = self.contact_repository.find_by_phone(contact_data['phone'])
    
    if not existing:
        contact = self.contact_repository.create(**contact_data)
        return contact, 'new'
    
    if strategy == 'skip':
        return existing, 'skipped'
    elif strategy == 'replace':
        # Update all fields
        for key, value in contact_data.items():
            setattr(existing, key, value)
        self.contact_repository.update(existing)
        return existing, 'updated'
    elif strategy == 'merge':
        # Only update empty fields
        changed = False
        for key, value in contact_data.items():
            if value and not getattr(existing, key):
                setattr(existing, key, value)
                changed = True
        if changed:
            self.contact_repository.update(existing)
            return existing, 'updated'
        return existing, 'skipped'
```

2. **Fix Progress Calculation**
```python
def import_csv(self, csv_content, filename, imported_by, list_name=None, 
               duplicate_strategy='skip', progress_callback=None):
    rows = list(csv.DictReader(io.StringIO(csv_content)))
    total_rows = len(rows)
    
    for row_num, row in enumerate(rows, 1):
        # Process row...
        
        # Correct progress calculation
        if progress_callback:
            progress_callback(row_num, total_rows)
```

3. **Fix List Association Persistence**
```python
def _add_contacts_to_list(self, contact_ids, list_id):
    """Add contacts to campaign list with proper commit"""
    for contact_id in contact_ids:
        existing = self.campaign_list_member_repository.find_by_list_and_contact(
            list_id, contact_id
        )
        if not existing:
            self.campaign_list_member_repository.create(
                list_id=list_id,
                contact_id=contact_id,
                status='active'
            )
    
    # CRITICAL: Commit list associations
    self.session.commit()
```

### UI Components

#### Import Configuration
```html
<div class="import-config">
    <h3>Configure Import</h3>
    
    <div class="form-group">
        <label>Duplicate Handling:</label>
        <select name="duplicate_strategy">
            <option value="skip">Skip existing records</option>
            <option value="replace">Replace existing records</option>
            <option value="merge">Merge (only add missing data)</option>
        </select>
    </div>
    
    <div class="form-group">
        <label>Campaign List Name (optional):</label>
        <input type="text" name="list_name" />
    </div>
    
    <button onclick="startImport()">Start Import</button>
</div>
```

#### Progress Display
```html
<div class="import-progress">
    <div class="progress-bar">
        <div class="progress-fill" style="width: 0%"></div>
    </div>
    <p class="status">Processing row 0 of 0</p>
</div>
```

#### Completion Report
```html
<div class="import-complete">
    <h3>Import Complete</h3>
    
    <table class="statistics">
        <tr>
            <th></th>
            <th>New</th>
            <th>Updated</th>
            <th>Skipped</th>
            <th>Failed</th>
        </tr>
        <tr>
            <td>Contacts</td>
            <td>{{ stats.contacts_new }}</td>
            <td>{{ stats.contacts_updated }}</td>
            <td>{{ stats.contacts_skipped }}</td>
            <td>{{ stats.contacts_failed }}</td>
        </tr>
        <tr>
            <td>Properties</td>
            <td>{{ stats.properties_new }}</td>
            <td>{{ stats.properties_updated }}</td>
            <td>{{ stats.properties_skipped }}</td>
            <td>{{ stats.properties_failed }}</td>
        </tr>
    </table>
    
    {% if errors %}
    <div class="errors">
        <h4>Errors ({{ errors|length }})</h4>
        <ul>
        {% for error in errors[:10] %}
            <li>Row {{ error.row }}: {{ error.message }}</li>
        {% endfor %}
        </ul>
    </div>
    {% endif %}
</div>
```

## Implementation Plan

### Phase 1: Core Fixes (Priority 1)
**Timeline: 2 days**

#### Day 1: TDD Tests
1. Write tests for statistics tracking
2. Write tests for duplicate strategies
3. Write tests for progress calculation
4. Write tests for list persistence

#### Day 2: Implementation
1. Fix `_process_contact` to return operation type
2. Fix `_process_property` to return operation type
3. Fix progress callback calculation
4. Add commit after list associations
5. Update statistics collection logic

### Phase 2: Database & Model Updates
**Timeline: 1 day**

1. Create migration for new CSVImport fields
2. Run migration on development
3. Update CSVImport model
4. Update repositories

### Phase 3: Service Enhancements
**Timeline: 2 days**

1. Implement duplicate strategies
2. Add error logging
3. Create progress tracking
4. Add transaction management

### Phase 4: UI Implementation
**Timeline: 2 days**

1. Create import configuration modal
2. Build progress display
3. Implement completion report
4. Add list view statistics

### Phase 5: Testing & Validation
**Timeline: 1 day**

1. Test with `/app/csvs/test-large.csv` (2181 rows)
2. Verify all statistics accurate
3. Test duplicate scenarios
4. Performance testing
5. Create campaign with imported list

## Test Strategy

### Unit Tests
```python
def test_first_import_all_new():
    """First import should mark all as new"""
    
def test_second_import_skip_all_skipped():
    """Second import with skip should mark all as skipped"""
    
def test_second_import_replace_all_updated():
    """Second import with replace should mark all as updated"""
    
def test_merge_only_updates_empty_fields():
    """Merge should only update null/empty fields"""
    
def test_progress_never_exceeds_100():
    """Progress should stay within 0-100%"""
    
def test_list_associations_persist():
    """List members should be in database after import"""
```

### Integration Tests
```python
def test_full_import_workflow():
    """Test complete import → list → campaign creation"""
    
def test_concurrent_imports():
    """Test multiple simultaneous imports"""
    
def test_large_file_performance():
    """Test with 10,000+ row file"""
```

## Acceptance Criteria

### Must Have
- [ ] Statistics accurately reflect database operations
- [ ] Progress bar never exceeds 100%
- [ ] List associations persist to database
- [ ] Duplicate strategies work correctly
- [ ] All tests pass with 0 skips

### Should Have
- [ ] Error log with row numbers
- [ ] Processing time displayed
- [ ] Ability to download error report
- [ ] Cancel import functionality

### Nice to Have
- [ ] Real-time statistics during import
- [ ] Preview before import
- [ ] Undo last import

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Data loss | High | Low | Transaction rollback, backups |
| Performance degradation | Medium | Medium | Batch processing, indexes |
| Memory overflow | High | Low | Streaming, batch limits |
| Concurrent import conflicts | Medium | Medium | Lock mechanisms, queuing |

## Success Metrics

1. **Accuracy**: 100% correlation between stats and database state
2. **Performance**: < 30 seconds for 2181 rows
3. **Reliability**: < 0.1% failure rate
4. **Usability**: < 3 clicks to complete import

## Rollback Plan

If issues occur:
1. Revert code changes
2. Restore database from backup
3. Clear Redis cache
4. Notify affected users

## Documentation Requirements

1. Update API documentation
2. Create user guide for duplicate strategies
3. Document error codes and meanings
4. Add inline code comments

## Timeline Summary

- **Week 1**: Core fixes + Database updates (Phases 1-2)
- **Week 2**: Service enhancements + UI (Phases 3-4)
- **Week 3**: Testing + Deployment (Phase 5)

Total: 8-10 working days

## Appendix A: Current vs Proposed Flow

### Current Flow
1. CSV uploaded
2. Rows processed, contacts counted from CSV
3. Statistics show CSV extraction counts
4. List associations created but not committed
5. Result: Inaccurate stats, empty lists

### Proposed Flow
1. CSV uploaded with strategy selection
2. Rows processed, operations tracked from database
3. Statistics reflect actual create/update/skip operations
4. List associations committed properly
5. Result: Accurate stats, populated lists

## Appendix B: Sample Test CSV Structure

File: `/app/csvs/test-large.csv`
- Rows: 2181 (1 header + 2180 data)
- Expected contacts: ~4000 (primary + secondary)
- Expected properties: 2180
- Headers: Type, Address, City, ZIP, Owner, Phone fields...

## Next Steps

1. Review and approve plan
2. Set up tracking for implementation
3. Begin Phase 1: TDD test creation
4. Daily progress updates
5. Deploy to staging after Phase 5

---

*Document Version: 1.0*
*Created: August 27, 2025*
*Author: Attack-a-Crack CRM Team*