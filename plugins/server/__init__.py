import sys, os, threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from core.plugin_loader import PluginInfo
from core.logger import log

def register():
    return PluginInfo(name='server', version='2.0', description='Local Qwen2.5 LLM Service')

def start():
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    log.info('server plugin dispatched')

def _run():
    from core.config import CFG
    sys.path.insert(0, os.path.dirname(__file__))
    from plugins.server.handler import main as handler_main
    handler_main()
