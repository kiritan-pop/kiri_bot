create table statuses (
    id integer primary key not null,
    date integer,
    time integer,
    content text,
    acct text,
    display_name text,
    media_attachments text
);
create index acct_idx on statuses(acct);
create index date_idx on statuses(date);
create index time_idx on statuses(time);
create index datetime_idx on statuses(date,time);
