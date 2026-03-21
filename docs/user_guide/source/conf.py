# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
from pathlib import Path
import sys

import scrutiny

os.environ['LATEXOPTS'] = '-interaction=nonstopmode -halt-on-error' # Bail on error. don't ask user for input

project = 'Scrutiny Debugger'
copyright = '2021, scrutinydebugger'
release = f'v{scrutiny.__version__}'
author=''

latex_engine = "pdflatex"
latex_elements = {
    'preamble':  r'\input{preamble.tex.txt}'
}


latex_additional_files = ["preamble.tex.txt"]
latex_show_urls = 'footnote'

default_filename = 'scrutinydebugger_v{scrutiny.__version__}_user_guide'
filename = os.environ.get('SCRUTINY_USER_GUIDE_FILENAME', default_filename)

latex_documents = [
    (
        'index',                            # Start file
        f'{filename}.tex',                  # File name
        'Scrutiny Debugger User Guide',     # Title
        '',                                 # Author name
        'manual'                            # Document class
        ),
]
