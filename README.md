# Plaza Housing Availability Monitor

A lightweight 24/7 Python service that monitors Plaza housing availability, detects newly published listings, retrieves full details, and sends Telegram notifications.

The service runs on an Ubuntu server and is managed by `systemd`, while development is done remotely from a Fedora laptop over Tailscale + SSH.

---

## 1. Goals

The project was built to:

- monitor Plaza housing availability continuously;
- detect newly appearing listings quickly;
- avoid duplicate notifications;
- retrieve full listing details only when necessary;
- optionally filter listings by the Amsterdam region;
- notify one or more users through Telegram;
- survive SSH disconnects, VS Code shutdowns, and server reboots;
- remain lightweight enough to run 24/7 on a small home server.

Current polling interval:

```text
60 seconds
```

---

## 2. High-Level Architecture

```text
                         ┌─────────────────────┐
                         │      Plaza Web      │
                         │ plaza.newnewnew...  │
                         └─────────┬───────────┘
                                   │
                    lightweight availability request
                                   │
                                   ▼
                 ┌─────────────────────────────────┐
                 │ Plaza Availability API          │
                 │ mosaic-plaza-aanbodapi.zig365.nl│
                 │ /api/v1/locaties                │
                 └───────────────┬─────────────────┘
                                 │ JSON
                                 ▼
                     ┌────────────────────┐
                     │ Python Monitor     │
                     │ every 60 seconds   │
                     └─────────┬──────────┘
                               │
                               ▼
                     ┌────────────────────┐
                     │ SQLite             │
                     │ seen listing IDs   │
                     └─────────┬──────────┘
                               │
                         new listing?
                         /           \
                       no             yes
                       │               │
                       ▼               ▼
                    ignore      retrieve details
                                       │
                                       ▼
                    ┌──────────────────────────────────┐
                    │ Plaza Detail Endpoint            │
                    │ /portal/object/frontend/         │
                    │ getobject/format/json            │
                    └───────────────┬──────────────────┘
                                    │
                                    ▼
                           full listing details
                                    │
                                    ▼
                         optional location filter
                              /           \
                            no             yes
                            │               │
                            ▼               ▼
                         ignore       Telegram Bot API
                                             │
                                             ▼
                                       User phone(s)
```

---

## 3. Infrastructure Architecture

```text
Fedora Laptop
│
│  VS Code
│  Remote - SSH
│
└──── Tailscale private network ────┐
                                    │
                                    ▼
                           Ubuntu Server
                           hostname: dorothy
                                    │
                                    ├── OpenSSH
                                    ├── Tailscale
                                    ├── Python virtualenv
                                    ├── SQLite
                                    ├── systemd
                                    └── plaza-monitor.service
```

The laptop does **not** need to remain powered on. Once deployed, the Ubuntu server runs the monitor independently.

---

## 4. Why Tailscale Was Used

The server is behind a rental router, so router configuration and port forwarding are not available.

Tailscale provides a private overlay network, allowing SSH access without changing router settings or exposing port 22 publicly.

Example SSH config:

```text
Host homeserver
    HostName <TAILSCALE_IP>
    User <UBUNTU_USERNAME>
    IdentityFile ~/.ssh/id_ed25519
```

Connect with:

```bash
ssh homeserver
```

---

## 5. Project Structure

```text
plaza-monitor/
│
├── .venv/
├── .private/
│   └── plaza_request.json
├── data/
│   └── plaza.db
├── logs/
├── src/
│   └── plaza_monitor/
│       ├── __init__.py
│       ├── main.py
│       ├── client.py
│       ├── storage.py
│       ├── filters.py
│       └── notifier.py
├── tests/
├── .env
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 6. Main Components

### `client.py`

Responsible for communication with Plaza.

#### Availability API

```text
POST https://mosaic-plaza-aanbodapi.zig365.nl/api/v1/locaties?locale=en_GB
```

Returns lightweight listing information such as:

```json
{
  "id": 17088,
  "latitude": 52.3334,
  "longitude": 4.93643,
  "netRent": 555,
  "totalRent": 828.65
}
```

This endpoint is polled every minute.

#### Detail API

```text
POST https://plaza.newnewnew.space/portal/object/frontend/getobject/format/json
```

Form data:

```text
id=<LISTING_ID>
```

Returns richer information including address, city, area, rent, publication date, availability date, URL key, and reaction data.

The detail endpoint is only called for newly detected listings.

---

## 7. SQLite State

SQLite stores listing IDs already seen by the monitor.

Example schema:

```sql
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY,
    net_rent REAL,
    total_rent REAL,
    latitude REAL,
    longitude REAL,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Conceptually:

