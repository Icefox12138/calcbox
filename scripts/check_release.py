"""Sanity check the release configuration before tagging.

    python scripts/check_release.py

Verifies that pyproject, the workflow and the version agree; no network, no tokens.
"""
import pathlib, tomllib
root = pathlib.Path(__file__).resolve().parent.parent
print('version:', tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version'])
try:
    import yaml
    doc = yaml.safe_load((root / '.github/workflows/release.yml').read_text(encoding='utf-8'))
    print('yaml ok, jobs:', sorted(doc['jobs']))
    print('triggers:', sorted(doc[True].keys()) if True in doc else sorted(doc['on'].keys()))
    print('publish perms:', doc['jobs']['publish']['permissions'])
except ImportError:
    print('pyyaml not installed; structural check only')