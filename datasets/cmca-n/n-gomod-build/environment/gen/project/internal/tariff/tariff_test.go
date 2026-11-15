package tariff

import (
	"testing"
	"testing/fstest"
)

func TestEmbeddedOverlays(t *testing.T) {
	set, err := Embedded()
	if err != nil {
		t.Fatal(err)
	}
	cases := []struct {
		region, source string
		standing       int64
	}{
		{"NW-1", "_base.csv", 1250},
		{"CE-3", "_base.csv", 1340},
		{"SW-2", "coastal.csv", 1490},
		{"MT-1", "upland.csv", 1190},
		{"UP-1", "upland.csv", 1540},
	}
	for _, c := range cases {
		tr, ok := set.Lookup(c.region)
		if !ok {
			t.Errorf("%s: not found", c.region)
			continue
		}
		if tr.Source != c.source || tr.Standing != c.standing {
			t.Errorf("%s: got %s %d, want %s %d", c.region, tr.Source, tr.Standing, c.source, c.standing)
		}
	}
}

func TestCost(t *testing.T) {
	fsys := fstest.MapFS{"t/a.csv": {Data: []byte("region,standing,export,tiers\nX-1,10.00,5.00,100:20.00 *:30.00\n")}}
	set, err := Load(fsys, "t")
	if err != nil {
		t.Fatal(err)
	}
	tr, _ := set.Lookup("x-1")
	for _, c := range []struct{ wh, cents int64 }{
		{0, 1000},
		{50000, 2000},
		{100000, 3000},
		{150000, 4500},
		{1, 1000},
		{25, 1001},
		{-10000, 950},
	} {
		if got := tr.Cost(c.wh); got != c.cents {
			t.Errorf("Cost(%d) = %d, want %d", c.wh, got, c.cents)
		}
	}
}
