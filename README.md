# AAPB Transcript Converter
Python package to read MMIF files to create transcripts in **AAPB Transcript JSON**, **WebVTT**, and other formats, along with associated transcript metadata.

These routines require existing MMIF files containing annotations of audio, as produced by a CLAMS ASR app, like the [CLAMS whisper-wrapper app](https://apps.clams.ai/whisper-wrapper/).

This package is used by by `run_job.py` in [clams-kitchen](https://github.com/WGBH-MLA/clams-kitchen).  It can also be run directly from the CLI.  The package is also designed to be invoked by other Python modules by calling the `mmif_to_all` function. 

## Installation

Clone the repository.  Change to the repository directory and do a `pip install -r requirements.txt`.

## Usage

### CLI

If you have an existing MMIF file, you can create a transcript in AAPB JSON and associated TPME, via the CLI, by running

```Shell
python -m transcript_converter.cli -m PATH/TO/YOURFILE.mmif
```

To see additional options, run
```Shell
python -m transcript_converter.cli -h 
```

### Importing into other Python projects

This package is intended to be used in other Python projects, via one primary function called `mmif_to_all`.  That function takes a string of MMIF and returns a dictionary of strings containing transcripts and transcript metadata in various formats.

Sample code:
```Python
import transcript_converter as tc

print("transcript_converter version:", tc.__version__)

mmif_dirpath = "PATH/TO/YOUR/MMIF/DIR"
mmif_filename = "YOUR_ITEM.mmif"
mmif_path = mmif_dirpath + "/" + mmif_filename
with open( mmif_path, "r") as f:
    mmif_str = f.read()

d = tc.mmif_to_all( mmif_str, item_id="YOUR_ITEM_ID", mmif_filename=mmif_filename )

print("Keys in dictionary from `mmif_to_all`:")
for k in d:
    print(k)

print("TPME data from transcript in AAPB JSON format:")
print(d["tpme_aajson"])
```

For full usage details of the `mmif_to_all` function, see its docstring `convert.py`, or run
```Python
import transcript_converter as tc
help(tc.mmif_to_all)
```
