#!/usr/bin/env python3
"""Script to change all fonts to Blackladder ITC"""

# Read the file
with open('promptcraft_studio.py', 'r') as f:
    content = f.read()

# Replace Franklin Gothic Medium with Blackladder ITC
content = content.replace('Franklin Gothic Medium', 'Blackladder ITC')

# Write back
with open('promptcraft_studio.py', 'w') as f:
    f.write(content)

print('Successfully replaced all fonts with Blackladder ITC!')
print('Searching for instances...')

# Show where changes were made
import re
lines = content.split('\n')
for i, line in enumerate(lines, 1):
    if 'Blackladder ITC' in line:
        print(f'{i}: {line.strip()}')
