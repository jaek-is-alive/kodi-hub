#!/usr/bin/env python3
"""Build the Kodi repository artifacts.

1. Zips our own source addons (any top-level dir with addon.xml) into
   zips/<id>/<id>-<version>.zip.
2. Generates zips/addons.xml + .md5 from EVERY addon zip present in zips/ —
   both our own and any vendored third-party zips placed there by tools/vendor.py.

Serve zips/ straight from GitHub Pages / raw.githubusercontent.com.
Run from anywhere:  python3 tools/build_repo.py
"""

import hashlib
import io
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIPS = os.path.join(ROOT, 'zips')

EXCLUDE = {'.git', '.github', '__pycache__', '.DS_Store', 'zips', 'tools', '.claude'}


def find_source_addons():
    for name in sorted(os.listdir(ROOT)):
        path = os.path.join(ROOT, name)
        if name in EXCLUDE or not os.path.isdir(path):
            continue
        if os.path.isfile(os.path.join(path, 'addon.xml')):
            yield name, path


def zip_source_addon(addon_id, path, version):
    out_dir = os.path.join(ZIPS, addon_id)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, '%s-%s.zip' % (addon_id, version))
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE]
            for fn in sorted(filenames):
                if fn in EXCLUDE:
                    continue
                full = os.path.join(dirpath, fn)
                arc = os.path.join(addon_id, os.path.relpath(full, path))
                z.write(full, arc)
    for asset in ('icon.png', 'fanart.png'):
        src = os.path.join(path, asset)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(out_dir, asset))
    return out


def vparse(v):
    parts = []
    for p in (v or '').replace('~', '.').replace('-', '.').replace('+', '.').split('.'):
        parts.append((0, int(p)) if p.isdigit() else (1, p))
    return parts


def newest_zip(addon_dir):
    zips = [f for f in os.listdir(addon_dir) if f.endswith('.zip')]
    if not zips:
        return None
    def ver_of(fn):
        m = re.match(r'.+-(.+)\.zip$', fn)
        return vparse(m.group(1)) if m else []
    return os.path.join(addon_dir, max(zips, key=ver_of))


def addon_xml_from_zip(zip_path):
    with open(zip_path, 'rb') as f:
        zf = zipfile.ZipFile(io.BytesIO(f.read()))
    name = next((n for n in zf.namelist()
                 if n.count('/') == 1 and n.endswith('/addon.xml')), None)
    if not name:
        raise ValueError('no top-level addon.xml in %s' % zip_path)
    text = zf.read(name).decode('utf-8')
    text = re.sub(r'<\?xml.*?\?>\s*', '', text, count=1)
    return text.strip()


def main():
    os.makedirs(ZIPS, exist_ok=True)

    print('Building our own addon zips:')
    for addon_id, path in find_source_addons():
        tree = ET.parse(os.path.join(path, 'addon.xml'))
        root = tree.getroot()
        if root.get('id') != addon_id:
            sys.exit('ERROR: dir %s has addon id %s' % (addon_id, root.get('id')))
        version = root.get('version')
        if not re.match(r'^\d+\.\d+\.\d+$', version or ''):
            sys.exit('ERROR: %s has bad version %r' % (addon_id, version))
        out = zip_source_addon(addon_id, path, version)
        print('  %s' % os.path.relpath(out, ROOT))

    print('Collecting all addon zips (ours + vendored) for the manifest:')
    blocks = []
    for name in sorted(os.listdir(ZIPS)):
        addon_dir = os.path.join(ZIPS, name)
        if not os.path.isdir(addon_dir):
            continue
        zpath = newest_zip(addon_dir)
        if not zpath:
            continue
        try:
            blocks.append(addon_xml_from_zip(zpath))
            print('  + %-36s %s' % (name, os.path.basename(zpath)))
        except Exception as e:
            print('  ! skipping %s: %s' % (name, e))

    manifest = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<addons>\n%s\n</addons>\n' % '\n'.join(blocks))
    manifest_path = os.path.join(ZIPS, 'addons.xml')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write(manifest)
    md5 = hashlib.md5(manifest.encode('utf-8')).hexdigest()
    with open(manifest_path + '.md5', 'w', encoding='utf-8') as f:
        f.write(md5)
    print('\nwrote zips/addons.xml (%d addons, md5 %s)' % (len(blocks), md5))
    print('Commit the zips/ directory so GitHub serves it.')


if __name__ == '__main__':
    main()
