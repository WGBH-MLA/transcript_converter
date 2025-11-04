"""
convert.py

High-level module for MMIF-origin transcript conversion.

Recommended usage is to call the `mmif_to_all` function, passing in a string
of well-formed MMIF.  That function will return a dictionary of transcripts 
and transcript metadata in various formats.  

The reason for having one function that returns all the formats is that the
most computationally expensive operation is the loading and processing of the 
MMIF file.  Once that is done, the conersion to various formats is extremely
fast, and the output strings are relatively short (compared to the length of
an MMIF file).  So, it's most efficient to do it all at once and then use only
the strings of interest.
"""

import json
from json.decoder import JSONDecodeError
from datetime import datetime
import logging
import time
import copy

from mmif import Mmif
from mmif import View
from mmif.vocabulary import DocumentTypes

from . import __version__
from .known_apps import KNOWN_APPS
from . import proc_asr
from .proc_asr import DEFAULT_MAX_SEGMENT_CHARS, DEFAULT_MAX_LINE_CHARS

# Other default values
DEFAULT_TPME_PROVIDER = "unspecified"


def mmif_to_all( mmif_str:str,
                 item_id:str = None,
                 mmif_filename:str = None,
                 languages:list = [],
                 tpme_provider:str = DEFAULT_TPME_PROVIDER,
                 max_segment_chars:int = DEFAULT_MAX_SEGMENT_CHARS,
                 max_line_chars:int = DEFAULT_MAX_LINE_CHARS,
                 embed_tpme_aajson = True,
                 processing_note:str = "",
                 prior_tpme_str:str = None
                 ) -> dict :
    """
    Converts MMIF to transcripts in other formats.

    Takes a MMIF transcript as a string and returns a dictionary with 
    transcripts in various formats and their associated TPME files.

    Args:
      item_id (str): Identifier for the media that was transcribed.
          This will be recorded in the TPME files.
      mmif_filename (str): The filename of the MMIF file which is being
          converted.  This will be recorded in the TPME files.
      languages (list of strings): This is a list of languages known to
          be in the transcript output.  This will be recorded in the AAPB 
          JSON transcript and TPME files.  If no list or an empty is list
          is given, inferring the language from the MMIF file will be 
          attempted.
      tpme_provider (str): This will be recorded as the transcript provider
          in the TPME.  If none is given, the hard-coded default value in 
          this module will be used.
      max_segment_chars (int): The maximum length in characters of a time-
          aligned segment of the transcript.
      max_line_chars (int):  The maximum length in characters before a line
          break in a transcript format, like WebVTT, designed for on-screen
          display.
      embed_tpme_aajson (bool): Whether to embed a TPME record within the
          AAPB JSON file itself (defaults to True).
      processing_note (str):  A notes string about processing to be included
          in the `processing_note` element of the TPME records.
      prior_tpme_str (str):  A JSON string of TPME (like from a previous run
          of this module) to be appended to the end of the newly newly created
          TPME records.

    Returns:
      dict:  A dictionary with strings of transcripts and TPME records.
      It includes the following keys, each of which has a string value.
      - item_id:  The item ID (derived from MMIF if no ID was passed inI)
      - transcript_aajson:  The transcript in AAPB Transcript JSON format
      - transcript_webvtt:  The transcript in WebVTT format
      - transcript_text:  The transcript in plain text
      - tpme_mmif:  TPME metadata for the MMIF transcript passed in
      - tpme_aajson:  TPME metadata for the corresponding output transcript      
      - tpme_webvtt:  TPME metadata for the corresponding output transcript
      - tpme_text:   TPME metadata for the corresponding output transcript
      - problems:  A list of short messages of problems encountered
      - infos:  A list of short messages of other conditions noticed
    """
    
    # create the dictionary of transcripts and TPME 
    tdict = {}

    # places to report problems or notable conditions encountered
    tdict["problems"] = []
    tdict["infos"] = []

    # create Mmif object
    usemmif = Mmif(mmif_str)

    # identify the right parts of the Mmif object
    asr_view_id = proc_asr.get_asr_view_id(usemmif)
    asr_view = usemmif.get_view_by_id(asr_view_id)

    # create tokens array (with sentence labels) from ASR view
    try:
        toks_arr = proc_asr.make_toks_arr(asr_view)
    except KeyError as e:
        logging.warning("Failed to convert MMIF transcript to an array.")
        logging.warning(f"Encountered exception {e}")
        return None

    # perform a check on the tokens array to record problems
    issues = proc_asr.check_toks_arr( toks_arr )
    if issues["tokens_without_sentences"]: 
        logging.warning("Encountered tokens without sentences: " + str(issues["tokens_without_sentences"]) )
        tdict["infos"].append("tokens_without_sentences:" + str(issues["tokens_without_sentences"]))
    if issues["discontinuous_sentences_ids"]:
        logging.warning("Encountered discontinuous sentences: " + str(issues["discontinuous_sentences_ids"]) )
        tdict["problems"].append("discontinuous_sentences_ids:" + str(issues["discontinuous_sentences_ids"]) )

    # sanitize tokens array
    toks_arr = proc_asr.sanitize_toks_arr ( toks_arr, max_segment_chars )

    # split (relabel) long segments, if appropriate
    try:
        toks_arr_split = proc_asr.split_long_segs(toks_arr, max_chars=max_segment_chars)
    except Exception as e:
        logging.warning("Splitting long segments failed.")
        logging.warning(f"Encountered exception: {e}")
        logging.warning("Will proceed without splitting long segments.")
        toks_arr_split = copy.deepcopy(toks_arr)

    # make sentence array
    sts_arr = proc_asr.make_sts_arr(toks_arr_split)

    # derive item ID if one was not given
    # (From here on, use `tdict["item_id"]` to refer to the item ID.)
    if item_id:
        tdict["item_id"] = item_id
    else:
        try:
            # first look for an AudioDocument
            doc_loc = usemmif.get_document_location(DocumentTypes.AudioDocument, path_only=True)
            if not doc_loc:
                # otherwise look for a VideoDocument
                doc_loc = usemmif.get_document_location(DocumentTypes.VideoDocument, path_only=True)
            if doc_loc:
                filename = doc_loc.split("/")[-1]
                tdict["item_id"] = filename.split(".")[0]
            else:
                raise Exception("No AudioDocument or VideoDocument found.")
        except Exception as e:
            logging.warning("No media ID given and could not derive it from MMIF file.")
            logging.warning(f"Exception: {e}")
            logging.warning("Will attempt to derive an ID from the MMIF filename.")
            tdict["item_id"] = (mmif_filename.split(".")[0]).split("_")[0]
    
    # make up the canonical MMIF filename, if not provided
    if not mmif_filename:
        mmif_filename = tdict["item_id"] + "-transcript.mmif"

    # try to infer the language from the MMIF if not state explicitly
    if not languages:
        try:
            model_lang = asr_view.metadata.appConfiguration["modelLang"] 
            languages = [ model_lang ]
        except KeyError:
            languages = []
    
    # decode prior tpme given as a string
    if prior_tpme_str:
        try:
            prior_tpme = json.loads(prior_tpme_str)
            if not isinstance(prior_tpme, list):
                raise TypeError("Top level of prior TPME was not list/array.")
        except JSONDecodeError as e:
            logging.warning("Warning: Unable to open prior TPME record string.  Will not use.")
            prior_tpme = []
        except TypeError as e:
            logging.warning(f"Warning: {e}.  Will not use prior TPME.")
            prior_tpme = []
    else:
        prior_tpme = []


    # 
    # Add each transcript or TPME string to the dictionary
    # 
    tdict["tpme_mmif"] = make_tpme_mmif( asr_view, 
                                         tdict["item_id"], 
                                         mmif_filename, 
                                         tpme_provider, 
                                         languages,
                                         processing_note,
                                         prior_tpme )

    prior_tpme_mmif = json.loads(tdict["tpme_mmif"])

    tdict["tpme_text"] = make_tpme_text( tdict["item_id"], 
                                         mmif_filename, 
                                         tpme_provider,
                                         languages, 
                                         max_segment_chars,
                                         processing_note,
                                         prior_tpme_mmif )

    tdict["tpme_webvtt"] = make_tpme_webvtt( tdict["item_id"], 
                                             mmif_filename, 
                                             tpme_provider, 
                                             languages,
                                             max_segment_chars,
                                             max_line_chars,
                                             processing_note,
                                             prior_tpme_mmif )

    tdict["tpme_aajson"] = make_tpme_aajson( tdict["item_id"], 
                                             mmif_filename, 
                                             tpme_provider, 
                                             languages,
                                             max_segment_chars,
                                             processing_note,
                                             prior_tpme_mmif )


    if embed_tpme_aajson:
        embedded_tpme = json.loads(tdict["tpme_aajson"])
    else:
        embedded_tpme = None

    tdict["transcript_aajson"] = make_transcript_aajson( sts_arr, 
                                                         tdict["item_id"], 
                                                         languages,
                                                         embedded_tpme )

    tdict["transcript_webvtt"] = make_transcript_webvtt( sts_arr,
                                                         max_line_chars )

    tdict["transcript_text"] = make_transcript_text( sts_arr )


    return tdict



