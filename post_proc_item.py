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
    from . import proc_ww
except ImportError:
    # if run as stand-alone
    import proc_ww

# Version notes
MODULE_VERSION = "0.01"

# These are the defaults specific to routines defined in this module.
POSTPROC_DEFAULTS = { "name": None,
                      "artifacts": [],
                      "max_line_chars": 100,
                      "lang_str": "en-US" }

VALID_ARTIFACTS = [ "transcripts_aajson",
                    "tpme_mmif",
                    "tpme_aajson" ]


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
        if key not in POSTPROC_DEFAULTS:
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
    
    print(ins + "Attempting to process MMIF transcript...")

    # Open MMIF and start processing
    mmif_path = item["mmif_paths"][-1]
    with open(mmif_path, "r") as file:
        mmif_str = file.read()

    usemmif = Mmif(mmif_str)

    # 
    # create transcript in AAPB JSON format
    # 
    if "transcripts_aajson" in artifacts:

        toks_arr = proc_ww.make_toks_arr( usemmif )

        proc_ww.split_long_sts( toks_arr, 
                                max_chars=pp_params["max_line_chars"]  )
        
        sts_arr = proc_ww.make_sts_arr( toks_arr )

        if len(sts_arr):

            fpath = artifacts_dir + "/transcripts_aajson/" + item["asset_id"] + "-transcript.json"
            proc_ww.export_aapbjson( sts_arr, 
                                     fpath, 
                                     asset_id=item["asset_id"] )

    # 
    # Finished with the whole postprocess
    # 
    return errors, problems, infos
