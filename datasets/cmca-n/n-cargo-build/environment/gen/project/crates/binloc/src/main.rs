//! binloc: checks and labels warehouse bin locations. docs/binloc.md is the reference.

use std::env;
use std::fs;
use std::io::{self, Read, Write};
use std::process;

use binloc_core::Location;
use fieldsplit::Splitter;

#[cfg(feature = "json")]
mod json;

const USAGE: &str = "usage: binloc check [--format text|json] [FILE|-]
       binloc label SITE AISLE BAY LEVEL
       binloc sites
       binloc --version
";

struct Failure {
    status: i32,
    message: String,
    usage: bool,
}

fn fail(status: i32, message: impl Into<String>) -> Failure {
    Failure { status, message: message.into(), usage: false }
}

fn usage(message: impl Into<String>) -> Failure {
    Failure { status: 2, message: message.into(), usage: true }
}

fn write_failed(e: io::Error) -> Failure {
    fail(2, format!("cannot write output: {}", e))
}

#[cfg_attr(not(feature = "json"), allow(dead_code))]
enum Format {
    Text,
    Json,
}

#[cfg_attr(not(feature = "json"), allow(dead_code))]
pub(crate) enum Row {
    Valid { line: usize, loc: Location },
    Rejected { line: usize, error: String },
}

fn version() -> String {
    let commit = match option_env!("BUILD_COMMIT") {
        Some(c) if !c.is_empty() => c,
        _ => "unknown",
    };
    format!("binloc {} (commit {})", env!("CARGO_PKG_VERSION"), commit)
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());
    let mut status = match run(&args, &mut out) {
        Ok(status) => status,
        Err(f) => {
            eprintln!("binloc: {}", f.message);
            if f.usage {
                eprint!("{}", USAGE);
            }
            f.status
        }
    };
    if let Err(e) = out.flush() {
        eprintln!("binloc: cannot write output: {}", e);
        status = 2;
    }
    drop(out);
    process::exit(status);
}

fn run(args: &[String], out: &mut dyn Write) -> Result<i32, Failure> {
    match args.first().map(String::as_str) {
        None => Err(usage("no command")),
        Some("--help") | Some("-h") | Some("help") => {
            out.write_all(USAGE.as_bytes()).map_err(write_failed)?;
            Ok(0)
        }
        Some("--version") | Some("-V") => {
            writeln!(out, "{}", version()).map_err(write_failed)?;
            Ok(0)
        }
        Some("check") => check(&args[1..], out),
        Some("label") => label(&args[1..], out),
        Some("sites") if args.len() == 1 => sites(out),
        Some("sites") => Err(usage("sites takes no arguments")),
        Some(other) => Err(usage(format!("unknown command {:?}", other))),
    }
}

fn parse_format(value: &str) -> Result<Format, Failure> {
    match value {
        "text" => Ok(Format::Text),
        "json" => json_format(),
        other => Err(usage(format!("unknown format {:?}", other))),
    }
}

#[cfg(feature = "json")]
fn json_format() -> Result<Format, Failure> {
    Ok(Format::Json)
}

#[cfg(not(feature = "json"))]
fn json_format() -> Result<Format, Failure> {
    Err(fail(2, "json output is not available in this build"))
}

fn read_input(path: Option<&str>) -> Result<Vec<u8>, Failure> {
    match path {
        None | Some("-") => {
            let mut buf = Vec::new();
            io::stdin().read_to_end(&mut buf).map_err(|e| fail(2, format!("cannot read standard input: {}", e)))?;
            Ok(buf)
        }
        Some(p) => fs::read(p).map_err(|e| fail(2, format!("cannot read {}: {}", p, e))),
    }
}

