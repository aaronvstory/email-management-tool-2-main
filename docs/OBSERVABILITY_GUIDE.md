# Observability & Monitoring Guide

## Overview

Email Management Tool v2.8 includes comprehensive observability with:
- **JSON Structured Logging** - RotatingFileHandler with contextual fields
- **Prometheus Metrics** - 14 metric types for monitoring
- **Health Endpoints** - `/healthz` with system status
- **Rate Limiting** - Protection against abuse
- **Audit Trail** - All actions logged to database

---

## JSON Logging

### Log Location & Rotation
- **File**: `app.log` (in project root)
- **Format**: JSON (one object per line)
- **Rotation**: 10MB max size, 5 backups (50MB total)
- **Retention**: Automatic deletion after 5 rotations

### Log Levels
Set via environment variable:
```bash
# In .env file
LOG_LEVEL=DEBUG    # Most verbose (includes debug messages)
LOG_LEVEL=INFO     # Normal operations
LOG_LEVEL=WARNING  # Only warnings and errors (recommended for production)
LOG_LEVEL=ERROR    # Only errors
```

### Log Format Example
```json
{
  "timestamp": "2025-10-15T14:23:45.123Z",
  "level": "INFO",
  "logger": "app.routes.interception",
  "message": "[interception::release] success",
  "email_id": 42,
  "target": "INBOX",
  "attachments_removed": false,
  "thread": "MainThread",
  "process": 12345
}
```

### Common Queries

**View all errors in last hour**:
```bash
# Using jq (JSON processor)
cat app.log | jq -r 'select(.level == "ERROR" and .timestamp > (now - 3600 | todate))'

# Using grep
grep '"level":"ERROR"' app.log | tail -20
```

**Find all IMAP failures**:
```bash
cat app.log | jq -r 'select(.message | contains("IMAP")) | select(.level == "WARNING" or .level == "ERROR")'
```

**Count errors by component (last 1000 lines)**:
```bash
tail -1000 app.log | jq -r 'select(.level == "ERROR") | .logger' | sort | uniq -c | sort -rn
```

**Extract release operation latencies**:
```bash
cat app.log | jq -r 'select(.message | contains("release")) | {timestamp, email_id, duration: .latency_ms}'
```

**Follow logs in real-time**:
```bash
# Windows (PowerShell)
Get-Content -Path app.log -Wait -Tail 20 | ForEach-Object { $_ | ConvertFrom-Json | Format-List }

# Git Bash / WSL
tail -f app.log | jq -r '"\(.timestamp) [\(.level)] \(.message)"'
```

---

## Prometheus Metrics

### Accessing Metrics
```bash
# Metrics endpoint (no authentication required)
curl http://localhost:5001/metrics

# Example output
# HELP emails_intercepted_total Total number of emails intercepted
# TYPE emails_intercepted_total counter
emails_intercepted_total{account_id="acct:ndayijecika_gmail.com",direction="inbound",status="HELD"} 42.0

# HELP emails_held_current Current number of emails in HELD status
# TYPE emails_held_current gauge
emails_held_current 5.0
```

### Available Metrics

#### Counters (always increasing)
| Metric | Labels | Description |
|--------|--------|-------------|
| `emails_intercepted_total` | direction, status, account_id | Total emails intercepted |
| `emails_released_total` | action, account_id | Total emails released |
| `emails_discarded_total` | reason, account_id | Total emails discarded |
| `emails_edited_total` | account_id | Total emails edited |
| `errors_total` | error_type, component | Total errors by type |
| `imap_connection_failures_total` | account_id, host | IMAP connection failures |
| `smtp_connection_failures_total` | account_id, host | SMTP connection failures |

#### Gauges (current state)
| Metric | Labels | Description |
|--------|--------|-------------|
| `emails_held_current` | - | Current number of held emails |
| `emails_pending_current` | - | Current number of pending emails |
| `imap_watcher_status` | account_id | Watcher status (1=running, 0=stopped) |
| `db_connections_active` | - | Active database connections |

