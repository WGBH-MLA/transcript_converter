"""
proc_asr.py

Defines low-level functions that perform basic processing on MMIF output 
from whisper-wrapper or similar ASR CLAMS apps.

The primary role of this module is to convert transcript data in the MMIF 
graph structure to tabular data.

It also provides functionality for relabling of transcript segments to 
adjust their lengths (to limit those that have too many characters).
"""
import logging
import json
import copy

from mmif import Mmif
from mmif import AnnotationTypes
from mmif import View

# import pprint # DIAG

# Default values
DEFAULT_MAX_SEGMENT_CHARS = 110
DEFAULT_MAX_LINE_CHARS = 42

# list of tokens which need not be preceded by a space when added to a sentence string
NO_SPACE_BEFORE = ['.', ',', '-', '/']


def get_asr_view_id( usemmif:Mmif ) -> str:
    """
    Takes a MMIF object and returns the ID of the view from whisper-wrapper
    """

    tf_views = usemmif.get_all_views_contain(AnnotationTypes.TimeFrame)
    to_views = usemmif.get_all_views_contain("http://vocab.lappsgrid.org/Token")
    al_views = usemmif.get_all_views_contain(AnnotationTypes.Alignment)
    st_views = usemmif.get_all_views_contain("http://vocab.lappsgrid.org/Sentence")

    candidate_views = [ v for v in tf_views if v in to_views and v in al_views ]

    asr_views = [ v for v in candidate_views if v in st_views ]

    if len(asr_views):
        # take the last view
        asr_view_id = asr_views[-1].id
    elif len(candidate_views):
        logging.warning("Warning: No candidate views contained Sentence annotations.")
        asr_view_id = candidate_views[-1].id
    else:
        asr_view_id = None

    return asr_view_id



def tpme_from_mmif( usemmif:Mmif, asr_view_id:str=None ):
    """
    Takes an MMIF string and a view ID and returns a dictionary of TPME elements
    and values.
    """
    raise NotImplementedError("tpme_from_mmif is not yet implemented")



def make_toks_arr( asr_view:View ) -> list :
    """
    Takes a MMIF view object and returns a table of tokens and their times.

    Columns:
        0: start time in ms
        1: end time in ms
        2: token string
        3: id of associated sentence
    """

    # get relevant MMIF annotations
    toanns = asr_view.get_annotations("http://vocab.lappsgrid.org/Token")
    tfanns = asr_view.get_annotations(AnnotationTypes.TimeFrame)
    alanns = asr_view.get_annotations(AnnotationTypes.Alignment)
    stanns = asr_view.get_annotations("http://vocab.lappsgrid.org/Sentence")

    # Build a dictionary of tokens indexed by token id
    # (We'll add the other properties as we get them.)
    tos = {}
    for ann in toanns:
        tos[ann.get_property("id")] = {"word": ann.get_property("word")}

    # Build a dictionary of tfs indexed by tf id
    tfs = {}
    for ann in tfanns:
        if ann.get_property("frameType") == "speech":
            tfs[ann.get_property("id")] = (ann.get_property("start"), ann.get_property("end"))

    # Use alignment annotations to add the tf information to the token dictionary
    for ann in alanns:
        # Not every alignment annotation is one of interest to us
        if ann.get_property("target") in tos and ann.get_property("source") in tfs:
            # look up the time span in tfs and add it to the token dictionary
            if "tspan" not in tos[ann.get_property("target")]:
                tos[ann.get_property("target")]["tspan"] = tfs[ann.get_property("source")]
            else:
                raise KeyError(f'Tried to align Token `{ann.get_property("target")}` to more than one TimeFrame.')

    # Add the sentence IDs to the token dictionary
    for ann in stanns:
        sid = ann.get_property("id")
        # for each target token add the sentence id to the token dictionary
        for tid in ann.get_property("targets"):
            # there should not yet be a sentence assigned to this token
            if "sid" not in tos[tid]:
                tos[tid]["sid"] = sid
            else:
                raise KeyError(f'Tried to assign Sentence `{sid}` to Token `{tid}` which already had sentence `{tos[tid]["sid"]}`.')

    # Create an array from the dictionary.
    # At this point, a token with out a "tspan" (because it did not get aligned) will 
    # raise a KeyError.
    # However, a token without a sentence assigned will simply have None as its 
    # sentence ID.
    toks_arr = [ [ tos[k]["tspan"][0], 
                   tos[k]["tspan"][1], 
                   tos[k]["word"], 
                   tos[k].get("sid") ] for k in tos ]

    # make sure the token annotations are ordered by their start time
    toks_arr.sort(key=lambda f:f[0])

    return toks_arr



