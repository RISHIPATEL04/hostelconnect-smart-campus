# Deploy HostelConnect

This prototype can use Vercel for the responsive web app and Python API, with Supabase PostgreSQL as its persistent shared database.

## 1. Create the database

1. Create a Supabase project.
2. In **SQL Editor**, run [`supabase/schema.sql`](supabase/schema.sql).
3. Open **Connect** in the Supabase project and copy the **Transaction pooler** connection URI (port `6543`). Do not use the direct database connection for a serverless deployment.

## 2. Deploy on Vercel

1. Import this GitHub repository into Vercel. The project root is the repository root.
2. Add an environment variable named `DATABASE_URL` for **Production**, **Preview**, and **Development**. Set it to the Supabase Transaction pooler URI, including `?sslmode=require`.
3. Deploy. Vercel serves the frontend at `/` and the Python API through `/api/*`.

The database URI is private server-side configuration. Never add the real URI to `.env.example`, frontend JavaScript, a commit, or a public issue. Vercel’s settings encrypt environment variables at rest. Redeploy after changing the value.

## 3. Create the first warden

Create an account through the app’s student signup screen. In Supabase SQL Editor, promote that account:

```sql
update public.profiles
set role = 'warden'
where email = 'warden@your-campus.example';
```

Use the exact email entered during signup. The app intentionally does not allow public visitors to choose the warden or maintenance role. The warden can publish notices and manage complaints. Promote maintenance accounts the same way by setting `role = 'maintenance'`.

## 4. Local development

The local SQLite workflow remains available:

```powershell
python server.py
```

For local PostgreSQL-backed development, set `DATABASE_URL` in your shell to a development database before starting the server. Do not point local development at production data.

## Prototype constraints

- New signup is capped at 15 total accounts for the classroom prototype.
- Hosted Supabase starts with an empty database; the local SQLite demo accounts are not copied to it.
- Complaint photos are currently stored in database rows. This is suitable only for a small demonstration; use object storage for a larger deployment.
- Vercel Hobby is intended for personal, non-commercial use. Check the current Vercel plan terms before using it for a campus-wide production service.
- Supabase’s free projects may pause after inactivity; check its current plan limits and resume the project if needed.
- Demo SQLite accounts share the password `hostel123`; never reuse that password for real users.
