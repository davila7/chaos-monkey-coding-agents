import { createHash } from 'node:crypto';

export function sha256(input: string): Buffer {
  return createHash('sha256').update(input, 'utf8').digest();
}

/** First 16 hex characters (64 bits) of sha256. */
export function shortHash(input: string): string {
  return sha256(input).subarray(0, 8).toString('hex');
}

/** uint32(sha256(input)) / 2^32, a uniform draw in [0, 1). */
export function unitDraw(input: string): number {
  return sha256(input).readUInt32BE(0) / 2 ** 32;
}
