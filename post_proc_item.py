"""
post_proc_item.py

Defines functions for doing post processing of MMIF created by CLAMS ASR apps
such as app-whisper-wrapper.

Assumes processing takes place in the context of job processing in the style of 
clams-kitchen, with `item` and `cf` dictionaries passed from the job runner 
routine.

Handles creation artifacts appearing in the VALID_ARTIFACTS global variable.

Handles options passed in via the `params` dict argument to the main function,
as long as they are defined in one of the option defauls global variables.
"""

import json
import datetime

from mmif import Mmif

try:
    # if being run from higher level module
    from . import lilhelp
    from . import proc_ww
except ImportError:
    # if run as stand-alone
    import lilhelp
    import proc_ww

# Version notes
MODULE_VERSION = "0.01"

# These are the defaults specific to routines defined in this module.
POSTPROC_DEFAULTS = { }

VALID_ARTIFACTS = [ "aapb-json-transcript",
                    "aajson",
                    "tpme-mmif",
                    "tpme-aajson" ]


def run_post( item:dict, 
              cf:dict, 
              params:dict ):
    """
    Calls particular methods to run post processing for the item according to the 
    configuration specified in the `cf` and `params` dictionaries.
    """

    errors = []
    problems = []
    infos = []

    # shorthand item number string for screen output
    ins = f'[#{item["item_num"]}] '

    # 
    # Process and validate options passed in
    # 

    if "name" in params:
        if params["name"].lower() not in ["transcript_converter"]:
            print(ins + "Post-processing error: Tried to run", params["name"],
                  "process with transcript_converter post-processing function.")
            errors.append("post_proc_name")
            return errors
    else:
        print(ins + "Post-processing error: No post-process or name specified.")
        errors.append("post_proc_name")
        return errors

    # Set up for the particular kinds of artifacts requested 
    if "artifacts" in params:
        artifacts = params["artifacts"]
        artifacts_dir = cf["artifacts_dir"]
    else:
        print(ins + "Warning: No artifacts specified.")  
        artifacts = []

    for atype in artifacts:
        if atype not in VALID_ARTIFACTS:
            print(ins + "Warning: Invalid artifact type '" + atype + "' will not be created.")
            print(ins + "Valid artifact types:", VALID_ARTIFACTS)


    # check params for extra params
    for key in params:
        if key not in { **POSTPROC_DEFAULTS, 
                        **proc_swt.PROC_SWT_DEFAULTS,
                        **create_visaid.VISAID_DEFAULTS } :
            print(ins + "Warning: `" + key + "` is not a valid config option for this postprocess. Ignoring.")


    # Assign parameter values for this module
    # For each of the available parameter keys, if that parameter was passed in, then
    # use that.  Otherwise use default from this module.
    pp_params = {}
    for key in POSTPROC_DEFAULTS:
        if key in params:
            pp_params[key] = params[key]
        else:
            # use default from this module
            pp_params[key] = POSTPROC_DEFAULTS[key]


    #
    # Perform foundational processing of MMIF file
    #
    
    # Open MMIF and start processing
    mmif_path = item["mmif_paths"][-1]
    with open(mmif_path, "r") as file:
        mmif_str = file.read()

    ww_view_id = proc_ww.get_ww_view_id(mmif_str)

    print(ins + "Attempting to parse MMIF transcript...")

    token_tfs = proc_ww.seg_toks( mmif_str,
                                  ww_view_id=ww_view_id )

