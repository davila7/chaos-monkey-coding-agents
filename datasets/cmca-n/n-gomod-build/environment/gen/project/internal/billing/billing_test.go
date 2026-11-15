package billing

import (
	"reflect"
	"strings"
	"testing"

	"scm.tallow.lan/energy/wattbill/internal/tariff"
)

func TestRun(t *testing.T) {
	set, err := tariff.Embedded()
	if err != nil {
		t.Fatal(err)
	}
	in := "kwh,meter,region,period\n" +
		"312.5,M-1001,nw-1,2026-10\n" +
		"80,M-1002,SE-1,2026-10\n" +
		"-42.25,M-1003,SW-1,2026-10\n" +
		"10,,NW-1,2026-10\n" +
		"10,M-1004,XX-9,2026-10\n" +
		"ten,M-1005,NW-1,2026-10\n"
	res, err := Run(strings.NewReader(in), set, nil)
	if err != nil {
		t.Fatal(err)
	}
	want := []Line{
		{"M-1001", "NW-1", 312500, 1250 + 2760 + 3599},
		{"M-1002", "SE-1", 80000, 960 + 1376},
		{"M-1003", "SW-1", -42250, 1420 - 382},
	}
	if !reflect.DeepEqual(res.Lines, want) {
		t.Errorf("lines: got %v, want %v", res.Lines, want)
	}
	if res.Total != 1250+2760+3599+960+1376+1420-382 {
		t.Errorf("total: got %d", res.Total)
	}
	warn := []string{`line 5: missing meter`, `line 6: unknown region "XX-9"`, `line 7: bad kwh "ten"`}
	if !reflect.DeepEqual(res.Warnings, warn) {
		t.Errorf("warnings: got %q, want %q", res.Warnings, warn)
	}
}

func TestMissingColumn(t *testing.T) {
	set, err := tariff.Embedded()
	if err != nil {
		t.Fatal(err)
	}
	if _, err := Run(strings.NewReader("meter,kwh\nM-1,1\n"), set, nil); err == nil || err.Error() != `csvq: missing column "region"` {
		t.Errorf("got %v", err)
	}
}
