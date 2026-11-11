//go:build unix

package main

import (
	"fmt"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"
)

// watchProgress prints the number of records read so far to standard error each
// time the process receives SIGUSR1, until stop is called.
func watchProgress(rows *atomic.Int64) (stop func()) {
	ch := make(chan os.Signal, 1)
	signal.Notify(ch, syscall.SIGUSR1)
	done := make(chan struct{})
	go func() {
		for {
			select {
			case <-ch:
				fmt.Fprintf(os.Stderr, "wattbill: %d records read\n", rows.Load())
			case <-done:
				return
			}
		}
	}()
	return func() {
		signal.Stop(ch)
		close(done)
	}
}
