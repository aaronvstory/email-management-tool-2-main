#!/usr/bin/env python3
"""
Analyze color usage in unified.css to identify optimization opportunities
"""
import re
from collections import Counter
from pathlib import Path

def extract_colors(css_content):
    """Extract all color values from CSS content"""
    # Patterns for different color formats
    hex_pattern = r'#[0-9a-fA-F]{3,6}\b'
    rgba_pattern = r'rgba?\([^)]+\)'
    
    hex_colors = re.findall(hex_pattern, css_content)
    rgba_colors = re.findall(rgba_pattern, css_content)
    
    return hex_colors, rgba_colors

def analyze_css_colors(css_path):
    """Analyze color usage in CSS file"""
    css_path = Path(css_path)
    
    if not css_path.exists():
        print(f"❌ File not found: {css_path}")
        return
    
    content = css_path.read_text(encoding='utf-8')
    
    hex_colors, rgba_colors = extract_colors(content)
    
    print("=" * 80)
    print("CSS COLOR ANALYSIS - unified.css")
    print("=" * 80)
    print()
    
    # Analyze hex colors
    print("📊 HEX COLOR USAGE")
    print("-" * 80)
    hex_counter = Counter(hex_colors)
    print(f"Total hex colors: {len(hex_colors)}")
    print(f"Unique hex colors: {len(hex_counter)}")
    print()
    print("Most common hex colors:")
    for color, count in hex_counter.most_common(20):
        print(f"  {color:12} → {count:3} occurrences")
    print()
    
    # Analyze rgba colors
    print("📊 RGBA/RGB COLOR USAGE")
    print("-" * 80)
    rgba_counter = Counter(rgba_colors)
    print(f"Total rgba colors: {len(rgba_colors)}")
    print(f"Unique rgba colors: {len(rgba_counter)}")
    print()
    print("Most common rgba colors:")
    for color, count in rgba_counter.most_common(20):
        print(f"  {color:40} → {count:3} occurrences")
    print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    total_colors = len(hex_colors) + len(rgba_colors)
    unique_colors = len(hex_counter) + len(rgba_counter)
    print(f"Total color instances: {total_colors}")
    print(f"Unique color values: {unique_colors}")
    print()
    
    # Identify candidates for CSS variables
    print("🎯 CANDIDATES FOR CSS VARIABLES (≥5 occurrences)")
    print("-" * 80)
    
    candidates = []
    
    # Hex candidates
    for color, count in hex_counter.items():
        if count >= 5:
            candidates.append((color, count, 'hex'))
    
    # RGBA candidates  
    for color, count in rgba_counter.items():
        if count >= 5:
            candidates.append((color, count, 'rgba'))
    
    candidates.sort(key=lambda x: x[1], reverse=True)
    
    print(f"Found {len(candidates)} color values used 5+ times:")
    for color, count, type_ in candidates[:30]:
        print(f"  {color:45} → {count:3} occurrences ({type_})")
    
    print()
    print("=" * 80)
    print(f"✅ Analysis complete - {len(candidates)} optimization opportunities identified")
    print("=" * 80)

if __name__ == "__main__":
    css_file = r"C:\claude\Email-Management-Tool\static\css\unified.css"
    analyze_css_colors(css_file)
