-- Sabeel Homeo Clinic chatbot schema
-- Run this in Supabase SQL editor.

create extension if not exists vector;
create extension if not exists pgcrypto;

create table if not exists conversations (
    id uuid primary key default gen_random_uuid(),
    channel text not null,
    external_id text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_conversations_channel on conversations(channel);
create index if not exists idx_conversations_external_id on conversations(external_id);

create table if not exists messages (
    id bigint generated always as identity primary key,
    conversation_id text not null,
    role text not null check (role in ('system', 'user', 'assistant', 'tool')),
    content text not null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_messages_conversation_id on messages(conversation_id);
create index if not exists idx_messages_created_at on messages(created_at);

create table if not exists appointments (
    id uuid primary key default gen_random_uuid(),
    patient_name text not null,
    patient_phone text,
    preferred_date text,
    preferred_time text,
    reason text,
    channel text,
    conversation_id text,
    requested_at timestamptz,
    status text not null default 'pending',
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_appointments_status on appointments(status);
create index if not exists idx_appointments_phone on appointments(patient_phone);

create table if not exists kb_chunks (
    id text primary key,
    source_type text not null default 'wordpress',
    source_id text,
    source_url text,
    source_title text,
    content text not null,
    metadata jsonb not null default '{}'::jsonb,
    embedding vector(1536) not null,
    updated_at timestamptz not null default now()
);

create index if not exists idx_kb_chunks_source_type on kb_chunks(source_type);
create index if not exists idx_kb_chunks_source_id on kb_chunks(source_id);
create index if not exists idx_kb_chunks_embedding on kb_chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);

create or replace function match_kb_chunks(
    query_embedding vector(1536),
    match_count int default 5
)
returns table (
    id text,
    source_title text,
    source_url text,
    content text,
    similarity float
)
language sql
stable
as $$
    select
        kb.id,
        kb.source_title,
        kb.source_url,
        kb.content,
        1 - (kb.embedding <=> query_embedding) as similarity
    from kb_chunks kb
    order by kb.embedding <=> query_embedding
    limit greatest(match_count, 1);
$$;
