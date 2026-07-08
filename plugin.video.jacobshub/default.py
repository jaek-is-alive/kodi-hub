# -*- coding: utf-8 -*-
# Jacob's Hub — personal Kodi launcher addon.
# Menus live in resources/menu.json; upstream addon URLs/actions live in
# resources/targets.json so they can be fixed without touching code when
# Umbrella / The Loop change their internals.

import json
import os
import sys
import traceback
import urllib.parse
import random

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
THEATER_NAME = "Jake's Config Hub"
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]

RES = os.path.join(ADDON_PATH, 'resources')
ICON = os.path.join(ADDON_PATH, 'icon.png')
FANART = os.path.join(ADDON_PATH, 'fanart.png')


def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[%s] %s' % (ADDON_ID, msg), level)


def load_json(name):
    path = os.path.join(RES, name)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        log('failed to load %s\n%s' % (path, traceback.format_exc()), xbmc.LOGERROR)
        xbmcgui.Dialog().notification(THEATER_NAME, 'Bad JSON in %s' % name,
                                      xbmcgui.NOTIFICATION_ERROR)
        return {}


MENU = load_json('menu.json')
TARGETS = load_json('targets.json')


def target(dotted, default=''):
    """Look up 'umbrella.actions.movies' style keys in targets.json."""
    node = TARGETS
    for part in dotted.split('.'):
        if not isinstance(node, dict) or part not in node:
            log('missing target key: %s' % dotted, xbmc.LOGWARNING)
            return default
        node = node[part]
    return node


def hub_url(**params):
    return BASE_URL + '?' + urllib.parse.urlencode(params)


def installed(addon_id):
    return xbmc.getCondVisibility('System.HasAddon(%s)' % addon_id) == 1


def other_addon(addon_id):
    try:
        return xbmcaddon.Addon(addon_id)
    except Exception:
        return None


def notify(msg, icon=xbmcgui.NOTIFICATION_INFO, time=4000):
    xbmcgui.Dialog().notification(THEATER_NAME, msg, icon, time)


def show_trivia():
    """Home screen: pop a random trivia question, wait, then reveal the answer.
    Called AFTER the menu is rendered, so the short wait never blocks the UI."""
    trivia = load_json('trivia.json')
    labels = {'pokemon': '\u26A1 Pok\u00e9mon Trivia',
              'kirby': '\u2B50 Kirby Trivia',
              'minecraft': '\u26CF\uFE0F Minecraft Trivia'}
    pool = []
    for topic, items in trivia.items():
        label = labels.get(topic, topic.title() + ' Trivia')
        pool.extend((label, qa) for qa in items)
    if not pool:
        return
    win = xbmcgui.Window(10000)
    last = win.getProperty('jacobshub_last_trivia')
    heading, qa = random.choice(pool)
    for _ in range(5):  # avoid repeating the same question twice in a row
        if qa.get('q') != last:
            break
        heading, qa = random.choice(pool)
    win.setProperty('jacobshub_last_trivia', qa.get('q', ''))
    xbmcgui.Dialog().notification(heading, qa.get('q', ''), ICON, 7000)
    xbmc.sleep(6500)  # give everyone a few seconds to guess
    xbmcgui.Dialog().notification('\U0001F4A1 Answer', qa.get('a', ''), ICON, 6000)


# ---------------------------------------------------------------------------
# directory building
# ---------------------------------------------------------------------------

def add_item(label, url, is_folder, art=None, plot=None):
    li = xbmcgui.ListItem(label)
    li.setArt({'icon': (art or ICON), 'thumb': (art or ICON), 'fanart': FANART})
    if plot:
        li.setInfo('video', {'plot': plot})
    xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=is_folder)


def render_menu(menu_id):
    xbmcplugin.setPluginCategory(HANDLE, THEATER_NAME)
    items = MENU.get(menu_id)
    if items is None:
        notify('No menu named "%s" in menu.json' % menu_id, xbmcgui.NOTIFICATION_ERROR)
        items = []
    for it in items:
        label = it.get('label', '???')
        plot = it.get('plot')
        art = it.get('art')
        # requires: hide items whose backing addon is missing (show greyed hint instead)
        req = it.get('requires')
        if req and not installed(req):
            add_item('[COLOR gray]%s (install %s)[/COLOR]' % (label, req),
                     hub_url(action='missing', addon=req), False, art, plot)
            continue
        if 'menu' in it:
            add_item(label, hub_url(action='menu', id=it['menu']), True, art, plot)
        elif 'path' in it:
            # direct deep-link into another addon
            add_item(label, it['path'], it.get('folder', True), art, plot)
        elif 'run' in it:
            # RunPlugin-style fire-and-forget target
            add_item(label, hub_url(action='run', target=it['run']), False, art, plot)
        elif 'hub' in it:
            # internal hub action, e.g. search_movies, auth, coco_preset
            params = dict(it.get('params', {}))
            params['action'] = it['hub']
            add_item(label, hub_url(**params), it.get('folder', False), art, plot)
        elif 'builtin' in it:
            add_item(label, hub_url(action='builtin', cmd=it['builtin']), False, art, plot)
    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
    if menu_id == 'root':
        show_trivia()


