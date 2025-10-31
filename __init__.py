# transcript_converter/__init__.py
__version__ = "0.81"

# just one exposed function
from .convert import mmif_to_all

# some global default values
from .convert import DEFAULT_MAX_SEGMENT_CHARS, DEFAULT_MAX_LINE_CHARS, DEFAULT_TPME_PROVIDER

# minimal package-level API
__all__ = [ "mmif_to_all",
            "DEFAULT_MAX_SEGMENT_CHARS", 
            "DEFAULT_MAX_LINE_CHARS", 
            "DEFAULT_TPME_PROVIDER"
          ]