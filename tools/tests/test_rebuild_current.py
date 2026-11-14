"""Host-side regression tests; no XS installation or device required."""
import importlib.util
import pathlib
import types
import unittest
import tempfile
import json
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('rebuild_current', pathlib.Path(__file__).resolve().parents[2] / 'plc/tools/rebuild_current.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class RebuildTests(unittest.TestCase):
    def test_parse_current_sources(self):
        paths = list((pathlib.Path(build.ROOT) / 'plc/src').rglob('*.st'))
        self.assertTrue(paths)
        names = []
        for path in paths:
            names.extend(item[1] for item in build.parse_source(path.name, path.read_text(encoding='utf-8-sig')))
        self.assertEqual(len(names), len(set(names)))

    def test_no_variables_and_comment_tokens(self):
        item, = build.parse_source('f.st', 'FUNCTION f : BOOL\n(* END_VAR END_FUNCTION *)\nf := TRUE;\nEND_FUNCTION')
        self.assertEqual(item[3], '(* END_VAR END_FUNCTION *)\nf := TRUE;')
        self.assertEqual(item[2], 'FUNCTION f : BOOL')

    def test_dut_kinds(self):
        items = build.parse_source('types.st', 'TYPE S : STRUCT\nx:INT;\nEND_STRUCT END_TYPE\nTYPE A : ARRAY[0..2] OF INT; END_TYPE\nTYPE E : (a,b); END_TYPE')
        self.assertEqual([i[4] for i in items], ['Structure', 'Alias', 'Enumeration'])

    def test_create_and_update_all_object_kinds(self):
        created = []
        class Obj:
            textual_declaration = types.SimpleNamespace(replace=lambda text: created.append(text))
            textual_implementation = types.SimpleNamespace(replace=lambda text: created.append(text))
        obj = Obj()
        app = types.SimpleNamespace(find=lambda *args: [],
            create_gvl=lambda *args: (created.append(('gvl', args)) or obj),
            create_dut=lambda *args: (created.append(('dut', args)) or obj),
            create_pou=lambda *args: (created.append(('pou', args)) or obj))
        api = types.SimpleNamespace(DutType=types.SimpleNamespace(Structure='Structure', Alias='Alias'),
            PouType=types.SimpleNamespace(Function='Function', Program='Program', FunctionBlock='FunctionBlock'),
            ImplementationLanguages=types.SimpleNamespace(st='ST'))
        for kind, subtype in [('GVL', None), ('DUT', 'Structure'), ('POU', 'FUNCTION'), ('POU', 'PROGRAM'), ('POU', 'FUNCTION_BLOCK')]:
            self.assertEqual(build.update_object(app, (kind, 'X', 'DECL', 'BODY' if kind == 'POU' else None, subtype), api), 'CREATED X')
        self.assertEqual(len([x for x in created if isinstance(x, tuple)]), 5)
        build.update_object(app, ('DUT', 'AliasDut', 'TYPE AliasDut:INT; END_TYPE', None, 'Alias'), api)
        self.assertIn(('dut', ('AliasDut', 'Alias', 'INT')), created)
        app.find = lambda *args: [obj]
        self.assertEqual(build.update_object(app, ('GVL', 'X', 'new', None, None), api), 'UPDATED X')
        app.find = lambda *args: [obj, obj]
        with self.assertRaisesRegex(RuntimeError, 'Ambiguous'):
            build.update_object(app, ('GVL', 'X', '', None, None), api)

    def test_failed_compile_persists_failure_and_never_saves(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = pathlib.Path(root)
            (root_path / 'plc/project').mkdir(parents=True)
            (root_path / 'plc/src').mkdir()
            (root_path / 'plc/project/FM_XJV1.project').write_bytes(b'original')
            (root_path / 'plc/src/G.gvl.st').write_text('VAR_GLOBAL\nx:INT;\nEND_VAR')
            called = []
            obj = types.SimpleNamespace(textual_declaration=types.SimpleNamespace(replace=lambda text: None))
            app = types.SimpleNamespace(find=lambda *args: [obj], rebuild=lambda: called.append('rebuild'),
                                        generate_code=lambda: called.append('generate'))
            project = types.SimpleNamespace(active_application=app, close=lambda: called.append('close'),
                                            save=lambda: called.append('save'))
            system = types.SimpleNamespace(get_message_categories=lambda active: ['compile'],
                get_messages=lambda category: [], get_message_objects=lambda *args: ['error'] if 'rebuild' in called else [])
            api = types.SimpleNamespace(projects=types.SimpleNamespace(open=lambda *args, **kw: project),
                                        system=system, Severity=types.SimpleNamespace(Error=1, FatalError=2))
            output = str(root_path / 'output')
            with patch.object(build, 'ROOT', root), patch.dict('os.environ', {'PLC_REBUILD_OUTPUT': output}):
                self.assertEqual(build.main(api), 1)
            status = json.loads((pathlib.Path(output) / 'build-status.json').read_text())
            self.assertFalse(status['success'])
            self.assertEqual(status['stage'], 'rebuild')
            self.assertEqual(called, ['rebuild', 'close'])
            self.assertEqual((root_path / 'plc/project/FM_XJV1.project').read_bytes(), b'original')

    def test_localized_error_and_fatal_block_acceptance(self):
        severity = types.SimpleNamespace(Error=1, FatalError=2)
        masks = []
        system = types.SimpleNamespace(get_message_categories=lambda active: ['compile'],
            get_messages=lambda category: ['错误 C0001'],
            get_message_objects=lambda category, mask: (masks.append(mask) or ['error']))
        with self.assertRaisesRegex(RuntimeError, '1 compiler/system errors'):
            build.check_messages(system, severity, lambda text: None, 'REBUILD')
        self.assertEqual(masks, [3])
        system.get_message_objects = lambda *args: []
        build.check_messages(system, severity, lambda text: None, 'REBUILD')


if __name__ == '__main__':
    unittest.main()
