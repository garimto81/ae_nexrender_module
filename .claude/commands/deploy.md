---
name: deploy
description: Version update and Docker rebuild workflow
---

# /deploy - Version Update & Docker Rebuild

Update version and rebuild Docker containers in a single workflow.

## Usage

```
/deploy                        # Interactive mode
/deploy patch                  # Bump patch + rebuild
/deploy minor                  # Bump minor + rebuild
/deploy major                  # Bump major + rebuild
/deploy 2.3.4                  # Set version + rebuild
/deploy --docker-only          # Skip version, rebuild only
/deploy --version-only         # Version only, skip Docker
/deploy patch --no-cache       # Rebuild without cache
```

## Arguments

- `$ARGUMENTS` - Version (patch|minor|major|X.Y.Z) and/or options

## Options

| Option | Description |
|--------|-------------|
| `--docker-only` | Skip version update, Docker rebuild only |
| `--version-only` | Version update only, skip Docker |
| `--no-cache` | Docker build without cache |
| `--no-commit` | Skip version commit |

## Workflow

Claude Code will:

### 1. Version Update (unless `--docker-only`)

1. Detect current version from project files
2. Calculate new version based on input
3. Update version in all relevant files:
   - `package.json`
   - `pyproject.toml`
   - `CLAUDE.md`
   - Other version files
4. Commit version bump (unless `--no-commit`)

### 2. Docker Rebuild (unless `--version-only`)

1. Stop running containers
2. Remove old containers
3. Rebuild images (with `--no-cache` if specified)
4. Start new containers
5. Verify container health

### 3. Summary

- Show version change
- Show container status
- Report any issues

## Example

**Input**: `/deploy minor`

**Output**:
```
=== DEPLOY WORKFLOW ===

[1/2] Version Update
-------------------------------
Current version: 1.2.3
New version: 1.3.0

Updated files:
  - package.json: 1.2.3 -> 1.3.0
  - CLAUDE.md: 1.2.3 -> 1.3.0

Committed: chore(release): bump version to 1.3.0

[2/2] Docker Rebuild
-------------------------------
Stopping containers...
  myapp_web_1 stopped

Rebuilding images...
  Building web... done

Starting containers...
  myapp_web_1 started

Container Status:
NAME            STATUS          PORTS
myapp_web_1     Up 5 seconds    0.0.0.0:8080->8080/tcp

=== DEPLOY COMPLETE ===
Version: 1.2.3 -> 1.3.0
Containers: 1 running
```

## Semantic Versioning

| Bump | When to use | Example |
|------|-------------|---------|
| **patch** | Bug fixes | 1.0.0 -> 1.0.1 |
| **minor** | New features | 1.0.0 -> 1.1.0 |
| **major** | Breaking changes | 1.0.0 -> 2.0.0 |

## Docker Commands Executed

```bash
# Stop & remove
docker-compose down --remove-orphans

# Rebuild
docker-compose build [--no-cache]

# Start
docker-compose up -d

# Verify
docker-compose ps
```

## Safety

- Confirm before major version bumps
- Show diff before committing version changes
- Warn if containers have unsaved data
- Check container health after restart

## Standalone Actions

Need just one part? Use directly:

```bash
# Version only
/deploy --version-only patch

# Docker only
/deploy --docker-only
```

## Related

- `/commit` - Manual commit after changes
- `/check` - Run tests before deploy
- `/pr` - Create PR for version bump
