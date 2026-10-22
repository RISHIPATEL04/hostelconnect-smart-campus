-- HostelConnect hosted database schema (Supabase PostgreSQL)
-- Run this file once in Supabase Dashboard → SQL Editor before deploying.
-- The database connection string stays server-side in Vercel as DATABASE_URL.

create table if not exists public.profiles (
  id text primary key,
  full_name text not null,
  email text unique not null,
  role text not null check (role in ('student','warden','maintenance')),
  room_number text,
  password_hash text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.sessions (
  token text primary key,
  user_id text not null references public.profiles(id) on delete cascade,
  expires_at bigint not null
);

create table if not exists public.notices (
  id text primary key,
  created_by text not null references public.profiles(id),
  title text not null,
  body text not null,
  category text not null check (category in ('Hostel','Events','Academic','Facilities','Lost & found')),
  priority text not null default 'Normal' check (priority in ('Normal','Urgent')),
  expires_at timestamptz,
  archived_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.notice_reads (
  notice_id text not null references public.notices(id) on delete cascade,
  user_id text not null references public.profiles(id) on delete cascade,
  read_at timestamptz not null default now(),
  primary key (notice_id,user_id)
);

create table if not exists public.notice_saves (
  notice_id text not null references public.notices(id) on delete cascade,
  user_id text not null references public.profiles(id) on delete cascade,
  saved_at timestamptz not null default now(),
  primary key (notice_id,user_id)
);

create table if not exists public.complaints (
  id text primary key,
  created_by text not null references public.profiles(id),
  category text not null check (category in ('Electrical','Plumbing','Wi-Fi','Furniture','Other')),
  room_number text not null,
  description text not null,
  photo_data text,
  photo_mime text,
  status text not null default 'Pending' check (status in ('Pending','In Progress','Resolved')),
  assigned_to text references public.profiles(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  resolved_at timestamptz
);

create table if not exists public.complaint_updates (
  id text primary key,
  complaint_id text not null references public.complaints(id) on delete cascade,
  author_id text not null references public.profiles(id),
  status text,
  message text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.notifications (
  id text primary key,
  user_id text not null references public.profiles(id) on delete cascade,
  title text not null,
  body text not null,
  complaint_id text references public.complaints(id) on delete cascade,
  notice_id text references public.notices(id) on delete cascade,
  created_at timestamptz not null default now(),
  read_at timestamptz
);

create index if not exists idx_complaints_creator on public.complaints(created_by,created_at desc);
create index if not exists idx_complaints_assignee on public.complaints(assigned_to,status);
create index if not exists idx_notifications_user on public.notifications(user_id,created_at desc);

-- The app accesses these tables only from its server-side Vercel Function.
-- Enable RLS with no browser policies; the private database connection is never
-- bundled into the frontend. The server-side database owner bypasses these rules.
alter table public.profiles enable row level security;
alter table public.sessions enable row level security;
alter table public.notices enable row level security;
alter table public.notice_reads enable row level security;
alter table public.notice_saves enable row level security;
alter table public.complaints enable row level security;
alter table public.complaint_updates enable row level security;
alter table public.notifications enable row level security;
