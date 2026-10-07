-- =================================================================
-- PROJECT S.M.I.L.E. - SUPABASE ROW LEVEL SECURITY (RLS) HARDENING
-- =================================================================
-- Purpose:
--   Resolves all "RLS Disabled in Public" ERRORS and WARNINGS in the
--   Supabase Security Advisor (https://supabase.com/dashboard/project/ukhmrgbkrfawgszltzsr/advisors/security)
--
-- How it works:
--   1. Enables Row Level Security (RLS) on all tables in the 'public' schema.
--   2. Blocks unauthorized anonymous HTTP queries via PostgREST (anon key).
--   3. Keeps 100% full read/write access for your Flask / SQLAlchemy backend
--      on Vercel because the Flask app connects directly as the table owner ('postgres').
--
-- Instructions:
--   1. Open Supabase Dashboard -> Project "jovenneljed-epic's Project"
--   2. Click on "SQL Editor" in the left sidebar (icon with >_ )
--   3. Paste this entire script into a New Query window
--   4. Click "Run" (or Ctrl + Enter)
--   5. Go to "Security Advisor" and click "Refresh" -> All 11 errors will be GONE!
-- =================================================================

-- Step 1: Explicitly enable RLS on all known Project S.M.I.L.E. tables
ALTER TABLE IF EXISTS public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.students ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.sections ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.attendance_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.staff_attendance_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.sms_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.excuse_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.announcements ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.school_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.pricing_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.payment_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.push_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.parent_device_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.parent_notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.push_workflows ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.workflow_executions ENABLE ROW LEVEL SECURITY;

-- Step 2: Dynamically enable RLS on ANY remaining table in the public schema
DO $$
DECLARE
    tbl record;
BEGIN
    FOR tbl IN 
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public'
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;', tbl.tablename);
    END LOOP;
END $$;

-- Step 3: Grant explicit service role bypass policy (optional defense-in-depth)
-- This ensures that any Supabase studio / service_role operations maintain full access.
DO $$
DECLARE
    tbl record;
BEGIN
    FOR tbl IN 
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public'
    LOOP
        -- Check if policy already exists to prevent duplicate error
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies 
            WHERE schemaname = 'public' 
              AND tablename = tbl.tablename 
              AND policyname = 'service_role_all_access'
        ) THEN
            EXECUTE format('CREATE POLICY "service_role_all_access" ON public.%I FOR ALL TO service_role USING (true) WITH CHECK (true);', tbl.tablename);
        END IF;
    END LOOP;
END $$;

-- Verification Query: Check that all public tables now have rowsecurity = true
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY tablename ASC;
