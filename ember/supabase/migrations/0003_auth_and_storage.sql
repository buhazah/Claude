-- Auto-create profile + free subscription row on signup
create or replace function handle_new_user() returns trigger
language plpgsql security definer as $$
begin
  insert into public.profiles (id, phone) values (new.id, new.phone);
  insert into public.subscriptions (user_id, tier) values (new.id, 'spark');
  return new;
end $$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function handle_new_user();

-- Storage buckets
insert into storage.buckets (id, name, public) values
  ('photos', 'photos', true),
  ('voice', 'voice', false)
on conflict (id) do nothing;

create policy "own photo upload" on storage.objects for insert
  with check (bucket_id = 'photos' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "photos readable" on storage.objects for select
  using (bucket_id = 'photos');
create policy "own voice upload" on storage.objects for insert
  with check (bucket_id = 'voice' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "own voice read" on storage.objects for select
  using (bucket_id = 'voice' and (storage.foldername(name))[1] = auth.uid()::text);
