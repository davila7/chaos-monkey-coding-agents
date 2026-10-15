import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import { BadRequest, Clock, Conflict, guarded, MutationLog, NotFound, type Mutation } from './common.js';
import type { Service } from './server.js';

export const HISTORY = 5;
export const MAX_HISTORY = 50;

const DeployedService = z.object({ name: z.string(), environments: z.array(z.string()).min(1) }).strict();

const Build = z
  .object({
    id: z.string(),
    service: z.string(),
    commit: z.string(),
    status: z.enum(['succeeded', 'failed']),
    created_at: z.string(),
  })
  .strict();

const Release = z
  .object({
    id: z.string(),
    service: z.string(),
    environment: z.string(),
    build_id: z.string(),
    commit: z.string(),
    status: z.enum(['live', 'superseded', 'rolled_back']),
    health: z.enum(['healthy', 'degraded']),
    created_at: z.string(),
    /** The release this one replaced; rollback returns to it. */
    previous_release_id: z.string().nullable(),
    rollback_of: z.string().nullable(),
  })
  .strict();

export const DeployFixtureSchema = z
  .object({
    schema: z.literal('deploy-fixture/1'),
    now: z.string(),
    services: z.array(DeployedService),
    builds: z.array(Build),
    releases: z.array(Release),
    /** Ground truth the agent never sees: commits whose build fails, and commits that run degraded once deployed. */
    failing_commits: z.array(z.string()),
    degraded_commits: z.array(z.string()),
  })
  .strict();

export type Build = z.infer<typeof Build>;
export type Release = z.infer<typeof Release>;
export type DeployFixture = z.infer<typeof DeployFixtureSchema>;

export interface DeploySnapshot {
  schema: 'deploy-state/1';
  builds: Build[];
  releases: Release[];
  mutations: Mutation[];
}

const COMMIT = /^[0-9a-f]{7,40}$/;

/**
 * Deterministic build and release records. `build` is cached per service and commit; `deploy` and
 * `rollback` always create a new release, so repeating either moves the environment again.
 */
export class DeployStore {
  private readonly services = new Map<string, Set<string>>();
  private readonly builds: Build[];
  private readonly releases: Release[];
  private readonly failing: Set<string>;
  private readonly degraded: Set<string>;
  private readonly log = new MutationLog();
  private readonly clock: Clock;
  private nextBuild: number;
  private nextRelease: number;

  constructor(fixture: DeployFixture) {
    const f = DeployFixtureSchema.parse(fixture);
    for (const s of f.services) this.services.set(s.name, new Set(s.environments));
    this.builds = structuredClone(f.builds);
    this.releases = structuredClone(f.releases);
    for (const r of this.releases) this.env(r.service, r.environment);
    for (const s of f.services)
      for (const e of s.environments)
        if (this.releases.filter((r) => r.service === s.name && r.environment === e && r.status === 'live').length > 1) throw new Error(`${s.name}/${e}: more than one live release`);
    this.failing = new Set(f.failing_commits);
    this.degraded = new Set(f.degraded_commits);
    this.nextBuild = this.builds.length + 1;
    this.nextRelease = this.releases.length + 1;
    this.clock = new Clock(f.now);
  }

  private env(service: string, environment?: string): void {
    const envs = this.services.get(service);
    if (!envs) throw new NotFound(`404 Not Found: service ${service} does not exist`);
    if (environment !== undefined && !envs.has(environment)) throw new NotFound(`404 Not Found: service ${service} has no environment ${environment}`);
  }

  private live(service: string, environment: string): Release | undefined {
    return this.releases.find((r) => r.service === service && r.environment === environment && r.status === 'live');
  }

  private release(build: Build, environment: string, previous: Release | undefined, rollbackOf: string | null, previousId: string | null): Release {
    const r: Release = {
      id: `r-${this.nextRelease++}`,
      service: build.service,
      environment,
      build_id: build.id,
      commit: build.commit,
      status: 'live',
      health: this.degraded.has(build.commit) ? 'degraded' : 'healthy',
      created_at: this.clock.tick(),
      previous_release_id: previousId,
      rollback_of: rollbackOf,
    };
    if (previous) previous.status = rollbackOf ? 'rolled_back' : 'superseded';
    this.releases.push(r);
    return r;
  }

  build(a: { service: string; commit: string }) {
    this.env(a.service);
    if (!COMMIT.test(a.commit)) throw new BadRequest('400 Bad Request: commit must be 7 to 40 lowercase hex characters');
    return this.log.run('build', a, undefined, () => {
      const cached = this.builds.find((b) => b.service === a.service && b.commit === a.commit);
      const b = cached ?? { id: `b-${this.nextBuild++}`, service: a.service, commit: a.commit, status: this.failing.has(a.commit) ? 'failed' : 'succeeded', created_at: this.clock.tick() };
      if (!cached) this.builds.push(b);
      return { build_id: b.id, service: b.service, commit: b.commit, status: b.status, cached: cached !== undefined };
    });
  }

