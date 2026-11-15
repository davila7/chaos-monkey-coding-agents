// Command wattbill prices electricity meter readings with the regional tariffs.
package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"sync/atomic"

	"scm.tallow.lan/kit/money"

	"scm.tallow.lan/energy/wattbill/internal/billing"
	"scm.tallow.lan/energy/wattbill/internal/buildinfo"
	"scm.tallow.lan/energy/wattbill/internal/tariff"
)

const usage = `usage: wattbill bill [FILE]
       wattbill rate REGION
       wattbill regions
       wattbill --version
`

func main() {
	os.Exit(run(os.Args[1:], os.Stdin, os.Stdout, os.Stderr))
}

func run(args []string, stdin io.Reader, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		fmt.Fprint(stderr, usage)
		return 2
	}
	out := bufio.NewWriter(stdout)
	defer out.Flush()
	cmd, rest := args[0], args[1:]
	switch cmd {
	case "--version":
		if len(rest) != 0 {
			break
		}
		fmt.Fprintf(out, "wattbill %s (commit %s)\n", buildinfo.Version(), buildinfo.Commit())
		return 0
	case "-h", "--help", "help":
		fmt.Fprint(out, usage)
		return 0
	case "regions":
		if len(rest) != 0 {
			break
		}
		set, err := tariff.Embedded()
		if err != nil {
			fmt.Fprintf(stderr, "wattbill: %v\n", err)
			return 2
		}
		for _, r := range set.Regions() {
			t, _ := set.Lookup(r)
			fmt.Fprintf(out, "%s\t%s\n", r, t.Source)
		}
		return 0
	case "rate":
		if len(rest) != 1 {
			break
		}
		set, err := tariff.Embedded()
		if err != nil {
			fmt.Fprintf(stderr, "wattbill: %v\n", err)
			return 2
		}
		t, ok := set.Lookup(rest[0])
		if !ok {
			fmt.Fprintf(stderr, "wattbill: unknown region %q\n", rest[0])
			return 1
		}
		fmt.Fprint(out, t.Describe())
		return 0
	case "bill":
		if len(rest) > 1 {
			break
		}
		return bill(rest, stdin, out, stderr)
	default:
		fmt.Fprintf(stderr, "wattbill: unknown command %q\n", cmd)
	}
	fmt.Fprint(stderr, usage)
	return 2
}

func bill(rest []string, stdin io.Reader, out *bufio.Writer, stderr io.Writer) int {
	in := stdin
	if len(rest) == 1 && rest[0] != "-" {
		f, err := os.Open(rest[0])
		if err != nil {
			fmt.Fprintf(stderr, "wattbill: %v\n", err)
			return 2
		}
		defer f.Close()
		in = f
	}
	set, err := tariff.Embedded()
	if err != nil {
		fmt.Fprintf(stderr, "wattbill: %v\n", err)
		return 2
	}
	var rows atomic.Int64
	stop := watchProgress(&rows)
	defer stop()
	res, err := billing.Run(in, set, &rows)
	if err != nil {
		fmt.Fprintf(stderr, "wattbill: %v\n", err)
		return 2
	}
	for _, l := range res.Lines {
		fmt.Fprintf(out, "%s\t%s\t%s\t%s\n", l.Meter, l.Region, kwh(l.Wh), money.Format(l.Cents))
	}
	fmt.Fprintf(out, "total\t%d\t-\t%s\n", len(res.Lines), money.Format(res.Total))
	for _, w := range res.Warnings {
		fmt.Fprintf(stderr, "wattbill: %s\n", w)
	}
	if len(res.Warnings) > 0 {
		return 1
	}
	return 0
}

func kwh(wh int64) string {
	sign := ""
	if wh < 0 {
		sign, wh = "-", -wh
	}
	return fmt.Sprintf("%s%d.%03d", sign, wh/1000, wh%1000)
}
