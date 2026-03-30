import os
import re
from pathlib import Path
import argparse
from typing import List, Set

def extract_external_links(root_folder:Path) -> List[str]:
    url_pattern = re.compile(r'<([^>`]+)>`__')

    urls:Set[str] = set()

    for dirpath, _, filenames in os.walk(root_folder):
        for filename in filenames:
            if filename.endswith(".rst"):
                full_path = os.path.join(dirpath, filename)
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        found = [m.group(1) for m in url_pattern.finditer(content)]
                        urls.update(found)
                except (OSError, UnicodeDecodeError):
                    # Skip unreadable files
                    pass

    return sorted(urls)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('folders', nargs='+')
    args = parser.parse_args()

    for folder in args.folders:
        urls = extract_external_links(folder)
        for url in urls:
            print(url)

if __name__ == '__main__':
    main()
