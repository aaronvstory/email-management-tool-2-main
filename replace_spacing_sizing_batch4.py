#!/usr/bin/env python3
"""
Batch 4: Replace high-frequency spacing, radius, and font-size values with CSS variables
Smart :root section skipping to avoid circular references
"""
import re

CSS_FILE = 'static/css/unified.css'

# Batch 4 replacement mappings (matched to actual :root variables)
SPACING_REPLACEMENTS = [
    (r'(?<![0-9.])5px(?![0-9])', 'var(--space-2xs)'),    # 14x
    (r'(?<![0-9.])6px(?![0-9])', 'var(--space-xs)'),     # 19x
    (r'(?<![0-9.])8px(?![0-9])', 'var(--space-sm)'),     # 25x
    (r'(?<![0-9.])10px(?![0-9])', 'var(--space-base)'),  # 40x - MOST USED!
    (r'(?<![0-9.])12px(?![0-9])', 'var(--space-md)'),    # 39x
    (r'(?<![0-9.])15px(?![0-9])', 'var(--space-lg)'),    # 37x
    (r'(?<![0-9.])20px(?![0-9])', 'var(--space-xl)'),    # 35x
]

RADIUS_REPLACEMENTS = [
    # Border-radius values (must be specific to avoid conflicts)
    (r'border-radius\s*:\s*4px', 'border-radius: var(--radius-xs)'),   # 10x
    (r'border-radius\s*:\s*6px', 'border-radius: var(--radius-sm)'),   # 7x
    (r'border-radius\s*:\s*8px', 'border-radius: var(--radius-base)'), # 21x - MOST USED!
    (r'border-radius\s*:\s*10px', 'border-radius: var(--radius-md)'),  # 8x
]

FONTSIZE_REPLACEMENTS = [
    # Font-size values (use lookbehind/lookahead to avoid matching decimals)
    (r'font-size\s*:\s*0\.75rem', 'font-size: var(--text-xs)'),     # 12x
    (r'font-size\s*:\s*0\.8rem', 'font-size: var(--text-sm)'),      # 10x
    (r'font-size\s*:\s*0\.85rem', 'font-size: var(--text-base)'),   # 27x
    (r'font-size\s*:\s*0\.875rem', 'font-size: var(--text-md)'),    # 12x
    (r'font-size\s*:\s*0\.9rem', 'font-size: var(--text-lg)'),      # 16x
]

def replace_smart(css_path):
    """Replace values while skipping :root section"""
    
    with open(css_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the :root { ... } block
    root_match = re.search(r'(:root\s*\{.*?\n\})', content, re.DOTALL)
    
    if not root_match:
        print('❌ Could not find :root section')
        return
    
    root_section = root_match.group(1)
    root_start = root_match.start()
    root_end = root_match.end()
    
    # Split content
    before_root = content[:root_start]
    after_root = content[root_end:]
    
    print('=' * 80)
    print('BATCH 4: SPACING & SIZING OPTIMIZATION')
    print('=' * 80)
    print()
    print(f'✓ Found :root section ({root_end - root_start} chars)')
    print(f'✓ Skipping :root to avoid circular references')
    print()
    
    # Only replace AFTER :root
    modified_after = after_root
    total_replacements = 0
    
    # Process spacing
    print('📏 SPACING REPLACEMENTS:')
    print('-' * 80)
    for pattern, replacement in SPACING_REPLACEMENTS:
        matches = re.findall(pattern, modified_after)
        count = len(matches)
        if count > 0:
            modified_after = re.sub(pattern, replacement, modified_after)
            total_replacements += count
            var_name = replacement.split('(')[1].split(')')[0]
            print(f'✓ {count:3d}x → {var_name}')
    
    # Process border-radius
    print()
    print('🔘 BORDER-RADIUS REPLACEMENTS:')
    print('-' * 80)
    for pattern, replacement in RADIUS_REPLACEMENTS:
        matches = re.findall(pattern, modified_after)
        count = len(matches)
        if count > 0:
            modified_after = re.sub(pattern, replacement, modified_after)
            total_replacements += count
            var_name = replacement.split('var(')[1].split(')')[0]
            print(f'✓ {count:3d}x → {var_name}')
    
    # Process font-size
    print()
    print('🔤 FONT-SIZE REPLACEMENTS:')
    print('-' * 80)
    for pattern, replacement in FONTSIZE_REPLACEMENTS:
        matches = re.findall(pattern, modified_after)
        count = len(matches)
        if count > 0:
            modified_after = re.sub(pattern, replacement, modified_after)
            total_replacements += count
            var_name = replacement.split('var(')[1].split(')')[0]
            print(f'✓ {count:3d}x → {var_name}')
    
    # Reconstruct
    content = before_root + root_section + modified_after
    
    # Write back
    with open(css_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print()
    print('=' * 80)
    print(f'✅ Total replacements: {total_replacements}')
    print(f'✅ File updated: {css_path}')
    print('=' * 80)

if __name__ == '__main__':
    replace_smart(CSS_FILE)
