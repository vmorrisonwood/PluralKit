-- SCHEMA VERSION 6: 2020-03-21
alter table systems add column pings bool not null default true;
update info set schema_version = 6;