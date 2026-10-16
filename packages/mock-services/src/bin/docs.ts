import { DocsFixtureSchema, DocsStore, docsService } from '../docs.js';
import { run } from './run.js';

run('docs', (f) => docsService(new DocsStore(DocsFixtureSchema.parse(f))));
