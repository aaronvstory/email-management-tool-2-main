# UI Migration Playbook

**Purpose**: Standardize all templates to match the `watchers.html` design system.  
**Lead Example**: `templates/accounts.html` → Modern unified patterns  
**Date**: 2025-01-19

---

## Table of Contents
1. [CSS Design Tokens](#css-design-tokens)
2. [Markup Transformations](#markup-transformations)
3. [Component Patterns](#component-patterns)
4. [Implementation Checklist](#implementation-checklist)

---

## CSS Design Tokens

### Phase 1: Introduce CSS Custom Properties

Add these to the top of `static/css/main.css` (after existing `:root` block):

```css
:root {
  /* === SURFACE COLORS === */
  --surface-base: #1a1a1a;
  --surface-elevated: #1f1f1f;
  --surface-highest: #242424;
  --surface-overlay: rgba(26, 26, 26, 0.95);
  
  /* === BORDER COLORS === */
  --border-subtle: rgba(255, 255, 255, 0.06);
  --border-default: rgba(255, 255, 255, 0.12);
  --border-emphasis: rgba(220, 38, 38, 0.15);
  
  /* === BRAND COLORS === */
  --brand-primary: #dc2626;
  --brand-primary-dark: #991b1b;
  --brand-primary-darker: #7f1d1d;
  --brand-secondary: #991b1b;
  
  /* === SEMANTIC COLORS === */
  --success-base: #10b981;
  --success-light: #22c55e;
  --success-bg: rgba(16, 185, 129, 0.15);
  --success-border: rgba(16, 185, 129, 0.35);
  
  --warning-base: #f59e0b;
  --warning-light: #fbbf24;
  --warning-bg: rgba(251, 191, 36, 0.15);
  --warning-border: rgba(251, 191, 36, 0.35);
  
  --danger-base: #dc2626;
  --danger-light: #ef4444;
  --danger-bg: rgba(239, 68, 68, 0.15);
  --danger-border: rgba(239, 68, 68, 0.35);
  
  --info-base: #06b6d4;
  --info-light: #60a5fa;
  --info-bg: rgba(59, 130, 246, 0.15);
  --info-border: rgba(59, 130, 246, 0.35);
  
  /* === TEXT COLORS === */
  --text-primary: #ffffff;
  --text-secondary: #e5e7eb;
  --text-muted: #9ca3af;
  --text-disabled: #6b7280;
  
  /* === SPACING === */
  --space-xs: 8px;
  --space-sm: 12px;
  --space-md: 20px;
  --space-lg: 30px;
  --space-xl: 40px;
  
  /* === BORDER RADIUS === */
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 15px;
  
  /* === SHADOWS === */
  --shadow-sm: 0 2px 4px -1px rgba(0, 0, 0, 0.6), 0 1px 2px rgba(0, 0, 0, 0.4);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.6);
  --shadow-lg: 0 4px 12px -2px rgba(0, 0, 0, 0.75), 0 2px 6px rgba(0, 0, 0, 0.5);
  --shadow-xl: 0 10px 30px rgba(0, 0, 0, 0.6);
  
  /* === GRADIENTS === */
  --gradient-surface: linear-gradient(145deg, var(--surface-base) 0%, var(--surface-elevated) 60%, var(--surface-highest) 100%);
  --gradient-brand: linear-gradient(135deg, var(--brand-primary) 0%, var(--brand-primary-dark) 50%, var(--brand-primary-darker) 100%);
  --gradient-header: linear-gradient(135deg, var(--brand-primary) 0%, var(--brand-primary-dark) 50%, var(--brand-primary-darker) 100%);
}
```

### Phase 2: Refactor Existing Classes to Use Tokens

Replace hardcoded values in these existing classes:

```css
/* BEFORE */
.stat-card-modern {
    background: linear-gradient(145deg, #1a1a1a 0%, #1f1f1f 60%, #242424 100%);
    border: 1px solid rgba(255,255,255,0.06);
}

/* AFTER */
.stat-card-modern {
    background: var(--gradient-surface);
    border: 1px solid var(--border-subtle);
}
```

---

## Markup Transformations

### 1. Page Header Pattern

#### ❌ BEFORE (accounts.html lines 117-132)
```html
<div class="accounts-header">
    <div class="d-flex justify-content-between align-items-center">
        <h2><i class="bi bi-envelope-at"></i> Email Account Management</h2>
        <div class="action-buttons">
            <button class="btn btn-modern btn-primary-modern" onclick="...">
                <i class="bi bi-plus-circle"></i> Add Account
            </button>
            <!-- more buttons -->
        </div>
    </div>
</div>
```

#### ✅ AFTER (watchers pattern)
```html
<div class="d-flex justify-content-between align-items-center mb-3">
    <h1 style="font-size:1.4rem"><i class="bi bi-envelope-at"></i> Email Accounts</h1>
    <div class="d-flex" style="gap:.5rem">
        <a href="/accounts/add" class="btn-secondary btn-sm">
            <i class="bi bi-plus-circle"></i> Add Account
        </a>
        <a href="/accounts/import" class="btn-secondary btn-sm">
            <i class="bi bi-cloud-upload"></i> Import
        </a>
        <button class="btn-secondary btn-sm" onclick="exportAccounts()">
            <i class="bi bi-cloud-download"></i> Export
        </button>
    </div>
</div>
```

**Changes**:
- Remove custom `.accounts-header` class
- Use inline flex with `mb-3` margin
- Standardize to `h1` with inline font-size
- Replace `.btn-modern .btn-primary-modern` with `.btn-secondary .btn-sm`
- Use `gap:.5rem` for button spacing
- Convert buttons to links where appropriate

---

### 2. Card Grid Pattern

#### ❌ BEFORE (accounts.html lines 16-21, 134-200)
```html
<style>
.accounts-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
    gap: 20px;
}
.account-card {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 15px;
    padding: 25px;
    box-shadow: 0 5px 20px rgba(0,0,0,0.3);
}
</style>

<div class="accounts-grid">
    <div class="account-card">
        <div class="account-header">
            <div class="account-title">{{ account.account_name }}</div>
            <span class="account-status">Active</span>
        </div>
        <div class="account-details">...</div>
        <div class="account-actions">...</div>
    </div>
</div>
```

#### ✅ AFTER (watchers pattern)
```html
<!-- Remove inline styles, use existing .cards-grid class -->

<div class="cards-grid">
    <div class="stat-card-modern">
        <div class="stat-label">{{ account.account_name }}</div>
        <div class="stat-value" style="font-size:1.1rem">{{ account.email_address }}</div>
        <div class="stat-delta">
            <span class="watcher-chip {% if account.is_active %}active{% else %}stopped{% endif %}">
                {% if account.is_active %}Active{% else %}Inactive{% endif %}
            </span>
        </div>
        
        <!-- Details section -->
        <div style="margin-top:15px;padding-top:15px;border-top:1px solid var(--border-subtle)">
            <div style="display:flex;justify-content:space-between;padding:6px 0;font-size:.85rem">
                <span style="color:var(--text-muted)">IMAP</span>
                <span style="color:var(--text-secondary)">{{ account.imap_host }}:{{ account.imap_port }}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:6px 0;font-size:.85rem">
                <span style="color:var(--text-muted)">SMTP</span>
                <span style="color:var(--text-secondary)">{{ account.smtp_host }}:{{ account.smtp_port }}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:6px 0;font-size:.85rem">
                <span style="color:var(--text-muted)">Watcher</span>
                <span id="watcher-{{ account.id }}" class="watcher-chip unknown">Unknown</span>
            </div>
        </div>
        
        <!-- Actions -->
        <div class="panel-actions" style="margin-top:15px;flex-wrap:wrap">
            <button class="btn-secondary btn-sm" onclick="testAccount('{{ account.id }}')">
                <i class="bi bi-play-circle"></i> Test
            </button>
            <button class="btn-secondary btn-sm" onclick="startWatcher('{{ account.id }}')">
                <i class="bi bi-power"></i> Start
            </button>
            <button class="btn-secondary btn-sm" onclick="stopWatcher('{{ account.id }}')">
                <i class="bi bi-stop-circle"></i> Stop
            </button>
            <button class="btn-ghost btn-sm" onclick="editAccount('{{ account.id }}')">
                <i class="bi bi-pencil"></i> Edit
            </button>
            <button class="btn-ghost btn-sm" onclick="deleteAccount('{{ account.id }}')">
                <i class="bi bi-trash"></i> Delete
            </button>
        </div>
    </div>
</div>
```

**Changes**:
- Replace `.accounts-grid` → `.cards-grid` (already exists in main.css)
- Replace `.account-card` → `.stat-card-modern`
- Replace `.account-header` → Use `.stat-label` for title
- Replace `.account-title` → `.stat-label`
- Replace `.account-status` → `.watcher-chip` with state classes
- Replace `.account-details` → Inline flex layout with CSS tokens
- Replace `.account-actions` → `.panel-actions` with `flex-wrap:wrap`
- Replace custom button classes → `.btn-secondary .btn-sm` and `.btn-ghost .btn-sm`
- Remove ALL custom CSS from `<style>` block

---

### 3. Button Cluster Pattern

#### ❌ BEFORE (accounts.html lines 174-199)
```html
<div class="account-actions">
    <button class="btn btn-primary btn-small">Test</button>
    <button class="btn btn-success btn-small">Start Watcher</button>
    <button class="btn btn-secondary btn-small">Stop Watcher</button>
    <button class="btn btn-warning btn-small">Edit</button>
    <button class="btn btn-info btn-small">Diagnostics</button>
    <button class="btn btn-outline-light btn-small">IMAP Live Test</button>
    <button class="btn btn-outline-warning btn-small">Scan Inbox</button>
    <button class="btn btn-danger btn-small">Delete</button>
</div>
```

#### ✅ AFTER (standardized)
```html
<div class="panel-actions" style="flex-wrap:wrap;gap:6px">
    <button class="btn-secondary btn-sm" onclick="testAccount('{{ account.id }}')">
        <i class="bi bi-play-circle"></i> Test
    </button>
    <button class="btn-secondary btn-sm" onclick="startWatcher('{{ account.id }}')">
        <i class="bi bi-power"></i> Start
    </button>
    <button class="btn-secondary btn-sm" onclick="stopWatcher('{{ account.id }}')">
        <i class="bi bi-stop-circle"></i> Stop
    </button>
    <button class="btn-ghost btn-sm" onclick="editAccount('{{ account.id }}')">
        <i class="bi bi-pencil"></i> Edit
    </button>
    <button class="btn-ghost btn-sm" onclick="runDiagnostics('{{ account.id }}')">
        <i class="bi bi-heart-pulse"></i> Diagnostics
    </button>
    <button class="btn-ghost btn-sm" onclick="imapLiveTest('{{ account.id }}')">
        <i class="bi bi-activity"></i> IMAP Test
    </button>
    <button class="btn-ghost btn-sm" onclick="scanInbox('{{ account.id }}')">
        <i class="bi bi-search"></i> Scan
    </button>
    <button class="btn-danger btn-sm" onclick="deleteAccount('{{ account.id }}')">
        <i class="bi bi-trash"></i> Delete
    </button>
</div>
```

**Changes**:
- Replace `.account-actions` → `.panel-actions`
- Remove ALL color-specific button classes (`.btn-primary`, `.btn-success`, `.btn-info`, `.btn-warning`, `.btn-outline-*`)
- Use ONLY: `.btn-secondary .btn-sm` (default), `.btn-ghost .btn-sm` (secondary actions), `.btn-danger .btn-sm` (destructive)
- Remove `.btn-small` → Use `.btn-sm` (already defined in main.css)
- Add `flex-wrap:wrap` for responsive wrapping
- Reduce gap to `6px` for compact layout

---

### 4. Status Badge Pattern

#### ❌ BEFORE (accounts.html lines 52-69, 109-112)
```html
<style>
.account-status {
    padding: 5px 12px;
    border-radius: 20px;
    font-size: 0.85em;
    font-weight: 600;
}
.status-active {
    background: rgba(34, 197, 94, 0.2);
    color: #22c55e;
    border: 1px solid #22c55e;
}
.status-inactive {
    background: rgba(220, 38, 38, 0.2);
    color: #dc2626;
    border: 1px solid #dc2626;
}
.mini-badge { padding: 2px 8px; border-radius: 10px; font-size: 0.75em; }
.ok { background: rgba(34,197,94,0.15); color:#22c55e; }
.warn { background: rgba(234,179,8,0.15); color:#eab308; }
.err { background: rgba(220,38,38,0.15); color:#dc2626; }
</style>

<span class="account-status status-active">Active</span>
<span id="watcher-123" class="mini-badge warn">Unknown</span>
```

#### ✅ AFTER (use existing .watcher-chip)
```html
<!-- Remove ALL custom badge styles -->

<span class="watcher-chip active">Active</span>
<span id="watcher-{{ account.id }}" class="watcher-chip unknown">Unknown</span>
```

**Changes**:
- Remove `.account-status`, `.status-active`, `.status-inactive`
- Remove `.mini-badge`, `.ok`, `.warn`, `.err`
- Use existing `.watcher-chip` class (already in main.css lines 1312-1315)
- Use state classes: `.active`, `.stopped`, `.unknown`

---

### 5. Panel/Section Pattern

#### ❌ BEFORE (custom wrapper)
```html
<div class="accounts-header">
    <div class="d-flex justify-content-between">
        <h2>Title</h2>
        <div>Actions</div>
    </div>
</div>
```

#### ✅ AFTER (watchers pattern)
```html
<div class="panel">
    <div class="panel-header">
        <div class="panel-title">Title</div>
        <div class="panel-actions">
            <button class="btn-secondary btn-sm">Action</button>
        </div>
    </div>
    <div class="cards-grid">
        <!-- content -->
    </div>
</div>
```

**Changes**:
- Use `.panel` wrapper (already in main.css lines 1367-1372)
- Use `.panel-header` for header section (lines 1374-1381)
- Use `.panel-title` for heading (lines 1383-1387)
- Use `.panel-actions` for action buttons (lines 1389-1393)

---

### 6. Modal Pattern

#### ❌ BEFORE (accounts.html lines 229-303)
```html
<div class="modal-content" style="background:#1a1a1a;border:1px solid rgba(255,255,255,0.06);color:#fff;">
    <div class="modal-header" style="border-bottom:1px solid rgba(255,255,255,0.06);">
        <h5 class="modal-title">Edit Account</h5>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
    </div>
    <div class="modal-body">
        <!-- form fields -->
    </div>
    <div class="modal-footer" style="border-top:1px solid rgba(255,255,255,0.06);">
        <button class="btn btn-secondary">Close</button>
        <button class="btn btn-primary">Save</button>
    </div>
</div>
```

#### ✅ AFTER (remove inline styles, rely on main.css)
```html
<div class="modal-content">
    <div class="modal-header">
        <h5 class="modal-title"><i class="bi bi-pencil-square"></i> Edit Account</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
    </div>
    <div class="modal-body">
        <!-- form fields -->
    </div>
    <div class="modal-footer">
        <button class="btn-secondary" data-bs-dismiss="modal">Close</button>
        <button class="btn-primary-modern" onclick="saveAccountEdit()">Save Changes</button>
    </div>
</div>
```

**Changes**:
- Remove ALL inline `style` attributes
- Remove `.btn-close-white` (main.css handles this automatically)
- Use `.btn-secondary` and `.btn-primary-modern` for footer buttons
- Modal styling already handled by main.css lines 152-194

---

### 7. Table Pattern

#### ❌ BEFORE (accounts.html line 458)
```html
<table class="table table-dark table-hover">
    <thead>
        <tr><th>UID</th><th>Subject</th><th></th></tr>
    </thead>
    <tbody>
        <!-- rows -->
    </tbody>
</table>
```

#### ✅ AFTER (use .table-modern wrapper)
```html
<div class="table-modern">
    <table class="table">
        <thead>
            <tr><th>UID</th><th>Subject</th><th></th></tr>
        </thead>
        <tbody>
            <!-- rows -->
        </tbody>
    </table>
</div>
```

**Changes**:
- Wrap table with `.table-modern` div
- Remove `.table-dark` and `.table-hover` classes
- Keep only `.table` class
- Styling handled by main.css lines 80-147

---

## Component Patterns

### Complete Button Reference

```html
<!-- PRIMARY ACTIONS (brand gradient) -->
<button class="btn-primary-modern">Save</button>
<button class="btn-primary-modern btn-sm">Save</button>

<!-- SECONDARY ACTIONS (neutral dark) -->
<button class="btn-secondary">Action</button>
<button class="btn-secondary btn-sm">Action</button>

<!-- GHOST ACTIONS (transparent, subtle) -->
<button class="btn-ghost">Cancel</button>
<button class="btn-ghost btn-sm">Cancel</button>

<!-- DESTRUCTIVE ACTIONS (red) -->
<button class="btn-danger">Delete</button>
<button class="btn-danger btn-sm">Delete</button>

<!-- SUCCESS ACTIONS (green) -->
<button class="btn-success">Approve</button>
<button class="btn-success btn-sm">Approve</button>

<!-- WARNING ACTIONS (orange) -->
<button class="btn-warning">Caution</button>
<button class="btn-warning btn-sm">Caution</button>
```

**Button Sizing**:
- Default: 42px height
- `.btn-sm`: 34px height
- `.btn-lg`: 50px height

### Complete Badge/Chip Reference

```html
<!-- STATUS CHIPS (email status) -->
<span class="status-chip status-HELD">HELD</span>
<span class="status-chip status-PENDING">PENDING</span>
<span class="status-chip status-RELEASED">RELEASED</span>
<span class="status-chip status-REJECTED">REJECTED</span>

<!-- WATCHER CHIPS (service status) -->
<span class="watcher-chip active">Active</span>
<span class="watcher-chip stopped">Stopped</span>
<span class="watcher-chip unknown">Unknown</span>

<!-- GENERIC BADGES -->
<span class="badge">Default</span>
<span class="badge-soft-success">Success</span>
<span class="badge-soft-danger">Danger</span>
<span class="badge-soft-muted">Muted</span>
```

### Complete Card Reference

```html
<!-- STAT CARD (for metrics/overview) -->
<div class="stat-card-modern">
    <div class="stat-label">LABEL</div>
    <div class="stat-value">123</div>
    <div class="stat-delta">Additional info</div>
    <div class="panel-actions">
        <button class="btn-ghost btn-sm">Action</button>
    </div>
</div>

<!-- PANEL (for sections with header) -->
<div class="panel">
    <div class="panel-header">
        <div class="panel-title">Section Title</div>
        <div class="panel-actions">
            <button class="btn-secondary btn-sm">Action</button>
        </div>
    </div>
    <div style="padding:20px">
        <!-- content -->
    </div>
</div>

<!-- CARDS GRID (responsive grid layout) -->
<div class="cards-grid">
    <div class="stat-card-modern">Card 1</div>
    <div class="stat-card-modern">Card 2</div>
    <div class="stat-card-modern">Card 3</div>
</div>
```

---

## Implementation Checklist

### For Each Template File:

#### Step 1: Remove Custom CSS
- [ ] Delete entire `{% block extra_css %}<style>...</style>{% endblock %}` section
- [ ] If any styles are truly unique, move to main.css with proper naming

#### Step 2: Update Page Header
- [ ] Replace custom header wrapper with flex layout
- [ ] Standardize heading to `<h1 style="font-size:1.4rem">`
- [ ] Add icon to heading
- [ ] Replace button classes with `.btn-secondary .btn-sm` or `.btn-ghost .btn-sm`
- [ ] Use `gap:.5rem` for button spacing

#### Step 3: Update Card Grids
- [ ] Replace custom grid class with `.cards-grid`
- [ ] Replace custom card class with `.stat-card-modern`
- [ ] Use `.stat-label`, `.stat-value`, `.stat-delta` for content structure
- [ ] Use `.panel-actions` for action buttons

#### Step 4: Update Buttons
- [ ] Replace ALL custom button classes
- [ ] Use only: `.btn-primary-modern`, `.btn-secondary`, `.btn-ghost`, `.btn-danger`, `.btn-success`, `.btn-warning`
- [ ] Add `.btn-sm` for compact buttons
- [ ] Ensure all buttons have icons

#### Step 5: Update Status Badges
- [ ] Replace custom badge classes with `.watcher-chip` or `.status-chip`
- [ ] Use state classes: `.active`, `.stopped`, `.unknown`
- [ ] For email status: `.status-HELD`, `.status-PENDING`, etc.

#### Step 6: Update Modals
- [ ] Remove ALL inline styles from modal markup
- [ ] Remove `.btn-close-white` class
- [ ] Standardize footer buttons

#### Step 7: Update Tables
- [ ] Wrap all tables with `<div class="table-modern">`
- [ ] Remove `.table-dark`, `.table-hover`, `.table-striped`
- [ ] Keep only `.table` class

#### Step 8: Test Responsiveness
- [ ] Test at 1920px, 1200px, 768px, 375px widths
- [ ] Verify cards wrap properly
- [ ] Verify buttons stack on mobile
- [ ] Verify no horizontal scroll

---

## CSS Token Migration Priority

### High Priority (Do First)
1. **Surface colors**: Replace all `#1a1a1a`, `#1f1f1f`, `#242424` with tokens
2. **Border colors**: Replace all `rgba(255,255,255,0.06)` with `var(--border-subtle)`
3. **Text colors**: Replace all `#ffffff`, `#9ca3af`, `#e5e7eb` with tokens
4. **Gradients**: Replace all gradient definitions with `var(--gradient-surface)` or `var(--gradient-brand)`

### Medium Priority (Do Second)
1. **Spacing**: Replace hardcoded padding/margin with token variables
2. **Border radius**: Replace hardcoded radius with token variables
3. **Shadows**: Replace hardcoded shadows with token variables

### Low Priority (Do Last)
1. **Semantic colors**: Consolidate success/warning/danger color definitions
2. **Animation values**: Extract to tokens if patterns emerge

---

## File-by-File Rollout Plan

### Phase 1: Proof of Concept
1. ✅ `templates/watchers.html` - Already the reference
2. 🔄 `templates/accounts.html` - Lead migration example
3. 🔄 `static/css/main.css` - Add CSS tokens

### Phase 2: High-Traffic Pages
4. `templates/dashboard_interception.html` - Minor updates
5. `templates/emails-unified.html` - Button standardization
6. `templates/compose.html` - Form and button updates

### Phase 3: Admin Pages
7. `templates/settings.html` - Panel header updates
8. `templates/rules.html` - Card and button updates
9. `templates/diagnostics.html` - Table and card updates

### Phase 4: Supporting Pages
10. `templates/styleguide.html` - Complete refresh with new tokens
11. `templates/base.html` - Footer logout bar update
12. Any remaining templates

---

## Quick Reference: Class Mapping

| Old Class | New Class | Notes |
|-----------|-----------|-------|
| `.accounts-header` | `.panel` + `.panel-header` | Use panel pattern |
| `.account-card` | `.stat-card-modern` | Already exists |
| `.account-title` | `.stat-label` | Already exists |
| `.account-status` | `.watcher-chip` | Use state classes |
| `.account-actions` | `.panel-actions` | Already exists |
| `.btn-small` | `.btn-sm` | Already exists |
| `.btn-modern` | Remove | Not needed |
| `.btn-primary-modern` | Keep | Primary actions |
| `.btn-success-modern` | `.btn-success` | Use standard |
| `.btn-info-modern` | `.btn-secondary` | Consolidate |
| `.mini-badge` | `.watcher-chip` | Already exists |
| `.ok` | `.watcher-chip.active` | Use state class |
| `.warn` | `.watcher-chip.unknown` | Use state class |
| `.err` | `.watcher-chip.stopped` | Use state class |

---

## Testing Checklist

After each template migration:

- [ ] Visual inspection matches watchers.html aesthetic
- [ ] All buttons are 42px (default) or 34px (.btn-sm)
- [ ] All cards have consistent shadows and borders
- [ ] All text uses correct color hierarchy (white → gray → muted)
- [ ] Hover states work on all interactive elements
- [ ] No console errors
- [ ] No inline styles remain (except minimal layout)
- [ ] Responsive behavior works at all breakpoints
- [ ] Toast notifications work
- [ ] Modal styling is consistent
- [ ] Forms are readable and accessible

---

## Success Criteria

✅ **Zero custom CSS** in template files (except truly unique cases)  
✅ **Consistent button heights** across all pages (42px / 34px)  
✅ **Unified card styling** using `.stat-card-modern` and `.panel`  
✅ **Token-based colors** throughout main.css  
✅ **No hardcoded colors** in templates  
✅ **Responsive grid layouts** using `.cards-grid`  
✅ **Accessible color contrast** (4.5:1 minimum)  
✅ **Updated styleguide** documenting all patterns  

---

**Next Step**: Review this playbook, then proceed with `templates/accounts.html` migration as proof of concept.