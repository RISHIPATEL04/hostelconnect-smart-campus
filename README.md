# HostelConnect prototype

A responsive mobile and laptop web app with a Python standard-library HTTP API and a SQLite database. No package installation is required.

## Start the app

From this folder, run:

```powershell
python server.py
```

Then open [http://localhost:8000](http://localhost:8000). The database is created at `work/hostelconnect.sqlite3` the first time the server starts. Stop the server with `Ctrl+C`.

## Demo accounts

All seeded demo accounts use the password **`hostel123`**. There are 12 accounts: 7 students, 2 wardens and 3 maintenance staff.

| Role | Email | Room |
|---|---|---|
| Student | `aarav@hostel.demo` | B-204 |
| Student | `mira@hostel.demo` | A-108 |
| Student | `kabir@hostel.demo` | B-311 |
| Student | `anaya@hostel.demo` | C-206 |
| Student | `ishaan@hostel.demo` | A-214 |
| Student | `diya@hostel.demo` | C-118 |
| Student | `rohan@hostel.demo` | B-109 |
| Warden | `priya@hostel.demo` | — |
| Warden | `dev@hostel.demo` | — |
| Maintenance | `sanjay@hostel.demo` | — |
| Maintenance | `farah@hostel.demo` | — |
| Maintenance | `manoj@hostel.demo` | — |

## Share on the same Wi-Fi

Run `python server.py --host 0.0.0.0`, find this computer's local IPv4 address, then open `http://<computer-ip>:8000` from another device on the same Wi-Fi. The host computer must stay on and the local firewall must allow the port. This is a classroom/demo setup; use HTTPS and a hosted database before exposing the app to the public internet.

## What works

- Role-aware sign-in and student registration (capped at 15 total accounts): students see their own complaints, maintenance see assigned work, and wardens manage hostel complaints and notices.
- Student dashboard tiles, dedicated complaint submission and confirmation screens, complaint history, notice details, and profile/edit/password screens.
- Notice board: search, category and urgency filters, sorting, full notice details, per-user pin/read state, warden publishing, expiry, and archiving.
- Complaint flow: submit category, room and description, optionally attach an image; wardens assign staff and change status; assigned maintenance staff update status and add notes; students can follow their own complaint timeline.
- In-app alerts for new notices, new complaints and complaint changes.
- SQLite persistence shared by browser sessions that use this server.

## API overview

The same-origin JSON API is served by `server.py`:

- `POST /api/login`, `POST /api/signup` (student-only), `POST /api/logout`, `GET /api/session`
- `GET /api/notices`, `POST /api/notices` (warden), `PATCH /api/notices/{id}` (archive), `PATCH /api/notices/{id}/pin`, `PATCH /api/notices/read`
- `GET /api/complaints`, `POST /api/complaints` (student), `PATCH /api/complaints/{id}` (warden or assigned staff), `POST /api/complaints/{id}/updates`
- `GET /api/notifications`, `PATCH /api/notifications/{id}`
- `PATCH /api/profile`, `PATCH /api/password`
- `GET /api/photo/{complaint-id}` (permission-checked image attachment)

## Hosting

The project includes a Vercel Python API configuration and a Supabase PostgreSQL schema. See [DEPLOYMENT.md](DEPLOYMENT.md) for the setup steps. The hosted database is separate from the local SQLite demo database.
