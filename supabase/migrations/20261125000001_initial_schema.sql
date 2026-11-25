-- WasteWise initial schema
-- Tables: profiles, predictions, model_metrics, feedback
-- Security: RLS on every table; users can only touch their own rows.
-- Storage: private buckets `waste-images` and `avatars`, path-scoped to auth.uid().

-- ---------------------------------------------------------------------------
-- helpers
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- profiles
-- ---------------------------------------------------------------------------
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  full_name text check (char_length(full_name) <= 120),
  email text,
  avatar_url text,                       -- storage path inside the private `avatars` bucket
  preferred_language text not null default 'en' check (preferred_language in ('en', 'hi')),
  theme text not null default 'system' check (theme in ('light', 'dark', 'system')),
  save_images boolean not null default true,  -- privacy: keep uploaded images in history
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger profiles_set_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

-- create a profile automatically for every new auth user
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, email, full_name)
  values (new.id, new.email, nullif(new.raw_user_meta_data ->> 'full_name', ''))
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

alter table public.profiles enable row level security;

create policy "profiles: select own" on public.profiles
  for select to authenticated using ((select auth.uid()) = id);
create policy "profiles: update own" on public.profiles
  for update to authenticated using ((select auth.uid()) = id) with check ((select auth.uid()) = id);

-- users may not change id/email/timestamps directly (email mirrors auth.users).
-- Column privileges only take effect once the table-level grant is removed.
revoke insert, update on public.profiles from anon, authenticated;
grant update (full_name, avatar_url, preferred_language, theme, save_images) on public.profiles to authenticated;

-- ---------------------------------------------------------------------------
-- predictions
-- ---------------------------------------------------------------------------
create table if not exists public.predictions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  image_path text,                       -- `<user_id>/<yyyy>/<mm>/<prediction_id>.jpg` in bucket waste-images (null if user opted out)
  predicted_category text not null check (predicted_category in
    ('organic', 'paper_cardboard', 'plastic', 'metal', 'glass', 'e_waste', 'hazardous')),
  predicted_class text,                  -- fine-grained item (nullable: only when the model supports/trusts it)
  confidence_score real not null check (confidence_score >= 0 and confidence_score <= 1),
  is_confident boolean not null,         -- false => shown to the user as "uncertain"
  top_predictions jsonb not null,        -- [{category, probability}, ...] (top 3)
  disposal_instructions jsonb not null default '{}'::jsonb,  -- {"en": [...], "hi": [...]}
  safety_precautions jsonb not null default '{}'::jsonb,     -- {"en": [...], "hi": [...]}
  recyclable boolean,
  quality_warnings jsonb not null default '[]'::jsonb,
  model_name text not null,
  model_version text not null,
  inference_time_ms real,
  created_at timestamptz not null default now(),
  constraint image_path_scoped check (image_path is null or image_path like user_id::text || '/%')
);

create index if not exists predictions_user_created_idx on public.predictions (user_id, created_at desc);
create index if not exists predictions_user_category_idx on public.predictions (user_id, predicted_category);

alter table public.predictions enable row level security;

create policy "predictions: select own" on public.predictions
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "predictions: insert own" on public.predictions
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "predictions: delete own" on public.predictions
  for delete to authenticated using ((select auth.uid()) = user_id);
-- no update policy: prediction records are immutable audit entries

-- ---------------------------------------------------------------------------
-- model_metrics (read-only for users; written by the service role / admin pipeline)
-- ---------------------------------------------------------------------------
create table if not exists public.model_metrics (
  id uuid primary key default gen_random_uuid(),
  model_name text not null,
  model_version text not null,
  accuracy real,
  precision_macro real,
  recall_macro real,
  f1_macro real,
  test_dataset text,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (model_name, model_version, test_dataset)
);

alter table public.model_metrics enable row level security;

create policy "model_metrics: read for everyone" on public.model_metrics
  for select to anon, authenticated using (true);
-- intentionally no insert/update/delete policies -> only service_role (bypasses RLS) can write

-- ---------------------------------------------------------------------------
-- feedback (stored separately; NOT automatically used as training labels)
-- ---------------------------------------------------------------------------
create table if not exists public.feedback (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  prediction_id uuid not null references public.predictions (id) on delete cascade,
  user_correctness_feedback boolean not null,      -- was the prediction correct?
  corrected_category text check (corrected_category in
    ('organic', 'paper_cardboard', 'plastic', 'metal', 'glass', 'e_waste', 'hazardous', 'other')),
  comments text check (char_length(comments) <= 1000),
  verified_label boolean not null default false,   -- set only by a reviewer before use in training
  created_at timestamptz not null default now(),
  unique (user_id, prediction_id)
);

create index if not exists feedback_prediction_idx on public.feedback (prediction_id);
create index if not exists feedback_user_idx on public.feedback (user_id);

alter table public.feedback enable row level security;

create policy "feedback: select own" on public.feedback
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "feedback: insert own for own prediction" on public.feedback
  for insert to authenticated with check (
    (select auth.uid()) = user_id
    and exists (select 1 from public.predictions p where p.id = prediction_id and p.user_id = (select auth.uid()))
  );
create policy "feedback: update own" on public.feedback
  for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "feedback: delete own" on public.feedback
  for delete to authenticated using ((select auth.uid()) = user_id);

-- users must never be able to mark their own feedback as verified
revoke insert, update on public.feedback from anon, authenticated;
grant insert (user_id, prediction_id, user_correctness_feedback, corrected_category, comments)
  on public.feedback to authenticated;
grant update (user_correctness_feedback, corrected_category, comments) on public.feedback to authenticated;

-- anon role needs nothing on user tables
revoke all on public.predictions from anon;
revoke update on public.predictions from authenticated;

-- ---------------------------------------------------------------------------
-- storage: private buckets + per-user folder policies
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('waste-images', 'waste-images', false, 5242880, array['image/jpeg', 'image/png', 'image/webp']),
  ('avatars', 'avatars', false, 2097152, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do update
  set public = excluded.public,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

create policy "waste-images: read own" on storage.objects
  for select to authenticated
  using (bucket_id = 'waste-images' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy "waste-images: upload own" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'waste-images' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy "waste-images: delete own" on storage.objects
  for delete to authenticated
  using (bucket_id = 'waste-images' and (storage.foldername(name))[1] = (select auth.uid())::text);

create policy "avatars: read own" on storage.objects
  for select to authenticated
  using (bucket_id = 'avatars' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy "avatars: upload own" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'avatars' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy "avatars: update own" on storage.objects
  for update to authenticated
  using (bucket_id = 'avatars' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy "avatars: delete own" on storage.objects
  for delete to authenticated
  using (bucket_id = 'avatars' and (storage.foldername(name))[1] = (select auth.uid())::text);
