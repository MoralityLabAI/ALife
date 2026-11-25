"""Fresh reconstructed facade for the StegoHive V8 credit-path factorial."""

from stegohive_v2.versions import cell_registry as _registry
from stegohive_v2.versions import run_spec as _run_spec
from stegohive_v2.versions import run_versioned_world as _run


def cell_registry():
    return _registry("V8")


def run_spec(cell=None):
    return _run_spec("V8", cell)


def run_world(seed, cell=None):
    return _run("V8", seed, cell)


__all__ = ["cell_registry", "run_spec", "run_world"]