def check_toks_arr( toks_arr:list ) -> dict:
    """
    Take a token array, as output by `make_toks_arr`, and scans for issues.
    Returns a dictionary of any issues encountered.

    Checks:
    - Make sure tokens have associated sentences.
    - Make sure sentences are not disjointed.
      (Sentences are disjointed if a token is associated with a previously
      seen sentence other than the immediately preceding token's sentence.)
    """
    toks_without_sts = []
    seen_sts = []
    last_st = ''
    disc_sts = []
    for t in toks_arr:
        if t[3] != last_st:
            if not t[3] or str(t[3]) == 'nan':
                # found a token without a sentence
                toks_without_sts.append(t[2])
            elif t[3] in seen_sts:
                # found a discontinuous sentence
                disc_sts.append(t[3])
            else:
                # beginning of a new senences
                seen_sts.append(t[3])
                last_st = t[3]
    disc_sts = list(set(disc_sts))

    issues = {}

    if len(toks_without_sts):
        issues["tokens_without_sentences"] = toks_without_sts
    else:
        issues["tokens_without_sentences"] = None

    if len(disc_sts):
        issues["discontinuous_sentences_ids"] = disc_sts
    else:
        issues["discontinuous_sentences_ids"] = None

    return issues



def sanitize_toks_arr ( toks_arr_in:list, 
                        max_chars:int=DEFAULT_MAX_SEGMENT_CHARS
                        ) -> list:
    """
    Before the splitting algorithm, this function runs a couple of sanitizing
    steps:  truncating extremely long tokens and adding a sentence name for
    tokens without one.
    """

    DEFAULT_SENTENCE_ID = "no_sentence"

    # deep copy input token array for non-destructive editing
    toks_arr = copy.deepcopy(toks_arr_in)

    max_tok_chars = max_chars - 3

    for r in toks_arr:
        # Limit the character length of each token. (Whisper has been known to output 
        # crazy long tokens, but tokens needs to be shorter than the lines, since 
        # we're splitting between tokens.)
        if len(r[2]) > max_tok_chars:
            r[2] = r[2][:max_tok_chars]
        # Give tokens without sentences a stand-in sentence name.
        if not r[3] or not isinstance(r[3], str):
            r[3] = DEFAULT_SENTENCE_ID
    
    return toks_arr



