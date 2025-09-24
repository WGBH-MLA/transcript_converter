# AAPB Transcript Converter
Routines for processing MMIF files to create AAPB-style JSON transcripts and associated transcript metadata.

These routines require existing MMIF files containing annotations of audio, as produced by a CLAMS ASR app, like the [CLAMS whisper-wrapper app](https://apps.clams.ai/whisper-wrapper/).

## Overview

The `proc_asr` module includes functions for processing MMIF produced by a CLAMS ASR app.

The `post_proc_item` module includes functions called by `run_job.py` from [clams-kitchen](https://github.com/WGBH-MLA/clams-kitchen), and it calls functions in `proc_asr.py` to perform postprocessing on MMIF produced by a CLAMS ASR app.

## Installation

Clone the repository.  Change to the repository directory and do a `pip install -r requirements.txt`.