# ---------------------------------------------------------------------------
# hub actions
# ---------------------------------------------------------------------------

def do_search(kind):
    """Prompt once, then jump straight into the upstream addon's search results."""
    spec = target('search.%s' % kind)
    if not spec:
        notify('No search target "%s" configured' % kind, xbmcgui.NOTIFICATION_ERROR)
        return
    query = xbmcgui.Dialog().input(spec.get('title', 'Search'))
    if not query:
        return
    # 'path' quoting for addons that take the query as a URL path segment
    # (The Loop); default query-string quoting for Umbrella's &name= param.
    quote = urllib.parse.quote if spec.get('quote') == 'path' else urllib.parse.quote_plus
    url = spec['url'].replace('{query}', quote(query))
    xbmc.executebuiltin('Container.Update(%s)' % url)


def do_run(dotted):
    """Fire a RunPlugin target defined in targets.json (auth buttons etc.)."""
    url = target(dotted)
    if not url:
        notify('Target %s not configured' % dotted, xbmcgui.NOTIFICATION_ERROR)
        return
    log('RunPlugin(%s)' % url)
    xbmc.executebuiltin('RunPlugin(%s)' % url)


def open_settings(addon_id):
    if not installed(addon_id):
        notify('%s is not installed' % addon_id, xbmcgui.NOTIFICATION_WARNING)
        return
    xbmc.executebuiltin('Addon.OpenSettings(%s)' % addon_id)


def apply_preset(preset_id, confirm=True):
    """Apply a named settings preset from presets.json across one or more addons.
    confirm=False skips the yes/no + post-notice (used by the one-tap Setup flow)."""
    preset = load_json('presets.json').get(preset_id)
    if not preset:
        notify('No preset named "%s"' % preset_id, xbmcgui.NOTIFICATION_ERROR)
        return
    settings = preset.get('settings', {})
    total = sum(len(v) for v in settings.values())
    if confirm and not xbmcgui.Dialog().yesno(THEATER_NAME, '%s\n\nApply %d settings?' %
                                  (preset.get('label', preset_id), total)):
        return
    applied, failed = 0, []
    for addon_id, kv in settings.items():
        target_addon = other_addon(addon_id) if installed(addon_id) else None
        if target_addon is None:
            log('preset %s: %s not installed' % (preset_id, addon_id), xbmc.LOGWARNING)
            failed.extend('%s (missing addon)' % k for k in kv)
            continue
        for key, value in kv.items():
            try:
                target_addon.setSetting(key, str(value))
                applied += 1
            except Exception:
                log('setSetting %s.%s failed\n%s' % (addon_id, key, traceback.format_exc()),
                    xbmc.LOGERROR)
                failed.append(key)
    msg = 'Applied %d settings' % applied
    if failed:
        msg += ', %d failed (see log)' % len(failed)
    notify(msg)
    if confirm and preset.get('post_notice'):
        xbmcgui.Dialog().ok(THEATER_NAME, preset['post_notice'])


def status_report():
    """One screen: what's installed and which debrid services are connected."""
    lines = []
    for label, key in [('Umbrella', 'ids.umbrella'),
                       ('CocoScrapers', 'ids.cocoscrapers'),
                       ('The Loop', 'ids.theloop')]:
        aid = target(key)
        ok = installed(aid)
        ver = ''
        if ok:
            a = other_addon(aid)
            ver = ' v' + a.getAddonInfo('version') if a else ''
        lines.append('%s [%s]: %s%s' % (label, aid,
                                        'INSTALLED' if ok else '[COLOR red]MISSING[/COLOR]', ver))
    lines.append('')
    umb = other_addon(target('ids.umbrella'))
    if umb:
        for svc, spec in (TARGETS.get('debrid_status') or {}).items():
            try:
                val = umb.getSetting(spec['setting'])
            except Exception:
                val = ''
            connected = bool(val) and val not in ('', 'false')
            lines.append('%s: %s' % (svc, '[COLOR green]connected[/COLOR]' if connected
                                     else 'not connected'))
    xbmcgui.Dialog().textviewer("Jacob's Hub — status", '\n'.join(lines))


def _install_addon(addon_id, timeout=90):
    """Ask Kodi to install an addon from an available repo; wait for it to appear.
    Works because our own repo (already installed) vendors these addons, so Kodi
    resolves them and their dependencies without any external repo."""
    if installed(addon_id):
        xbmc.executebuiltin('EnableAddon(%s)' % addon_id)
        return True
    xbmc.executebuiltin('InstallAddon(%s)' % addon_id)
    for _ in range(timeout):  # InstallAddon is async and may prompt
        if installed(addon_id):
            xbmc.executebuiltin('EnableAddon(%s)' % addon_id)
            return True
        xbmc.sleep(1000)
    return installed(addon_id)


