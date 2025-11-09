# Tengil Templates & Datasets

This directory contains reusable templates and dataset definitions for Tengil configurations.

## Architecture

Templates and datasets follow a **DRY (Don't Repeat Yourself)** principle:

- **Templates** (`*.yml`) - Reference lists of datasets for common setups
- **Datasets** (`datasets/*.yml`) - Individual dataset definitions that can be combined

This allows for:
- Clean, maintainable template files
- Easy mixing and matching of datasets
- No duplication of dataset configurations
- Ability to override individual datasets

## Usage

### Using Templates

Templates provide pre-configured setups for common use cases:

```bash
# Use a single template
tg init --template homelab

# Combine multiple templates
tg init --templates homelab,media-server

# List all templates with descriptions
tg init --list-templates
```

### Using Individual Datasets

Pick specific datasets for a custom setup:

```bash
# Select specific datasets
tg init --datasets movies,tv,photos

# List all datasets with descriptions
tg init --list-datasets
```

### Combining Approaches

You can't mix `--template(s)` with `--datasets` flags - choose one approach.

## Available Templates

Run `tg init --list-templates` to see all templates with descriptions.

### Template Structure

Templates use dataset references instead of inline definitions:

```yaml
description: Brief description of what this template provides

version: 1
mode: converged-nas
pool: ${pool}  # Will be substituted with --pool value

datasets:
  - movies      # Reference to datasets/movies.yml
  - tv          # Reference to datasets/tv.yml
  - photos      # Reference to datasets/photos.yml
```

## Available Datasets

Run `tg init --list-datasets` to see all datasets with descriptions.

### Dataset Structure

Each dataset file contains:
- **description** - Explains the purpose and features
- **dataset definition** - The actual ZFS/container/share configuration

Example (`datasets/movies.yml`):

```yaml
description: Movies library for streaming services (Jellyfin/Plex) with automation (Radarr)

movies:
  profile: media
  containers:
    - name: jellyfin
      mount: /movies
      readonly: true
    - name: radarr
      mount: /movies
      readonly: false
  shares:
    smb:
      name: "Movies"
      guest_ok: true
      browseable: true
```

## Creating Custom Templates

1. Create a new YAML file in this directory
2. Add a `description` field
3. List dataset references under `datasets`
4. Optionally set `mode`, `version`, etc.

Example:

```yaml
description: My custom media setup

version: 1
mode: converged-nas
pool: ${pool}

datasets:
  - movies
  - tv
  - downloads
  - backups
```

## Creating Custom Datasets

1. Create a new YAML file in `datasets/`
2. Add a `description` field
3. Define the dataset configuration with a single key matching the filename

Example (`datasets/mydata.yml`):

```yaml
description: My custom dataset for special data

mydata:
  profile: documents
  zfs:
    compression: zstd
    recordsize: 128K
  shares:
    smb:
      name: "My Data"
      browseable: true
  permissions:
    mode: "0755"
```

Then use it:

```bash
tg init --datasets mydata,backups
```

## Variable Substitution

Templates support the `${pool}` variable which will be replaced with the value from the `--pool` flag:

```yaml
pool: ${pool}  # Becomes "tank" with --pool tank
```

## Best Practices

1. **Keep datasets focused** - One purpose per dataset
2. **Use descriptive names** - Clear, lowercase, no special chars
3. **Add good descriptions** - Help users understand what each provides
4. **Use profiles** - Leverage built-in profiles (media, documents, photos, backups, dev)
5. **Comment container names** - Users need to match their actual container names
6. **Set sensible defaults** - Pre-configure common scenarios

## Profiles

Datasets can use built-in profiles that provide default ZFS properties:

- **media** - Large files, compression, no atime
- **documents** - Medium files, high compression
- **photos** - Large files, moderate compression
- **backups** - Highest compression, redundancy
- **dev** - Small files, fast access

Profiles can be overridden with explicit `zfs:` properties in the dataset definition.
