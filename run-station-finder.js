const { execSync } = require('child_process');
const { spawn } = require('child_process');

const env = Object.assign({}, process.env, {
  PATH: '/opt/homebrew/bin:/usr/local/bin:' + (process.env.PATH || '/usr/bin:/bin'),
});

const child = spawn('/opt/homebrew/bin/node', [
  '/Users/yoshidanaoya/Documents/station-finder/node_modules/.bin/next',
  'dev',
], {
  cwd: '/Users/yoshidanaoya/Documents/station-finder',
  env,
  stdio: 'inherit',
});

child.on('exit', (code) => process.exit(code || 0));
