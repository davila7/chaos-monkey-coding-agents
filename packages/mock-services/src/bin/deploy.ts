import { DeployFixtureSchema, DeployStore, deployService } from '../deploy.js';
import { run } from './run.js';

run('deploy', (f) => deployService(new DeployStore(DeployFixtureSchema.parse(f))));
