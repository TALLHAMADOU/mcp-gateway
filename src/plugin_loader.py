# Minimal plugin loader placeholder for future extension
# For MVP we ship builtin handlers and remote proxying; plugin system will load modules by name

def load_plugin(name: str):
    raise NotImplementedError('Plugin loading not implemented in MVP')
