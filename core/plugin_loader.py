import sys, importlib
from pathlib import Path
from core.logger import log

class PluginInfo:
    def __init__(self, name, version="1.0", description=""):
        self.name = name; self.version = version; self.description = description

class PluginLoader:
    def __init__(self, plugin_dir=None):
        root = Path(__file__).parent.parent
        self.plugin_dir = Path(plugin_dir or root / "plugins")
        self.plugins = {}; self.infos = {}
    def discover(self):
        if not self.plugin_dir.exists(): return []
        sys.path.insert(0, str(self.plugin_dir.parent))
        for d in sorted(self.plugin_dir.iterdir()):
            if not d.is_dir() or d.name.startswith("_"): continue
            init = d / "__init__.py"
            if not init.exists(): continue
            try:
                mod = importlib.import_module("plugins." + d.name)
                if hasattr(mod, "register"):
                    info = mod.register()
                    self.plugins[d.name] = mod
                    self.infos[d.name] = info
                    log.info(f"Plugin: {info.name} v{info.version}")
            except Exception as e:
                log.warn(f"Plugin {d.name}: {e}")
        return list(self.infos.keys())
    def start_all(self):
        for name, mod in self.plugins.items():
            if hasattr(mod, "start"):
                try: mod.start(); log.info(f"Started: {name}")
                except Exception as e: log.error(f"Start {name}: {e}")
    def stop_all(self):
        for name in reversed(list(self.plugins.keys())):
            mod = self.plugins[name]
            if hasattr(mod, "stop"):
                try: mod.stop()
                except Exception: pass
