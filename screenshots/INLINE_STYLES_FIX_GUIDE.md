# Inline Styles Fix Guide

Quick reference for replacing inline styles with CSS classes in Email Management Tool templates.

## Step 1: Add Utility Classes to main.css

Add these utility classes to `static/css/main.css` (after line 1600):

```css
/* ============================================================
   UTILITY CLASSES - Replace inline styles
   ============================================================ */

/* Text Size & Opacity Utilities */
.text-xs {
    font-size: 0.65rem;
}

.text-xs-muted {
    font-size: 0.65rem;
    opacity: 0.75;
}

.text-sm {
    font-size: 0.85rem;
}

.text-sm-muted {
    color: var(--text-muted);
    font-size: 0.9rem;
}

/* Flex Layout Utilities */
.flex-row {
    display: flex;
    align-items: center;
}

.flex-row-gap {
    display: flex;
    align-items: center;
    gap: 10px;
}

.flex-row-gap-sm {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.flex-between {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

/* Input Width Utilities */
.input-wide {
    min-width: 240px;
}

.input-medium {
    min-width: 140px;
}

/* Error & Status Message Utilities */
.error-message {
    font-size: 0.85rem;
    color: var(--danger-base);
    white-space: pre-wrap;
    word-break: break-word;
}

.status-message {
    font-size: 0.85rem;
    color: var(--text-muted);
}
```

## Step 2: Template Replacements

### base.html (2 instances)

**Line 53:**
```html
<!-- BEFORE -->
<span style="font-size:.65rem;opacity:.75;">{{ current_user.username }}</span>

<!-- AFTER -->
<span class="text-xs-muted">{{ current_user.username }}</span>
```

**Line 98:**
```html
<!-- BEFORE -->
<div style="display:flex;align-items:center;gap:10px;">

<!-- AFTER -->
<div class="flex-row-gap">
```

### accounts_simple.html (16 instances)

**Line 162:**
```html
<!-- BEFORE -->
<input id="accounts-search" class="input-modern" placeholder="Search accounts..." style="min-width:240px;" />

<!-- AFTER -->
<input id="accounts-search" class="input-modern input-wide" placeholder="Search accounts..." />
```

**Line 185:**
```html
<!-- BEFORE -->
<div style="display:flex;align-items:center;gap:10px;">

<!-- AFTER -->
<div class="flex-row-gap">
```

**Line 188:**
```html
<!-- BEFORE -->
<div style="color: #9ca3af; font-size: 0.9rem;">{{ account.email_address }}</div>

<!-- AFTER -->
<div class="text-sm-muted">{{ account.email_address }}</div>
```

**Line 190:**
```html
<!-- BEFORE -->
<div style="display:flex;align-items:center;gap:8px;">

<!-- AFTER -->
<div class="flex-row-gap-sm">
```

**Line 201, 209:**
```html
<!-- BEFORE -->
<div style="font-size: 0.85rem; color: #9ca3af;">

<!-- AFTER -->
<div class="status-message">
```

**Line 218:**
```html
<!-- BEFORE -->
<div style="font-size: 0.85rem; color: #dc3545; white-space: pre-wrap; word-break: break-word;">

<!-- AFTER -->
<div class="error-message">
```

### inbox.html (12 instances)

**Line 99:**
```html
<!-- BEFORE -->
<select id="statusFilter" class="input-modern" style="max-width:140px;">

<!-- AFTER -->
<select id="statusFilter" class="input-modern input-medium">
```

**Line 50:**
```html
<!-- BEFORE -->
<div style="display:flex; gap:.5rem;">

<!-- AFTER -->
<div class="flex-row-gap-sm">
```

**Line 72:**
```html
<!-- BEFORE -->
<div style="display: flex; gap: 10px; align-items: center;">

<!-- AFTER -->
<div class="flex-row-gap">
```

### emails_unified.html (24 instances)

Similar patterns to inbox.html - replace flex containers and text sizing.

### watchers.html (7 instances)

**Line 7:**
```html
<!-- BEFORE -->
<div class="d-flex" style="gap:.5rem">

<!-- AFTER -->
<div class="d-flex" style="gap: var(--space-xs);">
<!-- OR better: -->
<div class="flex-row-gap-sm">
```

**Line 55:**
```html
<!-- BEFORE -->
<div class="text-muted" style="font-size:.9rem">

<!-- AFTER -->
<div class="text-sm-muted">
```

## Step 3: Testing After Changes

After making replacements, test each page:

```bash
# 1. Clear browser cache (Ctrl+Shift+Delete)
# 2. Hard reload pages (Ctrl+F5)
# 3. Verify visual appearance unchanged
# 4. Check responsive behavior (resize window)
```

## Step 4: Verification Checklist

- [ ] All inline styles removed from base.html
- [ ] All inline styles removed from accounts_simple.html
- [ ] All inline styles removed from inbox.html
- [ ] All inline styles removed from emails_unified.html
- [ ] All inline styles removed from watchers.html
- [ ] Utility classes added to main.css
- [ ] Visual regression testing completed
- [ ] No layout breaks on mobile/tablet sizes
- [ ] Browser cache cleared during testing

## Benefits After Completion

1. **Maintainability:** All styles in one place (main.css)
2. **Consistency:** Same spacing/sizing across all pages
3. **Performance:** Smaller HTML files, better caching
4. **Accessibility:** Easier to implement dark/light theme toggle
5. **Developer Experience:** Faster development with reusable classes

## Estimated Time

- Add utility classes: 15 minutes
- Replace base.html: 5 minutes
- Replace accounts_simple.html: 20 minutes
- Replace inbox.html: 15 minutes
- Replace emails_unified.html: 25 minutes
- Replace watchers.html: 10 minutes
- Testing: 30 minutes

**Total: ~2 hours**

## Notes

- Don't replace inline styles in email_editor_modal.html (uses TinyMCE which requires specific inline styles)
- Don't replace inline styles in styleguide.html (demonstration purposes)
- Keep inline styles in interception_test_dashboard.html for now (test utilities, lower priority)
