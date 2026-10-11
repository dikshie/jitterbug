# How to Pull and Merge Code in Jitterbug

This repository uses a fork-based workflow with two remotes:
- **`upstream`**: The canonical source repository (`https://github.com/estcarisimo/jitterbug`)
- **`origin`**: Your personal fork (`git@github.com:dikshie/jitterbug.git`)

---

## 1. Pulling Latest Upstream Code into Local Base Branch (`main`)

Use this workflow to sync your local `main` branch and fork with upstream changes.

### Step 1: Ensure your working tree is clean
Check that you do not have uncommitted changes:
```bash
git status
```
If you have work in progress, stash it (`git stash`) or commit it to a feature branch.

### Step 2: Switch to the `main` branch
```bash
git checkout main
```

### Step 3: Fetch the latest changes from upstream
```bash
git fetch upstream
```

### Step 4: Merge upstream into your local `main`
```bash
# If your local main has no divergent commits (fast-forward):
git merge --ff-only upstream/main

# Or if you have local commits on main and want a standard merge:
git merge upstream/main
```

### Step 5: Sync the environment and verify
Whenever the base code updates, sync dependencies using `uv` and ensure tests pass:
```bash
uv sync --extra bcp --extra visualization
uv run ruff check src/ tests/
uv run pytest -m "not slow"
```

### Step 6: Push the updated `main` to your fork
```bash
git push origin main
```

---

## 2. Bringing Latest Base Code into an Active Feature Branch

When developing a feature branch (e.g., `feat/my-feature`), keep it synchronized with the latest upstream `main`.

### Step 1: Fetch upstream and switch to your feature branch
```bash
git fetch upstream
git checkout feat/my-feature
```

### Step 2: Rebase or merge from upstream
```bash
# Option A: Rebase (recommended for linear git history)
git rebase upstream/main

# Option B: Standard merge commit
git merge upstream/main
```
If merge conflicts occur, resolve them in your editor, stage the files (`git add <file>`), and continue:
```bash
git rebase --continue
# or if merging:
git commit
```

---

## 3. Merging Feature Code into the Base Repository (`main`)

As defined in [`AGENTS.md`](AGENTS.md), `main` is protected by the `protect-main` ruleset. Direct pushes to `main` are blocked. All code must be merged via the Pull Request workflow.

### Step 1: Run local quality gates
Ensure all linter, type, and test suites pass locally:
```bash
uv run ruff check src/ tests/ examples/ tools/
uv run ruff format --check src/ tests/ examples/ tools/
uv run mypy src/jitterbug
uv run pytest
```

### Step 2: Push your feature branch to your fork
```bash
git push -u origin feat/my-feature
```

### Step 3: Open the Pull Request
```bash
gh pr create --base main --head feat/my-feature
```
Complete the PR template checklist.

### Step 4: Monitor CI checks
Wait for GitHub Actions CI to turn green:
```bash
gh pr checks <PR_NUMBER> --watch
```

### Step 5: Independent review & squash merge
Repository policy requires an independent review returning `APPROVE`. Once CI is green and the review verdict is `APPROVE`:
```bash
gh pr merge <PR_NUMBER> --squash
```