def do_setup():
    """One-tap install of the backend addons, served from our own repo, then
    optionally wire CocoScrapers into Umbrella."""
    steps = TARGETS.get('setup', [])
    if not steps:
        notify('No setup targets configured', xbmcgui.NOTIFICATION_ERROR)
        return
    title = "Jake's Config Hub \u2014 Setup"
    todo = [s for s in steps if not installed(s['addon_id'])]
    ok, failed = [], []
    if todo:
        names = '\n'.join(' - ' + s.get('label', s['addon_id']) for s in todo)
        if xbmcgui.Dialog().yesno(title,
                                  'Install the backend add-ons?\n\n%s\n\n'
                                  'Kodi may ask you to confirm each one.' % names):
            for s in todo:
                label = s.get('label', s['addon_id'])
                notify('Installing %s\u2026' % label)
                (ok if _install_addon(s['addon_id']) else failed).append(label)

    # Always offer to (re)configure CocoScrapers when both are present.
    umb, coco = target('ids.umbrella'), target('ids.cocoscrapers')
    if installed(umb) and installed(coco):
        if xbmcgui.Dialog().yesno(title,
                                  'Configure CocoScrapers for Umbrella now?\n\n'
                                  'Wires it in and turns on the recommended providers.'):
            apply_preset('wire_cocoscrapers', confirm=False)
            apply_preset('coco_recommended', confirm=False)
            notify('CocoScrapers configured \u2705')

    if todo:
        summary = 'Installed: %s' % (', '.join(ok) if ok else 'none')
        if failed:
            summary += '\nFailed (try again / check log): %s' % ', '.join(failed)
    else:
        summary = 'Everything is already installed. \U0001F44D'
    xbmcgui.Dialog().ok(title, summary)
    xbmc.executebuiltin('Container.Refresh')


def do_surprise(kind):
    """Spin a random pick: a movie (via Umbrella search) or a live sport zone."""
    pool = target('surprise.%s' % kind)
    if not pool:
        notify('No surprises configured for "%s"' % kind, xbmcgui.NOTIFICATION_ERROR)
        return
    pick = random.choice(pool)
    if kind == 'movie':
        notify('\U0001F3AC Tonight\'s pick: %s' % pick)
        url = ('plugin://plugin.video.umbrella/?action=movieSearchterm&name=%s'
               % urllib.parse.quote_plus(pick))
    else:
        notify('\U0001F3B2 Surprise: %s!' % pick.get('name', 'Sport'))
        url = pick['url']
    xbmc.executebuiltin('Container.Update(%s)' % url)


def do_clear_caches():
    """One button: clear Umbrella's caches and The Loop's cache (whatever's installed)."""
    jobs = [('plugin.video.umbrella', 'maintenance.umbrella_clear_all'),
            ('plugin.video.the-loop', 'maintenance.loop_clear_cache')]
    done = []
    for addon_id, dotted in jobs:
        if installed(addon_id):
            url = target(dotted)
            if url:
                xbmc.executebuiltin('RunPlugin(%s)' % url)
                done.append(addon_id.split('.')[-1])
    notify('Cleared caches: %s' % (', '.join(done) if done else 'nothing to clear'))


# ---------------------------------------------------------------------------
# router
# ---------------------------------------------------------------------------

def router():
    params = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
    action = params.get('action')
    log('route: %s' % (params or 'root'), xbmc.LOGDEBUG)

    if action is None:
        render_menu('root')
    elif action == 'menu':
        render_menu(params.get('id', 'root'))
    elif action == 'search':
        do_search(params.get('kind', 'movies'))
    elif action == 'run':
        do_run(params.get('target', ''))
    elif action == 'settings':
        open_settings(params.get('id', ''))
    elif action == 'preset':
        apply_preset(params.get('id', ''))
    elif action == 'status':
        status_report()
    elif action == 'setup':
        do_setup()
    elif action == 'clear_caches':
        do_clear_caches()
    elif action == 'surprise':
        do_surprise(params.get('kind', 'movie'))
    elif action == 'builtin':
        xbmc.executebuiltin(params.get('cmd', ''))
    elif action == 'missing':
        notify('Install %s first (see README)' % params.get('addon', '?'),
               xbmcgui.NOTIFICATION_WARNING)
    else:
        notify('Unknown action: %s' % action, xbmcgui.NOTIFICATION_ERROR)


if __name__ == '__main__':
    try:
        router()
    except Exception:
        log('unhandled error\n%s' % traceback.format_exc(), xbmc.LOGERROR)
        notify('Error — check kodi.log', xbmcgui.NOTIFICATION_ERROR)
        raise
