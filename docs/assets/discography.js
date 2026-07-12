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

  function render() {
    const c = fComposer.value;
    const l = fLabel.value;
    const live = fLive.value;
    const q = fSearch.value.trim().toLowerCase();

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

    const groups = new Map();
    filtered.forEach(d => {
      const key = d.composer + '|' + d.work;
      if (!groups.has(key)) groups.set(key, { composer: d.composer, work: d.work, recs: [] });
      groups.get(key).recs.push(d);
    });
    groups.forEach(g => g.recs.sort((a, b) => a.date_sort.localeCompare(b.date_sort)));

    let groupList = [...groups.values()];

    if (fSort.value === 'count') {
      groupList.sort((a, b) => b.recs.length - a.recs.length || a.composer.localeCompare(b.composer, 'en'));
    } else {
      groupList.sort((a, b) => a.composer.localeCompare(b.composer, 'en') || a.work.localeCompare(b.work, 'en'));
    }

    listEl.innerHTML = '';
    let lastComposer = null;

    groupList.forEach(g => {
      if (fSort.value === 'composer' && g.composer !== lastComposer) {
        const h = document.createElement('div');
        h.className = 'composer-head';
        h.textContent = g.composer;
        listEl.appendChild(h);
        lastComposer = g.composer;
      }

      const wrap = document.createElement('div');
      wrap.className = 'work-group';

      const titleRow = document.createElement('div');
      titleRow.className = 'work-title-row';
      const countBadge = g.recs.length > 1
        ? `<span class="work-count multi">${g.recs.length} recordings</span>`
        : `<span class="work-count">${g.recs.length}</span>`;
      titleRow.innerHTML = (fSort.value === 'count'
        ? `<span class="work-title">${g.composer} — ${g.work}</span>`
        : `<span class="work-title">${g.work}</span>`) + countBadge;
      wrap.appendChild(titleRow);

      g.recs.forEach(d => {
        const line = document.createElement('div');
        line.className = 'rec-line';
        const labelStr = d.labels.join(' / ');
        line.innerHTML = `
          <div class="rec-top">${d.is_live ? '<span class="live-mark">LIVE</span>' : ''}<span class="date">${d.date_display ?? 'undated'}</span>${d.location ? `<span class="loc-sep">|</span><span class="loc">${d.location}</span>` : ''}</div>
          <div class="rec-detail">
            <span class="people">${peopleStr(d.accompanists) || '(unaccompanied)'}</span>${d.orchestra ? `, <span class="orch">${d.orchestra}</span>` : ''}
            ${labelStr ? `<span class="label"> | ${labelStr}</span>` : ''}
            ${d.notes && !d.is_live ? `<span class="label"> | ${d.notes}</span>` : ''}
          </div>
        `;
        wrap.appendChild(line);
      });

      listEl.appendChild(wrap);
    });
  }

  [fComposer, fLabel, fLive, fSort].forEach(el => el.addEventListener('change', render));
  fSearch.addEventListener('input', render);

  render();
})();