#### Histograms (latency distribution)
| Metric | Labels | Buckets |
|--------|--------|---------|
| `email_interception_latency_seconds` | direction | 0.01s to 5s |
| `email_release_latency_seconds` | action | 0.1s to 10s |
| `imap_operation_latency_seconds` | operation, account_id | 0.1s to 60s |

### Label Cardinality Control

All account_id and host labels are **normalized** to prevent metric explosion:
- **Format**: `acct:username_domain.com` (48 char max)
- **Sanitization**: Non-alphanumeric characters replaced with `_`
- **Truncation**: Long values trimmed to 48 characters

Example:
```python
# Input: ndayijecika@gmail.com
# Output: acct:ndayijecika_gmail.com

# Input: very-long-email-address-that-exceeds-limit@example.com
# Output: acct:very-long-email-address-that-exceeds-limi (truncated)
```

### Sample PromQL Queries

**Error rate (errors per second over 5 minutes)**:
```promql
rate(errors_total[5m])
```

**95th percentile email release latency**:
```promql
histogram_quantile(0.95, rate(email_release_latency_seconds_bucket[5m]))
```

**Emails held for >1 hour** (requires custom label):
```promql
emails_held_current{held_duration="gt_1h"}
```

**IMAP watcher health** (0 = down, 1 = up):
```promql
imap_watcher_status
```

**Top 5 accounts by interception volume**:
```promql
topk(5, sum by (account_id) (rate(emails_intercepted_total[1h])))
```

### Recommended Alerts

**Critical Alerts** (page on-call):
```promql
# Email pipeline down (no interceptions in 10 minutes)
rate(emails_intercepted_total[10m]) == 0

# High error rate (>5% of requests)
rate(errors_total[5m]) / rate(emails_intercepted_total[5m]) > 0.05

# IMAP watcher crashed
imap_watcher_status == 0

# Database unavailable
up{job="email-manager"} == 0
```

**Warning Alerts** (investigate within 1 hour):
```promql
# Elevated release latency (p95 >5 seconds)
histogram_quantile(0.95, rate(email_release_latency_seconds_bucket[5m])) > 5

# IMAP connection failures increasing
rate(imap_connection_failures_total[5m]) > 0.1

# Held emails accumulating (>100)
emails_held_current > 100
```

---

## Rate Limiting

### Configuration

Rate limits are **configurable per endpoint** via environment variables:

```bash
# In .env file

# Release endpoint (default: 30 requests/minute)
RATE_LIMIT_RELEASE=30 per minute
RATE_LIMIT_RELEASE_REQUESTS=30
RATE_LIMIT_RELEASE_WINDOW_SECONDS=60

# Fetch endpoint (default: 30 requests/minute)
RATE_LIMIT_FETCH=30 per minute

# Edit endpoint (default: 30 requests/minute)
RATE_LIMIT_EDIT=30 per minute

# Disable rate limit for endpoint (set to 0)
RATE_LIMIT_RELEASE_REQUESTS=0
```

### Supported Time Windows
- `per second` - 1 second window
- `per minute` - 60 second window (default)
- `per hour` - 3600 second window

### Rate Limit Response

When rate limit exceeded, API returns **429 Too Many Requests**:

```json
{
  "error": "Rate limit exceeded",
  "retry_after": 42,
  "limit": 30
}
```

**Response Headers**:
- `Retry-After: 42` - Seconds until reset
- `X-RateLimit-Limit: 30` - Max requests per window
- `X-RateLimit-Remaining: 0` - Requests remaining
- `X-RateLimit-Reset: 42` - Seconds until reset

### Client Identification

Rate limits are **per-client** based on IP address with proxy support:

1. Check `X-Forwarded-For` header (first IP in list)
2. Check `X-Real-IP` header
3. Fall back to `request.remote_addr`

**Example with reverse proxy** (nginx):
```nginx
location / {
    proxy_pass http://localhost:5001;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP $remote_addr;
}
```

### Frontend Error Handling

