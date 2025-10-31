# transcript_converter/__init__.py
__version__ = "0.80"

# just one exposed method
from .convert import mmif_to_all
__all__ = ["mmif_to_all"]