import os
import importlib.util

_DIR = os.path.dirname(os.path.abspath(__file__))


def load_plugins():
    plugins = {}
    for fname in sorted(os.listdir(_DIR)):
        if fname.startswith("_") or not fname.endswith(".py"):
            continue
        path = os.path.join(_DIR, fname)
        spec = importlib.util.spec_from_file_location(fname[:-3], path)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            import sys
            print("[plugins] failed to load {}: {}".format(fname, e), file=sys.stderr)
            continue
        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if (
                isinstance(obj, type)
                and hasattr(obj, "NAME")
                and hasattr(obj, "COMMANDS")
                and hasattr(obj, "interpret")
            ):
                instance = obj()
                plugins[instance.NAME] = instance
    return plugins
