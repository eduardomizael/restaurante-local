from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

root = Path(SPECPATH).parent
hidden = []
for package in ("apps", "config", "runtime", "hardware", "django.contrib.contenttypes",
                "django.db.backends.sqlite3", "django.core.management.commands", "pystray"):
    hidden += collect_submodules(package)
datas = [(str(root / "templates"), "templates"), (str(root / "static"), "static")]
# Django discovers commands and migrations using filesystem enumeration.
datas += collect_data_files("apps", include_py_files=True)
datas += collect_data_files("django.contrib.contenttypes", include_py_files=True)
a = Analysis([str(root / "packaging" / "entrypoint.py")], pathex=[str(root)],
             binaries=[], datas=datas, hiddenimports=hidden, hookspath=[],
             runtime_hooks=[], excludes=["tkinter", "pytest"], noarchive=False)
pyz = PYZ(a.pure)
app = EXE(pyz, a.scripts, [], exclude_binaries=True, name="RestauranteLocal",
          console=False, upx=False)
maintenance = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Manutencao",
                  console=True, upx=False)
coll = COLLECT(app, maintenance, a.binaries, a.datas, strip=False, upx=False,
               name="RestauranteLocal")
