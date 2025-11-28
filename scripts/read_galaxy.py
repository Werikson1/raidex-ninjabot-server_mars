
import os

file_path = r"c:\Users\weriksonsr\Desktop\ogamex_developer\galaxy_page\galaxy.html"

try:
    with open(file_path, 'r', encoding='utf-16') as f:
        print(f.read(2000))
except Exception as e:
    print(f"Error reading utf-16: {e}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            print(f.read(2000))
    except Exception as e2:
        print(f"Error reading utf-8: {e2}")
