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

Copy-paste for `gh` (no secrets involved):

```bash
gh repo create Icefox12138/calcbox --private --source . --push

gh repo edit Icefox12138/calcbox \
  --description "Backend-agnostic math compute kernel: symbolic, numeric, units and control, with provenance (backend, version, assumptions, verification) in every answer. Python API, CLI, HTTP and MCP." \
  --add-topic mathematics --add-topic sympy --add-topic scipy \
  --add-topic symbolic-computation --add-topic computer-algebra \
  --add-topic units --add-topic control-systems --add-topic calculator \
  --add-topic provenance --add-topic mcp --add-topic mcp-server \
  --add-topic python
```

Same thing over the REST API:

```bash
curl -sX PATCH -H "Authorization: Bearer $GH_TOKEN" \
  https://api.github.com/repos/Icefox12138/calcbox \
  -d '{"description":"...","homepage":"https://pypi.org/project/calcbox/"}' -H "Content-Type: application/json"

curl -sX PUT -H "Authorization: Bearer $GH_TOKEN" \
  https://api.github.com/repos/Icefox12138/calcbox/topics \
  -d '{"names":["mathematics","sympy","scipy","symbolic-computation","computer-algebra","units","control-systems","calculator","provenance","mcp","mcp-server","python"]}' \
  -H "Content-Type: application/json"
```

Topics are chosen to stay truthful: no `llm`, no `ai`, no `sandbox` — this package
evaluates expressions, and its sandbox is audit-only.
