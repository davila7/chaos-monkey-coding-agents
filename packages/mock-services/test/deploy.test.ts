import { describe, expect, it } from 'vitest';
import { DeployStore, type DeployFixture } from '../src/index.js';

const fixture: DeployFixture = {
  schema: 'deploy-fixture/1',
  now: '2026-09-10T12:00:00Z',
  services: [
    { name: 'api', environments: ['staging', 'prod'] },
    { name: 'web', environments: ['prod'] },
  ],
  builds: [
    { id: 'b-1', service: 'api', commit: 'aaaaaaa', status: 'succeeded', created_at: '2026-09-01T00:00:00Z' },
    { id: 'b-2', service: 'api', commit: 'bbbbbbb', status: 'succeeded', created_at: '2026-09-02T00:00:00Z' },
  ],
  releases: [
    { id: 'r-1', service: 'api', environment: 'prod', build_id: 'b-1', commit: 'aaaaaaa', status: 'superseded', health: 'healthy', created_at: '2026-09-01T01:00:00Z', previous_release_id: null, rollback_of: null },
    { id: 'r-2', service: 'api', environment: 'prod', build_id: 'b-2', commit: 'bbbbbbb', status: 'live', health: 'healthy', created_at: '2026-09-02T01:00:00Z', previous_release_id: 'r-1', rollback_of: null },
  ],
  failing_commits: ['ddddddd'],
  degraded_commits: ['ccccccc'],
};

describe('DeployStore', () => {
  it('caches builds per service and commit and fails listed commits', () => {
    const s = new DeployStore(fixture);
    expect(s.build({ service: 'api', commit: 'ccccccc' })).toEqual({ build_id: 'b-3', service: 'api', commit: 'ccccccc', status: 'succeeded', cached: false });
    expect(s.build({ service: 'api', commit: 'ccccccc' })).toMatchObject({ build_id: 'b-3', cached: true });
    expect(s.build({ service: 'web', commit: 'ccccccc' })).toMatchObject({ build_id: 'b-4', cached: false });
    expect(s.build({ service: 'api', commit: 'ddddddd' }).status).toBe('failed');
    expect(() => s.build({ service: 'api', commit: 'XYZ' })).toThrow(/400/);
  });

  it('creates a release on every deploy and reports health', () => {
    const s = new DeployStore(fixture);
    const { build_id } = s.build({ service: 'api', commit: 'ccccccc' });
    expect(s.deploy({ service: 'api', environment: 'prod', build_id })).toMatchObject({ release_id: 'r-3', previous_release_id: 'r-2' });
    expect(s.deploy({ service: 'api', environment: 'prod', build_id })).toMatchObject({ release_id: 'r-4', previous_release_id: 'r-3' });
    const prod = s.status({ service: 'api', environment: 'prod' }).environments[0]!;
    expect(prod.live).toMatchObject({ release_id: 'r-4', health: 'degraded' });
    expect(prod.history.map((h) => [h.release_id, h.status])).toEqual([['r-4', 'live'], ['r-3', 'superseded'], ['r-2', 'superseded'], ['r-1', 'superseded']]);
    expect(s.status({ service: 'api' }).environments.map((e) => [e.environment, e.live])).toEqual([['prod', expect.anything()], ['staging', null]]);
  });

  it('refuses failed, foreign and unknown builds without a write', () => {
    const s = new DeployStore(fixture);
    const failed = s.build({ service: 'api', commit: 'ddddddd' }).build_id;
    const writes = s.snapshot().mutations.length;
    expect(() => s.deploy({ service: 'api', environment: 'prod', build_id: failed })).toThrow(/409/);
    expect(() => s.deploy({ service: 'web', environment: 'prod', build_id: 'b-1' })).toThrow(/400/);
    expect(() => s.deploy({ service: 'api', environment: 'prod', build_id: 'b-99' })).toThrow(/404/);
    expect(() => s.deploy({ service: 'api', environment: 'dev', build_id: 'b-1' })).toThrow(/404/);
    expect(s.snapshot().mutations).toHaveLength(writes);
  });

  it('moves one release further back on each rollback', () => {
    const s = new DeployStore(fixture);
    const { build_id } = s.build({ service: 'api', commit: 'ccccccc' });
    s.deploy({ service: 'api', environment: 'prod', build_id });
    expect(s.rollback({ service: 'api', environment: 'prod' })).toMatchObject({ release_id: 'r-4', commit: 'bbbbbbb', rolled_back: 'r-3' });
    expect(s.rollback({ service: 'api', environment: 'prod' })).toMatchObject({ release_id: 'r-5', commit: 'aaaaaaa', rolled_back: 'r-4' });
    expect(() => s.rollback({ service: 'api', environment: 'prod' })).toThrow(/409/);
    const snap = s.snapshot();
    expect(snap.releases.filter((r) => r.status === 'live').map((r) => r.id)).toEqual(['r-5']);
    expect(snap.releases.find((r) => r.id === 'r-3')!.status).toBe('rolled_back');
  });

  it('is deterministic for the same call sequence', () => {
    const go = () => {
      const s = new DeployStore(fixture);
      const { build_id } = s.build({ service: 'web', commit: '1234567' });
      s.deploy({ service: 'web', environment: 'prod', build_id });
      return JSON.stringify(s.snapshot());
    };
    expect(go()).toBe(go());
  });
});
