#!/usr/bin/env python3
"""
Replace hardcoded colors with CSS variables in unified.css
"""
from pathlib import Path
import re

# Color replacement mappings (from analysis)
COLOR_REPLACEMENTS = [
    # White opacity variants (handle both spacing styles)
    (r'rgba\s*\(\s*255\s*,\s*255\s*,\s*255\s*,\s*0\.03\s*\)', 'var(--white-03)'),
    (r'rgba\s*\(\s*255\s*,\s*255\s*,\s*255\s*,\s*0\.04\s*\)', 'var(--white-04)'),
    (r'rgba\s*\(\s*255\s*,\s*255\s*,\s*255\s*,\s*0\.05\s*\)', 'var(--white-05)'),
    (r'rgba\s*\(\s*255\s*,\s*255\s*,\s*255\s*,\s*0\.06\s*\)', 'var(--white-06)'),
    (r'rgba\s*\(\s*255\s*,\s*255\s*,\s*255\s*,\s*0\.08\s*\)', 'var(--white-08)'),
    (r'rgba\s*\(\s*255\s*,\s*255\s*,\s*255\s*,\s*0\.12\s*\)', 'var(--white-12)'),
    (r'rgba\s*\(\s*255\s*,\s*255\s*,\s*255\s*,\s*0\.2\s*\)', 'var(--white-20)'),
    
    # Brand color overlays
    (r'rgba\s*\(\s*127\s*,\s*29\s*,\s*29\s*,\s*0\.18\s*\)', 'var(--brand-overlay-light)'),
    (r'rgba\s*\(\s*127\s*,\s*29\s*,\s*29\s*,\s*0\.2\s*\)', 'var(--brand-overlay-medium)'),
    (r'rgba\s*\(\s*127\s*,\s*29\s*,\s*29\s*,\s*0\.35\s*\)', 'var(--brand-overlay-strong)'),
    
    # Success overlays
    (r'rgba\s*\(\s*16\s*,\s*185\s*,\s*129\s*,\s*0\.15\s*\)', 'var(--success-overlay-light)'),
    (r'rgba\s*\(\s*16\s*,\s*185\s*,\s*129\s*,\s*0\.3\s*\)', 'var(--success-overlay-medium)'),
    
    # Danger overlays
    (r'rgba\s*\(\s*220\s*,\s*38\s*,\s*38\s*,\s*0\.18\s*\)', 'var(--danger-overlay-light)'),
    (r'rgba\s*\(\s*239\s*,\s*68\s*,\s*68\s*,\s*0\.3\s*\)', 'var(--danger-overlay-medium)'),
]

def replace_colors_in_css(css_path):
    """Replace hardcoded colors with CSS variables"""
    css_path = Path(css_path)
    
    if not css_path.exists():
        print(f"❌ File not found: {css_path}")
        return
    
    content = css_path.read_text(encoding='utf-8')
    original_content = content
    
    print("=" * 80)
    print("REPLACING HARDCODED COLORS WITH CSS VARIABLES")
    print("=" * 80)
    print()
    
    total_replacements = 0
    
    for pattern, replacement in COLOR_REPLACEMENTS:
        matches = re.findall(pattern, content, re.IGNORECASE)
        count = len(matches)
        
        if count > 0:
            content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
            total_replacements += count
            print(f"✓ Replaced {count:3} instances → {replacement}")
    
    print()
    print("=" * 80)
    print(f"✅ Total replacements: {total_replacements}")
    print("=" * 80)
    
    # Show before/after stats
    original_color_count = len(re.findall(r'rgba?\s*\([^)]+\)|#[0-9a-fA-F]{3,6}', original_content))
    new_color_count = len(re.findall(r'rgba?\s*\([^)]+\)|#[0-9a-fA-F]{3,6}', content))
    
    print()
    print("📊 IMPACT")
    print("-" * 80)
    print(f"Hardcoded colors before: {original_color_count}")
    print(f"Hardcoded colors after:  {new_color_count}")
    print(f"Reduction:               {original_color_count - new_color_count} ({100 * (original_color_count - new_color_count) / original_color_count:.1f}%)")
    print()
    
    # Write back to file
    css_path.write_text(content, encoding='utf-8')
    print(f"✅ File updated: {css_path}")

if __name__ == "__main__":
    css_file = r"C:\claude\Email-Management-Tool\static\css\unified.css"
    replace_colors_in_css(css_file)