```text
API listing ID
      │
      ▼
already in SQLite?
    /       \
  yes        no
  │          │
ignore       process
             │
             ▼
          save ID
```

---

## 8. Telegram Notifications

Telegram was chosen because it is simple, lightweight, and easy to use for multiple users or groups.

Example notification:

```text
🏠 NEW PLAZA LISTING

📍 Address, City
💶 €xxx / month
📐 xx m²
📅 Available: YYYY-MM-DD

https://plaza.newnewnew.space/...
```

Secrets live in `.env`:

```text
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

or for multiple recipients:

```text
TELEGRAM_CHAT_IDS=123456789,987654321
```

Never commit `.env`.

---

## 9. Optional Amsterdam Filter

The filter can be toggled through `.env`:

```text
FILTER_AMSTERDAM=true
```

or:

```text
FILTER_AMSTERDAM=false
```

When disabled, all new Plaza listings are sent to Telegram.

Example configured cities:

```python
AMSTERDAM_AREA = {
    "Amsterdam",
    "Amstelveen",
    "Diemen",
    "Duivendrecht",
}
```

---

## 10. Continuous Monitoring

The monitor executes a cycle approximately once per minute:

```text
start cycle
   ↓
request current listings
   ↓
compare IDs with SQLite
   ↓
process new listings
   ↓
send notifications
   ↓
sleep 60 seconds
   ↓
repeat
```

Temporary failures are logged so one failed HTTP request does not immediately kill the process.

---

## 11. systemd Deployment

Service file:

```text
/etc/systemd/system/plaza-monitor.service
```

Example:

```ini
[Unit]
Description=Plaza Housing Availability Monitor
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=carpdiem
WorkingDirectory=/home/carpdiem/Projects/plaza-monitor
EnvironmentFile=/home/carpdiem/Projects/plaza-monitor/.env
ExecStart=/home/carpdiem/Projects/plaza-monitor/.venv/bin/python /home/carpdiem/Projects/plaza-monitor/src/plaza_monitor/main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Useful commands:

```bash
sudo systemctl enable plaza-monitor
sudo systemctl start plaza-monitor
sudo systemctl restart plaza-monitor
sudo systemctl stop plaza-monitor
systemctl status plaza-monitor
journalctl -u plaza-monitor -f
journalctl -u plaza-monitor -n 50 --no-pager
```

---

## 12. Tradeoffs and Design Decisions

### Direct API vs Playwright

**Chosen:** direct HTTP API.

Advantages:

- much lower CPU/RAM usage;
- no headless Chromium process;
- faster polling;
- simpler deployment;
- less fragile than DOM scraping.

Disadvantages:

- endpoint behavior is not formally documented for this project;
- API structures may change.

Playwright should only be added if Plaza moves required functionality behind browser-only interactions.

### Polling vs Webhook

**Chosen:** polling every 60 seconds.

Advantages:

- simple;
- reliable;
- no dependency on Plaza supporting webhooks;
- detection latency is acceptable.

Disadvantage:

- repeated API traffic.

### SQLite vs PostgreSQL

**Chosen:** SQLite.

Advantages:

- no DB server process;
- no roles, ports, or credentials;
- lightweight;
- trivial backup;
- enough for a single monitor process.

PostgreSQL becomes more attractive if the project grows into multiple collectors, dashboards, analytics, or concurrent services.

### Telegram vs WhatsApp

**Chosen:** Telegram.

Advantages:

- simpler setup;
- easy bot API;
- easy group notifications;
- no business account/template workflow.

### Telegram vs AWS SNS

Telegram is the direct user-facing channel.

SNS would make more sense later as a fan-out layer:

```text
monitor
   ↓
SNS
├── email
├── SQS
├── Lambda → Telegram
└── other consumers
```

### systemd vs cron

**Chosen:** systemd.

Advantages:

- automatic restart;
- startup after reboot;
- central logs with `journalctl`;
- proper service state management.

Cron would be better for a short one-shot job, not a persistent loop.

---

## 13. Problems and Mistakes Encountered

### Mistake 1 — Creating the virtual environment with `sudo`

Initial attempt:

```bash
sudo python3 -m venv .venv
```

Problems:

- `python3-venv` was missing;
- `sudo` inside the home project can create root-owned project files.

Fix:

```bash
sudo apt install python3-venv
python3 -m venv .venv
```

Lesson: use `sudo` for system packages, not for project virtual environments.

