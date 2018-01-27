create table scoremanager (
    acct text primary key not null,
    score_getnum integer,
    score_fav integer,
    datetime_fav text,
    score_boost integer,
    datetime_boost text,
    score_reply integer,
    score_func integer
);
