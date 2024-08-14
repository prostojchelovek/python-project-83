DROP TABLE IF EXISTS urls;
DROP TABLE IF EXISTS url_checks;

CREATE TABLE urls (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    name VARCHAR(255),
    created_at DATE
);

CREATE TABLE url_checks (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    url_id BIGINT REFERENCES urls (id) ON DELETE CASCADE,
    status_code int,
    h1 VARCHAR(255),
    title VARCHAR(255),
    description VARCHAR(255),
    created_at DATE
);