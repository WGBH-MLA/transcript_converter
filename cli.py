"""
cli.py

Use the converstion functionality provided by covert.py for simple usage
from the command line.

Basic usage: 
   python -m transcript_converter.cli PATH/TO/YOURFILE.mmif

To see additional options
   python -m transcript_converter.cli -h 

"""

import argparse
import warnings
from datetime import datetime

#from .convert import mmif_to_all
from . import mmif_to_all
from . import VERSION
from transcript_converter.convert import DEFAULT_TPME_PROVIDER, DEFAULT_MAX_SEGMENT_CHARS, DEFAULT_MAX_LINE_CHARS


def main():

    app_desc = f"MMIF transcript_converter (version {VERSION}). "
    app_desc += """
Performs transcript conversion from MMIF to AAPB transcript JSON.

This module is primarily intended to be invoked by other modules by importing it and calling the `mmif_to_all` function.
Only limited functionality is exposed by this CLI.
    """

    parser = argparse.ArgumentParser(
        prog='convert.py',
        description=app_desc,
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument("mmifpath", metavar="MMIF",
        help="Path to the source MMIF file")
    parser.add_argument("-v", "--vtt", action="store_true",
        help="Output transcript in WebVTT format instead of AAPB JSON")
    parser.add_argument("-m", "--tpme", action="store_true",
        help="Output TPME metadata sidecars for the transcripts produced.")
    parser.add_argument("-s", "--max-seg-chars", type=int, default=DEFAULT_MAX_SEGMENT_CHARS,
        help="Maximum number of characters in a time-aligned segment")
    parser.add_argument("-l", "--max-line-chars", type=int, default=DEFAULT_MAX_LINE_CHARS,
        help="Maximum number of charcters in a line before a line break in WebVTT")
    parser.add_argument("-i", "--item-id", default="",
        help="The identifier of the media, to be recorded in TPME.")
    parser.add_argument("-p", "--provider", default=DEFAULT_TPME_PROVIDER,
        help="The transcript provider, to be recorded in TPME.")
    parser.add_argument("-n", "--processing-note", default="",
        help="Processing note to be recorded in TPME.")
    
    args = parser.parse_args()

    try:
        mmif_filename = args.mmifpath.split("/")[-1]
        with open(args.mmifpath, "r") as file:
            mmif_str = file.read()
    except Exception as e:
        print("Failed to open source MMIF file.  Encountered exception:")
        print(e)
        print("Use `-h` flag to see usage instructions.")

    # suppress MMIF warnings
    warnings.filterwarnings("ignore")

    # perform conversion
    tdict = mmif_to_all( mmif_str = mmif_str,
                         item_id = args.item_id,
                         mmif_filename = mmif_filename,
                         tpme_provider = args.provider,
                         max_segment_chars = args.max_seg_chars,
                         max_line_chars = args.max_line_chars,
                         embed_tpme_aajson = True,
                         processing_note = args.processing_note )

    # get potentially more informative media ID
    item_id = tdict["item_id"]

    # write out file(s)
    if args.vtt:
        # write out WebVTT
        fname = item_id + "-transcript.vtt"
        with open(fname, "w") as file:
            file.write(tdict["transcript_webvtt"])
        if args.tpme:
            dt = datetime.now()
            tpme_ts = f"{dt.year:04d}{dt.month:02d}{dt.day:02d}-{dt.hour:02d}{dt.minute:02d}{dt.second:02d}-{dt.microsecond:06d}"
            tpme_fname = f'{item_id}-tpme-{tpme_ts}.json'
            with open(tpme_fname, "w") as file:
                file.write(tdict["tpme_webvtt"])
    else:
        # write out AAPB JSON
        fname = item_id + "-transcript.json"
        with open(fname, "w") as file:
            file.write(tdict["transcript_aajson"])
        if args.tpme:
            dt = datetime.now()
            tpme_ts = f"{dt.year:04d}{dt.month:02d}{dt.day:02d}-{dt.hour:02d}{dt.minute:02d}{dt.second:02d}-{dt.microsecond:06d}"
            tpme_fname = f'{item_id}-tpme-{tpme_ts}.json'
            with open(tpme_fname, "w") as file:
                file.write(tdict["tpme_aajson"])

if __name__ == "__main__":
    main()