---
name: tdd
description: Guide Test-Driven Development with Red-Green-Refactor discipline
---

# /tdd - Test-Driven Development Guide

Follow TDD best practices with Red-Green-Refactor workflow and git integration.

## Usage

```
/tdd <feature-name>
```

## Red-Green-Refactor Cycle

### 🔴 Red: Write Failing Test

1. **Write Test First**
   ```bash
   # Example: tests/test_auth.py
   def test_login_success():
       user = login("test@example.com", "password")
       assert user.is_authenticated == True
   ```

2. **Run Test (Must Fail)**
   ```bash
   pytest tests/test_auth.py -v
   # ❌ FAILED - Expected behavior
   ```

3. **Commit Failing Test**
   ```bash
   git add tests/test_auth.py
   git commit -m "test: Add login success test (RED) 🔴"
   ```

### 🟢 Green: Make It Pass

1. **Implement Minimum Code**
   ```python
   # src/auth.py
   def login(email, password):
       user = User(email=email)
       user.is_authenticated = True
       return user
   ```

2. **Run Test (Must Pass)**
   ```bash
   pytest tests/test_auth.py -v
   # ✅ PASSED
   ```

3. **Commit Implementation**
   ```bash
   git add src/auth.py
   git commit -m "feat: Implement login function (GREEN) 🟢"
   ```

### ♻️ Refactor: Improve Code

1. **Improve Without Breaking**
   ```python
   # Refactor for real authentication
   def login(email, password):
       user = User.authenticate(email, password)
       return user
   ```

2. **Run Test (Must Still Pass)**
   ```bash
   pytest tests/test_auth.py -v
   # ✅ PASSED
   ```

3. **Commit Refactoring**
   ```bash
   git add src/auth.py
   git commit -m "refactor: Use User.authenticate method ♻️"
   ```

## Phase Integration

### Phase 1: Implementation
- Start with `/tdd <feature>` before coding
- Write test first (RED)
- Implement (GREEN)
- Refactor

### Phase 2: Testing
- All features have tests from Phase 1
- 1:1 test pairing enforced
- High coverage guaranteed

## Workflow

```bash
/tdd user-authentication

# Claude Code guides:
# 1. Create test file: tests/test_auth.py
# 2. Write failing test
# 3. Commit: "test: Add auth test (RED) 🔴"
# 4. Create implementation: src/auth.py
# 5. Make test pass
# 6. Commit: "feat: Implement auth (GREEN) 🟢"
# 7. Refactor if needed
# 8. Commit: "refactor: Improve auth ♻️"
```

## Best Practices

1. **One Test at a Time**
   - Focus on single behavior
   - Small iterations

2. **Git Commits Mark Progress**
   - RED: Failing test
   - GREEN: Passing implementation
   - REFACTOR: Improvement

3. **Never Skip RED**
   - Always see test fail first
   - Confirms test works

4. **Refactor Often**
   - Clean code continuously
   - Tests provide safety net

## Integration with Agents

- **test-engineer**: Generate test suggestions
- **debugger**: Fix failing tests
- **code-reviewer**: Review refactoring

## Related

- `/check` - Quality checks
- `/check --perf` - Performance
- `scripts/validate-phase-1.sh` - 1:1 test pairing
- Phase 2 validation
