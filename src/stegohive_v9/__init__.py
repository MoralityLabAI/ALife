"""Fresh reconstructed facade for the StegoHive V9 role-credit factorial."""

from stegohive_v2.versions import cell_registry as _registry
from stegohive_v2.versions import run_spec as _run_spec
from stegohive_v2.versions import run_versioned_world as _run


def cell_registry():
    return _registry("V9")


def run_spec(cell=None):
    return _run_spec("V9", cell)


def run_world(seed, cell=None):
    return _run("V9", seed, cell)


__all__ = ["cell_registry", "run_spec", "run_world"]
