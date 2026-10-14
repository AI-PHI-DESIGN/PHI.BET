-- Mis Plazos · preparación de la base de datos en Supabase.
-- Pegar entero en Supabase → SQL Editor → New query → Run. Se puede ejecutar más de una vez sin problema.

-- 1) Una tabla con todos los datos de cada cuenta: cada plazo es una fila, y abogados, festivos y perfil una fila cada uno.
create table if not exists public.registros (
  user_id    uuid        not null default auth.uid() references auth.users on delete cascade,
  tipo       text        not null,               -- 'plazo' | 'kv'
  id         text        not null,               -- id del plazo, o 'abogados' | 'festivos' | 'perfil'
  datos      jsonb       not null,
  borrado    boolean     not null default false,
  updated_at timestamptz not null default now(),
  primary key (user_id, tipo, id)
);
create index if not exists registros_cambios on public.registros (user_id, updated_at);

-- La fecha de cambio la pone el servidor, así los dispositivos saben qué ha cambiado desde la última vez.
create or replace function public.registros_tocar() returns trigger language plpgsql as $$
begin new.updated_at := clock_timestamp(); return new; end $$;
drop trigger if exists registros_tocar on public.registros;
create trigger registros_tocar before insert or update on public.registros for each row execute function public.registros_tocar();

-- 2) Cada cuenta solo puede ver y tocar sus propias filas.
alter table public.registros enable row level security;
drop policy if exists "cada cuenta lo suyo" on public.registros;
create policy "cada cuenta lo suyo" on public.registros for all to authenticated
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- 3) Los PDF de las notificaciones, en un almacén privado: <id de la cuenta>/<id del plazo>.pdf
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('pdfs', 'pdfs', false, 52428800, array['application/pdf'])
on conflict (id) do nothing;

drop policy if exists "pdfs: ver los propios" on storage.objects;
drop policy if exists "pdfs: subir los propios" on storage.objects;
drop policy if exists "pdfs: cambiar los propios" on storage.objects;
drop policy if exists "pdfs: borrar los propios" on storage.objects;
create policy "pdfs: ver los propios" on storage.objects for select to authenticated
  using (bucket_id = 'pdfs' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "pdfs: subir los propios" on storage.objects for insert to authenticated
  with check (bucket_id = 'pdfs' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "pdfs: cambiar los propios" on storage.objects for update to authenticated
  using (bucket_id = 'pdfs' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "pdfs: borrar los propios" on storage.objects for delete to authenticated
  using (bucket_id = 'pdfs' and (storage.foldername(name))[1] = auth.uid()::text);
