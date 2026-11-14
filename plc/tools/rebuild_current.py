# -*- coding: utf-8 -*-
"""XS Studio IronPython offline rebuild. Never logs in or downloads.

Run using XS Studio --profile="XS Studio V2.3.2a"
--runscript=".../plc/tools/rebuild_current.py". Use Start-Process on Windows
so the profile quotes survive. Do not pass --noUI: the installed vendor
DeviceConfigurationEditor throws NullReferenceException on project load
without UI initialization. This UI process still performs offline operations only.
PLC_REBUILD_OUTPUT may select a NEW output
folder; otherwise each invocation creates artifacts/plc-probe/build-<uuid>.
The result JSON, not process completion alone, is the acceptance record.
"""
import os
import io
import re
import json
import hashlib
import traceback
import uuid
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    text_type = unicode
except NameError:
    text_type = str


def masked(text):
    # Preserve offsets while ignoring comments and strings in structural parsing.
    pattern = r"\(\*.*?\*\)|//[^\n]*|'(?:\$ .|[^'])*'"
    return re.sub(pattern, lambda m: re.sub(r'[^\n]', ' ', m.group()), text,
                  flags=re.S | re.X)


def parse_source(filename, text):
    """Yield (kind, name, declaration, implementation, subtype)."""
    if filename.lower().endswith('.gvl.st'):
        return [('GVL', filename[:-7], text, None, None)]
    clean = masked(text)
    types = list(re.finditer(r'(?im)^\s*TYPE\s+(\w+)\s*:', clean))
    if types:
        result = []
        for match in types:
            end = re.search(r'\bEND_TYPE\b', clean[match.end():], re.I)
            if end is None:
                raise ValueError('Missing END_TYPE: ' + filename)
            body = clean[match.end():match.end() + end.start()].strip()
            subtype = ('Structure' if re.match(r'STRUCT\b', body, re.I) else
                       'Union' if re.match(r'UNION\b', body, re.I) else
                       'Enumeration' if body.startswith('(') else 'Alias')
            result.append(('DUT', match.group(1),
                           text[match.start():match.end() + end.end()], None, subtype))
        return result
    header = re.search(r'(?im)^\s*(FUNCTION_BLOCK|FUNCTION|PROGRAM)\s+(\w+)[^\n]*', clean)
    if header is None:
        raise ValueError('No POU header: ' + filename)
    kind, name = header.group(1).upper(), header.group(2)
    ending = re.search(r'(?im)^\s*END_' + kind + r'\b', clean[header.end():])
    if ending is None:
        raise ValueError('Missing END_' + kind + ': ' + filename)
    end = header.end() + ending.start()
    vars_end = list(re.finditer(r'\bEND_VAR\b', clean[header.end():end], re.I))
    split = header.end() + vars_end[-1].end() if vars_end else header.end()
    return [('POU', name, text[:split], text[split:end].strip(), kind)]


def update_object(app, item, api):
    kind, name, declaration, implementation, subtype = item
    hits = app.find(name, True)
    if len(hits) > 1:
        raise RuntimeError('Ambiguous object name: ' + name)
    created = not hits
    if hits:
        obj = hits[0]
    elif kind == 'GVL':
        obj = app.create_gvl(name)
    elif kind == 'DUT':
        obj = app.create_dut(name, getattr(api.DutType, subtype),
                             'INT' if subtype == 'Alias' else None)
    else:
        pou_type = {'FUNCTION': 'Function', 'FUNCTION_BLOCK': 'FunctionBlock',
                    'PROGRAM': 'Program'}[subtype]
        # Full source declaration replaces the initial function return type.
        obj = app.create_pou(name, getattr(api.PouType, pou_type),
                             api.ImplementationLanguages.st,
                             'BOOL' if subtype == 'FUNCTION' else None)
    obj.textual_declaration.replace(declaration)
    if implementation is not None:
        obj.textual_implementation.replace(implementation)
    return ('CREATED ' if created else 'UPDATED ') + name


def check_messages(system, severity, emit, stage):
    errors = 0
    # Inactive registered categories can have no backing message store in XS.
    for category in system.get_message_categories(True):
        emit(stage + ' CATEGORY ' + text_type(category))
        for message in system.get_messages(category):
            emit(message)
        errors += len(system.get_message_objects(category, severity.Error | severity.FatalError))
    if errors:
        raise RuntimeError('%s: %d compiler/system errors' % (stage, errors))


def main(api):
    output_dir = os.environ.get('PLC_REBUILD_OUTPUT') or os.path.join(
        ROOT, 'artifacts', 'plc-probe', 'build-' + uuid.uuid4().hex)
    # A fresh directory prevents stale success and never overwrites evidence.
    os.makedirs(output_dir)
    output_path = os.path.join(output_dir, 'FM_XJV1_rebuilt.project')
    log = io.open(os.path.join(output_dir, 'rebuild-current.txt'), 'w', encoding='utf-8')
    def emit(message):
        log.write(text_type(message) + u'\n')
        log.flush()
    result = {'success': False, 'stage': 'snapshot', 'sources': {},
              'output_project': output_path, 'offline_only': True}
    project = None
    exitcode = 1
    try:
        items = []
        names = set()
        for directory, dirs, files in os.walk(os.path.join(ROOT, 'plc', 'src')):
            dirs.sort()
            for filename in sorted(files):
                if not filename.lower().endswith('.st'):
                    continue
                path = os.path.join(directory, filename)
                with open(path, 'rb') as stream:
                    raw = stream.read()
                result['sources'][os.path.relpath(path, ROOT)] = hashlib.sha256(raw).hexdigest()
                for item in parse_source(filename, raw.decode('utf-8-sig')):
                    key = item[1].lower()
                    if key in names:
                        raise ValueError('Duplicate source object: ' + item[1])
                    names.add(key)
                    items.append(item)
        result['stage'] = 'open'
        # Open a filesystem copy: the vendor original cannot be saved accidentally.
        shutil.copy2(os.path.join(ROOT, 'plc', 'project', 'FM_XJV1.project'), output_path)
        project = api.projects.open(output_path, primary=True)
        app = project.active_application
        if app is None:
            raise RuntimeError('No active application')
        check_messages(api.system, api.Severity, emit, 'OPEN')
        result['stage'] = 'update'
        for item in items:
            emit(update_object(app, item, api))
        result['stage'] = 'rebuild'
        app.rebuild()
        check_messages(api.system, api.Severity, emit, 'REBUILD')
        result['stage'] = 'generate_code'
        app.generate_code()
        check_messages(api.system, api.Severity, emit, 'CODE GENERATION')
        result['stage'] = 'verify_sources'
        for relative, expected in result['sources'].items():
            with open(os.path.join(ROOT, relative), 'rb') as stream:
                if hashlib.sha256(stream.read()).hexdigest() != expected:
                    raise RuntimeError('Source changed during build: ' + relative)
        project.save()
        project.close()
        project = None
        result['stage'] = 'complete'
        result['success'] = True
        exitcode = 0
        emit('ACCEPTED ' + output_path)
    except Exception:
        result['exception'] = traceback.format_exc()
        emit(result['exception'])
    finally:
        if project is not None:
            try:
                project.close()
            except Exception:
                emit(traceback.format_exc())
        with io.open(os.path.join(output_dir, 'build-status.json'), 'w', encoding='utf-8') as stream:
            stream.write(text_type(json.dumps(result, ensure_ascii=True, indent=2)))
        log.close()
    return exitcode


if __name__ == '__main__':
    import scriptengine
    code = 1
    try:
        code = main(scriptengine)
    finally:
        scriptengine.system.exit(code)
