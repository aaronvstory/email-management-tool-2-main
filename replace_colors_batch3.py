#!/usr/bin/env python3
"""
CSS Color Replacement - Batch 3 (Medium Frequency)
Replaces medium-frequency colors (2-4 occurrences) with CSS variables
Smart :root section skipping to avoid circular references
"""

import re

CSS_FILE = 'static/css/unified.css'

# Batch 3: Medium-frequency colors (2-4 occurrences)
COLOR_REPLACEMENTS = [
    # RGBA colors (10 instances)
    (r'rgba\s*\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0\.4\s*\)', 'var(--black-40)'),  # 4x
    (r'rgba\s*\(\s*255\s*,\s*255\s*,\s*255\s*,\s*0\.15\s*\)', 'var(--white-15)'),  # 3x
    (r'rgba\s*\(\s*127\s*,\s*29\s*,\s*29\s*,\s*0\.4\s*\)', 'var(--brand-overlay-strong)'),  # 3x (already exists!)

    # Hex colors (19 instances)
    (r'#60a5fa\b', 'var(--color-blue-400)'),  # 4x - blue accent
    (r'#fecaca\b', 'var(--color-red-200)'),   # 3x - light red
    (r'#28a745\b', 'var(--color-green-600)'), # 2x - green
    (r'#ffc107\b', 'var(--color-yellow-400)'), # 2x - yellow/amber
    (r'#dc3545\b', 'var(--color-red-600)'),   # 2x - red
    (r'#888888\b', 'var(--color-gray-500)'),  # 2x - mid gray
    (r'#2a2a2a\b', 'var(--surface-panel)'),   # 2x - dark surface
    (r'#e2e8f0\b', 'var(--color-gray-200)'),  # 2x - light gray
]

def replace_colors_smart(css_path):
    """Replace colors while skipping :root section to avoid circular references"""

    with open(css_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the :root { ... } block
    root_match = re.search(r'(:root\s*\{.*?\n\})', content, re.DOTALL)

    if not root_match:
        print('⚠️  Warning: Could not find :root section')
        return

    root_section = root_match.group(1)
    root_start = root_match.start()
    root_end = root_match.end()

    # Split content into before :root, :root itself, and after :root
    before_root = content[:root_start]
    after_root = content[root_end:]

    # Only replace in the section AFTER :root
    modified_after = after_root
    total_replacements = 0

    for pattern, replacement in COLOR_REPLACEMENTS:
        matches = re.findall(pattern, modified_after, re.IGNORECASE)
        count = len(matches)
        if count > 0:
            modified_after = re.sub(pattern, replacement, modified_after, flags=re.IGNORECASE)
            total_replacements += count
            print(f'✅ Replaced {count:2d}x: {pattern[:40]:40s} → {replacement}')

    # Reconstruct the file
    content = before_root + root_section + modified_after

    # Write back
    with open(css_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f'\n🎯 Total replacements: {total_replacements}')
    print(f'✅ File updated: {css_path}')

if __name__ == '__main__':
    print('=' * 80)
    print('CSS COLOR REPLACEMENT - BATCH 3 (Medium Frequency)')
    print('=' * 80)
    print()

    replace_colors_smart(CSS_FILE)

    print()
    print('=' * 80)
    print('✅ Batch 3 complete!')
    print('=' * 80)
