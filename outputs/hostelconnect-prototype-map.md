# HostelConnect — Prototype Map

**One app. Every campus need.**

## Purpose

Build a responsive, working Version 1 prototype for a small campus group. Students use it to report and follow repairs and read hostel notices. Wardens manage complaints, publish notices and monitor outstanding work. Maintenance staff receive assigned jobs and update their progress. The same app and shared database work from laptop and mobile browsers.

## Version 1 scope

### Included

1. **Accounts and roles** — sign in, profile, role-aware navigation for students, wardens/admins, and maintenance staff.
2. **Complaint tracking** — submit a category, description, room, optional photo; view status and updates; wardens assign work; staff update progress; student sees resolution.
3. **Digital notice board** — warden creates, categorizes, prioritizes, and expires notices; students see current notices and urgent items first.
4. **Notifications** — in-app alerts for complaint changes, new/urgent notices, and later leave/event reminders. Version 1 implements complaint and notice alerts; leave and event workflows are later additions.
5. **Dashboards** — students see their open complaints and current notices; wardens see workload, statuses and notice controls; maintenance staff see assigned jobs.

### Later, outside Version 1

Timetable, library, event booking, leave requests, payment, attendance, campus-wide services and automated push notifications. Keep the data model extensible, but do not add these flows to the first prototype.

## Roles and permissions

| Role | Main actions | Data they can see |
|---|---|---|
| Student | Create complaints, attach a photo, see own complaint history/status, read notices, mark alerts read | Own profile and complaints; published, unexpired notices; own notifications |
| Warden/admin | Review and filter complaints, assign maintenance staff, update status, add updates, publish/edit/archive notices | Hostel complaints, staff directory, notices, relevant activity |
| Maintenance staff | View assigned complaints, change work status, add progress/resolution notes | Assigned complaints and the information needed to complete them |

For a class/demo deployment, account creation should be controlled by an admin or use a pre-created set of accounts. Role is assigned by trusted setup, never selected by a user at sign-up.

## Main flows

### Student reports a repair

Sign in → Student dashboard → New complaint → choose category, enter room and description, optionally attach a photo → Submit → complaint appears as **Pending** → receive in-app updates as it is assigned, worked on and resolved.

### Warden handles work

Sign in → Warden dashboard → open pending queue → review details/photo → assign staff → set **In Progress** and add an update → verify completion → set **Resolved**. The student receives an in-app notification at each status change.

### Warden publishes a notice

Notices → Create notice → add title/body/category, urgency and optional expiry → Publish → students see it in the notice feed and receive an in-app alert. Expired or archived notices leave the current feed but remain available to admins.

### Maintenance staff completes a job

Sign in → Assigned to me → open complaint → add progress note/change status → submit resolution update → warden/student can see the latest update.

## Screen map

| Area | Mobile layout | Laptop layout |
|---|---|---|
| Sign in | Compact form, clear role-neutral entry | Centered form and short product introduction |
| Student home | Bottom navigation; status summary cards; urgent notices; recent complaints | Side navigation; summary cards; recent complaints and notice panel in columns |
| Complaints list/detail | Stacked cards; status timeline; full-width actions | Filterable table/list with a detail panel and timeline |
| New complaint | Short stepwise form; camera/photo upload; room and category easy to reach | Single-page form with preview and clear submit action |
| Notices | White pinboard with tactile pinned-paper cards, urgent markers, category filters and tap-to-open details | Same pinboard, with search/sort controls and a warden management action |
| Warden dashboard | Compact queue, priority/status filters, prominent pending count | Work queue/table, filters and workload summary; create-notice action |
| Staff assignments | Assigned-job cards and simple status controls | Assigned jobs table/list and detail panel |
| Notifications/profile | Simple list and account actions | Notification panel/list and account actions |

Navigation adapts by role. On mobile it uses a compact bottom bar plus a profile/menu sheet; on larger screens it uses a persistent side rail. Forms, tables and detail screens must remain usable at narrow widths without horizontal scrolling.

