#!/usr/bin/env python3
"""Vendor the backend addons + their non-official dependency closure into zips/,
so our own repo serves everything the Setup button needs (no external repo at
install time).

Starting from the three seed addons, this walks each addon's <import> deps and
downloads any that are NOT in the official Kodi repo, pulling them from the
upstream community repos below. Run manually (needs network):

    python3 tools/vendor.py && python3 tools/build_repo.py

No auto-refresh: whatever versions are current upstream at run time get frozen
into the repo until you run this again.
"""

import io
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIPS = os.path.join(ROOT, 'zips')
UA = 'Kodi/21.1 (Linux; Android) vendor-script'

# Upstream sources (addons.xml URL, datadir base). Searched together; highest
# version across all sources wins. loopaddon.uk needs a Kodi User-Agent.
SOURCES = [
    ('umbrella',
     'https://raw.githubusercontent.com/umbrellaplug/umbrellaplug.github.io/master/omega/zips/addons.xml',
     'https://raw.githubusercontent.com/umbrellaplug/umbrellaplug.github.io/master/omega/zips/'),
    ('cocoscrapers',
     'https://raw.githubusercontent.com/not-coco-joe/repository.cocoscrapers/master/zips/addons.xml',
     'https://raw.githubusercontent.com/not-coco-joe/repository.cocoscrapers/master/zips/'),
    ('theloop',
     'https://loopaddon.uk/zips19/addons.xml',
     'https://loopaddon.uk/zips19/'),
    ('smrzips',
     'https://raw.githubusercontent.com/Gujal00/smrzips/master/zips/addons.xml',
     'https://raw.githubusercontent.com/Gujal00/smrzips/master/zips/'),
]

SEEDS = ['plugin.video.umbrella', 'script.module.cocoscrapers', 'plugin.video.the-loop']

# In the official Kodi repo (or virtual) -> never vendor; Kodi resolves these.
OFFICIAL = {
    'script.module.requests', 'script.module.routing', 'script.module.unidecode',
    'script.module.tzlocal', 'script.module.pytz', 'script.module.pycryptodome',
    'script.module.inputstreamhelper', 'inputstream.adaptive', 'script.module.pysocks',
    'script.module.six', 'script.module.chardet', 'script.module.idna',
    'script.module.urllib3', 'script.module.certifi', 'script.module.dateutil',
    'script.module.kodi-six', 'script.module.simplejson', 'script.module.beautifulsoup4',
    'script.module.soupsieve', 'script.module.setuptools', 'plugin.video.youtube',
    'script.module.charset-normalizer', 'script.module.future', 'script.module.pyaes',
    # these are in the official Kodi repo too (The Loop relies on that, doesn't bundle them):
    'script.module.pyamf', 'plugin.video.dailymotion_com', 'script.module.python.twitch',
    'plugin.googledrive',
}


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()


def vparse(v):
    parts = []
    for p in (v or '').replace('~', '.').replace('-', '.').replace('+', '.').split('.'):
        parts.append((0, int(p)) if p.isdigit() else (1, p))
    return parts


def load_index():
    """Merge every source's addons.xml -> {id: (version, datadir)} keeping highest."""
    index = {}
    for name, ax_url, datadir in SOURCES:
        try:
            data = fetch(ax_url)
            root = ET.fromstring(data)
        except Exception as e:
            print('  WARN: source %s unavailable: %s' % (name, e))
            continue
        n = 0
        for addon in root.findall('addon'):
            aid, ver = addon.get('id'), addon.get('version')
            if not aid:
                continue
            cur = index.get(aid)
            if cur is None or vparse(ver) > vparse(cur[0]):
                index[aid] = (ver, datadir)
            n += 1
        print('  source %-13s %d addons' % (name, n))
    return index


def imports_of(zip_bytes):
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    name = next((n for n in zf.namelist()
                 if n.count('/') == 1 and n.endswith('/addon.xml')), None)
    if not name:
        return []
    root = ET.fromstring(zf.read(name))
    return [imp.get('addon') for imp in root.iter('import') if imp.get('addon')]


def download_addon(aid, index):
    if aid not in index:
        return None, 'not in any source'
    ver, datadir = index[aid]
    url = '%s%s/%s-%s.zip' % (datadir, aid, aid, ver)
    try:
        data = fetch(url)
    except Exception as e:
        return None, 'download failed: %s' % e
    if data[:2] != b'PK':
        return None, 'not a zip: %s' % url
    out_dir = os.path.join(ZIPS, aid)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, '%s-%s.zip' % (aid, ver)), 'wb') as f:
        f.write(data)
    try:  # best-effort icon/fanart for the repo browser
        zf = zipfile.ZipFile(io.BytesIO(data))
        for asset in ('icon.png', 'fanart.png'):
            n = '%s/%s' % (aid, asset)
            if n in zf.namelist():
                with open(os.path.join(out_dir, asset), 'wb') as f:
                    f.write(zf.read(n))
    except Exception:
        pass
    return (ver, data), None


def main():
    print('Loading upstream indexes...')
    index = load_index()
    if not index:
        sys.exit('No sources reachable - aborting.')
    print('Indexed %d addons total.\n' % len(index))

    queue, done, missing = list(SEEDS), {}, []
    while queue:
        aid = queue.pop(0)
        if aid in done or aid in OFFICIAL or aid.startswith(('xbmc.', 'kodi.')):
            continue
        res, err = download_addon(aid, index)
        if err:
            print('  MISS %-34s %s' % (aid, err))
            missing.append(aid)
            done[aid] = None
            continue
        ver, data = res
        done[aid] = ver
        print('  OK   %-34s %s' % (aid, ver))
        for dep in imports_of(data):
            if dep not in done and dep not in OFFICIAL and not dep.startswith(('xbmc.', 'kodi.')):
                queue.append(dep)

    vendored = {k: v for k, v in done.items() if v}
    print('\nVendored %d addons into zips/:' % len(vendored))
    for aid in sorted(vendored):
        print('  %s %s' % (aid, vendored[aid]))
    if missing:
        print('\nMISSING (may be official - Kodi still resolves those at install; '
              'otherwise add a source): %s' % ', '.join(sorted(missing)))
    print('\nNext: python3 tools/build_repo.py')


if __name__ == '__main__':
    main()
