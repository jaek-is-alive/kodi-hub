#!/usr/bin/env python3
"""Build the Kodi repository artifacts for this repo.

Zips every addon directory (any top-level dir containing addon.xml) into
zips/<id>/<id>-<version>.zip, and generates zips/addons.xml + addons.xml.md5
so the repo can be served straight from raw.githubusercontent.com.

Run from anywhere:  python3 tools/build_repo.py
"""

import hashlib
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIPS = os.path.join(ROOT, 'zips')

EXCLUDE = {'.git', '.github', '__pycache__', '.DS_Store', 'zips', 'tools'}


def find_addons():
    for name in sorted(os.listdir(ROOT)):
        path = os.path.join(ROOT, name)
        if name in EXCLUDE or not os.path.isdir(path):
            continue
        if os.path.isfile(os.path.join(path, 'addon.xml')):
            yield name, path


def zip_addon(addon_id, path, version):
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
    # Kodi's repo browser shows icon/fanart from alongside the zip
    for asset in ('icon.png', 'fanart.png'):
        src = os.path.join(path, asset)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(out_dir, asset))
    print('  %s' % os.path.relpath(out, ROOT))
    return out


def main():
    os.makedirs(ZIPS, exist_ok=True)
    addon_xmls = []
    print('Building repo zips:')
    for addon_id, path in find_addons():
        tree = ET.parse(os.path.join(path, 'addon.xml'))
        root = tree.getroot()
        if root.get('id') != addon_id:
            sys.exit('ERROR: dir %s has addon id %s — rename one.' % (addon_id, root.get('id')))
        version = root.get('version')
        if not re.match(r'^\d+\.\d+\.\d+$', version or ''):
            sys.exit('ERROR: %s has bad version %r' % (addon_id, version))
        zip_addon(addon_id, path, version)
        with open(os.path.join(path, 'addon.xml'), 'r', encoding='utf-8') as f:
            xml_text = f.read()
        xml_text = re.sub(r'<\?xml.*?\?>\s*', '', xml_text, count=1)
        addon_xmls.append(xml_text.strip())

    manifest = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n%s\n</addons>\n' \
               % '\n'.join(addon_xmls)
    manifest_path = os.path.join(ZIPS, 'addons.xml')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write(manifest)
    md5 = hashlib.md5(manifest.encode('utf-8')).hexdigest()
    with open(manifest_path + '.md5', 'w', encoding='utf-8') as f:
        f.write(md5)
    print('wrote zips/addons.xml (+.md5 %s)' % md5)
    print('Done. Commit the zips/ directory so GitHub can serve it.')


if __name__ == '__main__':
    main()
