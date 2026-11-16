# -*- coding: utf-8 -*-
"""Dump the IEC object tree of a project for offline review (no login, no download)."""
import os, io, json, traceback
import scriptengine as api

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULT = os.path.join(ROOT, 'artifacts', 'plc-tree.json')

def describe(obj):
    try:
        return type(obj).__name__
    except Exception:
        return '?'

def walk(obj, prefix, out, depth=0):
    if depth > 8:
        return
    try:
        children = list(obj.get_children(False))
    except Exception:
        children = []
    for child in children:
        try:
            name = child.get_name()
        except Exception:
            name = '?'
        path = prefix + '/' + name
        kind = describe(child)
        has_text = hasattr(child, 'textual_declaration')
        has_impl = hasattr(child, 'textual_implementation')
        out.append({'path': path, 'name': name, 'type': kind,
                    'textual': has_text, 'implementation': has_impl})
        if not has_text:
            walk(child, path, out, depth + 1)

result = {'success': False, 'projects': {}}
project = None
try:
    for label, filename in (('production', 'FM_XJV1_Cylinder_v13.project'),
                            ('baseline', 'FM_XJV1.project')):
        path = os.path.join(ROOT, 'plc', 'project', filename)
        if not os.path.isfile(path):
            result['projects'][label] = {'exists': False}
            continue
        project = api.projects.open(path, primary=(label == 'production'))
        app = project.active_application
        objects = []
        walk(app, app.get_name(), objects)
        result['projects'][label] = {'exists': True, 'application': app.get_name(),
                                     'objects': objects}
        project.close()
        project = None
    result['success'] = True
except Exception:
    result['exception'] = traceback.format_exc()
finally:
    if project is not None:
        try:
            project.close()
        except Exception:
            pass
    with io.open(RESULT, 'w', encoding='utf-8') as stream:
        stream.write(unicode(json.dumps(result, ensure_ascii=True, indent=2)))
    api.system.exit(0 if result['success'] else 1)