fn check(args: &[String], out: &mut dyn Write) -> Result<i32, Failure> {
    let mut format = Format::Text;
    let mut path: Option<&str> = None;
    let mut i = 0;
    while i < args.len() {
        let a = args[i].as_str();
        if a == "--format" {
            let value = args.get(i + 1).ok_or_else(|| usage("--format needs a value"))?;
            format = parse_format(value)?;
            i += 2;
            continue;
        }
        if let Some(value) = a.strip_prefix("--format=") {
            format = parse_format(value)?;
        } else if a.len() > 1 && a.starts_with('-') {
            return Err(usage(format!("unknown option {:?}", a)));
        } else if path.is_some() {
            return Err(usage("more than one input"));
        } else {
            path = Some(a);
        }
        i += 1;
    }

    let data = read_input(path)?;
    let text = String::from_utf8(data).map_err(|_| fail(2, "input is not UTF-8"))?;
    let text = text.strip_prefix('\u{feff}').unwrap_or(&text);
    let mut lines: Vec<&str> = text.split('\n').collect();
    if lines.last() == Some(&"") {
        lines.pop();
    }
    let lines: Vec<&str> = lines.into_iter().map(|l| l.strip_suffix('\r').unwrap_or(l)).collect();
    if lines.is_empty() {
        return Err(fail(2, "no header row"));
    }

    let splitter = Splitter::new(',').trim(true);
    let header = splitter.split(lines[0]).map_err(|e| fail(2, format!("line 1: {}", e)))?;
    let columns: Vec<usize> = (0..header.len()).filter(|&c| header[c].eq_ignore_ascii_case("location")).collect();
    let col = match columns.as_slice() {
        [c] => *c,
        [] => return Err(fail(2, "no \"location\" column")),
        _ => return Err(fail(2, "more than one \"location\" column")),
    };

    let (mut checked, mut rejected) = (0, 0);
    for (i, line) in lines.iter().enumerate().skip(1) {
        let n = i + 1;
        if line.trim_matches(|c| c == ' ' || c == '\t').is_empty() {
            continue;
        }
        checked += 1;
        let row = match splitter.split(line) {
            Err(e) => Row::Rejected { line: n, error: e.to_string() },
            Ok(f) if f.len() != header.len() => Row::Rejected {
                line: n,
                error: format!("expected {} fields, found {}", header.len(), f.len()),
            },
            Ok(f) => match binloc_core::parse(&f[col]) {
                Ok(loc) => Row::Valid { line: n, loc },
                Err(e) => Row::Rejected { line: n, error: e.to_string() },
            },
        };
        if let Row::Rejected { .. } = row {
            rejected += 1;
        }
        emit(&format, &row, out).map_err(write_failed)?;
    }
    eprintln!("binloc: {} checked, {} rejected", checked, rejected);
    Ok(if rejected > 0 { 1 } else { 0 })
}

fn emit(format: &Format, row: &Row, out: &mut dyn Write) -> io::Result<()> {
    match (format, row) {
        (Format::Text, Row::Valid { loc, .. }) => {
            writeln!(out, "{}\t{}\tZ{}\t{}", loc.code(), loc.site.code, loc.zone(), loc.sequence())
        }
        (Format::Text, Row::Rejected { line, error }) => {
            eprintln!("binloc: line {}: {}", line, error);
            Ok(())
        }
        (Format::Json, row) => emit_json(row, out),
    }
}

#[cfg(feature = "json")]
fn emit_json(row: &Row, out: &mut dyn Write) -> io::Result<()> {
    json::write_row(row, out)
}

#[cfg(not(feature = "json"))]
fn emit_json(_row: &Row, _out: &mut dyn Write) -> io::Result<()> {
    unreachable!("json output is not built in")
}

/// The number printed under the bar code of a label: the pick sequence in seven digits and
/// its Luhn check digit.
fn scan_number(loc: &Location) -> String {
    let digits = format!("{:07}", loc.sequence());
    let check = checkchar::luhn(&digits).expect("seven decimal digits");
    format!("{}{}", digits, check)
}

fn label(args: &[String], out: &mut dyn Write) -> Result<i32, Failure> {
    if args.len() != 4 {
        return Err(usage("label needs SITE AISLE BAY LEVEL"));
    }
    let loc = binloc_core::complete(&args.join("-")).map_err(|e| fail(1, e.to_string()))?;
    writeln!(out, "{}\t{}", loc.code(), scan_number(&loc)).map_err(write_failed)?;
    Ok(0)
}

fn sites(out: &mut dyn Write) -> Result<i32, Failure> {
    for s in binloc_core::sites() {
        let layout = if s.serpentine { "serpentine" } else { "straight" };
        writeln!(out, "{}\t{}\t{}\t{}\t{}\t{}", s.code, s.aisles, s.bays, s.levels, layout, s.zone_width)
            .map_err(write_failed)?;
    }
    Ok(0)
}
