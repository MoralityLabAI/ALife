"""Fresh reconstructed facade for the StegoHive V7 horizon/rate factorial."""

from stegohive_v2.versions import cell_registry as _registry
from stegohive_v2.versions import run_spec as _run_spec
from stegohive_v2.versions import run_versioned_world as _run


def cell_registry():
    return _registry("V7")


def run_spec(cell=None):
    return _run_spec("V7", cell)


def run_world(seed, cell=None):
    return _run("V7", seed, cell)


__all__ = ["cell_registry", "run_spec", "run_world"]
