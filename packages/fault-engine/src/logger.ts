import { appendFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import type { InjectionRecord } from './schemas.js';

export interface RecordSink {
  write(record: InjectionRecord): void;
}

/** One JSON object per line. Single appends under PIPE_BUF are atomic with O_APPEND. */
export class JsonlSink implements RecordSink {
  constructor(private readonly path: string) {
    mkdirSync(dirname(path), { recursive: true });
  }
  write(record: InjectionRecord): void {
    appendFileSync(this.path, `${JSON.stringify(record)}\n`);
  }
}

export class MemorySink implements RecordSink {
  readonly records: InjectionRecord[] = [];
  write(record: InjectionRecord): void {
    this.records.push(record);
  }
}
