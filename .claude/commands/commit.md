---
name: commit
description: Create git commits using conventional commit format with emojis
---

# /commit - Conventional Commit & Push

Create well-formatted git commits following Conventional Commits specification and push to remote.

## Usage

```
/commit              # Commit and push to current branch
/commit --no-push    # Commit only, skip push
```

## Workflow

Claude Code will:
1. Check for staged changes (`git diff --cached`)
2. If no staged changes, show `git status` and ask what to stage
3. Analyze changes and determine commit type (feat, fix, docs, etc.)
4. Generate descriptive commit message with emoji
5. Execute `git commit`
6. **Push to remote** (`git push`)
7. Show final status

## Commit Format

```
<type>(<scope>): <subject> <emoji>

<body>

<footer>

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

## Commit Types

| Type | Description | Emoji |
|------|-------------|-------|
| **feat** | New feature | ✨ |
| **fix** | Bug fix | 🐛 |
| **docs** | Documentation | 📝 |
| **style** | Formatting | 💄 |
| **refactor** | Code restructuring | ♻️ |
| **perf** | Performance | ⚡ |
| **test** | Tests | ✅ |
| **chore** | Maintenance | 🔧 |
| **ci** | CI/CD | 👷 |
| **build** | Build system | 📦 |

## Push Behavior

- **Default**: Push to current tracking branch
- **New branch**: Use `git push -u origin <branch>`
- **Diverged**: Warn user and ask before force push
- **--no-push**: Skip push step entirely

## Example

**Input**: `/commit`

**Output**:
```bash
# 1. Commit
git commit -m "feat(auth): Add OAuth2 authentication ✨

- Implement OAuth2 provider
- Add token validation
- Create auth middleware

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# 2. Push
git push origin main

# 3. Result
✅ Committed and pushed: feat(auth): Add OAuth2 authentication ✨
   Remote: https://github.com/user/repo/commit/abc1234
```

## Safety

- Never force push to main/master without explicit user confirmation
- Check for upstream changes before push
- Show diff summary before commit

## Related

- `/create pr` - Create pull request after commit
- `/session changelog` - Update changelog before commit
