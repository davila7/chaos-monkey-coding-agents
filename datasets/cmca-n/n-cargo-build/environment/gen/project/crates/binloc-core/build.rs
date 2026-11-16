//! Compiles data/sites.csv into $OUT_DIR/sites.rs (the SITES table of src/lib.rs).

use std::collections::BTreeSet;
use std::env;
use std::fmt::Write as _;
use std::fs;
use std::path::Path;

const TABLE: &str = "data/sites.csv";

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed={}", TABLE);
    let text = fs::read_to_string(TABLE).unwrap_or_else(|e| panic!("{}: {}", TABLE, e));
    let mut seen = BTreeSet::new();
    let mut out = String::from("static SITES: &[Site] = &[\n");
    for (n, line) in text.lines().enumerate() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') || line.starts_with("site,") {
            continue;
        }
        let at = format!("{}:{}", TABLE, n + 1);
        let f: Vec<&str> = line.split(',').map(str::trim).collect();
        if f.len() != 6 {
            panic!("{}: expected 6 fields, found {}", at, f.len());
        }
        let code = f[0];
        if code.len() != 3 || !code.bytes().all(|b| b.is_ascii_uppercase() || b.is_ascii_digit()) {
            panic!("{}: bad site code {:?}", at, code);
        }
        if !seen.insert(code.to_string()) {
            panic!("{}: site {} listed twice", at, code);
        }
        let aisles = number(&at, f[1], 99);
        let bays = number(&at, f[2], 999);
        let levels = f[3];
        let distinct: BTreeSet<char> = levels.chars().collect();
        if levels.is_empty() || !levels.bytes().all(|b| b.is_ascii_uppercase()) || distinct.len() != levels.len() {
            panic!("{}: bad levels {:?}", at, levels);
        }
        let serpentine = match f[4] {
            "serpentine" => true,
            "straight" => false,
            other => panic!("{}: bad layout {:?}", at, other),
        };
        let zone_width = number(&at, f[5], 99);
        writeln!(
            out,
            "    Site {{ code: {:?}, aisles: {}, bays: {}, levels: {:?}, serpentine: {}, zone_width: {} }},",
            code, aisles, bays, levels, serpentine, zone_width
        )
        .unwrap();
    }
    out.push_str("];\n");
    let dest = Path::new(&env::var("OUT_DIR").unwrap()).join("sites.rs");
    fs::write(&dest, out).unwrap_or_else(|e| panic!("{}: {}", dest.display(), e));
}

fn number(at: &str, s: &str, max: u32) -> u32 {
    match s.parse::<u32>() {
        Ok(v) if (1..=max).contains(&v) => v,
        _ => panic!("{}: expected a number from 1 to {}, found {:?}", at, max, s),
    }
}
