#!/usr/bin/env python3
 
                                            
                                                                  
                                                                    
 
                                                                 
                                                                                 
                                                                                       
                                                                                
                                                                         
                                                                            

import os.path
import subprocess
import sys

project_root = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
os.chdir(project_root)

EXCLUDE_PATH_PREFIX = {
    "electrum/wordlist/",
    "fastlane/",
    "tests/",
}
EXCLUDE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".ttf", ".otf", ".pdn", ".icns", ".ico", ".gif",
}
UNICODE_WHITELIST = {
    "💬", "🗯", "⚠", chr(0xfe0f), "✓", "▷", "▽", "…", "•", "█", "™", "≈",
    "á", "é", "’",
    "│", "─", "└", "├", "📋",
}

exit_code = 0

bfiles = subprocess.check_output(["git", "ls-files"])
bfiles = bfiles.decode("utf-8")
for file_path in bfiles.splitlines():
    if os.path.isdir(file_path):
        continue
    if any(file_path.startswith(pattern) for pattern in EXCLUDE_PATH_PREFIX):
        continue
    _fname, ext = os.path.splitext(file_path)
    if ext in EXCLUDE_EXTENSIONS:
        continue
               
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f.read().splitlines()):
                for char in line:
                    if ord(char)>0x7f and char not in UNICODE_WHITELIST:
                        print(f"{file_path}:{line_no}. {line=}. hex={hex(ord(char))}. {char=}")
                        exit_code = 1
    except UnicodeDecodeError as e:
        raise Exception(f"cannot parse file {file_path=}") from e

sys.exit(exit_code)
