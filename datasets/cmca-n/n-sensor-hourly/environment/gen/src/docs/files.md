# Logger dumps

A logger dump is a text file of lines. Some lines are directives that say how
to read the rest; the others are data rows, one per logger sample.

    # station: KV07
    # upload: 112
    # interval: 300
    # tz: +01:00
    # firmware: 4.2.1
    # columns: time,temp,rh,pres,wspd,wdir
    # units: temp=degF pres=inHg
    2027-01-14 09:05:00,28.4,91,29.71,2.1,214
    2027-01-14 09:10:00,28.2,91,29.71,-9999,
    # sync: logger=2027-01-14 09:12:41 ref=2027-01-14T08:12:03Z
    2027-01-14 09:15:00,28.3,92,29.72,1.6,220

## 1. Bytes and lines

1.1 Dumps are UTF-8. A file can start with a byte order mark (`EF BB BF`),
which is not part of the first line.

1.2 Lines end with LF or with CR LF. Both can occur in one input directory.

1.3 Blank lines, and lines of spaces only, are ignored.

## 2. Directives and comments

2.1 A line whose first character is `#` is a directive or a comment, never a
data row.

2.2 A directive has the form `# key: value`: a `#`, optional spaces, a key of
lower-case letters, a colon, and a value that runs to the end of the line.
Spaces around the key and the value are not part of them.

2.3 A `#` line that does not have this form is a comment. A directive whose
key is not one of those in this note (for example `firmware`, `battery` or
`note`) is ignored.

## 3. Header directives

3.1 `station`: the station id, used as it is written. All files of a station
carry the same id.

3.2 `upload`: a positive whole number. Each upload of a logger gets a larger
number than the uploads before it. The numbers of one station are unique;
they are not consecutive, and they are the only reliable order of a
station's files (`clock.md` 3).

3.3 `interval`: the seconds between two samples of the logger, a divisor of
3600. All files of a station state the same interval.

3.4 `tz`: the time zone of the logger clock (`clock.md` 1).

3.5 `columns`: the names of the fields of a data row, separated by commas,
in the order the fields appear. One column is `time`; the others are names of
quantities (`quantities.md` 1). A station reports only the quantities in its
columns, and stations differ in which quantities they have and in their
order.

3.6 `units`: the units of some quantities (rule 4.2).

3.7 `station`, `upload`, `interval`, `tz` and the first `columns` line come
before the first data row of a file.

## 4. Directives inside a file

4.1 A `columns` or `units` line can appear again anywhere in a file. It
applies to the data rows after it, up to the end of the file or the next line
with the same key. Each file starts afresh: nothing carries over from another
file.

4.2 A `units` line is a list of `quantity=unit` pairs separated by spaces. It
sets the unit of the quantities it names and leaves every other quantity at
the unit it had. At the start of each file every quantity is in its
canonical unit (`quantities.md` 2) until a `units` line says otherwise.

    # units: temp=degF wspd=kn
    ...
    # units: wspd=ms

After the second line `wspd` is in m/s again and `temp` is still in
degrees Fahrenheit.

## 5. Data rows

5.1 A data row is a list of fields separated by commas, one per column of
the `columns` line in force. Spaces around a field are not part of it.

5.2 The `time` field is a logger time (`clock.md` 1), written
`YYYY-MM-DD HH:MM:SS` or `YYYY-MM-DDTHH:MM:SS`, always with seconds and
without a zone.

5.3 Every other field is a number written with a dot as decimal separator,
or a missing value (rule 6).

5.4 Within one file no two rows have the same logger time. Rows are in
logger time order.

## 6. Missing values

6.1 A field is missing when it is empty, when it is `-9999` written with any
number of zero decimals (`-9999`, `-9999.0`, `-9999.00`), when it is `NaN` in
any letter case, or when it is `---`.

6.2 A missing value is not a reading. The row it is in is still a row: it
counts for the range of hours of the station (`output.md` 2.2) and for repeated
rows (`clock.md` 3), and the other fields of the row are read as usual.

6.3 A value outside the valid range of its quantity (`quantities.md` 3) is
treated as missing.

## 7. Sync lines

7.1 A sync line is a directive with the key `sync` and two parts separated by
spaces, `logger=` followed by a logger time in the form of rule 5.2, and
`ref=` followed by a UTC time `YYYY-MM-DDTHH:MM:SSZ`. The two parts can come
in either order.

7.2 A sync line is not a data row and carries no readings. What it means is
in `clock.md` 2.
