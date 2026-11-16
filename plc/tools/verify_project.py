# -*- coding: utf-8 -*-
"""XS offline verification of delivered source objects, domain folders and task."""
import os, io, json, hashlib, traceback
from datetime import datetime
import sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rebuild_current import parse_source
import scriptengine as api
result = {'success': False, 'offline_only': True}
project = None
try:
    path = os.path.join(ROOT, 'plc', 'project', 'FM_XJV1_Cylinder_v13.project')
    project = api.projects.open(path, primary=True)
    app = project.active_application
    count = 0
    sources = {}
    domains = set()
    for folder, dirs, files in os.walk(os.path.join(ROOT, 'plc', 'src')):
        for filename in files:
            if not filename.endswith('.st'): continue
            source = os.path.join(folder, filename)
            relative = os.path.relpath(source, ROOT)
            with open(source, 'rb') as stream: sources[relative] = hashlib.sha256(stream.read()).hexdigest()
            domain = relative.replace('\\', '/').split('/')[2]
            domains.add(domain)
            with io.open(source, encoding='utf-8-sig') as stream: text = stream.read()
            for kind, name, decl, impl, subtype in parse_source(filename, text):
                hits = [o for o in app.find(name, True) if hasattr(o, 'textual_declaration')]
                if len(hits) != 1: raise RuntimeError('Unexpected source count ' + name)
                obj = hits[0]
                def norm(value): return value.replace('\r\n', '\n').strip()
                if norm(obj.textual_declaration.text) != norm(decl): raise RuntimeError('Declaration differs ' + name)
                if impl is not None and norm(obj.textual_implementation.text) != norm(impl): raise RuntimeError('Implementation differs ' + name)
                if obj.parent.get_name() != 'SRC_' + domain: raise RuntimeError('Wrong source domain ' + name)
                count += 1
    if app.find(u'结构体_气缸工程', True): raise RuntimeError('Retired type remains')
    wrapper = [o for o in app.find('PLC_PRG', True) if hasattr(o, 'textual_implementation')]
    if len(wrapper) != 1 or wrapper[0].textual_implementation.text.strip() != u'程序_主循环();': raise RuntimeError('Wrong wrapper')
    objects = list(project.get_children(True))
    calls = [o for o in objects if o.get_name() == 'PLC_PRG' and not hasattr(o, 'textual_implementation')]
    if len(calls) != 1: raise RuntimeError('Expected exactly one task call')
    owner = calls[0].parent.get_name()
    if owner != 'EtherCAT_Task': raise RuntimeError('Unexpected owner ' + owner)
    buses = []
    for o in objects:
        if o.get_name() in ('EtherCAT', 'Ethernet', 'ModbusTCP_Slave_XJV1', 'HIGH_SPEED_IO'):
            for connector in o.connectors:
                task = connector.driver_info.bus_cycle_task_by_name
                if task != 'EtherCAT_Task': raise RuntimeError('Unexpected bus task ' + o.get_name())
                buses.append({'device': o.get_name(), 'task': task})
    with open(path, 'rb') as stream: project_hash = hashlib.sha256(stream.read()).hexdigest()
    result.update(success=True, verified_objects=count, domains=sorted(domains), sources=sources,
                  project_sha256=project_hash, completed_at=datetime.utcnow().isoformat() + 'Z',
                  entry_program=u'PLC_PRG -> 程序_主循环', task_owner=owner,
                  task_call_count=len(calls), bus_bindings=buses)
except Exception:
    result['exception'] = traceback.format_exc()
finally:
    if project is not None: project.close()
    with io.open(os.path.join(ROOT, 'plc', 'evidence', 'architecture-project-verification.json'), 'w', encoding='utf-8') as stream:
        stream.write(unicode(json.dumps(result, ensure_ascii=True, indent=2)))
    api.system.exit(0 if result['success'] else 1)
