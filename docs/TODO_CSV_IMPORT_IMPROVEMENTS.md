# CSV Import Improvements - Action Plan

## 🚨 Immediate Fixes (Priority 1 - Fix Production Now)

### 1. Fix Template Crash (5 mins)
- [ ] Update `templates/campaigns/lists.html` line 101
- [ ] Change `import.failed_imports > 0` to `(import.failed_imports or 0) > 0`
- [ ] Deploy hotfix immediately

### 2. Update Incomplete Import Record (5 mins)
- [ ] Run SQL to fix CSV import ID 15:
  ```sql
  UPDATE csv_import 
  SET total_rows = 826,
      successful_imports = 826,
      failed_imports = 0
  WHERE id = 15;
  ```

### 3. Increase Gunicorn Timeout (10 mins)
- [ ] Update `entrypoint.sh`
- [ ] Change to: `exec gunicorn --workers=4 --bind=0.0.0.0:5000 --timeout=300 "app:create_app()"`
- [ ] Redeploy application

## 🔧 Short-term Fixes (Priority 2 - This Week)

### 4. Implement Smart Async Decision Logic (2 hours)
- [ ] Add file size check in CSVImportService
- [ ] If CSV > 500KB OR > 500 rows → Use Celery
- [ ] If CSV < 500KB AND < 500 rows → Process synchronously
- [ ] Show progress bar for async imports

### 5. Add Transaction Management (3 hours)
- [ ] Wrap import in database transaction
- [ ] Commit in batches of 100 records
- [ ] Update CSV import record even on failure
- [ ] Ensure atomic operations

### 6. Fix Missing Metadata (1 hour)
- [ ] Set `imported_at` on contacts during import
- [ ] Set `csv_import_id` on contacts
- [ ] Populate `contact_csv_import` junction table

## 🚀 Long-term Improvements (Priority 3 - Next Sprint)

### 7. Full Celery Background Processing (1 day)
```python
# Pseudo-code for implementation
@celery.task(bind=True, max_retries=3)
def process_csv_import(self, csv_file_path, list_name, enrichment_mode):
    try:
        # Process with progress updates
        for chunk in process_in_chunks(csv_file_path, chunk_size=100):
            process_chunk(chunk)
            self.update_state(state='PROGRESS', 
                            meta={'current': chunk.number, 
                                  'total': total_chunks})
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
```

### 8. Add Import Resume Capability (1 day)
- [ ] Track last processed row in CSV import record
- [ ] Allow resuming from failure point
- [ ] Implement idempotent import logic
- [ ] Add "retry failed import" button

### 9. Improve Error Handling & Logging (4 hours)
- [ ] Add detailed error logging for each row
- [ ] Create import error report
- [ ] Store failed rows for manual review
- [ ] Email notification on import completion

### 10. Performance Optimizations (4 hours)
- [ ] Use bulk insert operations
- [ ] Optimize database queries
- [ ] Consider upgrading instance to basic-s (2GB RAM)
- [ ] Add database connection pooling

## 📊 Architectural Patterns to Add to CLAUDE.md

### Error Handling Pattern
```python
class ImportService:
    def import_with_recovery(self, file):
        import_record = self.create_import_record(file)
        try:
            result = self.process_import(file)
            import_record.update_success(result)
        except Exception as e:
            import_record.update_failure(e)
            # Still save partial progress
            self.save_partial_results()
        finally:
            # ALWAYS update the import record
            db.session.commit()
```

### Size-based Processing Decision
```python
def should_use_async(file):
    file_size_mb = os.path.getsize(file.path) / (1024 * 1024)
    row_count = self.estimate_row_count(file)
    
    # Use async for large files or many rows
    if file_size_mb > 0.5 or row_count > 500:
        return True
    return False
```

### Progress Tracking
```python
def import_with_progress(self, file, progress_callback=None):
    total_rows = self.count_rows(file)
    
    for index, row in enumerate(self.process_rows(file)):
        self.process_row(row)
        
        if index % 10 == 0:  # Update every 10 rows
            progress = (index / total_rows) * 100
            if progress_callback:
                progress_callback(progress)
            
            # Commit batch
            if index % 100 == 0:
                db.session.commit()
```

## 🎯 Success Metrics

After implementing these changes:
- ✅ No more timeout errors for imports up to 50,000 rows
- ✅ Template never crashes even with incomplete data
- ✅ All imports trackable and resumable
- ✅ Clear progress indication for users
- ✅ Graceful error recovery

## 💡 Lessons Learned

1. **Always use defensive programming in templates** - Check for NULL/None values
2. **Large operations need async processing** - Don't rely on web request timeouts
3. **Transaction management is critical** - Partial commits prevent total data loss
4. **File size isn't everything** - Row count matters for CSV processing
5. **Always update tracking records** - Even on failure, record what happened

---

*Created: August 26, 2025*
*Context: PropertyRadar CSV import timeout issue affecting production*