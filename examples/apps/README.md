# App Config Examples

This directory contains example app configurations for Tengil's app deployment system.

## Workflow Overview

1. **Store app configs in git** - Keep your infrastructure configs separate from app code
2. **Keep secrets local** - Use `.env.local` (git-ignored) for sensitive values
3. **Deploy with one command** - `tg app deploy apps/your-app.yml`

## Quick Start

### 1. Create Your App Config

```yaml
# apps/my-node-app.yml
name: my-node-app
description: My custom Node.js application

container:
  template: debian-12-standard
  pool: production
  memory: 2048
  cores: 2

source:
  type: git
  url: https://github.com/yourname/my-node-app
  branch: main
  path: /app

runtime:
  secrets:
    - DATABASE_URL
    - API_KEY
  packages:
    - nodejs
    - npm
    - git
  startup_command: cd /app && npm install && npm start
```

### 2. Create .env.local (git-ignored)

```bash
# .env.local
DATABASE_URL=postgres://user:pass@db-host:5432/mydb
API_KEY=your-secret-api-key
```

### 3. Deploy

```bash
# Load secrets into your environment
source .env.local

# Deploy the app
tg app deploy apps/my-node-app.yml
```

## App Config Structure

### Required Fields

- **name**: App name (becomes container hostname)
- **container.template**: LXC template to use

### Optional Fields

#### Container Configuration

```yaml
container:
  template: debian-12-standard    # Required
  pool: production                 # Proxmox resource pool
  memory: 2048                     # MB
  cores: 2
  disk: 16G
  privileged: false                # Default: false (safer)
  network:
    ip: 192.168.1.100/24          # Or 'dhcp'
    gateway: 192.168.1.1
  description: "App description"
  tags: [tag1, tag2]
```

#### Source Configuration

```yaml
source:
  type: git                        # 'git', 'docker', or 'local'
  url: https://github.com/user/repo
  branch: main                     # Default: main
  path: /app                       # Where to clone inside container
```

#### Runtime Configuration

```yaml
runtime:
  secrets:                         # Loaded from local env vars
    - DATABASE_URL
    - API_KEY
  packages:                        # Installed via apt-get
    - nodejs
    - npm
    - git
  startup_command: |               # Runs after deployment
    cd /app
    npm install
    npm start
```

## Examples

### Node.js API Server
- **File**: [node-api.yml](node-api.yml)
- **Use case**: REST API with database
- **Secrets**: DATABASE_URL, API_KEY, JWT_SECRET

### Python Worker
- **File**: [python-worker.yml](python-worker.yml)
- **Use case**: Background job processor
- **Secrets**: REDIS_URL, POSTGRES_URL

## Secret Management

### Best Practices

1. **Never commit secrets** - Add `.env.local` to `.gitignore`
2. **Use environment variables** - Not hardcoded in configs
3. **Validate secret names** - Must be UPPERCASE_WITH_UNDERSCORES
4. **Share templates** - Commit app configs, everyone uses their own `.env.local`

### .gitignore Pattern

```gitignore
# Keep secrets local
.env.local
.env.*.local
secrets/
```

### Example .env.local

```bash
# .env.local - NEVER COMMIT THIS FILE

# Database
DATABASE_URL=postgres://user:pass@localhost:5432/mydb

# API Keys
API_KEY=your-api-key-here
JWT_SECRET=your-jwt-secret-here

# Environment
NODE_ENV=production
WORKER_CONCURRENCY=4
```

## App Lifecycle Commands

```bash
# Deploy app
tg app deploy apps/my-app.yml

# List deployed apps
tg app list

# Start/stop/restart
tg app start my-app
tg app stop my-app
tg app restart my-app

# Update from git
tg app update my-app

# Remove app
tg app remove my-app
tg app remove my-app --delete-container  # Also delete container
```

## Team Collaboration

### Repository Structure

```
homelab-config/
├── .gitignore              # Ignore .env.local
├── .env.local.example      # Template for teammates
├── tengil.yml              # Infrastructure config
└── apps/
    ├── api-server.yml      # App configs (committed)
    ├── worker.yml
    └── frontend.yml
```

### .env.local.example

```bash
# Copy this to .env.local and fill in your values
# .env.local is git-ignored and never committed

DATABASE_URL=
API_KEY=
JWT_SECRET=
```

### Workflow

1. Team member clones repo
2. Copies `.env.local.example` to `.env.local`
3. Fills in their own secret values
4. Deploys: `source .env.local && tg app deploy apps/api-server.yml`

Everyone shares the same app configs but uses their own secrets!
