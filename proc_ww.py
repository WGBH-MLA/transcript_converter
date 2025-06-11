"""
proc_www.py

Defines functions that perform processing on MMIF output from whisper-wrapper.
"""
# %%
import json
import logging
from pprint import pprint

import pandas as pd

from mmif import Mmif
from mmif import AnnotationTypes


def get_ww_view_id(mmif_str):
    """
    Takes a MMIF string and returns the ID of the view from whisper-wrapper
    """

    usemmif = Mmif(mmif_str)

    tf_views = usemmif.get_all_views_contain(AnnotationTypes.TimeFrame)
    to_views = usemmif.get_all_views_contain("http://vocab.lappsgrid.org/Token")
    al_views = usemmif.get_all_views_contain(AnnotationTypes.Alignment)
    st_views = usemmif.get_all_views_contain("http://vocab.lappsgrid.org/Sentence")

    candidate_views = [ v for v in tf_views if v in to_views and v in al_views ]

    ww_views = [ v for v in candidate_views if v in st_views ]

    if len(ww_views):
        # take the last view
        ww_view_id = ww_views[-1].id
    elif len(candidate_views):
        logging.warning("Warning: No candidate views contained Sentence annotations.")
        ww_view_id = candidate_views[-1].id
    else:
        ww_view_id = None

    return ww_view_id



def seg_toks( mmif_str, ww_view_id):
    """
    Takes a MMIF string and a view ID and returns a table of tokens and their times.
    """

    usemmif = Mmif(mmif_str)

    ww_view = usemmif.get_view_by_id(ww_view_id)

    tfanns = ww_view.get_annotations(AnnotationTypes.TimeFrame)
    toanns = ww_view.get_annotations("http://vocab.lappsgrid.org/Token")
    alanns = ww_view.get_annotations(AnnotationTypes.Alignment)
    stanns = ww_view.get_annotations("http://vocab.lappsgrid.org/Sentence")

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

    tfs_df = pd.DataFrame(tfs, columns=['tf_id','start','end'])
    tos_df = pd.DataFrame(tos, columns=['to_id','word'])
    als_df = pd.DataFrame(als, columns=['tf_id','to_id'])
    sts_df = pd.DataFrame(sts, columns=['to_id','st_id'])

    tfs_tos_df = pd.merge( pd.merge( tfs_df, pd.merge(tos_df,als_df) ), sts_df )

    return tfs_tos_df



# %%
