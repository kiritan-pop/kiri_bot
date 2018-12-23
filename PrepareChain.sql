drop table if exists chain_freqs;
create table chain_freqs (
    id integer primary key autoincrement not null,
    prefix1 text not null,
    prefix2 text not null,
    suffix text not null,
    freq integer not null
);
create index prefix1_idx on chain_freqs(prefix1);
create index prefix2_idx on chain_freqs(prefix2);
create index prefix_idx on chain_freqs(prefix1,prefix2);
