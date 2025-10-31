# Diagnostics Status Colors Fix

**Date:** October 31, 2025
**Issue:** Status chips in `/diagnostics` page had no colors - "Running" should be green, "Stopped" should be red

## Problem

The diagnostics page uses tag chips with status classes:
- `tag-chip success` for "Running" status
- `tag-chip accent` for "Stopped" status
- `tag-chip muted` for "Checking..." status

However, the CSS variables referenced by these classes were NOT DEFINED:
- `--success-bg`, `--success-border`, `--success-light`
- `--danger-bg`, `--danger-border`, `--danger-light`
- `--warning-bg`, `--warning-border`, `--warning-light`
- `--info-bg`, `--info-border`, `--info-light`

This caused the status chips to display without proper colors.

---

## Solution

Added missing CSS variables for tag chip status colors.

### File Modified

**`static/css/unified.css`** (Lines 99-114)

### Changes

Added 12 new CSS variables after line 97:

```css
/* Tag chip status colors */
--success-bg: rgba(16, 185, 129, 0.15);
--success-border: rgba(16, 185, 129, 0.35);
--success-light: #6ee7b7;

--danger-bg: rgba(239, 68, 68, 0.15);
--danger-border: rgba(239, 68, 68, 0.35);
--danger-light: #fca5a5;

--warning-bg: rgba(251, 191, 36, 0.15);
--warning-border: rgba(251, 191, 36, 0.35);
--warning-light: #fcd34d;

--info-bg: rgba(59, 130, 246, 0.15);
--info-border: rgba(59, 130, 246, 0.35);
--info-light: #93c5fd;
```

---

## Color Palette

### Success (Green)
- **Background**: `rgba(16, 185, 129, 0.15)` - 15% opacity emerald green
- **Border**: `rgba(16, 185, 129, 0.35)` - 35% opacity emerald green
- **Text**: `#6ee7b7` - Light emerald green

### Danger/Accent (Red)
- **Background**: `rgba(239, 68, 68, 0.15)` - 15% opacity red
- **Border**: `rgba(239, 68, 68, 0.35)` - 35% opacity red
- **Text**: `#fca5a5` - Light red/pink

### Warning (Yellow)
- **Background**: `rgba(251, 191, 36, 0.15)` - 15% opacity amber
- **Border**: `rgba(251, 191, 36, 0.35)` - 35% opacity amber
- **Text**: `#fcd34d` - Light yellow

### Info (Blue)
- **Background**: `rgba(59, 130, 246, 0.15)` - 15% opacity blue
- **Border**: `rgba(59, 130, 246, 0.35)` - 35% opacity blue
- **Text**: `#93c5fd` - Light blue

---

## Existing CSS Classes

These CSS classes already existed and were referencing the now-defined variables:

### Lines 1151-1155: Success
```css
.tag-chip.success {
  background: var(--success-bg);
  border-color: var(--success-border);
  color: var(--success-light);
}
```

### Lines 1145-1149: Accent (Danger)
```css
.tag-chip.accent {
  background: var(--danger-bg);
  border-color: var(--danger-border);
  color: var(--danger-light);
}
```

### Lines 1157-1161: Warning
```css
.tag-chip.warning {
  background: var(--warning-bg);
  border-color: var(--warning-border);
  color: var(--warning-light);
}
```

### Lines 1163-1167: Info
```css
.tag-chip.info {
  background: var(--info-bg);
  border-color: var(--info-border);
  color: var(--info-light);
}
```

---

## Diagnostics Page Usage

The diagnostics page (`templates/diagnostics.html`) dynamically generates status chips:

### Running Status (Line 129)
```javascript
const smtpChip = smtpData.listening
  ? '<span class="tag-chip success"><i class="bi bi-check-circle"></i> Running</span>'
  : '<span class="tag-chip accent"><i class="bi bi-exclamation-triangle"></i> Stopped</span>';
```

**Result**:
- **Running**: Green background with check-circle icon
- **Stopped**: Red background with warning triangle icon

### Loading State (Line 23)
```html
<span class="tag-chip muted">Checking...</span>
```

**Result**: Gray muted chip while loading

---

## Before/After

### Before (Broken)
```
SMTP Status
┌─────────────────────┐
│ Running             │  ← No background color, default styling
└─────────────────────┘
```

### After (Fixed)
```
SMTP Status
┌─────────────────────┐
│ ✓ Running           │  ← Green background (#10b981 15% opacity)
└─────────────────────┘  ← Light green text (#6ee7b7)
```

---

## Impact

This fix applies to ALL uses of tag-chip status classes across the entire application:
- **Diagnostics page**: SMTP status, watcher status
- **Accounts page**: Status indicators (if using tag-chip)
- **Any future pages**: Will have consistent status colors

---

## Testing

1. Navigate to http://127.0.0.1:5010/diagnostics
2. Verify SMTP Status chip:
   - ✅ **Running** = Green background with light green text
   - ✅ **Stopped** = Red background with light red text
   - ✅ **Checking...** = Gray muted styling

---

## Related Components

Other status indicators using different classes (still working correctly):
- **Watcher chips**: `.watcher-chip.active`, `.watcher-chip.stopped` (separate styling)
- **Status badges**: `.status-badge.status-HELD`, etc. (separate styling)
- **Alert boxes**: `.alert-success`, `.alert-danger` (Bootstrap native)

---

## Technical Notes

### Why Variables Were Missing

The CSS classes `.tag-chip.success`, `.tag-chip.accent`, etc. were defined but referenced CSS variables that didn't exist in the `:root` declaration. This is a common mistake when copying CSS patterns without the corresponding variable definitions.

### Design Consistency

The new variables follow the existing dark theme palette:
- 15% opacity backgrounds (subtle, not overwhelming)
- 35% opacity borders (visible but not harsh)
- Light/pastel text colors (high contrast on dark backgrounds)

All colors match the existing success/danger/warning/info overlays defined earlier in the CSS (lines 82-97).

---

## Summary

**Fixed**: Missing CSS variables for tag chip status colors

**Solution**: Added 12 CSS variables (4 states × 3 properties each)

**Result**: Status chips now display with proper colors:
- Success/Running = Green
- Danger/Stopped/Accent = Red
- Warning = Yellow
- Info = Blue

**Status**: ✅ Complete
**Lines Added**: 16 lines in unified.css (lines 99-114)
**Scope**: Global - affects all tag-chip status classes across the application
