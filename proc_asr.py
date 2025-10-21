"""
proc_asr.py

Defines functions that perform processing on MMIF output from whisper-wrapper.
"""
# %%
import logging
import json

import pandas as pd

from mmif import Mmif
from mmif import AnnotationTypes
from mmif import View


# Version number
MODULE_VERSION = "0.70"


# list of tokens which need not be preceded by a space when added to a sentence string
NO_SPACE_BEFORE = ['.', ',', '-', '/']

# %%
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


# %%
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
    tfanns = asr_view.get_annotations(AnnotationTypes.TimeFrame)
    toanns = asr_view.get_annotations("http://vocab.lappsgrid.org/Token")
    alanns = asr_view.get_annotations(AnnotationTypes.Alignment)
    stanns = asr_view.get_annotations("http://vocab.lappsgrid.org/Sentence")

    # build lists from annotations
    tfs = [ [ ann.get_property("id"), 
              ann.get_property("start"), 
              ann.get_property("end") ] for ann in tfanns 
                                        if ann.get_property("frameType") == "speech" ]
    tos = [ [ ann.get_property("id"),
              ann.get_property("word") ] for ann in toanns ]
    als = [ [ ann.get_property("source"),
              ann.get_property("target") ] for ann in alanns ]
    sts = []
    for ann in stanns:
        for tg in ann.get_property("targets"):
            sts.append([ tg, ann.get_property("id") ])

    # make lists into dataframes
    tfs_df = pd.DataFrame(tfs, columns=['tf_id','start','end'])
    tos_df = pd.DataFrame(tos, columns=['to_id','word'])
    als_df = pd.DataFrame(als, columns=['tf_id','to_id'])
    sts_df = pd.DataFrame(sts, columns=['to_id','st_id'])

    # perform joins
    tfs_tos_df = pd.merge( tfs_df, pd.merge(tos_df,als_df) )
    if len(sts):
        tfs_tos_df = pd.merge( tfs_tos_df, sts_df, how='left' )
    else:
        tfs_tos_df['st_id'] = None

    # discard uncessary columns
    del tfs_tos_df['tf_id']
    del tfs_tos_df['to_id']

    # want to return a list instead of a dataframe
    toks_arr = tfs_tos_df.values.tolist()
    
    # make sure the annotations are in the right order
    toks_arr.sort(key=lambda f:f[0])

    # Scan through list to look for issues:
    #  - Make sure tokens have associated sentences.
    #  - Make sure sentences are not disjointed.
    # (Sentences are disjointed if a token is associated with a known sentence
    # other than the immediately preceding sentence.)
    toks_without_sts = []
    sts = []
    last = ''
    disc_sts = []
    for t in toks_arr:
        if t[3] != last:
            if str(t[3]) == 'nan':
                # first checking for non-sentence totkens
                toks_without_sts.append(t[2])
            elif t[3] in sts:
                # found a discontinuous sentence
                disc_sts.append(t[3])
            else:
                # beginning of a new senences
                sts.append(t[3])
                last = t[3]
    disc_sts = list(set(disc_sts))
    if len(toks_without_sts):
        logging.warning("Encountered tokens without sentences: " + str(toks_without_sts) )
    if len(disc_sts):
        logging.warning("Encountered discontinuous sentences: " + str(disc_sts) )

    return toks_arr


# %%
def split_long_sts( toks_arr_in:list, 
                    max_chars:int=80,
                    max_toks_backtrack:int=3,
                    min_toks_dangled:int=3 ) -> list:
    """
    Splitting long lines of the token array is simply a matter of reassigning 
    tokens to different sentences.  This function re-assigns seentece labels to 
    limit the manximum length of a sentence.  
    
    Since "sentences" here are not necessarily sentences but rather wherever 
    Whisper created segments (effectively among lines), this function is useful 
    for limiting the maximum line length.

    Strategy:
      - Take a token arrary and make a deep copy of it.
      - Analyze the sentences, to look for ones that are too long. 
      - If a sentence is too long, split it into to parts by finding a suitable 
        split point to make the first part of the sentence shorter than the max
        length.  Then assignging a new sentence ID to tokens after that.
      - But note that the remainder may itself be too long.  So run the function
        again on just the part of the array corresponding to the sentence in focus.
        (This is the recursion step.)

    Heuristics for split points:
      - Aim for lines near but not above the max.
      - Avoid stranding too few tokens on a line by themsleves.
      - Try to split after punctuation, if convenient to do so without having 
        to backtrack too far to find the punctuation.

    Parameters
      - max_chars: the maximum length of a sentence in characters
      - max_toks_backtrack: the maximum number of tokens to backtrack from the
           end of a maximally long line in order to find an elegant location
           to divide
      - min_toks_dangled: the minimum number of tokens that a new sentence division
           should leave dangled in a new sentence by themselves.  (This value
           must be >= 1.)
    """

    # Some hard-coded characters and tokens for splitting heuristics
    splitting_punc = ['.', ',']
    common_abbrevs = ["Mr.", "Mrs.", "Ms.", "Dr.", "Sr.", "Sra.", "Srta."]

    # deep copy input token array
    toks_arr = []
    for r_in in toks_arr_in:
        r = []
        for i in r_in:
            r.append(i)
        toks_arr.append(r)

    # Sanitize the array of tokens limiting character length of each token.
    # (Whisper has been known to output crazy long tokens, but tokens needs to be
    # be shorter than the lines, since we're splitting between tokens.)
    max_tok_chars = max_chars - 3
    for r in toks_arr:
        if len(r[2]) > max_tok_chars:
            r[2] = r[2][:max_tok_chars]

    # build ordered lists of sentence ids
    st_ids = []
    for t in toks_arr:
        if t[3] not in st_ids:
            st_ids.append(t[3])

    # perform analysis and splitting sentence-by-sentence
    for st_id in st_ids:
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
            
            #
            # Recursion step: In case the part after the cut-off is also too long, 
            # run function again on just the part of the array we're focused on.
            #
            sttoks_arr_split = split_long_sts(sttoks_arr, max_chars, max_toks_backtrack, min_toks_dangled)
            # copy the results of the new split back into this array
            for i, r in enumerate(sttoks_arr):
                r = sttoks_arr_split[i]

    # return the new array that has been relabeled
    return toks_arr



# %%
def make_sts_arr( toks_arr:list ) -> list:
    """
    Takes the token array and combines tokens into their sentences.
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
        

