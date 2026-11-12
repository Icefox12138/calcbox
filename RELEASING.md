# Releasing calcbox

The release runs in GitHub Actions and authenticates to PyPI with **Trusted
Publishing (OIDC)**. No PyPI token is created, stored, or pasted anywhere.

## One-time setup

1. Publish the first version manually once (or use a *pending publisher*):
   on PyPI → *Your projects* → *Publishing tools* → **Add a new pending
   publisher** with:

   | Field | Value |
   |---|---|
   | PyPI project name | `calcbox` |
   | Owner | `Icefox12138` |
   | Repository name | `calcbox` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

2. In the GitHub repository: *Settings → Environments → New environment* named
   `pypi` (no secrets needed; it exists so the workflow can require approval
   before publishing if you want that).

That is the whole setup. Nothing secret is copied.

## Before you tag

```bash
python scripts/check_release.py      # pyproject version, workflow parsed, jobs present
```

## Cutting a release

```bash
# 1. bump the version in pyproject.toml and calcbox/__init__.py
# 2. update README.md "Status" and MIGRATION.md
git commit -am "release: 0.4.0"
git tag v0.4.0
git push origin main --tags
```

The tag triggers `.github/workflows/release.yml`:

| job | what it does |
|---|---|
| `build` | asserts tag == version, runs the test suite, `uv build`, `twine check` |
| `publish` | downloads the artefacts and uploads via OIDC (`id-token: write`) |

A tag that does not match `project.version` fails before anything is uploaded.

## Publishing by hand (no tag)

Actions → *release* → **Run workflow** → set `publish` to true. Same OIDC path,
no token.

## Why not a token

A PyPI token in a repository secret is still a long-lived credential that can be
exfiltrated and has to be rotated. OIDC issues a signed, short-lived token bound
to this repository, workflow and environment. It also produces a provenance
attestation that PyPI shows on the project page.

## Fallback (offline machines)

If you must publish from a laptop, put the token in `~/.pypirc` once and run
`uvx twine upload dist/*`; `twine` reads the file itself, so the token never
enters a shell history or a chat log.

## npm

calcbox is Python-only. If the MCP server is ever published to npm as well, add
a second job with `NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}`, or use npm's
trusted publishing for GitHub Actions. Not needed today.


## Repository metadata

No CLI is needed; the fields live in the web UI.

| Field | Value |
|---|---|
| Description | Backend-agnostic math compute kernel: symbolic, numeric, units and control, with provenance (backend, version, assumptions, verification) in every answer. Python API, CLI, HTTP and MCP. |
| Website | https://pypi.org/project/calcbox/ (after the first release) |
| Topics | mathematics, sympy, scipy, symbolic-computation, computer-algebra, units, control-systems, calculator, provenance, mcp, mcp-server, python |

Description: repo → **About** (gear icon) → paste → Save.
Topics: same dialog → **Topics** → add each one → Save.

Topics stay truthful: no llm, no ai, no sandbox — the package evaluates
expressions and its sandbox is audit-only.
## Creating the `pypi` environment

The workflow declares `environment: pypi`. That gives two things: the OIDC token
PyPI verifies, and an optional human approval gate. GitHub creates the environment
automatically on the first run, but creating it first lets you add the gate.

### Web UI

1. Repository → **Settings** → **Environments** → **New environment**
2. Name: `pypi` (must match the workflow exactly) → **Configure environment**
3. **Deployment protection rules**
   - ✅ **Required reviewers** → add yourself (up to six people or teams).
     A run that reaches `publish` then waits for approval.
   - **Deployment branches and tags** → *Selected branches and tags* → add a
     **tag** rule `v*`, so only release tags can deploy.
     Do **not** pick "Protected branches only": a plain tag is not a protected
     branch and the deployment would be rejected.
4. **Environment secrets**: leave empty. Trusted Publishing uses no secret.
5. **Save protection rules**

### Without a CLI

`gh` is not installable on this machine, and the environment fields are all in
the web UI above, so nothing else is required. If you ever automate it, the
REST calls are:

```bash
curl -sX PUT -H "Authorization: Bearer $GH_TOKEN" \
  https://api.github.com/repos/Icefox12138/calcbox/environments/pypi

curl -sX PUT -H "Authorization: Bearer $GH_TOKEN" -H "Content-Type: application/json" \
  https://api.github.com/repos/Icefox12138/calcbox/environments/pypi \
  -d '{"reviewers":[{"type":"User","id":123456}],"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}'
```

`$GH_TOKEN` is set in your own terminal, never pasted into a chat.
### Checking it worked

- Settings → Environments shows `pypi` with the reviewer you added.
- Push a tag → the run stops at **publish** with *"Waiting for approval"*;
  approve under **Actions → the run → Review deployments**.
- If you remove the environment, the workflow still runs but without the gate
  (GitHub recreates it unprotected) — and PyPI's pending publisher will only
  accept the token when the declared environment matches what it was configured
  with.


## First push without `gh`

The local machine cannot install `gh`, so use SSH: it is the only route that needs
no token at all.

1. Create an **empty** repository on GitHub (no README, no .gitignore):
   <https://github.com/new> — owner `Icefox12138`, name `calcbox`, private.
2. Run the helper once, from a normal PowerShell window (not inside any sandbox).
   No PowerShell 7 is required — Windows PowerShell 5.1 works, and the wrapper
   bypasses the execution policy for this run only:

   ```powershell
   scripts\setup-ssh.cmd
   ```

   Equivalent without the wrapper:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup-ssh.ps1
   ```

   It generates `id_ed25519` if missing, copies the **public** key to the
   clipboard, opens the GitHub "new SSH key" page, verifies the handshake, and
   points `origin` at `git@github.com:Icefox12138/calcbox.git`.
3. ```powershell
   git push -u origin main
   ```

### If SSH is not an option

Cache a token once, in your own terminal, so it never enters a chat log:

```powershell
git remote set-url origin https://github.com/Icefox12138/calcbox.git
git push -u origin main      # username: your account, password: the token
```

Windows Credential Manager (`wincred`, already configured) stores it, and later
pushes need no credential. Tokens used this way should be fine-grained and
short-lived (7 days).


## PowerShell compatibility

The helper targets **Windows PowerShell 5.1** (the version that ships with
Windows) and also runs under PowerShell 7. It uses nothing newer than
`Set-Clipboard`, and it has no Chinese text, so the file needs no BOM and 5.1's
ANSI default does not mangle it.

Verified on this machine:

```
parses OK under 5.1.26100.9711
key generation works (-N '""' produces an unencrypted key non-interactively)
Set-Clipboard available
```

`scripts/setup-ssh.cmd` exists because 5.1 refuses to run `.ps1` files under the
default `Restricted` policy; the wrapper passes `-ExecutionPolicy Bypass` for that
single invocation instead of changing a machine-wide setting.