### Notice board visual direction

Use a clean white page and white notice-board surface, inspired by a physical campus pinboard. Display announcements as pinned paper cards in a responsive grid, with subtle rotations, soft pastel paper colors, and a small pin detail. Keep urgent notices visibly marked. Cards should support category filtering, search, sorting, pin/unpin, read/unread, and opening the full announcement. Wardens can add a notice through a short form; newly posted notices appear pinned at the top. This is a visual treatment for interactive controls, not drag-and-drop: the controls remain easy to use with a mouse, touch screen, and keyboard.

## Data map

The working prototype uses SQLite behind a same-origin Python HTTP API. It creates the database at `work/hostelconnect.sqlite3`, so separate browser sessions using this server share the same data. For internet-wide hosting, migrate this schema to hosted PostgreSQL. The initial tables are:

- **profiles** — `id` (auth user ID), `full_name`, `email`, `role`, `room_number` (student only), `created_at`.
- **complaints** — `id`, `created_by`, `category` (electrical/plumbing/Wi-Fi/furniture/other), `room_number`, `description`, `photo_path` (optional), `status` (pending/in_progress/resolved), `assigned_to` (optional staff profile), `created_at`, `updated_at`, `resolved_at` (optional).
- **complaint_updates** — `id`, `complaint_id`, `author_id`, `status` (optional), `message`, `created_at`. Append an update on assignment, status changes, and work notes to make a readable timeline.
- **notices** — `id`, `created_by`, `title`, `body`, `category`, `priority` (normal/urgent), `published_at`, `expires_at` (optional), `archived_at` (optional).
- **notifications** — `id`, `user_id`, `type`, `title`, `body`, `complaint_id` or `notice_id` (optional), `created_at`, `read_at` (optional).

Relationships: one profile creates many complaints; a complaint can be assigned to one staff profile and has many updates; notices belong to a warden/admin profile; each notification belongs to one recipient and can link to its source complaint or notice.

## Prototype setup

- **UI:** responsive web app served by the Python API; one deployment works on desktop and mobile browsers.
- **Database and accounts:** SQLite for a zero-setup class prototype, with 12 seeded accounts. The server can be shared with devices on the same Wi-Fi; for internet-wide access, migrate to hosted PostgreSQL and configure HTTPS.
- **Photo uploads:** image data is stored with the complaint and returned only through a permission-checked API route.
- **Access control:** server API checks roles and ownership for complaints, assignment, notices, and photo access. Demo role accounts are pre-created; users cannot grant themselves a role.
- **Notifications:** in-app notification records are created for new notices, complaint submissions and complaint changes.
- **Demo size:** 7 student, 2 warden and 3 maintenance accounts, with sample complaints in each status and urgent/normal notices.

## Prototype acceptance checklist

- Student, warden/admin and maintenance accounts can sign in and see role-appropriate screens.
- A student can submit a complaint with a room and category, optionally attach a photo, then see it after refreshing or signing in on another device.
- A warden can assign the complaint to a staff account and move it through **Pending → In Progress → Resolved** with a visible update history.
- The student and assigned staff see the appropriate complaint and an in-app alert after a change.
- A warden can publish an urgent notice with an expiry; students can see it, and expired/archived notices do not appear as current.
- Mobile and laptop layouts support the same core actions.
- Role checks are enforced by the database, not only by hiding UI controls.

## Decisions to confirm while implementation starts

1. **Demo access:** pre-created accounts for the project demonstration, or student self-registration with admin approval?
2. **Hosting:** Supabase hosted database (recommended for a shared 10–15-person demo), or a database/hosting service required by the course?
3. **Notice audience:** one hostel for Version 1, or multiple hostels with notices scoped by hostel?

Unless course constraints say otherwise, a sensible first build uses one hostel, pre-created demo accounts, and Supabase hosted services.
