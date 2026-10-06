// Local sandbox process manager (production runs on Render / Vercel)
module.exports = {
  apps: [
    {
      name: 'compass-api',
      cwd: './backend',
      script: '.venv/bin/uvicorn',
      args: 'app.main:app --host 0.0.0.0 --port 8000',
      interpreter: 'none',
      env: { CRON_SECRET: 'local-dev-secret' },
      watch: false, instances: 1, exec_mode: 'fork',
    },
    {
      name: 'compass-web',
      cwd: './frontend',
      script: 'npm',
      args: 'run start -- -p 3000',
      env: { NODE_ENV: 'production' },
      watch: false, instances: 1, exec_mode: 'fork',
    },
  ],
}
