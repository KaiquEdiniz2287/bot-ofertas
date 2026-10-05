from PyInstaller.utils.hooks import collect_all

playwright_data, playwright_binaries, playwright_hidden = collect_all("playwright")
tz_data, _, tz_hidden = collect_all("tzdata")

analysis = Analysis(
    ["../ofertas/frozen_entry.py"],
    pathex=[".."],
    binaries=playwright_binaries,
    datas=playwright_data + tz_data + [("../config.yaml", "."), ("../.env.example", ".")],
    hiddenimports=playwright_hidden + tz_hidden + ["ofertas.desktop_service"],
    excludes=[],
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="bot-ofertas-backend",
    console=True,
    onefile=True,
)
