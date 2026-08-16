// Generic discography renderer.
// Each performer page sets window.DISCOGRAPHY_CONFIG = { dataUrl: '../data/xxx.json' }
// before loading this script.

(async function () {
  const cfg = window.DISCOGRAPHY_CONFIG;
  if (!cfg || !cfg.dataUrl) {
    console.error('DISCOGRAPHY_CONFIG.dataUrl is required');
    return;
  }

  const listEl = document.getElementById('list');
  const countEl = document.getElementById('count');
  const fComposer = document.getElementById('f-composer');
  const fLabel = document.getElementById('f-label');
  const fLive = document.getElementById('f-live');
  const fSort = document.getElementById('f-sort');
  const fSearch = document.getElementById('f-search');

  let DATA = [];
  try {
    const res = await fetch(cfg.dataUrl);
    DATA = await res.json();
  } catch (err) {
    listEl.innerHTML = '<div class="empty">Could not load discography data.</div>';
    console.error(err);
    return;
  }

  function unique(arr) { return [...new Set(arr)].sort((a, b) => a.localeCompare(b, 'en')); }

  unique(DATA.map(d => d.composer)).forEach(c => {
    const o = document.createElement('option'); o.value = c; o.textContent = c;
    fComposer.appendChild(o);
  });
  unique(DATA.flatMap(d => d.labels)).forEach(l => {
    const o = document.createElement('option'); o.value = l; o.textContent = l;
    fLabel.appendChild(o);
  });

  function peopleStr(people) {
    return people.map(p => p.role ? `${p.name}(${p.role})` : p.name).join(', ');
  }

  const menuToggle = document.getElementById('menu-toggle');
  const toolbarFields = document.getElementById('toolbar-fields');
  if (menuToggle && toolbarFields) {
    menuToggle.addEventListener('click', () => {
      const isOpen = toolbarFields.classList.toggle('open');
      menuToggle.setAttribute('aria-expanded', String(isOpen));
      menuToggle.textContent = isOpen ? '\u2715 Close filters' : '\u2630 Filters';
    });
  }

  function render() {
    const c = fComposer.value;
    const l = fLabel.value;
    const live = fLive.value;
    const q = fSearch.value.trim().toLowerCase();
    const sortMode = fSort.value;

    const filtered = DATA.filter(d => {
      if (c && d.composer !== c) return false;
      if (l && !d.labels.includes(l)) return false;
      if (live === 'live' && !d.is_live) return false;
      if (live === 'studio' && d.is_live) return false;
      if (q) {
        const hay = [d.composer, d.work, peopleStr(d.accompanists), d.orchestra, d.notes, d.location]
          .filter(Boolean).join(' ').toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });

    countEl.textContent = `${filtered.length} recordings`;

    if (filtered.length === 0) {
      listEl.innerHTML = '<div class="empty">No recordings match these filters</div>';
      return;
    }

    listEl.innerHTML = '';

    function renderRecLine(d) {
      const row = document.createElement('div');
      row.className = 'rec-row';
      const labelStr = d.labels.join(' / ');
      const labelWithNotes = [labelStr, (d.notes && !d.is_live) ? d.notes : null]
        .filter(Boolean).join(' · ');
      row.innerHTML = `
        <div class="cell cell-date"><span class="cell-label">Date</span>${d.date_display ?? 'undated'}</div>
        <div class="cell cell-type"><span class="cell-label">Type</span>${d.is_live ? '<span class="live-mark">LIVE</span>' : ''}</div>
        <div class="cell cell-performers"><span class="cell-label">Accompanists</span><span class="people">${peopleStr(d.accompanists) || '(unaccompanied)'}</span>${d.orchestra ? `, <span class="orch">${d.orchestra}</span>` : ''}</div>
        <div class="cell cell-location"><span class="cell-label">Location</span>${d.location ?? ''}</div>
        <div class="cell cell-labelcol"><span class="cell-label">Label</span>${labelWithNotes}</div>
      `;
      return row;
    }

    function renderWorkGroup(g, showComposerInTitle) {
      const wrap = document.createElement('div');
      wrap.className = 'work-group';

      const titleRow = document.createElement('div');
      titleRow.className = 'work-title-row';
      const countBadge = g.recs.length > 1
        ? `<span class="work-count multi">${g.recs.length} recordings</span>`
        : `<span class="work-count">${g.recs.length}</span>`;
      titleRow.innerHTML = (showComposerInTitle
        ? `<span class="work-title">${g.composer} — ${g.work}</span>`
        : `<span class="work-title">${g.work}</span>`) + countBadge;
      wrap.appendChild(titleRow);

      g.recs.forEach(d => wrap.appendChild(renderRecLine(d)));
      return wrap;
    }

    // Generic collapsed-by-default accordion section, reused for both the
    // composer view and the recording-date (by year) view.
    function appendAccordionSection(labelText, buildSectionContents) {
      const head = document.createElement('button');
      head.type = 'button';
      head.className = 'composer-head';
      head.setAttribute('aria-expanded', 'false');
      head.innerHTML = `<span>${labelText}</span><span class="composer-arrow" aria-hidden="true">&#9662;</span>`;

      const section = document.createElement('div');
      section.className = 'composer-section';
      buildSectionContents(section);

      head.addEventListener('click', () => {
        const isOpen = section.classList.toggle('open');
        head.classList.toggle('expanded', isOpen);
        head.setAttribute('aria-expanded', String(isOpen));
      });

      listEl.appendChild(head);
      listEl.appendChild(section);
    }

    function renderDateSession(s) {
      const wrap = document.createElement('div');
      wrap.className = 'date-session';
      const items = s.recs.map(d => `
        <li>
          ${d.is_live ? '<span class="live-mark">LIVE</span> ' : ''}<span class="ds-work">${d.composer} — ${d.work}</span>
          <span class="ds-acc"> — ${peopleStr(d.accompanists) || '(unaccompanied)'}${d.orchestra ? `, <span class="orch">${d.orchestra}</span>` : ''}</span>
        </li>`).join('');
      wrap.innerHTML = `
        <div class="ds-when">
          <div class="ds-date">${s.date_display ?? 'undated'}</div>
          ${s.location ? `<div class="ds-loc">${s.location}</div>` : ''}
        </div>
        <ul class="ds-list">${items}</ul>
      `;
      return wrap;
    }

    if (sortMode === 'date') {
      // Accordion by year; within a year, recordings sharing the exact
      // same date and location are grouped into one session entry.
      const byYear = new Map();
      filtered.forEach(d => {
        const key = d.date_sort.startsWith('9999') ? 'Undated' : d.date_sort.slice(0, 4);
        if (!byYear.has(key)) byYear.set(key, []);
        byYear.get(key).push(d);
      });

      const yearKeys = [...byYear.keys()].sort((a, b) => {
        if (a === 'Undated') return 1;
        if (b === 'Undated') return -1;
        return a.localeCompare(b);
      });

      yearKeys.forEach(year => {
        const records = byYear.get(year);
        const sessions = new Map();
        records.forEach(d => {
          const key = (d.date_display ?? '\u0000') + '||' + (d.location ?? '');
          if (!sessions.has(key)) {
            sessions.set(key, { date_display: d.date_display, location: d.location, sortKey: d.date_sort, recs: [] });
          }
          sessions.get(key).recs.push(d);
        });
        const sessionList = [...sessions.values()].sort((a, b) => a.sortKey.localeCompare(b.sortKey));

        appendAccordionSection(year, (section) => {
          sessionList.forEach(s => section.appendChild(renderDateSession(s)));
        });
      });
      return;
    }

    const groups = new Map();
    filtered.forEach(d => {
      const key = d.composer + '|' + d.work;
      if (!groups.has(key)) groups.set(key, { composer: d.composer, work: d.work, recs: [] });
      groups.get(key).recs.push(d);
    });
    groups.forEach(g => g.recs.sort((a, b) => a.date_sort.localeCompare(b.date_sort)));

    let groupList = [...groups.values()];

    if (sortMode === 'count') {
      groupList.sort((a, b) => b.recs.length - a.recs.length || a.composer.localeCompare(b.composer, 'en'));
      groupList.forEach(g => listEl.appendChild(renderWorkGroup(g, true)));
      return;
    }

    // sortMode === 'composer': collapsed accordion, one section per composer.
    groupList.sort((a, b) => a.composer.localeCompare(b.composer, 'en') || a.work.localeCompare(b.work, 'en'));

    const byComposer = new Map();
    groupList.forEach(g => {
      if (!byComposer.has(g.composer)) byComposer.set(g.composer, []);
      byComposer.get(g.composer).push(g);
    });

    byComposer.forEach((works, composer) => {
      appendAccordionSection(composer, (section) => {
        works.forEach(g => section.appendChild(renderWorkGroup(g, false)));
      });
    });
  }

  [fComposer, fLabel, fLive, fSort].forEach(el => el.addEventListener('change', render));
  fSearch.addEventListener('input', render);

  render();
})();