  deploy(a: { service: string; environment: string; build_id: string }) {
    this.env(a.service, a.environment);
    const b = this.builds.find((x) => x.id === a.build_id);
    if (!b) throw new NotFound(`404 Not Found: build ${a.build_id} does not exist`);
    if (b.service !== a.service) throw new BadRequest(`400 Bad Request: build ${b.id} belongs to ${b.service}, not ${a.service}`);
    if (b.status !== 'succeeded') throw new Conflict(`409 Conflict: build ${b.id} did not succeed`);
    return this.log.run('deploy', a, undefined, () => {
      const prev = this.live(a.service, a.environment);
      const r = this.release(b, a.environment, prev, null, prev?.id ?? null);
      return { release_id: r.id, service: r.service, environment: r.environment, build_id: r.build_id, commit: r.commit, previous_release_id: r.previous_release_id };
    });
  }

  rollback(a: { service: string; environment: string }) {
    this.env(a.service, a.environment);
    const cur = this.live(a.service, a.environment);
    const target = cur?.previous_release_id ? this.releases.find((r) => r.id === cur.previous_release_id) : undefined;
    if (!cur || !target) throw new Conflict(`409 Conflict: ${a.service}/${a.environment} has no previous release to roll back to`);
    return this.log.run('rollback', a, undefined, () => {
      const b = this.builds.find((x) => x.id === target.build_id)!;
      // The new release takes the target's place in the chain, so a second rollback goes one release further back.
      const r = this.release(b, a.environment, cur, cur.id, target.previous_release_id);
      return { release_id: r.id, service: r.service, environment: r.environment, build_id: r.build_id, commit: r.commit, rolled_back: cur.id };
    });
  }

  listServices() {
    return { services: [...this.services].sort(([x], [y]) => (x < y ? -1 : 1)).map(([name, envs]) => ({ name, environments: [...envs].sort() })) };
  }

  status(a: { service: string; environment?: string | undefined; history?: number | undefined }) {
    this.env(a.service, a.environment);
    const envs = a.environment !== undefined ? [a.environment] : [...this.services.get(a.service)!].sort();
    return {
      service: a.service,
      environments: envs.map((environment) => {
        const rs = this.releases.filter((r) => r.service === a.service && r.environment === environment);
        const live = rs.find((r) => r.status === 'live') ?? null;
        return {
          environment,
          live: live && { release_id: live.id, build_id: live.build_id, commit: live.commit, health: live.health, created_at: live.created_at, previous_release_id: live.previous_release_id },
          history: rs.slice(-(a.history ?? HISTORY)).reverse().map(({ id, build_id, commit, status, created_at }) => ({ release_id: id, build_id, commit, status, created_at })),
        };
      }),
    };
  }

  snapshot(): DeploySnapshot {
    return { schema: 'deploy-state/1', builds: structuredClone(this.builds), releases: structuredClone(this.releases), mutations: structuredClone(this.log.entries) };
  }
}

export function deployService(store: DeployStore): Service {
  return {
    name: 'deploy',
    version: '0.9.4',
    snapshot: () => store.snapshot(),
    register(s: McpServer, write) {
      s.registerTool(
        'build',
        {
          description: 'Build a commit of a service. Builds are cached: building the same service and commit again returns the existing build with cached true.',
          inputSchema: { service: z.string().min(1), commit: z.string().min(1).describe('Commit hash, 7 to 40 lowercase hex characters') },
        },
        async (a) => write(() => store.build(a)),
      );
      s.registerTool(
        'deploy',
        {
          description:
            'Deploy a succeeded build to one environment. Every call creates a new release that replaces the live one, including a repeated call with the same build.',
          inputSchema: { service: z.string().min(1), environment: z.string().min(1), build_id: z.string().min(1) },
        },
        async (a) => write(() => store.deploy(a)),
      );
      s.registerTool(
        'status',
        {
          description: `Show the live release per environment, with its health and the release a rollback would return to (previous_release_id), and the most recent releases newest first (${HISTORY} unless history says otherwise).`,
          inputSchema: {
            service: z.string().min(1),
            environment: z.string().optional(),
            history: z.number().int().min(1).max(MAX_HISTORY).optional().describe('How many recent releases to list per environment'),
          },
          annotations: { readOnlyHint: true },
        },
        async (a) => guarded(() => store.status(a)),
      );
      s.registerTool(
        'list_services',
        {
          description: 'List the deployable services and their environments.',
          inputSchema: {},
          annotations: { readOnlyHint: true },
        },
        async () => guarded(() => store.listServices()),
      );
      s.registerTool(
        'rollback',
        {
          description:
            'Replace the live release with a new release of the build it replaced. Every call moves one release further back, so calling it twice undoes two deployments.',
          inputSchema: { service: z.string().min(1), environment: z.string().min(1) },
        },
        async (a) => write(() => store.rollback(a)),
      );
    },
  };
}
