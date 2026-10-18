-- Basis of record as words instead of registry codes, enforced by a CHECK constraint.

CREATE TABLE specimen_new (
    specimen_id  INTEGER PRIMARY KEY,
    catalog_no   TEXT NOT NULL UNIQUE,
    taxon_id     INTEGER NOT NULL REFERENCES taxon (taxon_id),
    collector_id INTEGER REFERENCES collector (collector_id),
    site_code    TEXT NOT NULL REFERENCES site (code),
    collected_on TEXT,
    basis        TEXT NOT NULL CHECK (basis IN ('preserved', 'living', 'tissue', 'image', 'seed')),
    elevation_ft INTEGER
);
INSERT INTO specimen_new
    SELECT specimen_id, catalog_no, taxon_id, collector_id, site_code, collected_on,
           CASE basis WHEN 'PS' THEN 'preserved' WHEN 'LS' THEN 'living' WHEN 'TS' THEN 'tissue'
                      WHEN 'IM' THEN 'image' WHEN 'SD' THEN 'seed' ELSE basis END,
           elevation_ft
    FROM specimen;
DROP TABLE specimen;
ALTER TABLE specimen_new RENAME TO specimen;
CREATE INDEX idx_specimen_taxon ON specimen (taxon_id);
CREATE INDEX idx_specimen_collector ON specimen (collector_id);
