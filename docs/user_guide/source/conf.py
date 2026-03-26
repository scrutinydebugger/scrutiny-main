import os
from typing import Any

# region Override code-block font
# https://stackoverflow.com/questions/9899283/how-do-you-change-the-code-example-font-size-in-latex-pdf-output-with-sphinx

from sphinx.highlighting import PygmentsBridge
from pygments.formatters.latex import LatexFormatter

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
author=''   # Leave empty

latex_engine = "pdflatex"
latex_elements = {
    'preamble':  r'\input{preamble.tex.txt}',
    'figure_align' : 'H'
}

html_static_path = ['_static']
latex_additional_files = ["preamble.tex.txt"]

filename = os.path.splitext(scrutiny.expected_user_guide_filename())[0] # Name without extension

latex_documents = [
    (
        'index',                                    # Start file
        f'{filename}.tex',                          # File name
        'Scrutiny Debugger User Guide',             # Title
        'https://github.com/scrutinydebugger',      # Author name
        'manual'                                    # Document class
        ),
]

extensions = ["sphinx_subfigure"]
