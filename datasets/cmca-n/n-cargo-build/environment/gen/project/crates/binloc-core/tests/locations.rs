use binloc_core::{check_char, complete, find_site, parse, sites, LocError};

#[test]
fn site_table_is_compiled_in() {
    let codes: Vec<&str> = sites().iter().map(|s| s.code).collect();
    assert!(codes.contains(&"NB2") && codes.contains(&"QM8"), "{:?}", codes);
    let qm8 = find_site("qm8").expect("QM8");
    assert_eq!((qm8.aisles, qm8.bays, qm8.levels, qm8.serpentine), (20, 90, "BCDEFGH", false));
}

#[test]
fn check_characters() {
    let nb2 = find_site("NB2").unwrap();
    assert_eq!(check_char(nb2, 7, 31, 'C'), 'A');
    assert_eq!(check_char(nb2, 1, 1, 'A'), '8');
    assert_eq!(check_char(nb2, 1, 36, 'B'), '*');
    assert_eq!(check_char(find_site("HX4").unwrap(), 8, 25, 'B'), '5');
}

#[test]
fn parse_normalizes() {
    let loc = parse("  nb2-7-31-c-a\t").unwrap();
    assert_eq!(loc.code(), "NB2-07-031-C-A");
    assert_eq!((loc.zone(), loc.sequence()), (2, 1953));
    assert_eq!(parse("NB2-01-036-B-*").unwrap().sequence(), 177);
}

#[test]
fn serpentine_and_straight_sequences() {
    assert_eq!(parse("NB2-08-031-C-F").unwrap().sequence(), 2248);
    assert_eq!(parse("NB2-24-060-E-S").unwrap().sequence(), 6905);
    assert_eq!(parse("NB7-02-005-D-H").unwrap().sequence(), 180);
    assert_eq!(parse("QM8-20-090-H-1").unwrap().zone(), 4);
}

#[test]
fn errors() {
    assert_eq!(parse("NB2-07-031-C-B"), Err(LocError::Check { found: 'B', expected: 'A' }));
    assert_eq!(parse("NB2-07-031-C"), Err(LocError::MissingCheck { expected: 'A' }));
    assert_eq!(parse("XX1-07-031-C-A"), Err(LocError::UnknownSite("XX1".into())));
    assert_eq!(parse("NB2-25-031-C-A").unwrap_err().to_string(), "aisle 25 is outside NB2 (1-24)");
    assert_eq!(parse("QM8-01-001-A-0").unwrap_err().to_string(), "level A is not a level of QM8 (BCDEFGH)");
    assert_eq!(parse("NB2-07-0031-C-A").unwrap_err().to_string(), "malformed location \"NB2-07-0031-C-A\"");
}

#[test]
fn complete_adds_the_check_character() {
    assert_eq!(complete("kd3-16-1-f").unwrap().code(), "KD3-16-001-F-4");
    assert!(complete("KD3-16-001-F-4").is_err());
}
