from PyInstaller.utils.hooks import collect_all

playwright_data, playwright_binaries, playwright_hidden = collect_all("playwright")
tz_data, _, tz_hidden = collect_all("tzdata")
cloak_data, cloak_binaries, cloak_hidden = collect_all("cloakbrowser")

analysis = Analysis(
    ["../ofertas/frozen_entry.py"],
    pathex=[".."],
    binaries=playwright_binaries + cloak_binaries,
    datas=playwright_data + tz_data + cloak_data + [("../config.yaml", "."), ("../.env.example", ".")],
    hiddenimports=playwright_hidden + tz_hidden + cloak_hidden + ["ofertas.desktop_service"],
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