############################################################################
# Make transcript functions

def make_transcript_aajson( sts_arr:list, 
                            item_id:str, 
                            languages:list[str],
                            embedded_tpme:dict = None
                            ) -> str:
    
    # create a semicolon-separated language string
    language = ";".join(languages)

    # create AAPB JSON structure
    d = {}
    d["id"] = item_id
    d["language"] = language

    if embedded_tpme:
        d["tpme"] = embedded_tpme

    d["parts"] = []
    # add a new "part" for every row of the sentence array
    # (Must convert milliseconds to fractional seconds.)
    for i, st in enumerate(sts_arr):
        d["parts"].append( { 
            "start_time": st[0] / 1000,
            "end_time": st[1] / 1000,
            "text": st[2],
            "speaker_id": i+1 } )

    text = json.dumps(d, indent=2)
    return text


def make_transcript_webvtt( sts_arr:list,
                            max_line_chars:int = 42,
                            ) -> str:

    def ms2str ( total_ms: int ) -> str:
        # break time codes into components for VTT
        ms = total_ms % 1000
        total_seconds = total_ms // 1000
        s = total_seconds % 60
        total_minutes = total_seconds // 60
        m = total_minutes % 60
        h = total_minutes // 60

        # observe VTT convention of dropping unnecessary hours digits
        if h > 0:
            timecode = f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"  # HH:MM:SS.mmm
        else:
            timecode = f"{m:02d}:{s:02d}.{ms:03d}"  # MM:SS.mmm
        return timecode

    # build one big string of text
    text = "WEBVTT\n\n"
    for st in sts_arr:
        # write out the time cue followed by the text 
        cue_line = ms2str(st[0]) + " --> " + ms2str(st[1]) 
        text_lines = proc_asr.break_long_line(st[2], max_line_chars)
        text += ( cue_line + "\n" + text_lines + "\n\n" )

    return text


