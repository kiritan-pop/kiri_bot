create table bottlemail (
    id integer primary key autoincrement not null,
    acct text not null,
    msg text not null,
    count integer,
    send_fg integer,
    dest text,
    reply_id integer
);
