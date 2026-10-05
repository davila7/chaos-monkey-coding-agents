import { closeSync, mkdirSync, openSync, readFileSync, renameSync, statSync, unlinkSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { emptyState, type TrialState } from './schedule.js';

export interface StateStore {
  /** Runs `fn` with exclusive access to the trial state and persists the result. */
  transact<T>(fn: (state: TrialState) => T): T;
}

export class MemoryStateStore implements StateStore {
  private state: TrialState = emptyState();
  transact<T>(fn: (state: TrialState) => T): T {
    const draft = structuredClone(this.state);
    const out = fn(draft);
    this.state = draft;
    return out;
  }
}

export interface FileStateStoreOptions {
  /** Give up acquiring the lock after this many milliseconds. */
  lockTimeoutMs?: number;
  /** A lock older than this is considered abandoned by a crashed process. */
  staleLockMs?: number;
}

const sleepBuf = new Int32Array(new SharedArrayBuffer(4));
function sleepMs(ms: number): void {
  Atomics.wait(sleepBuf, 0, 0, ms);
}

/**
 * File-backed store for command-style adapters that run one process per
 * call. Exclusive access uses an O_EXCL lock file; writes go through a
 * temp file and rename so readers never see a partial state.
 */
export class FileStateStore implements StateStore {
  private readonly statePath: string;
  private readonly lockPath: string;
  private readonly lockTimeoutMs: number;
  private readonly staleLockMs: number;

  constructor(dir: string, opts: FileStateStoreOptions = {}) {
    mkdirSync(dir, { recursive: true });
    this.statePath = join(dir, 'state.json');
    this.lockPath = join(dir, 'state.lock');
    this.lockTimeoutMs = opts.lockTimeoutMs ?? 5000;
    this.staleLockMs = opts.staleLockMs ?? 10_000;
  }

  transact<T>(fn: (state: TrialState) => T): T {
    this.acquire();
    try {
      const state = this.read();
      const out = fn(state);
      const tmp = `${this.statePath}.${process.pid}.tmp`;
      writeFileSync(tmp, JSON.stringify(state));
      renameSync(tmp, this.statePath);
      return out;
    } finally {
      this.release();
    }
  }

  private read(): TrialState {
    let raw: string;
    try {
      raw = readFileSync(this.statePath, 'utf8');
    } catch (e) {
      if ((e as NodeJS.ErrnoException).code === 'ENOENT') return emptyState();
      throw e;
    }
    return JSON.parse(raw) as TrialState;
  }

  private acquire(): void {
    const deadline = Date.now() + this.lockTimeoutMs;
    let wait = 1;
    for (;;) {
      try {
        closeSync(openSync(this.lockPath, 'wx'));
        return;
      } catch (e) {
        if ((e as NodeJS.ErrnoException).code !== 'EEXIST') throw e;
      }
      try {
        if (Date.now() - statSync(this.lockPath).mtimeMs > this.staleLockMs) {
          unlinkSync(this.lockPath);
          continue;
        }
      } catch {
        continue;
      }
      if (Date.now() > deadline) throw new Error(`lock timeout on ${this.lockPath}`);
      sleepMs(wait);
      wait = Math.min(wait * 2, 16);
    }
  }

  private release(): void {
    try {
      unlinkSync(this.lockPath);
    } catch {
      // already removed as stale by another process
    }
  }
}
