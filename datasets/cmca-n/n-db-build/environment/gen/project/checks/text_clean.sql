-- Text values must not contain control characters (U+0000 to U+001F, U+007F to U+009F)
-- or the replacement character U+FFFD left by a wrong decoding.
WITH t(tbl, id, value) AS (
    SELECT 'collector', collector_id, name FROM collector
    UNION ALL SELECT 'collector', collector_id, initials FROM collector
    UNION ALL SELECT 'site', code, name FROM site
    UNION ALL SELECT 'taxon', taxon_id, genus FROM taxon
    UNION ALL SELECT 'taxon', taxon_id, epithet FROM taxon
    UNION ALL SELECT 'taxon', taxon_id, infra FROM taxon
    UNION ALL SELECT 'specimen', catalog_no, habitat FROM specimen
)
SELECT tbl, id, value
FROM t
WHERE value GLOB '*[' || char(1) || '-' || char(31) || char(127) || '-' || char(159) || char(65533) || ']*'
   OR instr(value, char(0)) > 0;
