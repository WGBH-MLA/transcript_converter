"""
This file defines a what is known about the CLAMS ASR apps that can feed 
the transcript_converter post process.

The entries here are used to populate the TPME files that the postprocess
generates to describe the CLAMS apps.

To run clams-kitchen with a new (version of a) CLAMS ASR app, create 
a new entry in this list. 
"""

KNOWN_APPS = {
    "http://apps.clams.ai/whisper-wrapper/v12": {
        "application_name": "CLAMS whisper-wrapper",
        "application_provider": "Brandeis Lab for Linguistics and Computation",
        "application_repo": "https://github.com/clamsproject/app-whisper-wrapper",
        "application_version": "v12",
        "model_prefix": "whisper-",
        "model_sizes": {
            't': 'tiny', 
            'b': 'base', 
            's': 'small', 
            'm': 'medium', 
            'l': 'large', 
            'l2': 'large-v2', 
            'l3': 'large-v3',
            'tu': "large-v3-turbo",
            "turbo": "large-v3-turbo"
        }
    },
    "http://apps.clams.ai/parakeet-wrapper/v1.0": {
        "application_name": "CLAMS parakeet-wrapper",
        "application_provider": "Brandeis Lab for Linguistics and Computation",
        "application_repo": "https://github.com/clamsproject/app-parakeet-wrapper",
        "application_version": "v1.0",
        "model_prefix": "",
        "model_sizes": {
            '110m': "nvidia/parakeet-tdt_ctc-110m",
            '0.6b': "nvidia/parakeet-tdt-0.6b-v2",
            '1.1b': "nvidia/parakeet-tdt_ctc-1.1b"
        }
    }
}