**Recommended pattern**:
```javascript
async function releaseEmail(emailId) {
    try {
        const response = await fetch(`/api/interception/release/${emailId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({target_folder: 'INBOX'})
        });

        if (response.status === 429) {
            const data = await response.json();
            showWarning(`Rate limit exceeded. Retry in ${data.retry_after} seconds.`);
            return;
        }

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const result = await response.json();
        showSuccess('Email released successfully');
    } catch (error) {
        showError(`Failed to release email: ${error.message}`);
    }
}
```

---

## Health Checks

### Endpoint: GET /healthz

**No authentication required** - suitable for load balancers and monitoring.

**Response (200 OK)**:
```json
{
  "ok": true,
  "db": "ok",
  "held_count": 5,
  "released_24h": 42,
  "median_latency_ms": 150,
  "workers": [
    {
      "worker_id": "imap_watcher_3",
      "last_heartbeat": "2025-10-15T14:23:45Z",
      "status": "running"
    }
  ],
  "timestamp": "2025-10-15T14:24:00Z",
  "smtp": {
    "listening": true,
    "last_selfcheck_ts": "2025-10-15T14:23:50Z",
    "last_inbound_ts": "2025-10-15T14:23:45Z"
  },
  "security": {
    "secret_key_configured": true,
    "secret_key_prefix": "a1b2c3d4",
    "csrf_enabled": true,
    "csrf_time_limit": null,
    "session_cookie_secure": false,
    "session_cookie_httponly": true
  }
}
```

**Response (503 Service Unavailable)** - Database unavailable or critical error:
```json
{
  "ok": false,
  "db": null,
  "error": "database is locked",
  "timestamp": "2025-10-15T14:24:00Z"
}
```

### Health Check Caching
- **Cache Duration**: 5 seconds
- **Purpose**: Reduce database load from frequent health checks
- **Bypass**: Not currently supported (cache always used)

### Monitoring Worker Heartbeats

IMAP watcher threads write heartbeats every ~60 seconds:
```sql
SELECT worker_id, last_heartbeat, status
FROM worker_heartbeats
WHERE datetime(last_heartbeat) > datetime('now', '-2 minutes')
```

**Stale worker detection**:
- No heartbeat in >2 minutes = worker likely crashed
- Check IMAP watcher status: `imap_watcher_status{account_id="..."} == 0`

---

## Audit Trail

### Database Table: audit_log

All actions are logged with:
- **Action type**: LOGIN, INTERCEPT, RELEASE, EDIT, DISCARD, etc.
- **User ID**: Who performed the action
- **Email ID**: Which email was affected
- **Details**: Free-text description
- **Timestamp**: When action occurred

### Query Examples

**Recent releases**:
```sql
SELECT action, email_id, details, created_at
FROM audit_log
WHERE action = 'RELEASE'
ORDER BY created_at DESC
LIMIT 20;
```

**User activity**:
```sql
SELECT action, COUNT(*) as count
FROM audit_log
WHERE user_id = 1
  AND created_at > datetime('now', '-1 day')
GROUP BY action;
```

**Suspicious patterns** (multiple discards):
```sql
SELECT user_id, COUNT(*) as discard_count
FROM audit_log
WHERE action = 'DISCARD'
  AND created_at > datetime('now', '-1 hour')
GROUP BY user_id
HAVING discard_count > 10;
```

---

## Operational Runbooks

### Runbook: High Error Rate

**Symptoms**: `rate(errors_total[5m]) > 0.1`

**Steps**:
1. Check recent errors: `grep '"level":"ERROR"' app.log | tail -50`
2. Identify error type: `tail -1000 app.log | jq -r 'select(.level == "ERROR") | .error_type' | sort | uniq -c`
3. Check component: `tail -1000 app.log | jq -r 'select(.level == "ERROR") | .component'`
4. Common causes:
   - **IMAP auth failures**: Check account credentials in database
   - **SMTP connection failures**: Verify SMTP proxy is running (`netstat -an | findstr :8587`)
   - **Database locked**: Check for long-running queries or file locks

### Runbook: IMAP Watcher Down

**Symptoms**: `imap_watcher_status == 0`

**Steps**:
1. Check worker heartbeats: `curl http://localhost:5001/healthz | jq '.workers'`
2. Check logs: `grep 'imap_watcher' app.log | tail -50`
3. Restart watcher via UI:
   - Navigate to `/accounts`
   - Click "Start Monitor" for affected account
