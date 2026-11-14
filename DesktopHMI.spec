# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

modbus_data, modbus_binaries, modbus_imports = collect_all('pymodbus')
a = Analysis(
    ['desktop_launcher.py'], pathex=[],
    binaries=modbus_binaries,
    datas=[('docs/protocol-v1.json', 'docs'), ('web/dist', 'web/dist')] + modbus_data,
    hiddenimports=modbus_imports,
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=['PyQt5', 'PyQt6', 'PySide2'],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='FM_GPTPRO',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='FM_GPTPRO')
