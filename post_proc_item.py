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
from datetime import datetime
import time

from mmif import Mmif

try:
    # if being run from higher level module (such as clams-kitchen)
    from . import convert
except ImportError:
    # if run as stand-alone
    import convert

# These are the defaults specific to routines defined in this module.
POSTPROC_DEFAULTS = { "name": None,
                      "artifacts": [],
                      "max_segment_chars": 100,
                      "max_line_chars": 42,
                      "lang_str": "en" }

VALID_ARTIFACTS = [ "transcript_aajson",
                    "transcript_mmif",
                    "transcript_text",
                    "transcript_webvtt",
                    "tpme_mmif",
                    "tpme_aajson",
                    "tpme_text" ]

TPME_PROVIDER = "GBH Archives"


def write_out_tpme( tdict:dict,
                    artifact:str,
                    item:dict,
                    cf:dict,
                    ins:str = None,
                    ) -> None:
    """
    Write out one of the TPME strings to a file.
    """
    # try to pull the most recent date from the TPME file
    tpme = json.loads(tdict[artifact])
    dates = [ e["modification_date"] for e in tpme ]
    dates.sort(reverse=True) 
    if dates:
        dt = datetime.fromisoformat(dates[0])
    else: 
        dt = datetime.now()

    # formulate filename and write out file
    tpme_ts = f"{dt.year:04d}{dt.month:02d}{dt.day:02d}-{dt.hour:02d}{dt.minute:02d}{dt.second:02d}-{dt.microsecond:06d}"
    tpme_fname = f'{item["asset_id"]}-tpme-{tpme_ts}.json'
    tpme_fpath = cf["artifacts_dir"] + "/" + artifact + "/" + tpme_fname
    with open(tpme_fpath, "w") as file:
        file.write( tdict[artifact] )
        print(ins + f"TPME `{artifact}` saved: {tpme_fpath}" )



def run_post( item:dict, 
              cf:dict, 
              params:dict 
              ) -> tuple[list, list, list] :
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
    # Perform processing of MMIF file
    #
    print(ins + "Attempting to process MMIF transcript...")

    # Open MMIF and start processing
    mmif_str = ""
    mmif_path = item["mmif_paths"][-1]
    with open(mmif_path, "r") as file:
        mmif_str = file.read()

    # Call the main conversion function
    tdict = convert.mmif_to_all( mmif_str = mmif_str,
                                 asset_id = item["asset_id"],
                                 mmif_filename = f'{item["asset_id"]}-transcript.mmif',
                                 tpme_provider = TPME_PROVIDER,
                                 max_segment_chars = pp_params["max_segment_chars"],
                                 max_line_chars = pp_params["max_line_chars"],
                                 embed_tpme_aajson = True,
                                 processing_note = "clams-kitchen job ID: " + cf["job_id"] )
    
    # Scan for problems with transcripts and append to logging structures
    # TO IMPLEMENT
    # (Or better, have `mmif_to_all` return problems, and append this to postproc problems.)


    # 
    # Write out all the artifact files, as appropriate
    #

    # create transcript in MMIF format (as output by the CLAMS app)
    artifact = "transcript_mmif"
    if artifact in artifacts:
        mmif_tr_fname = item["asset_id"] + "-transcript.mmif"
        mmif_tr_fpath = cf["artifacts_dir"] + "/" + artifact + "/" + mmif_tr_fname
        with open(mmif_tr_fpath, "w") as file:
            file.write(mmif_str)
        print(ins + "MMIF transcript saved: " + mmif_tr_fpath)

        # create TPME for MMIF transcript 
        artifact = "tpme_mmif"
        if artifact in artifacts:
            write_out_tpme( tdict, artifact, item, cf, ins )

    # create transcript in AAPB JSON format
    artifact = "transcript_aajson"
    if artifact in artifacts:
        tr_fname = item["asset_id"] + "-transcript.json"
        tr_fpath = cf["artifacts_dir"] + "/" + artifact + "/" + tr_fname
        with open(tr_fpath, "w") as file:
            file.write(tdict["transcript_aajson"])
        print(ins + "AAPB-Transcript-JSON transcript saved: " + tr_fpath)

        # create TPME for AAPB JSON transcript 
        artifact = "tpme_aajson"
        if artifact in artifacts:
            write_out_tpme( tdict, artifact, item, cf, ins )

    # create transcript in WebVTT format
    artifact = "transcript_webvtt"
    if artifact in artifacts:
        tr_fname = item["asset_id"] + "-transcript.vtt"
        tr_fpath = cf["artifacts_dir"] + "/" + artifact + "/" + tr_fname
        with open(tr_fpath, "w") as file:
            file.write(tdict["transcript_webvtt"])
        print(ins + "WebVTT transcript saved: " + tr_fpath)

        # create TPME for AAPB JSON transcript 
        artifact = "tpme_webvtt"
        if artifact in artifacts:
            write_out_tpme( tdict, artifact, item, cf, ins )

    # create transcript in plain text format
    artifact = "transcript_text"
    if artifact in artifacts:
        tr_fname = item["asset_id"] + "-transcript.txt"
        tr_fpath = cf["artifacts_dir"] + "/" + artifact + "/" + tr_fname
        with open( tr_fpath, "w" ) as file:
            file.write( tdict["transcript_text"] )
        print(ins + "Plain text transcript saved: " + tr_fpath)

        # create TPME for plain text transcript 
        artifact = "tpme_text"
        if artifact in artifacts:
            write_out_tpme( tdict, artifact, item, cf, ins )

    # 
    # Finished with the whole postprocess
    # 
    return errors, problems, infos
