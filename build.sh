!#/usr/bin/env bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/database
make install && psql -a -d $DATABASE_URL -f database.sql