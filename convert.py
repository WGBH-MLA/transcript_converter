"""
convert.py

Top level module for MMIF-origin transcript conversion
"""

import json
from datetime import datetime
import time

from mmif import Mmif

try:
    # if being run from higher level module
    from . import proc_asr
    from .known_apps import KNOWN_APPS
except ImportError:
    # if run as stand-alone
    import proc_asr
    from known_apps import KNOWN_APPS

# Version number
MODULE_VERSION = proc_asr.MODULE_VERSION

# Default `provider` for TPME
DEFAULT_TPME_PROVIDER = "GBH Archives"

def mmif_to_all( mmif_str:str,
                 media_id:str = None,
                 mmif_filename:str = None,
                 tpme_provider:str = DEFAULT_TPME_PROVIDER,
                 processing_note:str = ""
                 ) -> dict :
    """
    Takes a MMIF transcript as a string.

    Returns a dictionary with transcripts in various forms and associated
    TPME files.
    """
    
    # create Mmif object
    usemmif = Mmif(mmif_str)

    # identify the right parts of the Mmif object
    asr_view_id = proc_asr.get_asr_view_id(usemmif)
    asr_view = usemmif.get_view_by_id(asr_view_id)

    # try to derive a media ID if not given
    if not media_id:
        try:
            document = asr_view.get_documents()[0]
            doc_loc = document["properties"]["location"]
            filename = doc_loc.split("/")[-1]
            media_id = filename.split(".")[0]
        except Exception as e:
            print("No media ID given and could not derive it from MMIF document location.")
            print("Encountered exception:\n", e)
    
    tdict = {}

    tdict["tpme_mmif"] = make_tpme_mmif(asr_view, 
                                        media_id, 
                                        mmif_filename, 
                                        tpme_provider, 
                                        processing_note)


    return tdict




def make_tpme_mmif( asr_view, 
                    media_id:str, 
                    mmif_filename:str, 
                    tpme_provider:str, 
                    processing_note:str 
                    ) -> str:

    iso_ts = asr_view.metadata["timestamp"]

    # Set values of TPME elements
    tpme = {}
    tpme["media_id"] = media_id
    tpme["transcript_id"] = mmif_filename
    tpme["modification_date"] = iso_ts
    tpme["provider"] = tpme_provider
    tpme["type"] = "transcript"
    tpme["file_format"] = "MMIF"
    tpme["features"] = { "time_aligned": True }
    tpme["human_review_level"] = "machine-generated"
    tpme["application_type"] = "ASR" 

    try:
        model_lang = asr_view.metadata.appConfiguration["modelLang"] 
        languages = [ model_lang ]
    except KeyError:
        languages = []
    tpme["transcript_language"] = languages

    app = asr_view.metadata.app
    tpme["application_id"] = app
    model_size = asr_view.metadata.appConfiguration["modelSize"]
    if app in KNOWN_APPS:
        tpme["application_provider"] = KNOWN_APPS[app]["application_provider"]
        tpme["application_name"] = KNOWN_APPS[app]["application_name"]
        tpme["application_version"] = KNOWN_APPS[app]["application_version"]
        tpme["application_repo"] = KNOWN_APPS[app]["application_repo"]
        try:
            model_size = KNOWN_APPS[app]["model_size_aliases"][model_size]
        except KeyError:
            model_size = model_size
        try:
            model_name = KNOWN_APPS[app]["implied_lang_specific_models"][(model_lang, model_size)]
        except KeyError:
            model_name = model_size
        try:
            tpme["inference_model"] = KNOWN_APPS[app]["model_prefix"] + model_name
        except KeyError:
            tpme["inference_model"] = model_name
    else:
        tpme["application_provider"] = "unknown"
        tpme["application_name"] = app
        try:
            tpme["application_version"] = asr_view.metadata.app.split("/")[-1]
        except:
            tpme["application_version"] = "unknown"
        tpme["application_repo"] = "unknown"
        tpme["inference_model"] = model_size

    tpme["application_params"] = asr_view.metadata["appConfiguration"]
    tpme["processing_note"] = processing_note


def main():
    app_desc="""
    Performs transcript conversion from MMIF to other formats.
    """
    print("This module is intended to be called by other modules.")

#
# Call to main function for stand-alone execution
#
if __name__ == "__main__":
    main()

