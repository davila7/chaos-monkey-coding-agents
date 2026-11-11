// Package csvq reads CSV input that starts with a header row and looks fields up by column name.
package csvq

import (
	"encoding/csv"
	"errors"
	"fmt"
	"io"
	"strings"
)

// Reader reads the records that follow the header row.
type Reader struct {
	r    *csv.Reader
	cols map[string]int
}

// Row is one record.
type Row struct {
	fields []string
	cols   map[string]int
	// Line is the input line on which the record starts.
	Line int
}

// NewReader reads the header row and checks that every required column is present.
// Column names are matched without case and surrounding spaces. A UTF-8 byte order
// mark before the first column name is skipped.
func NewReader(r io.Reader, required ...string) (*Reader, error) {
	cr := csv.NewReader(r)
	cr.FieldsPerRecord = -1
	header, err := cr.Read()
	if err == io.EOF {
		return nil, errors.New("csvq: empty input")
	}
	if err != nil {
		return nil, fmt.Errorf("csvq: header: %w", err)
	}
	cols := make(map[string]int, len(header))
	for i, h := range header {
		if i == 0 {
			h = strings.TrimPrefix(h, "\uFEFF")
		}
		h = strings.ToLower(strings.TrimSpace(h))
		if _, dup := cols[h]; dup {
			return nil, fmt.Errorf("csvq: duplicate column %q", h)
		}
		cols[h] = i
	}
	for _, c := range required {
		if _, ok := cols[c]; !ok {
			return nil, fmt.Errorf("csvq: missing column %q", c)
		}
	}
	return &Reader{r: cr, cols: cols}, nil
}

// Next returns the next record, or io.EOF after the last one.
func (r *Reader) Next() (Row, error) {
	rec, err := r.r.Read()
	if err != nil {
		return Row{}, err
	}
	line, _ := r.r.FieldPos(0)
	return Row{fields: rec, cols: r.cols, Line: line}, nil
}

// String returns the field in column col without surrounding spaces, or "" when the
// record has no such field.
func (r Row) String(col string) string {
	i, ok := r.cols[col]
	if !ok || i >= len(r.fields) {
		return ""
	}
	return strings.TrimSpace(r.fields[i])
}

// Decimal parses the field in column col with ParseDecimal.
func (r Row) Decimal(col string, places int) (int64, error) {
	return ParseDecimal(r.String(col), places)
}

// ParseDecimal parses a decimal number with at most places fractional digits and
// returns it scaled by 10^places: ParseDecimal("-1.5", 3) is -1500.
func ParseDecimal(s string, places int) (int64, error) {
	bad := fmt.Errorf("csvq: invalid decimal %q", s)
	t := s
	neg := false
	if strings.HasPrefix(t, "-") {
		neg, t = true, t[1:]
	} else if strings.HasPrefix(t, "+") {
		t = t[1:]
	}
	whole, frac, dot := strings.Cut(t, ".")
	if whole == "" || (dot && frac == "") || !digits(whole) || !digits(frac) {
		return 0, bad
	}
	if len(frac) > places {
		return 0, fmt.Errorf("csvq: %q has more than %d decimal places", s, places)
	}
	all := strings.TrimLeft(whole+frac+strings.Repeat("0", places-len(frac)), "0")
	if len(all) > 18 {
		return 0, fmt.Errorf("csvq: %q is out of range", s)
	}
	var v int64
	for _, c := range all {
		v = v*10 + int64(c-'0')
	}
	if neg {
		v = -v
	}
	return v, nil
}

func digits(s string) bool {
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}
