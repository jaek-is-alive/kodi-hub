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

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
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
        xbmcgui.Dialog().notification("Jacob's Hub", 'Bad JSON in %s' % name,
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
    xbmcgui.Dialog().notification("Jacob's Hub", msg, icon, time)


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


def apply_preset(preset_id):
    """Apply a named settings preset from presets.json across one or more addons."""
    preset = load_json('presets.json').get(preset_id)
    if not preset:
        notify('No preset named "%s"' % preset_id, xbmcgui.NOTIFICATION_ERROR)
        return
    settings = preset.get('settings', {})
    total = sum(len(v) for v in settings.values())
    if not xbmcgui.Dialog().yesno("Jacob's Hub", '%s\n\nApply %d settings?' %
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
    if preset.get('post_notice'):
        xbmcgui.Dialog().ok("Jacob's Hub", preset['post_notice'])


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
