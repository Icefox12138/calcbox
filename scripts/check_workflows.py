import pathlib, yaml
root = pathlib.Path(__file__).resolve().parent.parent
for name in ('ci.yml', 'release.yml'):
    doc = yaml.safe_load((root / '.github/workflows' / name).read_text(encoding='utf-8'))
    print(name, '->', sorted(doc['jobs']), '| on:', sorted((doc.get('on') or doc.get(True)).keys()))