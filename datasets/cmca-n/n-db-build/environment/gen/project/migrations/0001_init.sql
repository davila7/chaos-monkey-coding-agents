-- Herbarium specimen database: first schema.

CREATE TABLE collector (
    collector_id INTEGER PRIMARY KEY,
    name         TEXT NOT NULL
);

CREATE TABLE taxon (
    taxon_id  INTEGER PRIMARY KEY,
    parent_id INTEGER REFERENCES taxon (taxon_id),
    rank      TEXT NOT NULL,
    genus     TEXT NOT NULL,
    epithet   TEXT
);

CREATE TABLE site (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE specimen (
    specimen_id  INTEGER PRIMARY KEY,
    catalog_no   TEXT NOT NULL UNIQUE,
    taxon_id     INTEGER NOT NULL REFERENCES taxon (taxon_id),
    collector_id INTEGER REFERENCES collector (collector_id),
    site_code    TEXT NOT NULL REFERENCES site (code),
    collected_on TEXT,
    basis        TEXT NOT NULL
);
