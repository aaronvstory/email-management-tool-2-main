#!/usr/bin/env python3
"""
Batch 5: Optimize transition patterns
Replace hardcoded transition values with CSS variables
"""
import re

CSS_FILE = 'static/css/unified.css'

# Batch 5: Transition replacements
TRANSITION_REPLACEMENTS = [
    # Common transition patterns
    (r'transition\s*:\s*all\s+0\.2s\s+ease\s*;', 'transition: var(--transition-fast);'),  # 8x
    (r'transition\s*:\s*all\s+0\.3s\s+ease\s*;', 'transition: var(--transition-base);'), # 8x
]

def replace_transitions(css_path):
    """Replace transition patterns with CSS variables"""
    
    with open(css_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the :root section
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
    print('BATCH 5: TRANSITION OPTIMIZATION')
    print('=' * 80)
    print()
    
    # Only replace AFTER :root
    modified_after = after_root
    total_replacements = 0
    
    for pattern, replacement in TRANSITION_REPLACEMENTS:
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
    replace_transitions(CSS_FILE)
