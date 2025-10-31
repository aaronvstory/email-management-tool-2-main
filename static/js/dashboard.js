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
            <a class="btn btn-sm btn-secondary" href="/emails/${id}">Open</a>
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

  async function loadDashboardEmails() {
    try {
      setLoading(true);
      setEmpty(false);
      // Try several likely endpoints; keep whichever exists in your app.
      const items = await fetchFirstGood(
        '/api/emails/recent?limit=50',
        '/api/emails/unified?limit=50',
        '/api/emails?limit=50'
      );
      state.items = Array.isArray(items) ? items : [];
      const filtered = state.items.filter(matchesFilter);
      render(filtered);
      setEmpty(filtered.length === 0, 'No emails match your filters');
    } catch (err) {
      console.error('loadDashboardEmails failed', err);
      setEmpty(true, 'Could not load emails', 'See console for details.');
    } finally {
      setLoading(false);
    }
  }

  function performEmailSearch() {
    const box = $('#email-search-input') || $('#dashboardSearchBox');
    state.search = box ? box.value : '';
    const filtered = state.items.filter(matchesFilter);
    render(filtered);
    $('#email-search-clear')?.style && ( $('#email-search-clear').style.display = state.search ? 'inline-block' : 'none' );
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
  }

  function filterDashboardEmails() {
    const box = $('#dashboardSearchBox');
    state.search = box ? box.value : '';
    const filtered = state.items.filter(matchesFilter);
    render(filtered);
  }

  function toggleDashboardAutoRefresh(on) {
    if (on) {
      state._timer = setInterval(loadDashboardEmails, 15000);
    } else {
      clearInterval(state._timer);
      state._timer = null;
    }
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
    if (document.getElementById('dashboardEmailTableBody')) {
      loadDashboardEmails();
    }
  });
})();
