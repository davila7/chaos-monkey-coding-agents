//! Splits one delimited record into fields.
//!
//! A field that starts with a double quote runs to the matching closing quote, may contain the
//! delimiter, and writes a literal quote as two quotes. Records never span lines.

use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Error {
    /// A quoted field has no closing quote; the column of the opening quote, from 1.
    UnterminatedQuote(usize),
    /// A quote inside an unquoted field or after a closing quote; its column, from 1.
    StrayQuote(usize),
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::UnterminatedQuote(col) => write!(f, "unterminated quote at column {}", col),
            Error::StrayQuote(col) => write!(f, "unexpected quote at column {}", col),
        }
    }
}

impl std::error::Error for Error {}

#[derive(Debug, Clone)]
pub struct Splitter {
    delim: char,
    trim: bool,
}

impl Splitter {
    pub fn new(delim: char) -> Splitter {
        Splitter { delim, trim: false }
    }

    /// Strip spaces and tabs around unquoted fields and around the quotes of quoted fields.
    pub fn trim(mut self, yes: bool) -> Splitter {
        self.trim = yes;
        self
    }

    pub fn split(&self, line: &str) -> Result<Vec<String>, Error> {
        let chars: Vec<char> = line.chars().collect();
        let mut fields = Vec::new();
        let mut i = 0;
        loop {
            let mut start = i;
            if self.trim {
                while start < chars.len() && is_blank(chars[start]) {
                    start += 1;
                }
            }
            if start < chars.len() && chars[start] == '"' {
                let (value, next) = self.quoted(&chars, start)?;
                fields.push(value);
                i = next;
            } else {
                let mut end = start;
                while end < chars.len() && chars[end] != self.delim {
                    if chars[end] == '"' {
                        return Err(Error::StrayQuote(end + 1));
                    }
                    end += 1;
                }
                let raw: String = chars[i..end].iter().collect();
                fields.push(if self.trim { raw.trim_matches(is_blank).to_string() } else { raw });
                i = end;
            }
            if i >= chars.len() {
                return Ok(fields);
            }
            i += 1;
        }
    }

    fn quoted(&self, chars: &[char], open: usize) -> Result<(String, usize), Error> {
        let mut value = String::new();
        let mut i = open + 1;
        loop {
            if i >= chars.len() {
                return Err(Error::UnterminatedQuote(open + 1));
            }
            if chars[i] == '"' {
                if chars.get(i + 1).is_some_and(|c| *c == '"') {
                    value.push('"');
                    i += 2;
                    continue;
                }
                i += 1;
                break;
            }
            value.push(chars[i]);
            i += 1;
        }
        if self.trim {
            while i < chars.len() && is_blank(chars[i]) {
                i += 1;
            }
        }
        if chars.get(i).is_some_and(|c| *c != self.delim) {
            return Err(Error::StrayQuote(i + 1));
        }
        Ok((value, i))
    }
}

/// Splits on `delim` without trimming.
pub fn split(line: &str, delim: char) -> Result<Vec<String>, Error> {
    Splitter::new(delim).split(line)
}

fn is_blank(c: char) -> bool {
    c == ' ' || c == '\t'
}
