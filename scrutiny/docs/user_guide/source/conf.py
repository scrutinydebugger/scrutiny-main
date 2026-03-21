# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
from pathlib import Path
import sys

conf_folder = Path(os.path.dirname(__file__))

folder = conf_folder
scrutiny_base = None
while folder.parent != folder:
    if folder.name == 'scrutiny':
        scrutiny_base = folder
        break
    folder = folder.parent

if scrutiny_base is None:
    raise FileNotFoundError("Cannot find the parent scrutiny pacakge")

sys.path.insert(0, str(scrutiny_base.parent.absolute()))

import scrutiny

project = 'Scrutiny Debugger'
copyright = '2021, scrutinydebugger'
author = 'scrutinydebugger'
release = f'v{scrutiny.__version__}'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = []

templates_path = ['_templates']
exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'alabaster'
html_static_path = ['_static']