4. If manual restart fails:
   - Verify account credentials are correct
   - Check IMAP server connectivity: `telnet imap.gmail.com 993`
   - Restart entire application: `python simple_app.py`

### Runbook: Rate Limit Triggered

**Symptoms**: 429 responses in logs or user reports

**Steps**:
1. Identify offending IP: `grep '"status_code":429' app.log | jq -r '.client_ip' | sort | uniq -c | sort -rn`
2. Check if legitimate traffic:
   - Single user batch operation? → Temporarily increase limit via env var
   - Automated scraper/bot? → Block at firewall/reverse proxy level
3. Adjust rate limit if needed:
   ```bash
   # In .env
   RATE_LIMIT_RELEASE_REQUESTS=60  # Double the limit
   ```
4. Restart application to apply new limits

---

## Performance Tuning

### Log Volume Reduction

**Scenario**: Logs rotating too frequently (multiple times per day)

**Solutions**:
1. **Increase rotation size**:
   ```python
   # In app/utils/logging.py
   handler = RotatingFileHandler('app.log', maxBytes=50*1024*1024, backupCount=5)  # 50MB
   ```

2. **Increase log level** (reduce verbosity):
   ```bash
   # In .env
   LOG_LEVEL=WARNING  # Only warnings and errors
   ```

3. **External log aggregation** (recommended for production):
   - Configure app to log to stdout
   - Use Fluentd/Logstash to ship logs to centralized storage (Elasticsearch, Splunk, etc.)

### Metric Cardinality Issues

**Scenario**: Prometheus scrape timeouts or high memory usage

**Diagnosis**:
```bash
# Count unique label combinations
curl -s http://localhost:5001/metrics | grep -v '^#' | wc -l

# Should be <10,000 active series
```

**Solutions**:
1. **Check for unbounded labels**:
   - Account IDs should be normalized (prefix + truncation)
   - Email IDs should NEVER be used as labels
2. **Reduce label dimensions**:
   - Consider removing `account_id` from low-value metrics
3. **Increase scrape interval**: 15s → 60s

---

## FAQ

### Q: How do I rotate logs manually?
**A**: Logs rotate automatically. To force rotation, rename `app.log` to `app.log.1` and restart the app.

### Q: Can I disable rate limiting entirely?
**A**: Yes, set `RATE_LIMIT_<ENDPOINT>_REQUESTS=0` in .env for any endpoint.

### Q: How do I export metrics to Grafana?
**A**:
1. Install Prometheus server
2. Add scrape config:
   ```yaml
   scrape_configs:
     - job_name: 'email-manager'
       static_configs:
         - targets: ['localhost:5001']
       metrics_path: '/metrics'
       scrape_interval: 15s
   ```
3. Add Prometheus as Grafana data source
4. Import dashboard or create custom panels

### Q: What if healthz returns 503?
**A**: Service is degraded. Check `error` field in response and consult logs. Common causes: database locked, SMTP proxy down, IMAP auth failures.

### Q: How do I monitor from Uptime Robot / Pingdom?
**A**: Configure HTTP monitor for `http://localhost:5001/healthz` expecting 200 status code and JSON response containing `"ok": true`.

---

## Further Reading

- **CLAUDE.md** - Complete project documentation
- **STYLEGUIDE.md** - UI/UX standards
- **INTERCEPTION_IMPLEMENTATION.md** - Technical architecture details
- **Prometheus Documentation**: https://prometheus.io/docs/
- **Grafana Dashboards**: https://grafana.com/docs/

---

**Last Updated**: October 15, 2025
**Version**: 2.8
**Status**: Production Ready
