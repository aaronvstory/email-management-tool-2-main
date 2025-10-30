# Email Management Tool Style Guide

## 📋 Table of Contents
1. [Design Philosophy](#design-philosophy)
2. [Color System](#color-system)
3. [Typography](#typography)
4. [Spacing & Layout](#spacing--layout)
5. [Components](#components)
6. [Animation & Transitions](#animation--transitions)
7. [Responsive Design](#responsive-design)
8. [Dark Theme Principles](#dark-theme-principles)
9. [CSS Architecture](#css-architecture)
10. [Implementation Examples](#implementation-examples)
11. [Best Practices](#best-practices)

---

## 🎨 Design Philosophy

### Core Principles
- **Dark-First Design**: Built specifically for dark environments with reduced eye strain
- **Subtle Accents**: Matte, understated design with NO glow effects or bright gradients
- **High Contrast**: Clear visual hierarchy with strategic contrast ratios
- **Micro-Interactions**: Subtle animations and transitions for engagement
- **Consistent Sizing**: All similar components maintain identical dimensions
- **Full-Width Layouts**: Maximize screen real estate usage

### Visual Identity
- **Style**: Modern, professional, security-focused
- **Mood**: Sophisticated, reliable, cutting-edge
- **Personality**: Powerful yet approachable, serious but not intimidating
- **Aesthetic**: Subtle dark red accents with matte finishes

### Critical Rules
⚠️ **NEVER use bright red (#dc2626)** - Use ONLY dark red (#7f1d1d)
⚠️ **NO gradients on buttons** - Use rgba() backgrounds only
⚠️ **NO glow effects** - Keep shadows subtle and directional
⚠️ **Buttons hover: translateY(-2px)** - NOT -1px

---

## 🎨 Color System

### Primary Brand Colors

```css
/* CRITICAL: ONLY Dark Red - NO Bright Red Allowed */
--brand-primary: #7f1d1d;          /* Dark red - ONLY brand color */
--brand-primary-dark: #991b1b;      /* Medium red - alternative */
--brand-primary-darker: #7f1d1d;    /* Darkest red */

/* Background Colors */
--color-bg-gradient: #1a1a1a;       /* Base background */
--color-bg-panel: #1a1a1a;          /* Card/panel background */
--color-bg-panel-alt: #242424;      /* Alternative panel background */
--surface-base: #1a1a1a;            /* Surface layer */
--surface-highest: #242424;         /* Elevated surface */

/* Text Colors */
--color-text: #ffffff;              /* Primary text (white) */
--text-primary: #ffffff;            /* Primary text (white) */
--color-text-dim: #9ca3af;          /* Secondary/muted text (gray) */
--text-muted: #6b7280;              /* Disabled/placeholder text */
--text-secondary: #9ca3af;          /* Secondary text */
```

### Semantic Colors

```css
/* Status Colors */
--success-base: #10b981;            /* Success states (green) */
--color-positive: #10b981;          /* Success (green) */
--success-light: #6ee7b7;           /* Light success */

--danger-base: #7f1d1d;             /* Danger/error (dark red) */
--color-danger: #7f1d1d;            /* Danger (dark red) */
--danger-light: #fca5a5;            /* Light danger */

--warning-base: #f59e0b;            /* Warning (orange) */
--color-warn: #f59e0b;              /* Warning (orange) */
--warning-light: #fbbf24;           /* Light warning */

--info-base: #06b6d4;               /* Information (cyan) */
--color-info: #3b82f6;              /* Information (blue) */
--info-light: #60a5fa;              /* Light info */

/* Status Backgrounds (with opacity) */
--success-bg: rgba(16,185,129,0.15);
--success-border: rgba(16,185,129,0.35);

--danger-bg: rgba(127,29,29,0.15);  /* Dark red, NOT bright red */
--danger-border: rgba(127,29,29,0.35);

--warning-bg: rgba(245,158,11,0.15);
--warning-border: rgba(245,158,11,0.35);

--info-bg: rgba(59,130,246,0.15);
--info-border: rgba(59,130,246,0.35);
```

### Border Colors

```css
/* Border System */
--border-subtle: rgba(255,255,255,0.06);   /* Lightest borders */
--border-default: rgba(255,255,255,0.12);  /* Standard borders */
--border-emphasis: rgba(127,29,29,0.15);   /* Accent borders (dark red) */
--color-border: rgba(255,255,255,0.06);    /* Alias for subtle */
--color-border-strong: rgba(255,255,255,0.12); /* Strong borders */
```

### Radius System

```css
/* Border Radius */
--radius-sm: 6px;                   /* Small radius */
--radius-md: 12px;                  /* Medium radius (standard for chips/badges) */
--radius-lg: 20px;                  /* Large radius (panels) */
--radius-xl: 24px;                  /* Extra large */
```

### Shadow System

```css
/* Elevation Shadows - Subtle, Directional */
--shadow-sm: 0 1px 2px rgba(0,0,0,0.3);
--shadow-md: 0 2px 4px rgba(0,0,0,0.4);
--shadow-elev-1: 0 2px 4px -1px rgba(0,0,0,0.6), 0 1px 2px rgba(0,0,0,0.4);
--shadow-elev-2: 0 4px 12px -2px rgba(0,0,0,0.75), 0 2px 6px rgba(0,0,0,0.5);
--shadow-focus: 0 0 0 2px rgba(127,29,29,0.5); /* Dark red focus ring */
```

### ⛔ Forbidden Colors

**NEVER USE THESE:**
- ❌ `#dc2626` (bright red)
- ❌ `rgba(220,38,38,*)` (bright red with opacity)
- ❌ Pure black `#000000` (use `#0a0a0a` instead)
- ❌ Pure white backgrounds on dark theme

---

## ✍️ Typography

### Font Stack

```css
/* Primary Font Family */
--font-sans: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;

/* Monospace Font (for code/technical) */
--font-mono: 'JetBrains Mono', 'SFMono-Regular', Menlo, Consolas, monospace;
```

### Type Scale

```css
/* Headings - Compact for Space Efficiency */
h1 { font-size: 1.8rem; margin-bottom: 15px; }    /* 28.8px */
h2 { font-size: 1.5rem; margin-bottom: 12px; }    /* 24px */
h3 { font-size: 1.3rem; margin-bottom: 10px; }    /* 20.8px */
h4 { font-size: 1.15rem; margin-bottom: 8px; }    /* 18.4px */
h5 { font-size: 1.05rem; margin-bottom: 8px; }    /* 16.8px */
h6 { font-size: 0.95rem; margin-bottom: 6px; }    /* 15.2px */

/* Body Text */
body { font-size: 1rem; line-height: 1.6; }       /* 16px base */
.small-text { font-size: 0.875rem; }              /* 14px */
.tiny-text { font-size: 0.75rem; }                /* 12px */
```

### Font Weights

```css
/* Weight Scale */
--weight-regular: 400;
--weight-medium: 500;
--weight-semibold: 600;
--weight-bold: 700;
```

### Text Styling

```css
/* Letter Spacing for Headers */
.text-uppercase {
    text-transform: uppercase;
    letter-spacing: 1.4px;
}

/* Panel Titles */
.panel-title {
    font-size: 0.85rem;
    letter-spacing: 1px;
    font-weight: 600;
    color: var(--color-text-dim);
    text-transform: uppercase;
}

/* Stat Labels */
.stat-label {
    font-size: 0.65rem;
    letter-spacing: 1.4px;
    text-transform: uppercase;
    color: var(--color-text-dim);
    font-weight: 600;
}
```

---

## 📐 Spacing & Layout

### Spacing System

```css
/* Base Unit: 8px */
--space-xs: 4px;      /* 0.5x */
--space-sm: 8px;      /* 1x */
--space-md: 15px;     /* ~2x */
--space-lg: 25px;     /* ~3x */
--space-xl: 35px;     /* ~4.5x */
--space-2xl: 50px;    /* ~6x */

/* Margin Classes */
.mb-0 { margin-bottom: 0; }
.mb-1 { margin-bottom: 8px; }
.mb-2 { margin-bottom: 15px; }
.mb-3 { margin-bottom: 25px; }
.mb-4 { margin-bottom: 35px; }
.mb-5 { margin-bottom: 50px; }
```

### Grid System

```css
/* Responsive Grid */
.stats-grid {
    display: grid;
    gap: 14px;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

/* Card Grid */
.cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
    gap: 20px;
}
```

---

## 🧩 Components

### Buttons

#### ⚠️ CRITICAL: Button Styling Rules

**ALL red buttons MUST follow this exact pattern:**

```css
/* Primary & Secondary Buttons - IDENTICAL STYLING */
.btn-primary,
.btn-secondary,
.btn-primary-modern {
    background: rgba(127,29,29,0.18) !important;  /* Subtle dark red */
    color: var(--text-primary) !important;
    border: 1px solid rgba(127,29,29,0.35) !important;
    font-weight: 500;
    transition: all 0.2s ease;
}

/* Hover Effect - MUST use -2px lift, NOT -1px */
.btn-primary:hover,
.btn-secondary:hover,
.btn-primary-modern:hover {
    background: rgba(127,29,29,0.24) !important;
    transform: translateY(-2px) !important;      /* -2px NOT -1px */
    box-shadow: var(--shadow-md) !important;
    color: var(--text-primary) !important;
}

/* ⛔ FORBIDDEN on buttons:
   - NO gradients
   - NO glow effects
   - NO changing border-width on hover
   - NO bright red colors
   - NO translateY(-1px) - must be -2px
*/
```

#### Success Button

```css
.btn-success {
    background: rgba(16,185,129,0.18) !important;
    color: var(--text-primary) !important;
    border: 1px solid rgba(16,185,129,0.35) !important;
}

.btn-success:hover {
    background: rgba(16,185,129,0.24) !important;
    transform: translateY(-2px) !important;
    box-shadow: var(--shadow-md) !important;
}
```

#### Ghost Button

```css
.btn-ghost {
    background: rgba(255,255,255,0.07);
    border: 1px solid var(--border-default);
    color: var(--color-text);
}

.btn-ghost:hover {
    background: rgba(127,29,29,0.15);
    border-color: var(--color-accent);
}
```

#### Button Sizes

```css
/* Standard Size */
.btn {
    height: 42px;
    padding: 8px 20px;
    font-size: 15px;
    border-radius: var(--radius-md);
}

/* Size Variants */
.btn-sm { height: 34px; padding: 5px 15px; font-size: 14px; }
.btn-lg { height: 50px; padding: 12px 30px; font-size: 18px; }
```

### Cards

#### Card-Unified Pattern

```css
/* Modern Unified Card with Hover Effects */
.card-unified {
    background: var(--surface-highest);
    border-radius: var(--radius-lg);
    border: 1px solid var(--border-subtle);
    box-shadow: var(--shadow-sm);
    transition: all 0.3s ease;
    overflow: hidden;
}

.card-unified:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.6);
    border-color: rgba(127,29,29,0.3);
}

.card-unified-header {
    background: rgba(127,29,29,0.08);
    border-bottom: 1px solid rgba(255,255,255,0.06);
    padding: 15px 20px;
}

.card-unified-body {
    padding: 20px;
}
```

**Usage Example:**
```html
<div class="card-unified">
  <div class="card-unified-header">
    <h4>Card Title</h4>
  </div>
  <div class="card-unified-body">
    <p>Card content goes here</p>
  </div>
</div>
```

### Panels

#### Panel Header Pattern

```css
/* Panel with Header and Actions */
.panel {
    background: var(--color-bg-panel);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: 20px 22px;
    box-shadow: var(--shadow-elev-1);
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
}

.panel-title {
    font-size: 0.85rem;
    letter-spacing: 1px;
    font-weight: 600;
    color: var(--color-text-dim);
    text-transform: uppercase;
}

.panel-actions {
    display: flex;
    align-items: center;
    gap: 10px;
}

.panel-body {
    padding: 0; /* No padding - controlled by panel parent */
}

.panel-note {
    font-size: 0.8rem;
    color: var(--color-text-dim);
    font-style: italic;
    margin-top: 8px;
}
```

**Usage Example:**
```html
<div class="panel">
  <div class="panel-header">
    <div class="panel-title">
      <i class="bi bi-list-check"></i> Section Title
    </div>
    <div class="panel-actions">
      <button class="btn btn-secondary btn-sm">
        <i class="bi bi-plus-circle"></i> Add Item
      </button>
    </div>
  </div>
  <div class="panel-body">
    <!-- Content here -->
  </div>
  <div class="panel-note">Additional information or instructions</div>
</div>
```

### Tables

#### ⚠️ CRITICAL: Table Row Hover Effect

**ALL tables MUST use this exact hover effect:**

```css
/* Global Table Hover - Applies to ALL Tables */
.table tbody tr:hover,
.table-hover tbody tr:hover,
.table-modern tbody tr:hover,
.table-unified tbody tr:hover,
table tbody tr:hover {
    background: rgba(255,255,255,0.03) !important;  /* Just darkens, NO red tint */
    box-shadow: 0 0 0 1px rgba(127,29,29,.2) !important;  /* Subtle red outline */
    transition: all 0.2s ease;
}

/* ⛔ FORBIDDEN on table rows:
   - NO red background tint (like rgba(127,29,29,.08))
   - Background must be white with low opacity
   - Only the outline can be red
*/
```

#### Table Structure

```css
.table-modern {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0 6px;
}

.table-modern thead th {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 1.4px;
    font-weight: 600;
    color: var(--color-text-dim);
    padding: 0 10px 6px;
    text-align: left;
}

.table-modern tbody tr {
    background: var(--color-bg-panel-alt);
    box-shadow: 0 1px 0 0 var(--color-border);
}

.table-modern tbody tr td {
    padding: 15px 10px;
    font-size: 0.8rem;
    color: var(--color-text);
}
```

### Bulk Actions Bar (NEW)

```css
/* Sticky Bulk Actions Bar */
#bulkActions {
    position: sticky;
    top: 0;
    z-index: 10;
    background: var(--surface-highest);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 12px 16px;
    margin-bottom: 16px;
    box-shadow: var(--shadow-sm);
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    align-items: center;
}

#bulkActions::before {
    content: '✓ ' attr(data-count) ' selected';
    font-weight: 600;
    color: var(--text-primary);
    margin-right: 10px;
}
```

**Usage Example:**
```html
<div id="bulkActions" style="display: none;" data-count="0">
  <button class="btn-success" onclick="bulkAction('RELEASE')">
    <i class="bi bi-unlock"></i> Release
  </button>
  <button class="btn-danger" onclick="bulkAction('DISCARD')">
    <i class="bi bi-trash"></i> Discard
  </button>
</div>
```

### Meta Grid & Tag Chips

#### Meta Grid Layout

```css
/* Metadata Key-Value Grid */
.meta-grid {
    display: grid;
    gap: var(--space-xs);
}

.meta-row {
    display: flex;
    align-items: baseline;
}

.meta-label {
    font-weight: 600;
    color: var(--text-muted);
    min-width: 80px;
    margin-right: 10px;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.meta-value {
    color: var(--color-text);
    font-size: 0.85rem;
}
```

#### Tag Chips & Status Indicators

```css
/* Tag Chips - MUST use var(--radius-md), NOT 30px */
.tag-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border-radius: var(--radius-md);  /* 12px - NOT 30px! */
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.02em;
    background: rgba(255,255,255,0.06);
    border: 1px solid var(--border-subtle);
    color: var(--text-secondary);
}

.tag-chip.success {
    background: var(--success-bg);
    border-color: var(--success-border);
    color: var(--success-light);
}

.tag-chip.accent {
    background: var(--danger-bg);
    border-color: var(--danger-border);
    color: var(--danger-light);
}

.tag-chip.warning {
    background: var(--warning-bg);
    border-color: var(--warning-border);
    color: var(--warning-light);
}

.tag-chip.info {
    background: var(--info-bg);
    border-color: var(--info-border);
    color: var(--info-light);
}

.tag-chip.muted {
    background: rgba(148,163,184,0.08);
    border-color: rgba(148,163,184,0.2);
    color: var(--text-muted);
}

/* Status Indicators - MUST use var(--radius-md) */
.status-indicator {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: var(--radius-md);  /* 12px - NOT 20px or 30px! */
    font-size: 0.8rem;
    font-weight: 600;
    border: 1px solid;
}

.status-indicator.success {
    background: rgba(16,185,129,0.15);
    color: #10b981;
    border-color: rgba(16,185,129,0.3);
}

.status-indicator.warning {
    background: rgba(251,191,36,0.15);
    color: #fbbf24;
    border-color: rgba(251,191,36,0.3);
}

.status-indicator.danger {
    background: rgba(127,29,29,0.15);
    color: #fca5a5;
    border-color: rgba(127,29,29,0.3);
}

.status-indicator.info {
    background: rgba(59,130,246,0.15);
    color: #60a5fa;
    border-color: rgba(59,130,246,0.3);
}

/* Soft Badges */
.badge-soft-success {
    background: rgba(16,185,129,0.16) !important;
    border-color: rgba(16,185,129,0.32) !important;
    color: #6ee7b7 !important;
    border-radius: var(--radius-md) !important;
}

.badge-soft-danger {
    background: rgba(127,29,29,0.16) !important;
    border-color: rgba(127,29,29,0.36) !important;
    color: #fca5a5 !important;
    border-radius: var(--radius-md) !important;
}

.badge-soft-info {
    background: rgba(127,29,29,0.12) !important;
    border-color: rgba(127,29,29,0.28) !important;
    color: #fca5a5 !important;
    border-radius: var(--radius-md) !important;
}

.badge-soft-muted {
    background: rgba(148,163,184,0.08) !important;
    border-color: rgba(148,163,184,0.25) !important;
    color: var(--text-muted) !important;
    border-radius: var(--radius-md) !important;
}

/* ⛔ FORBIDDEN:
   - border-radius: 30px (use var(--radius-md) instead)
   - border-radius: 20px (use var(--radius-md) for chips)
   - border-radius: 999px (pill shape not allowed)
*/
```

### Action Bars

```css
/* Button Container for Card Actions */
.action-bar {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-sm);
    padding: var(--space-sm);
    border-radius: var(--radius-lg);
    border: 1px solid var(--border-subtle);
    background: rgba(255,255,255,0.03);
    margin-top: 12px;
}
```

### Forms

#### Input Fields

```css
.form-control {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid var(--border-default) !important;
    color: var(--text-primary) !important;
    padding: 10px 15px !important;
    border-radius: var(--radius-md) !important;
}

.form-control:focus {
    background: rgba(255,255,255,0.08) !important;
    border-color: rgba(127,29,29,0.5) !important;
    box-shadow: 0 0 0 2px rgba(127,29,29,0.2) !important;
    outline: none !important;
}

.form-control::placeholder {
    color: #888888 !important;
    opacity: 1 !important;
}
```

#### Checkboxes

```css
/* Checkboxes - Dark Red when Checked */
.form-check-input {
    background-color: rgba(255,255,255,0.06) !important;
    border: 1px solid var(--border-default) !important;
}

.form-check-input:checked {
    background-color: #7f1d1d !important;  /* Dark red, NOT bright red */
    border-color: #7f1d1d !important;
}
```

#### Labels

```css
.form-label {
    color: var(--text-primary);
    font-weight: 600;
    margin-bottom: 8px;
    font-size: 0.9rem;
}
```

#### Two-Line Setting Descriptions (NEW)

```css
/* Settings Page Pattern */
.setting-label {
    font-family: var(--font-mono);
    font-size: 0.875rem;
    color: var(--color-text);
    background: rgba(127,29,29,0.12);
    padding: 2px 6px;
    border-radius: 4px;
    border: 1px solid rgba(127,29,29,0.2);
}

.setting-desc {
    color: var(--color-text);
    font-weight: 500;
    font-size: 0.9rem;
    line-height: 1.4;
    margin-bottom: 4px;
}

.setting-detail {
    color: var(--color-text-dim);
    font-size: 0.8rem;
    font-style: italic;
    line-height: 1.3;
    margin-top: 3px;
}
```

**Usage Example:**
```html
<tr>
  <td><code class="setting-label">SETTING_NAME</code></td>
  <td>
    <div class="setting-desc">Main description of the setting</div>
    <div class="setting-detail">Detailed explanation with context and usage notes</div>
  </td>
  <td><!-- Input field --></td>
</tr>
```

### Modals

```css
.modal-content {
    background: var(--surface-highest) !important;
    border: 1px solid var(--border-subtle) !important;
    color: var(--text-primary) !important;
}

.modal-header {
    background: rgba(127,29,29,0.08);
    border-bottom: 1px solid var(--border-subtle);
    color: var(--text-primary);
}

.modal-body {
    color: var(--text-primary);
}
```

---

## ⚡ Animation & Transitions

### Standard Transition

```css
--transition: 140ms cubic-bezier(0.4, 0.2, 0.2, 1);

/* Apply to all interactive elements */
button, a, .card, .panel {
    transition: all 0.2s ease;
}
```

### Hover Effects

```css
/* Lift Effect - Buttons and Cards */
.btn:hover,
.card-unified:hover {
    transform: translateY(-2px);  /* MUST be -2px, NOT -1px */
    box-shadow: var(--shadow-md);
}

/* ⛔ FORBIDDEN Hover Effects:
   - NO glow effects (like box-shadow: 0 0 20px rgba(...))
   - NO brightness filters
   - NO scale transforms (except icons)
   - translateY must be -2px, NOT -1px
*/
```

### Animation Keyframes

```css
/* Fade In */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
}

/* Spin (for loading indicators) */
@keyframes spin-unified {
    to { transform: rotate(360deg); }
}

/* Loading Spinner */
.loading-spinner-unified {
    width: 24px;
    height: 24px;
    border: 3px solid rgba(255,255,255,0.1);
    border-radius: 50%;
    border-top-color: #7f1d1d;  /* Dark red, NOT bright red */
    animation: spin-unified 1s linear infinite;
}
```

---

## 📱 Responsive Design

### Breakpoints

```css
/* Mobile First Approach */
--breakpoint-sm: 640px;
--breakpoint-md: 768px;
--breakpoint-lg: 1024px;
--breakpoint-xl: 1280px;
```

### Responsive Patterns

```css
/* Tablet and Below */
@media (max-width: 1100px) {
    .split-layout { grid-template-columns: 1fr; }
    .sidebar { width: 220px; }
}

/* Mobile */
@media (max-width: 840px) {
    .sidebar {
        position: fixed;
        transform: translateX(-100%);
        z-index: 40;
    }
    .sidebar.open {
        transform: translateX(0);
    }
}
```

---

## 🌙 Dark Theme Principles

### Depth & Layering
1. **Base Layer**: `#0a0a0a` - Deepest background (never use pure black #000000)
2. **Primary Layer**: `#1a1a1a` - Cards and panels
3. **Secondary Layer**: `#242424` - Table rows, alternate backgrounds
4. **Elevated Layer**: `rgba(255,255,255,0.06)` - Form inputs
5. **Hover Layer**: `rgba(255,255,255,0.03)` - Interactive states (NOT red tint)

### Contrast Ratios
- **Primary Text on Dark**: 15:1 (#ffffff on #1a1a1a)
- **Secondary Text on Dark**: 7:1 (#9ca3af on #1a1a1a)
- **Minimum Interactive**: 4.5:1 (WCAG AA compliant)

---

## 🏗️ CSS Architecture

### CSS Variables Organization

```css
:root {
    /* === BRAND COLORS === */
    --brand-primary: #7f1d1d;
    --brand-primary-dark: #991b1b;

    /* === SEMANTIC COLORS === */
    --success-base: #10b981;
    --danger-base: #7f1d1d;
    --warning-base: #f59e0b;
    --info-base: #06b6d4;

    /* === SURFACE COLORS === */
    --surface-base: #1a1a1a;
    --surface-highest: #242424;

    /* === TEXT COLORS === */
    --text-primary: #ffffff;
    --text-secondary: #9ca3af;
    --text-muted: #6b7280;

    /* === BORDER COLORS === */
    --border-subtle: rgba(255,255,255,0.06);
    --border-default: rgba(255,255,255,0.12);
    --border-emphasis: rgba(127,29,29,0.15);

    /* === BORDER RADIUS === */
    --radius-sm: 6px;
    --radius-md: 12px;
    --radius-lg: 20px;

    /* === SHADOWS === */
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.3);
    --shadow-md: 0 2px 4px rgba(0,0,0,0.4);

    /* === ANIMATIONS === */
    --transition: 140ms cubic-bezier(0.4,0.2,0.2,1);
}
```

---

## 💻 Implementation Examples

### Creating a Panel with Header

```html
<div class="panel">
  <div class="panel-header">
    <div class="panel-title">
      <i class="bi bi-list-check"></i> Active Rules
      <span class="badge badge-soft-info ms-2">7 active</span>
    </div>
    <div class="panel-actions">
      <span class="text-muted small">Priority: High → Low</span>
    </div>
  </div>
  <div class="panel-body">
    <!-- Table or content here -->
  </div>
</div>
```

### Creating a Button Group

```html
<div class="action-bar">
  <button class="btn btn-secondary btn-sm">
    <i class="bi bi-pencil"></i> Edit
  </button>
  <button class="btn btn-ghost btn-sm">
    <i class="bi bi-trash"></i> Delete
  </button>
</div>
```

### Creating Status Chips

```html
<span class="tag-chip success">
  <i class="bi bi-check-circle"></i> Active
</span>
<span class="tag-chip accent">
  <i class="bi bi-x-circle"></i> Error
</span>
<span class="tag-chip warning">
  <i class="bi bi-exclamation-triangle"></i> Warning
</span>
```

### Creating a Table with Hover Effect

```html
<div class="table-modern">
  <table class="table table-hover">
    <thead>
      <tr>
        <th>Priority</th>
        <th>Name</th>
        <th>Status</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><span class="tag-chip info">80</span></td>
        <td><div class="fw-semibold">Rule Name</div></td>
        <td><span class="status-indicator success">Active</span></td>
        <td>
          <button class="btn btn-secondary btn-sm">
            <i class="bi bi-pencil"></i> Edit
          </button>
        </td>
      </tr>
    </tbody>
  </table>
</div>
```

---

## 📝 Best Practices

### ✅ Do's

✅ Use CSS variables for all colors and measurements
✅ Apply `var(--radius-md)` for all chips and badges
✅ Use `translateY(-2px)` for button hover effects
✅ Use `rgba(255,255,255,0.03)` for table row hover backgrounds
✅ Apply dark red (#7f1d1d) for all brand/danger colors
✅ Ensure text contrast meets WCAG AA standards
✅ Use subtle shadows with directional light source
✅ Apply transitions to all interactive elements

### ❌ Don'ts

❌ **NEVER use bright red (#dc2626)**
❌ **NEVER use gradients on buttons**
❌ **NEVER use glow effects (box-shadow with blur radius on all sides)**
❌ **NEVER use border-radius: 30px or 999px for chips (use var(--radius-md))**
❌ **NEVER use translateY(-1px) on hover (must be -2px)**
❌ **NEVER apply red background tint to table row hover**
❌ **NEVER change border-width on button hover**
❌ Mix different border radius values arbitrarily
❌ Use pure black (#000000) - use #0a0a0a instead
❌ Create buttons with inconsistent heights

---

## 🔄 Version History

- **v3.0** (Current): Dark red unification, subtle matte design, enhanced table hover effects
- **v2.1**: Unified dark theme with gradient system
- **v2.0**: Introduction of modular CSS architecture
- **v1.0**: Initial Bootstrap-based implementation

---

## 📚 Resources

- [Bootstrap 5.3 Documentation](https://getbootstrap.com/docs/5.3/)
- [Bootstrap Icons](https://icons.getbootstrap.com/)
- [Inter Font](https://fonts.google.com/specimen/Inter)
- [CSS Custom Properties](https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties)

---

**Last Updated**: January 19, 2025
**Maintained By**: Email Management Tool Development Team
