create table statuses (
    id integer primary key not null,
    date integer,
    time integer,
    content text,
    acct text,
    display_name text,
    media_attachments text
);