def split_long_segs( toks_arr_in:list, 
                    max_chars:int=DEFAULT_MAX_SEGMENT_CHARS,
                    max_toks_backtrack:int=3,
                    min_toks_dangled:int=3 
                    ) -> list:
    """
    Splitting long segments of the token array is simply a matter of reassigning 
    tokens to different "sentences".  This function re-assigns sentence IDs to 
    each token to limit the manximum length of a sentence.  
    
    Since "sentences" here are not necessarily sentences but rather wherever 
    Whisper created segments (effectively among lines), this function is useful 
    for limiting the maximum line length.  But for actually limiting line 
    length (e.g., to 42 characters for on-screen display), use a differnet function.

    Args:
      toks_arr_in (list):  a list of lists (as output by `make_toks_arr`)
      max_chars (int): the maximum length of a segment in characters.  A value less 
           than one will result in just returning a copy of the input array.
      max_toks_backtrack (int): the maximum number of tokens to backtrack from the
           end of a maximally long line in order to find an elegant location
           to divide
      min_toks_dangled (int): the minimum number of tokens that a new sentence 
           divisionshould leave dangled in a new sentence by themselves.  (This 
           value must be >= 1.)
    
    Returns:
      list:  a list of lists with the same structure as `toks_arr_in`

    Algorithm strategy:
      - Take a token arrary and make a deep copy of it.
      - Analyze the segments, to look for ones that are too long. 
      - If a segment is too long, split it into to parts by finding a suitable 
        split point to make the first part of the sentence shorter than the max
        length.  Then assignging a new sentence ID to tokens after that.
      - But, even then, the remainder may itself be too long.  So run the function
        again on just the part of the array corresponding to the sentence in focus.
        (This is the recursion step.)

    Heuristics for split points:
      - Aim for lines near but not above the max.
      - Avoid stranding too few tokens on a line by themsleves.
      - Try to split after punctuation, if convenient to do so without having 
        to backtrack too far to find the punctuation.
    """

    # Some hard-coded characters and tokens for splitting heuristics
    splitting_punc = ['.', ',']
    common_abbrevs = ["Mr.", "Mrs.", "Ms.", "Dr.", "Sr.", "Sra.", "Srta."]

    # deep copy input token array for non-destructive editing
    toks_arr = copy.deepcopy(toks_arr_in)

    # if max stated character is not positive, just return copy of array
    if max_chars < 1:
        return toks_arr

    assert max_chars >= 10, "Maximum characters per line must be at least 10."

    # build ordered lists of sentence ids
    st_ids = []
    for t in toks_arr:
        assert isinstance(t[3], str), "For segmentation, each token must have a sentence ID."
        if t[3] not in st_ids:
            st_ids.append(t[3])

    # perform analysis and splitting sentence-by-sentence
    for st_id in st_ids:

        # start by getting a much smaller array -- just for this sentence
        sttoks_arr = [ t for t in toks_arr if t[3] == st_id ]  
        
        # calculate the length of the current sentence
        st = ""
        for t in sttoks_arr:
            if len(st) > 0 and t[2][0] not in NO_SPACE_BEFORE:
                st += " "
            st += t[2]
        
        # print(t[3], len(st), st )  # DIAG

        # If the line is too long, analyze and re-label sentences to perform split 
        if len(st) > max_chars:

            # print("LENGTH:", len(st) ) # DIAG

            # find the index of the last token that would put the sentence under the limit            
            lasti = 0
            st = ""
            for i, t in enumerate(sttoks_arr):
                if len(st) > 0 and t[2][0] not in NO_SPACE_BEFORE:
                    st += " "
                st += t[2]
                if len(st) <= max_chars:
                    # don't want to advance `lasti` if the next line will be too short
                    if len(sttoks_arr) > i + min_toks_dangled:
                        # Make sure the last token on a line isn't immediately before a 
                        # token that has no space before it.
                        if sttoks_arr[i+1][2][0] not in NO_SPACE_BEFORE:
                            lasti = i

            # Perhaps backtrack `lasti` for elegant breaks on punctuation.
            # Idea: If posssible, want to break after punction commonly terminating
            # a semantic segment, like a comma or period. (But we don't want a 
            # split after the punctuation in a common abbreviaion, like Ms.)
            if sttoks_arr[lasti][2][-1] not in splitting_punc:
                for backup in range(1, max_toks_backtrack):
                    if ( (lasti-backup) >= 0 and 
                         sttoks_arr[lasti-backup][2][-1] in splitting_punc and
                         sttoks_arr[lasti-backup][2] not in common_abbrevs ):
                        lasti = lasti - backup
                        break 

            # Re-label by assigning a new sentence ID for all tokens after the cut-off
            for t in sttoks_arr[(lasti+1):]:
                t[3] = t[3]+"_x"
            
            # pprint.pprint(sttoks_arr) # DIAG

            #
            # Recursion step: In case the part after the cut-off is also too long, 
            # run function again on just the part of the array we're focused on.
            #
            sttoks_arr_split = split_long_segs( sttoks_arr, 
                                               max_chars, 
                                               max_toks_backtrack, 
                                               min_toks_dangled)
            
            # Copy the labels reflecting any new split back into the sentence array
            for i, t in enumerate(sttoks_arr):
                t[3] = sttoks_arr_split[i][3]

    # return the new array that has been relabeled
    return toks_arr



def make_sts_arr( toks_arr:list ) -> list:
    """
    Takes the token array and combines tokens into their sentences according to the 
    sentence labels in the toks array.
    """    

    # empty list of sentences
    sts_arr = []

    # begin first sentence
    start = toks_arr[0][0]
    end = toks_arr[0][1]
    st = toks_arr[0][2]
    st_id = toks_arr[0][3]

    for t in toks_arr[1:]:
        if t[3] == st_id:
            # Same sentence.  Extend sentence string
            end = t[1]
            if t[2][0] in NO_SPACE_BEFORE:
                st += t[2]
            else:
                st += " " + t[2]
        else:
            # New sentence id.  
            # Append current sentence to the list
            sts_arr.append([start, end, st])
            # Start new sentence
            start = t[0]
            end = t[1]
            st = t[2]
            st_id = t[3]

    # append final sentence to the list
    sts_arr.append([start, end, st])

    return sts_arr
        

def break_long_line( segment:str, 
                     max_line_chars:int=DEFAULT_MAX_LINE_CHARS
                     ) -> str:
    """
    Add line breaks within long segments.
    
    (Assumes that there are not yet any line breaks within individual segments.)
    """

    # break string into a list
    wordl = segment.split(" ")

    # truncate crazily long words
    for i, w in enumerate(wordl):
        if len(w) > max_line_chars:
            wordl[i] = w[:max_line_chars]

    # split long line
    llen = 0
    for i, w in enumerate(wordl):
        # if adding a space plus the new word would go over the limit
        if (llen + 1 + len(wordl[i])) > max_line_chars:
            # add a carriage return to the end of the preceding word
            wordl[i-1] += "\n"
            # start a new line length with the current word
            llen = len(wordl[i])
        else:
            llen += (1 + len(wordl[i]))

    # put string back together
    split_seg = " ".join(wordl)
    
    # remove spaces after newlines
    split_seg = split_seg.replace("\n ", "\n")

    return split_seg

