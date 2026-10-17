-- Species hang under a genus, subspecies and varieties under a species, with the same genus.
SELECT t.taxon_id, t.rank, p.taxon_id AS parent_id, p.rank AS parent_rank
FROM taxon AS t
LEFT JOIN taxon AS p ON p.taxon_id = t.parent_id
WHERE (t.rank = 'genus' AND t.parent_id IS NOT NULL)
   OR (t.rank = 'species' AND (p.rank IS NOT 'genus' OR p.genus <> t.genus))
   OR (t.rank IN ('subspecies', 'variety')
       AND (p.rank IS NOT 'species' OR p.genus <> t.genus OR p.epithet <> t.epithet));
