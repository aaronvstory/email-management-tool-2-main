#!/usr/bin/env python3
"""
Batch 2: Replace medium-frequency hardcoded colors with CSS variables
Skips the :root variable definition section to avoid circular references
"""
from pathlib import Path
import re

# Batch 2 color replacement mappings (3-4 occurrences)
COLOR_REPLACEMENTS = [
    # White opacity variants
    (r'rgba\s*\(\s*255\s*,\s*255\s*,\s*255\s*,\s*0\.1\s*\)', 'var(--white-10)'),
    
    # Black opacity variants
    (r'rgba\s*\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0\.3\s*\)', 'var(--black-30)'),
    (r'rgba\s*\(\s*0\s*,\s*0\s*,\s*0\s*,\s*\.3\s*\)', 'var(--black-30)'),
    (r'rgba\s*\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0\.4\s*\)', 'var(--black-40)'),
    (r'rgba\s*\(\s*0\s*,\s*0\s*,\s*0\s*,\s*\.4\s*\)', 'var(--black-40)'),
    (r'rgba\s*\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0\.6\s*\)', 'var(--black-60)'),
    (r'rgba\s*\(\s*0\s*,\s*0\s*,\s*0\s*,\s*\.6\s*\)', 'var(--black-60)'),
    
    # Dark overlay
    (r'rgba\s*\(\s*26\s*,\s*26\s*,\s*26\s*,\s*0\.9\s*\)', 'var(--overlay-dark)'),
    
    # Brand color variants
    (r'rgba\s*\(\s*127\s*,\s*29\s*,\s*29\s*,\s*0\.08\s*\)', 'var(--brand-overlay-subtle)'),
    (r'rgba\s*\(\s*127\s*,\s*29\s*,\s*29\s*,\s*0\.16\s*\)', 'var(--brand-overlay-soft)'),
    (r'rgba\s*\(\s*127\s*,\s*29\s*,\s*29\s*,\s*0\.3\s*\)', 'var(--brand-overlay-strong)'),
    
    # Success overlays
    (r'rgba\s*\(\s*16\s*,\s*185\s*,\s*129\s*,\s*0\.16\s*\)', 'var(--success-overlay-soft)'),
    (r'rgba\s*\(\s*16\s*,\s*185\s*,\s*129\s*,\s*0\.35\s*\)', 'var(--success-overlay-strong)'),
    
    # Danger overlays
    (r'rgba\s*\(\s*239\s*,\s*68\s*,\s*68\s*,\s*0\.15\s*\)', 'var(--danger-overlay-subtle)'),
    (r'rgba\s*\(\s*220\s*,\s*38\s*,\s*38\s*,\s*0\.4\s*\)', 'var(--danger-overlay-strong)'),
    
    # Info/blue overlays
    (r'rgba\s*\(\s*59\s*,\s*130\s*,\s*246\s*,\s*0\.16\s*\)', 'var(--info-overlay-soft)'),
    (r'rgba\s*\(\s*59\s*,\s*130\s*,\s*246\s*,\s*0\.28\s*\)', 'var(--info-overlay-medium)'),
    (r'rgba\s*\(\s*59\s*,\s*130\s*,\s*246\s*,\s*0\.3\s*\)', 'var(--info-overlay-strong)'),
    (r'rgba\s*\(\s*6\s*,\s*182\s*,\s*212\s*,\s*0\.35\s*\)', 'var(--info-overlay-cyan)'),
    
    # Warning overlay
    (r'rgba\s*\(\s*251\s*,\s*191\s*,\s*36\s*,\s*0\.3\s*\)', 'var(--warning-overlay-medium)'),
]

def replace_colors_smart(css_path):
    """Replace hardcoded colors with CSS variables, skipping :root section"""
    css_path = Path(css_path)
    
    if not css_path.exists():
        print(f"❌ File not found: {css_path}")
        return
    
    content = css_path.read_text(encoding='utf-8')
    original_content = content
    
    # Split content into :root section and rest
    # Find the :root { ... } block
    root_match = re.search(r'(:root\s*\{.*?\n\})', content, re.DOTALL)
    
    if root_match:
        root_section = root_match.group(1)
        root_start = root_match.start()
        root_end = root_match.end()
        
        before_root = content[:root_start]
        after_root = content[root_end:]
        
        print("=" * 80)
        print("BATCH 2: REPLACING MEDIUM-FREQUENCY COLORS")
        print("=" * 80)
        print()
        print(f"✓ Found :root section ({root_end - root_start} chars)")
        print(f"✓ Skipping :root to avoid circular references")
        print()
        
        # Only replace in the section after :root
        modified_after = after_root
        total_replacements = 0
        
        for pattern, replacement in COLOR_REPLACEMENTS:
            matches = re.findall(pattern, modified_after, re.IGNORECASE)
            count = len(matches)
            
            if count > 0:
                modified_after = re.sub(pattern, replacement, modified_after, flags=re.IGNORECASE)
                total_replacements += count
                print(f"✓ Replaced {count:3} instances → {replacement}")
        
        # Reconstruct the file
        content = before_root + root_section + modified_after
        
        print()
        print("=" * 80)
        print(f"✅ Total replacements: {total_replacements}")
        print("=" * 80)
    else:
        print("❌ Could not find :root section")
        return
    
    # Show before/after stats
    original_color_count = len(re.findall(r'rgba?\s*\([^)]+\)|#[0-9a-fA-F]{3,6}', original_content))
    new_color_count = len(re.findall(r'rgba?\s*\([^)]+\)|#[0-9a-fA-F]{3,6}', content))
    
    print()
    print("📊 CUMULATIVE IMPACT (Batch 1 + Batch 2)")
    print("-" * 80)
    print(f"Hardcoded colors before batch 2: {original_color_count}")
    print(f"Hardcoded colors after batch 2:  {new_color_count}")
    print(f"Reduction:                       {original_color_count - new_color_count} ({100 * (original_color_count - new_color_count) / original_color_count:.1f}%)")
    print()
    
    # Write back to file
    css_path.write_text(content, encoding='utf-8')
    print(f"✅ File updated: {css_path}")

if __name__ == "__main__":
    css_file = r"C:\claude\Email-Management-Tool\static\css\unified.css"
    replace_colors_smart(css_file)
