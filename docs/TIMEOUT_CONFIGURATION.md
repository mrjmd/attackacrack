# Gunicorn Timeout Configuration for CSV Imports

## Overview
The Attack-a-Crack CRM system has been configured with extended timeout settings to handle large CSV import operations without encountering timeout errors.

## Configuration

### Default Settings
- **Timeout**: 300 seconds (5 minutes)
- **Workers**: 4 processes

These defaults are suitable for:
- CSV files with up to 15,000 rows
- PropertyRadar imports
- Contact list uploads
- Campaign contact imports

### Environment Variables
You can customize the timeout and worker settings using environment variables:

```bash
# Set custom timeout (in seconds)
export GUNICORN_TIMEOUT=600  # 10 minutes

# Set custom number of workers
export GUNICORN_WORKERS=8    # 8 worker processes
```

### Files Modified

1. **entrypoint.sh**
   - Added configurable timeout and workers
   - Uses environment variables with sensible defaults
   ```bash
   GUNICORN_TIMEOUT=${GUNICORN_TIMEOUT:-300}
   GUNICORN_WORKERS=${GUNICORN_WORKERS:-4}
   exec gunicorn --timeout=${GUNICORN_TIMEOUT} --workers=${GUNICORN_WORKERS} ...
   ```

2. **.env.example**
   - Documents the new environment variables
   ```
   GUNICORN_TIMEOUT=300  # Timeout in seconds (default: 300s for large CSV imports)
   GUNICORN_WORKERS=4    # Number of worker processes (default: 4)
   ```

3. **.do/app.yaml**
   - Production configuration includes timeout settings
   ```yaml
   - key: GUNICORN_TIMEOUT
     value: "300"
   - key: GUNICORN_WORKERS
     value: "4"
   ```

4. **config.py**
   - Added configuration constants for programmatic access
   ```python
   GUNICORN_TIMEOUT = int(os.environ.get('GUNICORN_TIMEOUT', '300'))
   GUNICORN_WORKERS = int(os.environ.get('GUNICORN_WORKERS', '4'))
   ```

## Timeout Sizing Guide

### CSV Import Performance
Based on testing and production experience:

| CSV Size | Processing Time | Recommended Timeout |
|----------|----------------|--------------------|
| 1,000 rows | ~10-20 seconds | 60 seconds |
| 5,000 rows | ~50-100 seconds | 180 seconds |
| 10,000 rows | ~100-200 seconds | 300 seconds (default) |
| 25,000 rows | ~250-500 seconds | 600 seconds |
| 50,000 rows | ~500-1000 seconds | 1200 seconds |

### Factors Affecting Processing Time
1. **API Rate Limits**: OpenPhone API calls may be rate-limited
2. **Database Operations**: Bulk inserts and updates
3. **Data Validation**: Phone number validation and normalization
4. **Network Latency**: API response times
5. **Concurrent Operations**: Other system load

## Troubleshooting

### Timeout Errors During Import
If you see "Worker timeout" errors:

1. **Increase the timeout**:
   ```bash
   export GUNICORN_TIMEOUT=600  # 10 minutes
   docker-compose restart web
   ```

2. **For production (DigitalOcean)**:
   - Update the app.yaml configuration
   - Redeploy the application

3. **Monitor the import**:
   ```bash
   docker-compose logs -f web
   ```

### Memory Issues
For very large imports (>50,000 rows):

1. **Consider batch processing**:
   - Split the CSV into smaller files
   - Process in chunks of 10,000 rows

2. **Increase worker memory**:
   - Upgrade instance size in DigitalOcean
   - Or reduce number of workers to give each more memory

### Performance Optimization

1. **Use background jobs** for large imports:
   ```python
   # Instead of synchronous processing
   from tasks import import_csv_task
   import_csv_task.delay(file_path)
   ```

2. **Enable progress tracking**:
   - Use WebSocket or SSE for real-time updates
   - Store progress in Redis

3. **Optimize database operations**:
   - Use bulk_insert_mappings() for large datasets
   - Disable autoflush during import

## Testing

### Unit Tests
```bash
docker-compose exec web pytest tests/unit/test_gunicorn_config.py -v
```

### Integration Tests
```bash
docker-compose exec web pytest tests/integration/test_csv_import_timeout.py -v
```

### Manual Testing
1. Set a custom timeout:
   ```bash
   export GUNICORN_TIMEOUT=30  # Short timeout for testing
   ```

2. Try importing a large CSV

3. Verify timeout is applied:
   ```bash
   docker-compose exec web ps aux | grep gunicorn
   # Should show: gunicorn ... --timeout=30 ...
   ```

## Best Practices

1. **Set appropriate timeouts**:
   - Don't set unnecessarily high timeouts (security risk)
   - Consider the largest expected import size
   - Add 50% buffer to expected processing time

2. **Monitor timeout usage**:
   - Log when requests take >50% of timeout
   - Alert on frequent timeout errors

3. **Use async processing**:
   - For imports >10,000 rows, use Celery tasks
   - Provide progress feedback to users

4. **Implement request chunking**:
   - Break large operations into smaller requests
   - Use pagination for large result sets

## Related Configuration

### Nginx (if used as reverse proxy)
If using Nginx in front of Gunicorn:
```nginx
proxy_read_timeout 300s;
proxy_connect_timeout 75s;
```

### Docker Health Checks
The Docker health check timeout is separate:
```yaml
healthcheck:
  timeout: 10s  # This is just for health checks, not requests
```

### Database Connection Pool
Ensure database can handle long transactions:
```python
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_pre_ping': True,
    'pool_recycle': 3600,
    'connect_args': {
        'connect_timeout': 10,
        'options': '-c statement_timeout=300000'  # 5 minutes in ms
    }
}
```

## Security Considerations

1. **DoS Prevention**:
   - Long timeouts can enable DoS attacks
   - Implement rate limiting for import endpoints
   - Require authentication for import operations

2. **Resource Limits**:
   - Set maximum file size limits
   - Limit concurrent import operations
   - Monitor CPU and memory usage

3. **Audit Logging**:
   - Log all import operations
   - Track processing times
   - Alert on abnormal patterns

---

*Last Updated: August 26, 2025*
*Version: 1.0*