(() => {
  const $q = document.getElementById('q');
  const $res = document.getElementById('results');
  const $fN = document.getElementById('f-noun');
  const $fV = document.getElementById('f-verb');
  const $fA = document.getElementById('f-adj');
  const $fD = document.getElementById('f-adv');

  const idx = new FlexSearch.Document({
    document: {
      id: 'id',
      index: ['l', 'p', 't'],
      store: ['l', 'p', 't']
    }
  });

  let store = new Map();

  function render(items) {
    if (!items || !items.length) {
      $res.innerHTML = '<p>No results.</p>';
      return;
    }
    const html = items.slice(0, 100).map(it => {
      const lemma = it.l;
      const pos = it.p || '';
      const trs = (it.t || []).join(', ');
      return `<details open><summary><strong>${lemma}</strong>${pos ? ` <small>(${pos})</small>` : ''}</summary><p>${trs || ''}</p></details>`;
    }).join('');
    $res.innerHTML = html;
  }

  function currentPosFilter() {
    const need = new Set();
    if ($fN.checked) need.add('noun');
    if ($fV.checked) need.add('verb');
    if ($fA.checked) need.add('adjective');
    if ($fD.checked) need.add('adverb');
    return need;
  }

  async function load() {
    const resp = await fetch('data/index.json');
    const data = await resp.json();
    data.forEach((rec, i) => {
      const id = i + 1;
      const doc = { id, l: rec.l, p: rec.p || '', t: (rec.t || []).join(' ') };
      store.set(id, rec);
      idx.add(doc);
    });
    render(data.slice(0, 50));
  }

  function search() {
    const q = ($q.value || '').trim();
    const posFilter = currentPosFilter();
    if (!q) {
      const all = Array.from(store.values());
      const filtered = posFilter.size ? all.filter(r => posFilter.has(r.p)) : all;
      render(filtered.slice(0, 200));
      return;
    }
    const results = idx.search(q, { enrich: true });
    const ids = new Set();
    results.forEach(group => {
      (group.result || []).forEach(r => ids.add(r.id));
    });
    let items = Array.from(ids).map(id => store.get(id)).filter(Boolean);
    if (posFilter.size) items = items.filter(r => posFilter.has(r.p));
    render(items);
  }

  $q.addEventListener('input', search);
  [$fN,$fV,$fA,$fD].forEach(cb => cb.addEventListener('change', search));
  load();
})();