### Mistake 2 — Assuming `.env` variables were visible to Python

The shell used:

```bash
source .env
```

but Python reported missing Telegram variables.

Fix: use `python-dotenv` and load `.env` explicitly inside the application.

Lesson: environment configuration should be loaded predictably.

### Mistake 3 — SQLite connection leak

This was the most important bug.

The code used:

```python
with get_connection() as connection:
    ...
```

It was assumed that the SQLite connection closed automatically when the context ended. It did not.

Symptoms:

```text
Memory:
~20 MB
→ 31 MB
→ 41 MB
→ ~195 MB
```

Eventually:

```text
sqlite3.OperationalError: unable to open database file
```

The decisive diagnostic was file-descriptor inspection:

```text
169 plaza.db descriptors
→ 197
→ continuing upward
```

Fix:

```python
@contextmanager
def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
```

Afterward:

```text
plaza.db descriptors: 0
```

Lesson: transaction context management and resource lifetime are not necessarily the same thing.

### Mistake 4 — Trusting `systemctl status` too much

The service displayed:

```text
Active: active (running)
```

while every monitoring cycle was failing.

Reason: the process caught exceptions and stayed alive.

Lesson: process health and application health are different things.

Future improvement: track consecutive failures and send a health alert or exit after a threshold so systemd can restart the service.

### Mistake 5 — Initially suspecting permissions

When SQLite failed, permissions and disk capacity were investigated.

They were healthy. The actual cause was leaked SQLite connections.

Lesson: validate hypotheses with observability rather than repeatedly changing permissions.

Useful command:

```bash
ls -l /proc/$PID/fd
```

### Mistake 6 — Timezone mismatch

`journalctl` initially showed UTC while the user was in Amsterdam.

Fix:

```bash
sudo timedatectl set-timezone Europe/Amsterdam
```

Using an IANA timezone automatically handles daylight-saving changes.

### Mistake 7 — Browser session headers contained secrets

During API discovery, browser headers exposed active-looking cookies/session values.

These are not required for the monitoring endpoint and should never be copied into source control.

Do not store:

```text
Cookie
Authorization
Bearer tokens
session IDs
JWT/session cookies
```

### Mistake 8 — Endpoint-name assumption

`/api/v1/locaties` initially looked like a location-only endpoint.

Actual response inspection showed that it returned the lightweight listing feed.

Lesson: inspect actual request/response behavior before designing from endpoint names.

### Mistake 9 — Saving listings before notification success

Earlier flow:

```text
new listing
   ↓
save to SQLite
   ↓
send Telegram
      ↓
failure
```

This could cause a missed notification.

Improved approach:

```text
new listing
   ↓
fetch details
   ↓
send notification
   ↓
successful processing
   ↓
save as seen
```

Future schema should separate:

```text
seen
notified
notification_attempts
last_notification_error
```

### Mistake 10 — Assuming every RSS increase is automatically a leak

After fixing SQLite, RSS still rose somewhat.

RSS growth does not always mean live Python objects are leaking; Python/native allocators may retain memory for reuse.

Correct investigation order:

1. monitor RSS;
2. inspect SQLite/file descriptors;
3. inspect socket counts;
4. use `tracemalloc` if growth continues.

---

## 14. Useful Diagnostic Commands

Current service:

```bash
systemctl status plaza-monitor
```

Current PID:

```bash
PID=$(systemctl show plaza-monitor -p MainPID --value)
echo "$PID"
```

Total file descriptors:

```bash
ls /proc/$PID/fd | wc -l
```

SQLite descriptors:

```bash
ls -l /proc/$PID/fd 2>/dev/null | grep 'plaza.db' | wc -l
```

Expected after the leak fix:

```text
0
```

Socket count:

```bash
ls -l /proc/$PID/fd 2>/dev/null | grep socket | wc -l
```

Memory:

```bash
grep -E 'VmRSS|VmSize|RssAnon|RssFile' /proc/$PID/status
```

Errors:

```bash
journalctl -u plaza-monitor --no-pager | grep -E "ERROR|OperationalError"
```

---

## 15. Security

Never commit:

```text
.env
.private/
data/
```

Recommended `.gitignore`:

```gitignore
.venv/
__pycache__/
*.pyc

.env
.private/

data/
logs/

.vscode/
```

Protect credentials:

```bash
chmod 600 .env
chmod 700 .private
chmod 600 .private/plaza_request.json
```

Treat the Telegram bot token like a password.

---

## 16. Current Known Limitations

