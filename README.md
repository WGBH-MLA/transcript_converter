# AAPB Transcript Converter
Routines for processing MMIF files to create AAPB-style JSON transcripts and associated transcript metadata.

These routines require existing MMIF files containing annotations of audio, as produced by, for example, the [CLAMS whisper-wrapper app](https://github.com/clamsproject/app-whisper-wrapper).

## Overview

The `proc_ww` module includes functions for processing MMIF produced by the [CLAMS whisper-wrapper app](https://github.com/clamsproject/app-whisper-wrapper).

The `post_proc_item` module includes functions called by `run_job.py` from [clams-kitchen](https://github.com/WGBH-MLA/clams-kitchen) calls functions in `process_ww.py` to perform postprocessing on MMIF produced by whisper-wrapper.

## Installation

Clone the repository.  Change to the repository directory and do a `pip install -r requirements.txt`.



