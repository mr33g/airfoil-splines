# setup

This repo supports local setup for Windows (MSI) and macOS (DMG) without GitHub Actions.

## Windows MSI

Prereqs:
- Python 3.10+
- A sibling `../AirfoilFit` checkout, installed with `python -m pip install -r requirements.txt`
- WiX 6.0.2 (`dotnet tool install --global wix --version 6.0.2`)
- WiX extensions:
  - `wix extension add -g WixToolset.UI.wixext/6.0.2`
  - `wix extension add -g WixToolset.Util.wixext/6.0.2`

Build:
```powershell
setup\windows\build.ps1
```

Override version:
```powershell
setup\windows\build.ps1 -Version 1.2.3
```

Use `-Python .venv\Scripts\python.exe` to build with the project's virtual environment.
The shared `airfoil_fit` package and its metadata are bundled into the application;
users do not need a separate Python or core-library installation.
The installer copies `setup/default-config.json` beside the executable as
`airfoilfitter.config.json`, so local preference overrides do not affect releases.

GitHub Actions checks out both repositories, runs the desktop tests, and builds the MSI.
Tag builds attach it to the release; manual builds upload a workflow artifact only.

Output:
- `dist\AirfoilFitter-x.y.z.msi`

## macOS DMG

Prereqs:
- Python 3.10+
- create-dmg (`brew install create-dmg`)

Build:
```bash
chmod +x setup/macos/build.sh
setup/macos/build.sh
```

Override version:
```bash
setup/macos/build.sh 1.2.3
```

Output:
- `dist/AirfoilFitter-x.y.z-arm64.dmg` or `dist/AirfoilFitter-x.y.z-x64.dmg`

## Versioning

Version is resolved in this order:
- explicit build argument
- latest git tag
- `1.0.0`

