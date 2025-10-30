import re
from collections import Counter

with open('static/css/unified.css', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all rgba colors
rgba_pattern = r'rgba?\([^)]+\)'
rgba_colors = re.findall(rgba_pattern, content)

# Count frequencies
rgba_counter = Counter(rgba_colors)

print('🎯 RGBA COLORS TO OPTIMIZE (3-4 occurrences):')
print('=' * 70)
batch3_targets = []
for color, count in sorted(rgba_counter.items(), key=lambda x: x[1], reverse=True):
    if 3 <= count <= 4:
        print(f'{count}x → {color}')
        batch3_targets.append((color, count))

print(f'\n📊 Total medium-frequency colors: {len(batch3_targets)}')
print(f'📊 Potential savings: {sum(c for _, c in batch3_targets)} instances')

# Find hex colors too
hex_pattern = r'#[0-9a-fA-F]{3,6}\b'
hex_colors = re.findall(hex_pattern, content)
hex_counter = Counter(hex_colors)

print('\n🎯 HEX COLORS TO OPTIMIZE (2-4 occurrences):')
print('=' * 70)
hex_targets = []
for color, count in sorted(hex_counter.items(), key=lambda x: x[1], reverse=True):
    if 2 <= count <= 4:
        print(f'{count}x → {color}')
        hex_targets.append((color, count))

print(f'\n📊 Total medium-frequency hex: {len(hex_targets)}')
print(f'📊 Potential savings: {sum(c for _, c in hex_targets)} instances')