- Plaza endpoints may change.
- No official API contract is used.
- No health notification exists yet for repeated failures.
- Notification delivery state should be modeled separately.
- No automatic application submission is implemented.
- No explicit retry/backoff policy beyond the next polling cycle exists.
- Monitoring currently covers only Plaza.
- Automated tests are still limited/not yet established.
- Memory behavior should continue to be observed after resource-leak fixes.

---

## 17. Recommended Next Improvements

### Priority 1 — Health monitoring

Track consecutive failures and send a warning after a threshold.

### Priority 2 — Richer database state

Add:

```text
listing_id
first_seen
last_seen
notified
notified_at
notification_attempts
last_error
```

### Priority 3 — Load known IDs once per cycle

Instead of one SQLite query per listing, use:

```sql
SELECT id FROM listings;
```

then compare against a Python `set`.

### Priority 4 — Persistent HTTP client

Use a reusable `httpx.Client` for connection pooling and explicit lifecycle management.

### Priority 5 — Retries and backoff

Example:

```text
request fails
   ↓
retry after 2 sec
   ↓
retry after 5 sec
   ↓
retry after 15 sec
```

### Priority 6 — Testing

Add tests for:

```text
listing deduplication
location filtering
message formatting
SQLite persistence
API response parsing
notification failure behavior
```

### Priority 7 — Multiple housing sources

Future architecture:

```text
Plaza ─────────┐
               │
Provider B ────┼── collectors
               │
Provider C ────┘
                    ↓
               common model
                    ↓
                PostgreSQL
                    ↓
             notification bus
              /      |       \
        Telegram    Email     SNS
```

---

## 18. Design Philosophy

The project intentionally started with:

```text
direct API
+ Python
+ SQLite
+ Telegram
+ systemd
```

instead of immediately adding:

```text
Docker
PostgreSQL
Airflow
Kafka
AWS
Redis
Kubernetes
```

The current stack is sufficient for the actual workload.

Main lesson:

> Complexity should be added when the workload requires it, not simply because a technology exists.

---

## 19. Current Status

Implemented:

```text
✅ 24/7 monitoring
✅ 60-second polling
✅ API-based ingestion
✅ listing deduplication
✅ detailed listing retrieval
✅ optional Amsterdam filtering
✅ Telegram notifications
✅ multiple Telegram recipients/group support
✅ SQLite persistence
✅ systemd auto-start
✅ restart after reboot
✅ remote management through Tailscale + SSH
✅ journald logging
✅ explicit SQLite connection cleanup
```

Planned:

```text
⬜ health alerts
⬜ notification delivery state
⬜ retries/backoff
⬜ unit/integration tests
⬜ structured metrics
⬜ additional housing providers
⬜ optional PostgreSQL migration
```

---

## 20. Operational Cheat Sheet

```bash
# connect
ssh homeserver

# project
cd ~/Projects/plaza-monitor

# service status
systemctl status plaza-monitor

# live logs
journalctl -u plaza-monitor -f

# restart after code changes
sudo systemctl restart plaza-monitor

# stop/start
sudo systemctl stop plaza-monitor
sudo systemctl start plaza-monitor

# boot enablement
systemctl is-enabled plaza-monitor

# current PID
PID=$(systemctl show plaza-monitor -p MainPID --value)

# SQLite descriptor leak check
ls -l /proc/$PID/fd 2>/dev/null | grep 'plaza.db' | wc -l

# memory

grep -E 'VmRSS|VmSize|RssAnon|RssFile' /proc/$PID/status

# recent errors
journalctl -u plaza-monitor --since "1 hour ago" --no-pager | grep -E "ERROR|OperationalError"
```

---

## 21. Final Architecture Summary

```text
                      FEDORA LAPTOP
                           │
                      VS Code / SSH
                           │
                       Tailscale
                           │
                           ▼
                    UBUNTU SERVER
                         dorothy
                           │
                        systemd
                           │
                           ▼
                    Plaza Monitor
                           │
                ┌──────────┴──────────┐
                │                     │
                ▼                     ▼
       Plaza Availability API      SQLite
                │                     │
                └──────────┬──────────┘
                           │
                      new listing
                           │
                           ▼
                  Plaza Detail API
                           │
                           ▼
                   optional filters
                           │
                           ▼
                    Telegram Bot
                           │
                    ┌──────┴──────┐
                    ▼             ▼
                  User 1        User 2
```

The monitor is intentionally lightweight, locally controlled, remotely manageable, and easy to evolve into a larger event-driven data platform later.
