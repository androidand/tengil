# Compose Cache

This directory contains curated Docker Compose files for Tengil packages.

## Purpose

Instead of depending on external URLs that could break, we maintain known-good versions of compose files:
- **Reliability**: Tested, working versions
- **Speed**: No network calls during package init
- **Transparency**: See exactly what's being deployed
- **Offline**: Works without internet

## Structure

```
compose_cache/
├── ollama/
│   ├── docker-compose.yml      # Curated compose file
│   ├── version.txt             # Source URL + date cached
│   └── README.md               # Notes about modifications (if any)
├── jellyfin/
├── jupyter/
└── ...
```

## Curation Process

### 1. Download Compose File
```bash
# Download from official source
curl -o compose_cache/ollama/docker-compose.yml \
  https://raw.githubusercontent.com/ollama/ollama/main/docker-compose.yaml
```

### 2. Create Version Metadata
```bash
cat > compose_cache/ollama/version.txt << EOF
source: https://raw.githubusercontent.com/ollama/ollama/main/docker-compose.yaml
cached: 2025-11-10
verified: 2025-11-10
tested_with: ComposeAnalyzer v1.0.0
EOF
```

### 3. Test Parsing
```bash
python -m pytest tests/test_compose_cache.py -k ollama
```

### 4. Document Modifications
If we need to modify the compose file (rare), document it in README.md:

```markdown
# Ollama Compose

## Source
https://github.com/ollama/ollama/blob/main/docker-compose.yaml

## Modifications
- None (using official compose as-is)

## Last Verified
2025-11-10
```

## Usage in Packages

```yaml
docker_compose:
  sources:
    - name: ollama
      cache: "compose_cache/ollama/docker-compose.yml"  # Prefer cache
      source: "https://raw.githubusercontent.com/..."    # Fallback
      managed_volumes:
        - /root/.ollama
```

## Updating Cache

### Check for Updates
```bash
# Compare cached version with upstream
./scripts/check_compose_updates.sh ollama
```

### Update a Cached File
```bash
# Download latest version
curl -o compose_cache/ollama/docker-compose.new.yml \
  https://raw.githubusercontent.com/ollama/ollama/main/docker-compose.yaml

# Compare with cached version
diff compose_cache/ollama/docker-compose.yml \
     compose_cache/ollama/docker-compose.new.yml

# If acceptable, replace
mv compose_cache/ollama/docker-compose.new.yml \
   compose_cache/ollama/docker-compose.yml

# Update version.txt
date -I > compose_cache/ollama/version.txt
```

## Guidelines

### What to Cache
- ✅ Official compose files from project repos
- ✅ Stable, released versions
- ✅ Files that rarely change
- ❌ Alpha/beta versions
- ❌ Heavily customized files (maintain separately)

### Modifications
Prefer using compose files as-is. If modifications needed:
1. Document in README.md
2. Keep diff minimal
3. Comment changes clearly
4. Test thoroughly

### Testing
Every cached file must:
- Parse correctly with ComposeAnalyzer
- Have at least one service defined
- Have volume mounts we can extract
- Work with OpinionMerger

## Maintenance

Cached files should be reviewed:
- **Weekly**: Check high-priority apps (ollama, jellyfin)
- **Monthly**: Check all cached files
- **On report**: If users report issues with a compose file

Files over 90 days old without verification should be reviewed.
