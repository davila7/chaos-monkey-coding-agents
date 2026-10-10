import { writeFileSync } from 'node:fs';
const [out, type] = process.argv.slice(2);
const base = JSON.parse(process.env.BASE_CFG);
base.profile.weights = { [type]: 1 };
base.parity_set = [type];
writeFileSync(out, JSON.stringify(base));
