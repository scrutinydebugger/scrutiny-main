# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os

#region Override code-block font<
# https://stackoverflow.com/questions/9899283/how-do-you-change-the-code-example-font-size-in-latex-pdf-output-with-sphinx

from sphinx.highlighting import PygmentsBridge
from pygments.formatters.latex import LatexFormatter

from typing import Any
class CustomLatexFormatter(LatexFormatter):
    def __init__(self, *args:Any, **options:Any) -> None:
        super().__init__(*args, **options)
        self.verboptions = r"formatcom=\scriptsize"

PygmentsBridge.latex_formatter = CustomLatexFormatter
# endregion

import scrutiny

os.environ['LATEXOPTS'] = '-interaction=nonstopmode -halt-on-error' # Bail on error. don't ask user for input

project = 'Scrutiny Debugger'
copyright = '2021, scrutinydebugger'
release = f'v{scrutiny.__version__}'
author=''

latex_engine = "pdflatex"
latex_elements = {
    'preamble':  r'\input{preamble.tex.txt}',
    'fncychap': r'\usepackage[Sonny]{fncychap}',
}


html_static_path = ['_static']
latex_additional_files = ["preamble.tex.txt"]
latex_show_urls = 'footnote'

filename = os.path.splitext(scrutiny.expected_user_guide_filename())[0] # Name without extension

latex_documents = [
    (
        'index',                            # Start file
        f'{filename}.tex',                  # File name
        'Scrutiny Debugger User Guide',     # Title
        '',                                 # Author name
        'manual'                            # Document class
        ),
]
