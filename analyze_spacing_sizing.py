#!/usr/bin/env python3
"""
Comprehensive spacing and sizing analysis for Batch 4 optimization
Identifies high-frequency spacing, border-radius, and font-size values
"""
import re
from collections import Counter

CSS_FILE = 'static/css/unified.css'

with open(CSS_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

print('=' * 80)
print('BATCH 4: SPACING & SIZING OPTIMIZATION ANALYSIS')
print('=' * 80)
print()

# Analyze spacing values (padding, margin)
spacing_pattern = r'(?:padding|margin)(?:-(?:top|right|bottom|left))?\s*:\s*([0-9.]+(?:px|rem|em))'
spacing_values = re.findall(spacing_pattern, content)
spacing_counter = Counter(spacing_values)

print('🎯 SPACING VALUES (Padding & Margin):')
print('-' * 80)
spacing_targets = []
for value, count in sorted(spacing_counter.items(), key=lambda x: x[1], reverse=True):
    if count >= 10:
        print(f'{count:3d}x → {value}')
        spacing_targets.append((value, count))

total_spacing = sum(c for _, c in spacing_targets)
print(f'\n📊 Total high-frequency spacing: {len(spacing_targets)} values, {total_spacing} instances')

# Analyze border-radius
radius_pattern = r'border-radius\s*:\s*([0-9.]+(?:px|rem|em))'
radius_values = re.findall(radius_pattern, content)
radius_counter = Counter(radius_values)

print('\n' + '=' * 80)
print('🎯 BORDER-RADIUS VALUES:')
print('-' * 80)
radius_targets = []
for value, count in sorted(radius_counter.items(), key=lambda x: x[1], reverse=True):
    if count >= 5:  # Lower threshold for radius
        print(f'{count:3d}x → {value}')
        radius_targets.append((value, count))

total_radius = sum(c for _, c in radius_targets)
print(f'\n📊 Total high-frequency radius: {len(radius_targets)} values, {total_radius} instances')

# Analyze font-size
fontsize_pattern = r'font-size\s*:\s*([0-9.]+(?:px|rem|em))'
fontsize_values = re.findall(fontsize_pattern, content)
fontsize_counter = Counter(fontsize_values)

print('\n' + '=' * 80)
print('🎯 FONT-SIZE VALUES:')
print('-' * 80)
fontsize_targets = []
for value, count in sorted(fontsize_counter.items(), key=lambda x: x[1], reverse=True):
    if count >= 10:
        print(f'{count:3d}x → {value}')
        fontsize_targets.append((value, count))

total_fontsize = sum(c for _, c in fontsize_targets)
print(f'\n📊 Total high-frequency font-size: {len(fontsize_targets)} values, {total_fontsize} instances')

# Overall summary
print('\n' + '=' * 80)
print('📈 BATCH 4 OPTIMIZATION POTENTIAL')
print('=' * 80)
print(f'Spacing:      {len(spacing_targets):2d} values × {total_spacing:3d} instances')
print(f'Border-radius: {len(radius_targets):2d} values × {total_radius:3d} instances')
print(f'Font-size:     {len(fontsize_targets):2d} values × {total_fontsize:3d} instances')
print('-' * 80)
print(f'TOTAL:        {len(spacing_targets) + len(radius_targets) + len(fontsize_targets):2d} variables × {total_spacing + total_radius + total_fontsize:3d} instances')
