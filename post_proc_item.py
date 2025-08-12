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
    # if being run from higher level module
    from . import proc_asr
    from .known_apps import KNOWN_APPS
except ImportError:
    # if run as stand-alone
    import proc_asr
    from known_apps import KNOWN_APPS

# Version notes
MODULE_VERSION = "0.60"

# These are the defaults specific to routines defined in this module.
POSTPROC_DEFAULTS = { "name": None,
                      "artifacts": [],
                      "max_line_chars": 100,
                      "lang_str": "en" }

VALID_ARTIFACTS = [ "transcript_aajson",
                    "transcript_mmif",
                    "transcript_text",
                    "tpme_mmif",
                    "tpme_aajson",
                    "tpme_text" ]

TPME_PROVIDER = "GBH Archives"


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
    mmif_str = ""
    mmif_path = item["mmif_paths"][-1]
    with open(mmif_path, "r") as file:
        mmif_str = file.read()
    usemmif = Mmif(mmif_str)
    asr_view_id = proc_asr.get_asr_view_id(usemmif)
    asr_view = usemmif.get_view_by_id( asr_view_id )

    # 
    # create transcript in MMIF format (as output by the CLAMS app)
    # 
    artifact = "transcript_mmif"
    if artifact in artifacts:

        mmif_tr_fname = item["asset_id"] + "-transcript.mmif"
        mmif_tr_fpath = artifacts_dir + "/" + artifact + "/" + mmif_tr_fname

        if mmif_str:
            with open(mmif_tr_fpath, "w") as file:
                file.write(mmif_str)
            print(ins + "MMIF transcript saved: " + mmif_tr_fpath)

        # 
        # create TPME for MMIF transcript 
        # 
        artifact = "tpme_mmif"
        if artifact in artifacts:

            iso_ts = asr_view.metadata["timestamp"]
            dt = datetime.fromisoformat(iso_ts)

            # Set values of TPME elements
            tpme = {}
            tpme["media_id"] = item["asset_id"]
            tpme["transcript_id"] = mmif_tr_fname
            tpme["parent_transcript_id"] = ""
            tpme["modification_date"] = iso_ts
            tpme["provider"] = TPME_PROVIDER
            tpme["type"] = "transcript"
            tpme["file_format"] = "MMIF"
            tpme["features"] = { "time_aligned": True }
            try:
                languages = [ asr_view.metadata.get_parameter("modelLang") ]
            except KeyError:
                print(ins + f"Language not declared.  Assuming language is '{pp_params['lang_str']}'.")
                languages = [ "en" ]
            tpme["transcript_language"] = languages
            tpme["human_review_level"] = "machine-generated"
            tpme["application_type"] = "ASR" 

            app = asr_view.metadata.app
            tpme["application_id"] = app
            model_size = asr_view.metadata.appConfiguration["modelSize"]
            if app in KNOWN_APPS:
                tpme["application_provider"] = KNOWN_APPS[app]["application_provider"]
                tpme["application_name"] = KNOWN_APPS[app]["application_name"]
                tpme["application_version"] = KNOWN_APPS[app]["application_version"]
                tpme["application_repo"] = KNOWN_APPS[app]["application_repo"]
                
                if model_size in KNOWN_APPS[app]["model_sizes"]:
                    tpme["inference_model"] = KNOWN_APPS[app]["model_prefix"] + KNOWN_APPS[app]["model_sizes"][model_size]
                else:
                    tpme["inference_model"] = KNOWN_APPS[app]["model_prefix"] + model_size
            else:
                problems.append("app-unknown")
                tpme["application_provider"] = "unknown"
                tpme["application_name"] = app
                try:
                    tpme["application_version"] = asr_view.metadata.app.split("/")[-1]
                except:
                    tpme["application_version"] = "unknown"
                tpme["application_repo"] = "unknown"
                tpme["inference_model"] = model_size

            tpme["application_params"] = asr_view.metadata["appConfiguration"]
            tpme["processing_note"] = "clams-kitchen job ID: " + cf["job_id"]

            # Write out TPME JSON file
            tpme_ts = f"{dt.year:04d}{dt.month:02d}{dt.day:02d}-{dt.hour:02d}{dt.minute:02d}{dt.second:02d}-{dt.microsecond:06d}"
            mmif_tpme_fname = f'{item["asset_id"]}-tpme-{tpme_ts}.json'
            mmif_tpme_fpath = artifacts_dir + "/" + artifact + "/" + mmif_tpme_fname

            with open(mmif_tpme_fpath, "w") as file:
                json.dump( tpme, file, indent=2 )

            print(ins + "TPME for MMIF transcript saved: " + mmif_tpme_fpath)


    # 
    # create transcript in plain text format
    # 
    artifact = "transcript_text"
    if artifact in artifacts:

        # ensure no timestamp collisions
        time.sleep(0.01)

        toks_arr = proc_asr.make_toks_arr( usemmif )
        sts_arr = proc_asr.make_sts_arr( toks_arr )

        text_tr_fname = item["asset_id"] + "-transcript.txt"
        text_tr_fpath = artifacts_dir + "/" + artifact + "/" + text_tr_fname

        # Create a plain text transcript with line breaks between "sentences".
        text = ""
        if len(sts_arr):
            for st in sts_arr:
                if isinstance(st[2], str) and bool(st[2]):
                    text += (st[2] + "\n")
            with open( text_tr_fpath, "w" ) as file:
                file.write( text )

            print(ins + "Plain text transcript saved: " + text_tr_fpath)
            dt = datetime.now()
        else:
            print(ins + "Problem: Found no sentences to analyze.")
            print(ins + "Will not create a plain text transcript.")
            problems.append("plain-text")
            dt = None

        # 
        # create TPME for plain text transcript 
        # 
        artifact = "tpme_text"
        if artifact in artifacts:

            # Set values of TPME elements
            tpme = {}
            tpme["media_id"] = item["asset_id"]
            tpme["transcript_id"] = text_tr_fname
            tpme["parent_transcript_id"] = mmif_tr_fname
            tpme["modification_date"] = datetime.now().isoformat()
            tpme["provider"] = TPME_PROVIDER
            tpme["type"] = "transcript"
            tpme["file_format"] = "text/plain"
            tpme["features"] = { }
            try:
                languages = [ asr_view.metadata.get_parameter("modelLang") ]
            except KeyError:
                print(ins + "Language not declared.  Assuming language is 'en'.")
                languages = [ "en" ]
            tpme["transcript_language"] = languages
            tpme["human_review_level"] = "machine-generated"
            tpme["application_type"] = "format-conversion" 
            tpme["application_provider"] = "GBH Archives"            
            tpme["application_name"] = "transcript_converter"
            tpme["application_version"] = MODULE_VERSION
            tpme["application_repo"] = "https://github.com/WGBH-MLA/transcript_converter"
            tpme["application_params"] = pp_params
            tpme["processing_note"] = "clams-kitchen job ID: " + cf["job_id"]

            # Write out TPME JSON file
            if dt is not None:
                tpme_ts = f"{dt.year:04d}{dt.month:02d}{dt.day:02d}-{dt.hour:02d}{dt.minute:02d}{dt.second:02d}-{dt.microsecond:06d}"
                text_tpme_fname = f'{item["asset_id"]}-tpme-{tpme_ts}.json'
                text_tpme_fpath = artifacts_dir + "/" + artifact + "/" + text_tpme_fname

                with open(text_tpme_fpath, "w") as file:
                    json.dump( tpme, file, indent=2 )

                print(ins + "TPME for plain text transcript saved: " + text_tpme_fpath)


    # 
    # create transcript in AAPB JSON format
    # 
    artifact = "transcript_aajson"
    if artifact in artifacts:

        # ensure no timestamp collisions
        time.sleep(0.01)

        toks_arr = proc_asr.make_toks_arr( usemmif )
        proc_asr.split_long_sts( toks_arr, 
                                max_chars=pp_params["max_line_chars"]  )
        
        sts_arr = proc_asr.make_sts_arr( toks_arr )

        aajson_tr_fname = item["asset_id"] + "-transcript.json"
        aajson_tr_fpath = artifacts_dir + "/" + artifact + "/" + aajson_tr_fname
        if len(sts_arr):
            proc_asr.export_aapbjson( sts_arr, 
                                     aajson_tr_fpath, 
                                     asset_id=item["asset_id"] )
            print(ins + "AAPB-Transcript-JSON transcript saved: " + aajson_tr_fpath)
            dt = datetime.now()
        else:
            print(ins + "Problem: Found no sentences to analyze.")
            print(ins + "Will not create AAPB-Transcript-JSON transcript.")
            problems.append("aajson")
            dt = None

        # 
        # create TPME for AAPB JSON transcript 
        # 
        artifact = "tpme_aajson"
        if artifact in artifacts:

            # Set values of TPME elements
            tpme = {}
            tpme["media_id"] = item["asset_id"]
            tpme["transcript_id"] = aajson_tr_fname
            tpme["parent_transcript_id"] = mmif_tr_fname
            tpme["modification_date"] = datetime.now().isoformat()
            tpme["provider"] = TPME_PROVIDER
            tpme["type"] = "transcript"
            tpme["file_format"] = "AAPB-transcript-JSON"
            tpme["features"] = { "time_aligned": True,
                                 "max_line_chars": pp_params["max_line_chars"] }
            try:
                languages = [ asr_view.metadata.get_parameter("modelLang") ]
            except KeyError:
                print(ins + "Language not declared.  Assuming language is 'en'.")
                languages = [ "en" ]
            tpme["transcript_language"] = languages
            tpme["human_review_level"] = "machine-generated"
            tpme["application_type"] = "format-conversion" 
            tpme["application_provider"] = "GBH Archives"            
            tpme["application_name"] = "transcript_converter"
            tpme["application_version"] = MODULE_VERSION
            tpme["application_repo"] = "https://github.com/WGBH-MLA/transcript_converter"
            tpme["application_params"] = pp_params
            tpme["processing_note"] = "clams-kitchen job ID: " + cf["job_id"]

            # Write out TPME JSON file
            if dt is not None:
                tpme_ts = f"{dt.year:04d}{dt.month:02d}{dt.day:02d}-{dt.hour:02d}{dt.minute:02d}{dt.second:02d}-{dt.microsecond:06d}"
                aajson_tpme_fname = f'{item["asset_id"]}-tpme-{tpme_ts}.json'
                aajson_tpme_fpath = artifacts_dir + "/" + artifact + "/" + aajson_tpme_fname

                with open(aajson_tpme_fpath, "w") as file:
                    json.dump( tpme, file, indent=2 )

                print(ins + "TPME for AAPB-transcript-JSON saved: " + aajson_tpme_fpath)


    # 
    # Finished with the whole postprocess
    # 
    return errors, problems, infos
