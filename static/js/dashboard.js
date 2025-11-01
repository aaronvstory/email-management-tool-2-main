// static/js/dashboard.js
(() => {
  const state = {
    items: [],
    filter: 'ALL',
    search: ''
  };

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  function setLoading(on) {
    const sp = $('#dashboardLoadingSpinner');
    if (sp) sp.style.display = on ? 'block' : 'none';
  }
  function setEmpty(on, msg='No emails found', hint='') {
    const es = $('#dashboardEmptyState');
    if (es) es.style.display = on ? 'block' : 'none';
    const em = $('#emptyStateMessage');
    if (em) em.textContent = msg;
    const eh = $('#emptyStateHint');
    if (eh) eh.textContent = hint;
  }
  function setBulkBar() {
    const bar = $('#bulk-actions-bar');
    if (!bar) return;
    const count = $$('#dashboardEmailTableBody input[type=checkbox]:checked').length;
    $('#bulk-selection-count').textContent = `${count} selected`;
    bar.style.display = count ? 'block' : 'none';
  }

  function matchesFilter(item) {
    const f = state.filter;
    const s = state.search.trim().toLowerCase();
    const st = (item.status || item.moderation_status || 'ALL').toUpperCase();
    const hay = [
      item.subject, item.from, item.to, item.cc, item.snippet, item.preview
    ].filter(Boolean).join(' ').toLowerCase();
    const filterOk = (f === 'ALL') || (st === f);
    const searchOk = !s || hay.includes(s);
    return filterOk && searchOk;
  }

  function renderSkeleton() {
    const tbody = $('#dashboardEmailTableBody');
    if (!tbody) return;
    // Show 5 skeleton rows while loading
    const skeletonRows = Array.from({length: 5}, () => `
      <tr class="email-skeleton-row">
        <td><div class="skeleton-box" style="width:16px;height:16px;"></div></td>
        <td><div class="skeleton-box" style="width:120px;height:14px;"></div></td>
        <td><div class="skeleton-box" style="width:200px;height:14px;"></div></td>
        <td><div class="skeleton-box" style="width:300px;height:14px;"></div></td>
        <td><div class="skeleton-box" style="width:80px;height:14px;"></div></td>
        <td><div class="skeleton-box" style="width:60px;height:32px;border-radius:var(--radius-md);"></div></td>
      </tr>
    `).join('');
    tbody.innerHTML = skeletonRows;
  }

  function render(items) {
    const tbody = $('#dashboardEmailTableBody');
    if (!tbody) return;
    const rows = items.map(x => {
      const id = x.id || x.uuid || x.message_id || '';
      const when = x.received_at || x.date || '';
      const who  = `${x.from || ''} → ${x.to || ''}`;
      const subj = x.subject || '(no subject)';
      const st   = (x.status || x.moderation_status || '').toUpperCase();
      return `
        <tr>
          <td><input type="checkbox" data-id="${id}" /></td>
          <td>${when}</td>
          <td>${who}</td>
          <td>${subj}</td>
          <td>${st}</td>
          <td>
            <a class="btn btn-sm btn-secondary" href="/email/${id}">Open</a>
          </td>
        </tr>`;
    }).join('');

    tbody.innerHTML = rows || `<tr><td colspan="6" style="opacity:.7">No items</td></tr>`;
    setBulkBar();
  }

  async function fetchFirstGood(...urls) {
    for (const u of urls) {
      try {
        const r = await fetch(u, { credentials:'same-origin' });
        if (!r.ok) continue;
        const j = await r.json();
        const items = Array.isArray(j?.items) ? j.items : (Array.isArray(j) ? j : null);
        if (items) return items;
      } catch {}
    }
    return null;
  }

  function getEmptyStateMessage() {
    const hasSearch = state.search.trim();
    const filterMessages = {
      'ALL': hasSearch ? 'No emails match your search' : 'No emails found',
      'HELD': hasSearch ? 'No held emails match your search' : 'No emails are currently held for moderation',
      'RELEASED': hasSearch ? 'No released emails match your search' : 'No emails have been released yet',
      'DISCARDED': hasSearch ? 'No discarded emails match your search' : 'No emails have been discarded',
      'PENDING': hasSearch ? 'No pending emails match your search' : 'No emails are pending moderation'
    };
    return filterMessages[state.filter] || filterMessages['ALL'];
  }

  async function loadDashboardEmails() {
    try {
      renderSkeleton(); // Show skeleton immediately
      setEmpty(false);
      // Try several likely endpoints; keep whichever exists in your app.
      const items = await fetchFirstGood(
        '/api/emails/recent?limit=50',
        '/api/emails/unified?limit=50',
        '/api/emails?limit=50'
      );
      state.items = Array.isArray(items) ? items : [];
      const filtered = state.items.filter(matchesFilter);
      render(filtered); // Replace skeleton with real data
      setEmpty(filtered.length === 0, getEmptyStateMessage());
    } catch (err) {
      console.error('loadDashboardEmails failed', err);
      setEmpty(true, 'Could not load emails', 'See console for details.');
    }
  }

  function performEmailSearch() {
    const box = $('#email-search-input') || $('#dashboardSearchBox');
    state.search = box ? box.value : '';
    const filtered = state.items.filter(matchesFilter);
    render(filtered);
    setEmpty(filtered.length === 0, getEmptyStateMessage());

    // Show/hide clear button with smooth transition
    const clearBtn = $('#email-search-clear');
    if (clearBtn) {
      clearBtn.style.display = state.search ? 'inline-block' : 'none';
      clearBtn.style.opacity = state.search ? '1' : '0';
    }
  }

  function clearEmailSearch() {
    const box = $('#email-search-input') || $('#dashboardSearchBox');
    if (box) box.value = '';
    state.search = '';
    performEmailSearch();
  }

  function switchDashboardFilter(val) {
    state.filter = val;
    $$('.status-tab').forEach(el => el.classList.toggle('active', el.dataset.status === val));
    const filtered = state.items.filter(matchesFilter);
    render(filtered);
    setEmpty(filtered.length === 0, getEmptyStateMessage());
  }

  function filterDashboardEmails() {
    const box = $('#dashboardSearchBox');
    state.search = box ? box.value : '';
    const filtered = state.items.filter(matchesFilter);
    render(filtered);
    setEmpty(filtered.length === 0, getEmptyStateMessage());
  }

  function toggleDashboardAutoRefresh(on) {
    if (on) {
      state._timer = setInterval(loadDashboardEmails, 15000);
    } else {
      clearInterval(state._timer);
      state._timer = null;
    }
  }

  // Keyboard shortcuts for better UX
  function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
      // Don't interfere if user is typing in an input
      if (e.target.matches('input, textarea, select')) return;

      switch(e.key) {
        case 'Escape':
          // Clear search
          clearEmailSearch();
          break;

        case 'Enter':
          // Open first checked email
          const checked = document.querySelector('#dashboardEmailTableBody input[type=checkbox]:checked');
          if (checked) {
            const emailId = checked.dataset.id;
            if (emailId) window.location.href = `/email/${emailId}`;
          }
          break;

        case 'ArrowDown':
        case 'ArrowUp':
          // Navigate table rows with arrow keys
          e.preventDefault();
          const rows = Array.from(document.querySelectorAll('#dashboardEmailTableBody tr'));
          const currentChecked = document.querySelector('#dashboardEmailTableBody input[type=checkbox]:checked');

          if (rows.length === 0) return;

          let currentIndex = currentChecked
            ? rows.findIndex(r => r.querySelector('input[type=checkbox]') === currentChecked)
            : -1;

          let newIndex;
          if (e.key === 'ArrowDown') {
            newIndex = currentIndex < rows.length - 1 ? currentIndex + 1 : 0;
          } else {
            newIndex = currentIndex > 0 ? currentIndex - 1 : rows.length - 1;
          }

          // Uncheck all and check new row
          document.querySelectorAll('#dashboardEmailTableBody input[type=checkbox]').forEach(cb => cb.checked = false);
          const newCheckbox = rows[newIndex]?.querySelector('input[type=checkbox]');
          if (newCheckbox) {
            newCheckbox.checked = true;
            newCheckbox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }
          setBulkBar();
          break;
      }
    });
  }

  // Expose for your inline onclicks
  window.loadDashboardEmails = loadDashboardEmails;
  window.performEmailSearch = performEmailSearch;
  window.clearEmailSearch = clearEmailSearch;
  window.switchDashboardFilter = switchDashboardFilter;
  window.filterDashboardEmails = filterDashboardEmails;
  window.toggleDashboardAutoRefresh = toggleDashboardAutoRefresh;

  // Auto-boot if the table exists
  document.addEventListener('DOMContentLoaded', () => {
    const tbody = document.getElementById('dashboardEmailTableBody');
    if (tbody) {
      loadDashboardEmails();
      setupKeyboardShortcuts();
    }
  });
})();
