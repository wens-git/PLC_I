# Offline XS rebuild

Use the installed XS Studio profile and preserve the quotes with PowerShell `Start-Process`:

```powershell
$env:PLC_REBUILD_OUTPUT = 'C:\path\to\NEW-build-directory'
$p = Start-Process -FilePath 'C:\Program Files\XS Studio\CODESYS\Common\XS Studio.exe' `
  -WorkingDirectory 'C:\Program Files\XS Studio\CODESYS\Common' `
  -ArgumentList '--profile="XS Studio V2.3.2a" --runscript="C:\Users\Admin\Downloads\PLC_I-main\PLC_I-main\plc\tools\rebuild_current.py"' `
  -PassThru -Wait
$p.ExitCode
```

Omit `PLC_REBUILD_OUTPUT` to create a unique directory in `artifacts/plc-probe`.
The output directory must not already exist. Coordinate with anyone doing desktop GUI tests: XS opens a window and can steal focus.

Do **not** add `--noUI` on this installation. The vendor `DeviceConfigurationEditor.ConifgViewActived.ProjLoad` event handler throws `NullReferenceException` when loading either an existing or an empty project without UI initialization. Explicit `primary=True/False` and the installation working directory do not fix it. UI-enabled scripting opens the same project successfully. UI-enabled does not mean online: this tool never logs in, connects or downloads.

The tool opens a filesystem copy of the vendor project, loads all `plc/src/**/*.st`, creates missing GVL/DUT/POU objects, rebuilds, checks typed Error/FatalError messages in active message categories, generates code and checks again. Only then does it save and mark success. Duplicate names or source changes during the build cause failure. Warning messages remain in the log and do not count as errors. The full device tree, library references and existing mappings remain those of the original project.

Each build has `rebuild-current.txt`, `build-status.json`, and a project copy. A project file's mere presence does not mean a successful build: require process exit 0 **and** `build-status.json` with `success: true`, `stage: complete`, and matching current source hashes. On failure the project copy is diagnostic only; no historical evidence is overwritten.

Host-side regression tests:

```powershell
python -m unittest discover -s tools/tests -p test_rebuild_current.py -v
```

Actual XS API probes are stored separately under `artifacts/plc-probe`. Their temporary projects are not delivery projects. The compiler may omit unreferenced POUs: to check a new API or selftest, use a separate copy with calls reachable from its scheduled program, then rebuild and generate code. Compilation does not execute tests or establish physical-device acceptance.
