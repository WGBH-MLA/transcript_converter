# transcript_converter/__init__.py
from importlib import metadata
try:
    __version__ = metadata.version("aapb-transcript-converter")
except ModuleNotFoundError:
    __version__ = "local"

# just a couple of exposed functions
from .convert import mmif_to_all
from .post_proc_item import run_post

# some global default values
from .convert import DEFAULT_MAX_SEGMENT_CHARS, DEFAULT_MAX_LINE_CHARS, DEFAULT_TPME_PROVIDER

# minimal package-level API
__all__ = [ "mmif_to_all",
            "DEFAULT_MAX_SEGMENT_CHARS", 
            "DEFAULT_MAX_LINE_CHARS", 
            "DEFAULT_TPME_PROVIDER"
          ]