def make_transcript_text( sts_arr:list ) -> str:
    
    # build one big string of text
    text = ""
    if len(sts_arr):
        for st in sts_arr:
            if isinstance(st[2], str) and len(st[2]):
                text += (st[2] + "\n")

    return text


############################################################################
# Make TPME functions

def make_tpme_mmif( asr_view:View, 
                    item_id:str, 
                    mmif_filename:str, 
                    tpme_provider:str, 
                    languages:list[str],
                    processing_note:str,
                    prior_tpme:list = None 
                    ) -> str:

    iso_ts = asr_view.metadata["timestamp"]

    # Set values of TPME elements
    tpme = {}
    tpme["media_id"] = item_id
    tpme["transcript_id"] = mmif_filename
    tpme["modification_date"] = iso_ts
    tpme["provider"] = tpme_provider
    tpme["type"] = "transcript"
    tpme["file_format"] = "MMIF"
    tpme["features"] = { "time_aligned": True }
    tpme["human_review_level"] = "machine-generated"
    tpme["application_type"] = "ASR" 
    tpme["transcript_language"] = languages

    app = asr_view.metadata.app
    tpme["application_id"] = app
    try:
        model_size = asr_view.metadata.appConfiguration["modelSize"]
    except KeyError:
        model_size = ""
    try:
        model_lang = asr_view.metadata.appConfiguration["modelLang"] 
    except KeyError:
        model_lang = ""

    if app in KNOWN_APPS:
        tpme["application_provider"] = KNOWN_APPS[app]["application_provider"]
        tpme["application_name"] = KNOWN_APPS[app]["application_name"]
        tpme["application_version"] = KNOWN_APPS[app]["application_version"]
        tpme["application_repo"] = KNOWN_APPS[app]["application_repo"]

        # re-assign the model size if an alias was used
        try:
            model_size = KNOWN_APPS[app]["model_size_aliases"][model_size]
        except KeyError:
            pass
        
        # if the model was implied by both size and language assign model name accordingly.
        try:
            model_name = KNOWN_APPS[app]["implied_lang_specific_models"][(model_lang, model_size)]
        except KeyError:
            model_name = model_size

        # add a prefix if defined
        try:
            tpme["inference_model"] = KNOWN_APPS[app]["model_prefix"] + model_name
        except KeyError:
            tpme["inference_model"] = model_name

    else:
        tpme["application_provider"] = "UNKNOWN"
        tpme["application_name"] = app
        try:
            tpme["application_version"] = asr_view.metadata.app.split("/")[-1]
        except:
            tpme["application_version"] = "UNKNOWN"
        tpme["application_repo"] = "UNKNOWN"
        tpme["inference_model"] = model_size

    tpme["application_params"] = asr_view.metadata["appConfiguration"]
    tpme["processing_note"] = processing_note

    tpmel = [tpme]
    if prior_tpme:
        tpmel = tpmel + prior_tpme

    text = json.dumps(tpmel, indent=2)
    return text



def make_tpme_aajson( item_id:str, 
                      mmif_filename:str, 
                      tpme_provider:str,
                      languages:list[str],
                      max_segment_chars:int,
                      processing_note:str,
                      prior_tpme:list = None 
                      ) -> str:
    
    # try to ensure a unique modification time
    time.sleep(0.01)

    tpme = {}
    tpme["media_id"] = item_id
    tpme["transcript_id"] = f"{item_id}-transcript.json"
    tpme["parent_transcript_id"] = mmif_filename
    tpme["modification_date"] = datetime.now().isoformat()
    tpme["provider"] = tpme_provider
    tpme["type"] = "transcript"
    tpme["file_format"] = "AAPB-transcript-JSON"
    tpme["features"] = { "time_aligned": True, "max_segment_chars": max_segment_chars }
    tpme["transcript_language"] = languages
    tpme["human_review_level"] = "machine-generated"
    tpme["application_type"] = "format-conversion"
    tpme["application_provider"] = "GBH Archives"
    tpme["application_name"] = "aapb-transcript-converter"
    tpme["application_version"] = __version__
    tpme["application_repo"] = "https://github.com/WGBH-MLA/transcript_converter"
    tpme["application_params"] = {"max_segment_chars": max_segment_chars}
    tpme["processing_note"] = processing_note
    
    tpmel = [tpme]
    if prior_tpme:
        tpmel = tpmel + prior_tpme

    text = json.dumps(tpmel, indent=2)
    return text



def make_tpme_webvtt( item_id:str, 
                      mmif_filename:str, 
                      tpme_provider:str,
                      languages:list[str],
                      max_segment_chars:int,
                      max_line_chars:int,
                      processing_note:str,
                      prior_tpme:list = None 
                      ) -> str:
    
    # try to ensure a unique modification time
    time.sleep(0.01)

    tpme = {}
    tpme["media_id"] = item_id
    tpme["transcript_id"] = f"{item_id}-transcript.vtt"
    tpme["parent_transcript_id"] = mmif_filename
    tpme["modification_date"] = datetime.now().isoformat()
    tpme["provider"] = tpme_provider
    tpme["type"] = "transcript"
    tpme["file_format"] = "text/vtt"
    tpme["features"] = { "time_aligned": True, "max_segment_chars": max_segment_chars, "max_line_chars": max_line_chars }
    tpme["transcript_language"] = languages
    tpme["human_review_level"] = "machine-generated"
    tpme["application_type"] = "format-conversion"
    tpme["application_provider"] = "GBH Archives"
    tpme["application_name"] = "aapb-transcript-converter"
    tpme["application_version"] = __version__
    tpme["application_repo"] = "https://github.com/WGBH-MLA/transcript_converter"
    tpme["application_params"] = {"max_segment_chars": max_segment_chars, "max_line_chars": max_line_chars}
    tpme["processing_note"] = processing_note
    
    tpmel = [tpme]
    if prior_tpme:
        tpmel = tpmel + prior_tpme

    text = json.dumps(tpmel, indent=2)
    return text



def make_tpme_text( item_id:str, 
                    mmif_filename:str, 
                    tpme_provider:str, 
                    languages:list[str],
                    max_segment_chars:int,                    
                    processing_note:str,
                    prior_tpme:list = None 
                    ) -> str:

    # try to ensure a unique modification time
    time.sleep(0.01)

    tpme = {}
    tpme["media_id"] = item_id
    tpme["transcript_id"] = f"{item_id}-transcript.txt"
    tpme["parent_transcript_id"] = mmif_filename
    tpme["modification_date"] = datetime.now().isoformat()
    tpme["provider"] = tpme_provider
    tpme["type"] = "transcript"
    tpme["file_format"] = "text/plain"
    tpme["features"] = { "max_segment_chars": max_segment_chars }
    tpme["transcript_language"] = languages
    tpme["human_review_level"] = "machine-generated"
    tpme["application_type"] = "format-conversion"
    tpme["application_provider"] = "GBH Archives"
    tpme["application_name"] = "aapb-transcript-converter"
    tpme["application_version"] = __version__
    tpme["application_repo"] = "https://github.com/WGBH-MLA/transcript_converter"
    tpme["application_params"] = {"max_segment_chars": max_segment_chars}
    tpme["processing_note"] = processing_note

    tpmel = [tpme]
    if prior_tpme:
        tpmel = tpmel + prior_tpme

    text = json.dumps(tpmel, indent=2)
    return text



