
// Image error handling - hide broken images gracefully
document.querySelectorAll('.thesis-img').forEach(img => {
  img.addEventListener('error', function() {
    const fig = this.closest('figure');
    if (fig) {
      this.style.display = 'none';
      const fb = document.createElement('div');
      fb.className = 'img-missing';
      fb.textContent = '🖼 ' + (this.src.split('/').pop() || 'Image unavailable');
      fig.insertBefore(fb, this);
    }
  });
});

// Theme toggle
const themeBtn = document.getElementById('theme-toggle');
if (themeBtn) {
  themeBtn.addEventListener('click', () => {
    const isDark = document.documentElement.classList.toggle('dark');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    themeBtn.textContent = isDark ? '☀️' : '🌙';
  });
  // Set initial icon
  if (document.documentElement.classList.contains('dark')) {
    themeBtn.textContent = '☀️';
  }
}

// Mobile menu
const menuBtn = document.getElementById('menu-toggle');
const mobileMenu = document.getElementById('mobile-menu');
if (menuBtn && mobileMenu) {
  menuBtn.addEventListener('click', () => {
    mobileMenu.classList.toggle('hidden');
  });
}

// "More" dropdown
const moreBtn = document.getElementById('nav-more-btn');
const moreDropdown = document.getElementById('nav-more-dropdown');
if (moreBtn && moreDropdown) {
  moreBtn.addEventListener('click', e => {
    e.stopPropagation();
    moreDropdown.classList.toggle('open');
  });
  document.addEventListener('click', () => moreDropdown.classList.remove('open'));
}

// Search toggle
const searchToggle = document.getElementById('search-toggle');
const searchBar = document.getElementById('search-bar');
const searchInput = document.getElementById('search-input');
function openSearch() {
  if (searchBar) {
    searchBar.classList.remove('hidden');
    if (searchInput) searchInput.focus();
  }
}
function closeSearch() {
  if (searchBar) searchBar.classList.add('hidden');
}
if (searchToggle && searchBar) {
  searchToggle.addEventListener('click', () => {
    searchBar.classList.toggle('hidden');
    if (!searchBar.classList.contains('hidden') && searchInput) {
      searchInput.focus();
    }
  });
}

// Papers page filter
const filterInput = document.getElementById('paper-filter');
const papersGrid = document.getElementById('papers-grid');
const filterStats = document.getElementById('filter-stats');
if (filterInput && papersGrid) {
  filterInput.addEventListener('input', () => {
    const q = filterInput.value.toLowerCase().trim();
    const cards = papersGrid.querySelectorAll('.paper-card');
    let visible = 0;
    cards.forEach(card => {
      const title = card.dataset.title || '';
      const author = card.dataset.author || '';
      const year = card.dataset.year || '';
      const match = !q || title.includes(q) || author.includes(q) || year.includes(q);
      card.style.display = match ? '' : 'none';
      if (match) visible++;
    });
    if (filterStats) filterStats.textContent = `${visible} papers`;
  });
}

// Global search — uses window.SEARCH_INDEX set by search-index.js (works on file:// and http://)
(function() {
  const resultsDiv = document.getElementById('search-results');
  if (!searchInput || !resultsDiv) return;

  // Resolve a site-root-relative URL to an absolute path for the current page location
  function siteUrl(relUrl) {
    const p = window.location.pathname;
    const inSub = p.includes('/chapters/') || p.includes('/papers/');
    if (inSub) return '../' + relUrl;
    // Handle file:// — build relative to the directory of index.html
    return relUrl;
  }

  function renderResults(q) {
    if (!q) { resultsDiv.innerHTML = ''; return; }
    const index = window.SEARCH_INDEX;
    if (!index) {
      resultsDiv.innerHTML = '<div class="search-result-item"><div class="sri-meta">Search index unavailable.</div></div>';
      return;
    }
    const ql = q.toLowerCase();
    const matches = index.filter(item =>
      (item.title || '').toLowerCase().includes(ql) ||
      (item.text  || '').toLowerCase().includes(ql) ||
      (item.meta  || '').toLowerCase().includes(ql)
    );

    if (!matches.length) {
      resultsDiv.innerHTML = '<div class="search-result-item"><div class="sri-meta">No results found</div></div>';
      return;
    }

    // Group by type, up to 4 per group
    const groups = { chapter: [], paper: [], glossary: [] };
    for (const item of matches) {
      const g = groups[item.type];
      if (g && g.length < 4) g.push(item);
    }

    const typeLabels = { chapter: 'Chapters', paper: 'Papers', glossary: 'Glossary' };
    let out = '';
    for (const [type, items] of Object.entries(groups)) {
      if (!items.length) continue;
      out += `<div class="search-result-group">${typeLabels[type]}</div>`;
      out += items.map(item =>
        `<div class="search-result-item" onclick="window.location='${siteUrl(item.url)}'">
          <div class="sri-title">${escHtml((item.title || '').slice(0, 90))}</div>
          <div class="sri-meta">${escHtml((item.meta  || '').slice(0, 80))}</div>
        </div>`
      ).join('');
    }
    resultsDiv.innerHTML = out;
  }

  searchInput.addEventListener('input', () => renderResults(searchInput.value.trim()));

  document.addEventListener('click', e => {
    if (!searchBar?.contains(e.target) && !searchToggle?.contains(e.target)) {
      searchBar?.classList.add('hidden');
      resultsDiv.innerHTML = '';
    }
  });
})();

// Active TOC highlighting
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    const id = entry.target.id;
    const link = document.querySelector(`.toc-list a[href="#${id}"]`);
    if (link) {
      link.style.color = entry.isIntersecting ? 'var(--accent)' : '';
      link.style.borderColor = entry.isIntersecting ? 'var(--accent)' : 'transparent';
    }
  });
}, { rootMargin: '-20% 0px -70% 0px' });

document.querySelectorAll('h2[id], h3[id], h4[id]').forEach(h => observer.observe(h));

// ── Reading Progress Bar ──────────────────────────────────────────────
const progressBar = document.getElementById('reading-progress');
if (progressBar) {
  window.addEventListener('scroll', () => {
    const doc = document.documentElement;
    const scrollTop = doc.scrollTop || document.body.scrollTop;
    const scrollHeight = doc.scrollHeight - doc.clientHeight;
    progressBar.style.width = scrollHeight > 0 ? (scrollTop / scrollHeight * 100).toFixed(2) + '%' : '0%';
  }, { passive: true });
}

// ── Shared helpers ────────────────────────────────────────────────────
function escHtml(str) {
  const d = document.createElement('div');
  d.appendChild(document.createTextNode(str || ''));
  return d.innerHTML;
}
function termSlug(t) {
  return t.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}
function getRootPath() {
  const p = window.location.pathname;
  return (p.includes('/chapters/') || p.includes('/papers/')) ? '../' : '';
}

// ── Citation Hover Cards ──────────────────────────────────────────────
(function() {
  const meta = window.PAPERS_META;
  if (!meta) return;

  const card = document.createElement('div');
  card.className = 'cite-card';
  document.body.appendChild(card);
  let citeTimer;

  // Keep card alive while mouse is over it
  card.addEventListener('mouseenter', () => clearTimeout(citeTimer));
  card.addEventListener('mouseleave', () => {
    citeTimer = setTimeout(() => card.classList.remove('visible'), 200);
  });

  function positionCard(card, el, maxW) {
    const rect = el.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    let left = rect.left;
    // Use viewport-relative top since card is position:fixed
    let top = rect.bottom + 6;
    if (left + maxW > vw - 8) left = Math.max(8, vw - maxW - 8);
    if (left < 8) left = 8;
    // Flip above if would go off-screen bottom
    if (top + 180 > vh) top = rect.top - 180 - 6;
    card.style.left = left + 'px';
    card.style.top = top + 'px';
  }

  document.querySelectorAll('.cite[data-key]').forEach(el => {
    el.addEventListener('mouseenter', () => {
      clearTimeout(citeTimer);
      const d = meta[el.dataset.key];
      if (!d) return;
      const cc = typeof d.cc === 'number' ? `<span class="cite-card-cc">${d.cc.toLocaleString()} citations</span>` : '';
      card.innerHTML = `
        <div class="cite-card-title">${escHtml((d.title||'').slice(0,120))}</div>
        <div class="cite-card-authors">${escHtml((d.authors||'').slice(0,100))}</div>
        <div class="cite-card-meta">
          ${d.year ? `<span>${escHtml(d.year)}</span>` : ''}
          ${d.venue ? `<span>${escHtml(d.venue.slice(0,60))}</span>` : ''}
          ${cc}
        </div>
        ${d.abstract ? `<div class="cite-card-abstract">${escHtml(d.abstract.slice(0,280))}</div>` : ''}`;
      positionCard(card, el, 360);
      card.classList.add('visible');
    });
    el.addEventListener('mouseleave', () => {
      citeTimer = setTimeout(() => card.classList.remove('visible'), 200);
    });
  });
})();

// ── Glossary Hover Cards & Term Annotation ───────────────────────────
var showGlossaryCard, hideGlossaryCardFn;
(function() {
  const glossary = window.GLOSSARY_DATA;
  if (!glossary) return;

  const card = document.createElement('div');
  card.className = 'glossary-card';
  document.body.appendChild(card);
  let gTimer;

  // Keep card alive while mouse is over it
  card.addEventListener('mouseenter', () => clearTimeout(gTimer));
  card.addEventListener('mouseleave', () => {
    gTimer = setTimeout(() => card.classList.remove('visible'), 200);
  });

  showGlossaryCard = function(el) {
    clearTimeout(gTimer);
    const term = el.dataset.term;
    const d = glossary[term];
    if (!d) return;
    card.innerHTML = `
      <div class="glossary-card-term">${escHtml(term)}</div>
      ${d.full && d.full !== term ? `<div class="glossary-card-full">${escHtml(d.full)}</div>` : ''}
      <div class="glossary-card-def">${escHtml(d.definition.slice(0,260))}</div>
      <a class="glossary-card-link" href="${getRootPath()}glossary.html#${termSlug(term)}">View in Glossary →</a>`;
    // position: fixed — coords are viewport-relative, no scrollY
    const rect = el.getBoundingClientRect();
    const vw = window.innerWidth, vh = window.innerHeight;
    let left = rect.left;
    let top  = rect.bottom + 6;
    if (left + 340 > vw - 8) left = Math.max(8, vw - 340 - 8);
    if (left < 8) left = 8;
    if (top + 180 > vh) top = rect.top - 180 - 6;
    card.style.left = left + 'px';
    card.style.top  = top  + 'px';
    card.classList.add('visible');
  };

  hideGlossaryCardFn = function() {
    gTimer = setTimeout(() => card.classList.remove('visible'), 200);
  };

  function makeGlossarySpan(matchedText, term) {
    const span = document.createElement('span');
    span.className = 'glossary-term';
    span.dataset.term = term;
    span.textContent = matchedText;
    span.addEventListener('mouseenter', () => showGlossaryCard(span));
    span.addEventListener('mouseleave', hideGlossaryCardFn);
    return span;
  }

  // Annotate ALL occurrences of every glossary term in chapter content
  const content = document.querySelector('.chapter-content');
  if (content) {
    // Sort longest first so "Cross-species Adulteration" matches before "Adulteration"
    const terms = Object.keys(glossary).sort((a, b) => b.length - a.length);

    function collectTextNodes(root) {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
        acceptNode(node) {
          const p = node.parentElement;
          if (!p) return NodeFilter.FILTER_REJECT;
          const tag = p.tagName.toLowerCase();
          if (['code','pre','script','style','a'].includes(tag)) return NodeFilter.FILTER_REJECT;
          if (p.classList.contains('cite') || p.classList.contains('glossary-term') ||
              p.classList.contains('math')) return NodeFilter.FILTER_REJECT;
          return NodeFilter.FILTER_ACCEPT;
        }
      });
      const nodes = [];
      let n;
      while ((n = walker.nextNode())) nodes.push(n);
      return nodes;
    }

    for (const term of terms) {
      const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      // Match term not preceded/followed by word chars (handles hyphens in terms like OPLS-DA)
      const re = new RegExp('(?<![\\w])' + escaped + '(?![\\w])', 'g');

      // Re-collect text nodes each pass (previous annotations change the DOM)
      const textNodes = collectTextNodes(content);

      for (const tn of textNodes) {
        const text = tn.nodeValue;
        const matches = [...text.matchAll(re)];
        if (!matches.length) continue;

        const frag = document.createDocumentFragment();
        let cursor = 0;
        for (const m of matches) {
          if (m.index > cursor) frag.appendChild(document.createTextNode(text.slice(cursor, m.index)));
          frag.appendChild(makeGlossarySpan(m[0], term));
          cursor = m.index + m[0].length;
        }
        if (cursor < text.length) frag.appendChild(document.createTextNode(text.slice(cursor)));
        tn.parentNode.replaceChild(frag, tn);
      }
    }
  }
})();

// ── BibTeX Copy Button ────────────────────────────────────────────────
const copyBtn = document.getElementById('bibtex-copy-btn');
if (copyBtn) {
  copyBtn.addEventListener('click', () => {
    const bibtex = copyBtn.dataset.bibtex;
    const reset = () => {
      setTimeout(() => {
        copyBtn.textContent = '📋 Copy BibTeX';
        copyBtn.classList.remove('copied');
      }, 2000);
    };
    if (navigator.clipboard) {
      navigator.clipboard.writeText(bibtex).then(() => {
        copyBtn.textContent = '✓ Copied!';
        copyBtn.classList.add('copied');
        reset();
      }).catch(() => fallbackCopy(bibtex, copyBtn, reset));
    } else {
      fallbackCopy(bibtex, copyBtn, reset);
    }
  });
}
function fallbackCopy(text, btn, reset) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed'; ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  try { document.execCommand('copy'); } catch(e) {}
  document.body.removeChild(ta);
  btn.textContent = '✓ Copied!';
  btn.classList.add('copied');
  reset();
}

// ── Figure Gallery Filter ─────────────────────────────────────────────
const galleryFilters = document.getElementById('gallery-filters');
const galleryGrid = document.getElementById('gallery-grid');
if (galleryFilters && galleryGrid) {
  galleryFilters.addEventListener('click', e => {
    const btn = e.target.closest('.gallery-filter-btn');
    if (!btn) return;
    galleryFilters.querySelectorAll('.gallery-filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const ch = btn.dataset.ch;
    galleryGrid.querySelectorAll('.gallery-item').forEach(item => {
      item.style.display = (ch === 'all' || item.dataset.ch === ch) ? '' : 'none';
    });
  });
}

// ── Back to Top Button ────────────────────────────────────────────────
(function() {
  const btn = document.createElement('button');
  btn.id = 'back-to-top';
  btn.innerHTML = '&#8679;';
  btn.title = 'Back to top';
  document.body.appendChild(btn);
  window.addEventListener('scroll', () => {
    btn.classList.toggle('visible', window.scrollY > 300);
  }, { passive: true });
  btn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
})();

// ── Keyboard Shortcuts ────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  // Ignore when typing in inputs
  const tag = document.activeElement?.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA') {
    if (e.key === 'Escape') { document.activeElement.blur(); closeSearch(); }
    return;
  }
  if (e.key === '/' && !e.ctrlKey && !e.metaKey) {
    e.preventDefault();
    openSearch();
    return;
  }
  if (e.key === 'Escape') { closeSearch(); return; }
  // Left/right arrows → prev/next chapter
  if (e.key === 'ArrowLeft') {
    const prev = document.querySelector('.nav-btn[href*="chapter"]:first-of-type, .chapter-nav-bottom .nav-btn:first-child');
    if (prev && prev.textContent.includes('←')) prev.click();
  }
  if (e.key === 'ArrowRight') {
    const btns = document.querySelectorAll('.nav-btn');
    btns.forEach(b => { if (b.textContent.includes('→')) b.click(); });
  }
});

// ── Anchor Copy Links ─────────────────────────────────────────────────
(function() {
  document.querySelectorAll('h2[id], h3[id], h4[id]').forEach(h => {
    const anchor = document.createElement('span');
    anchor.className = 'heading-anchor';
    anchor.innerHTML = '&#182;';
    anchor.title = 'Copy link to this section';
    anchor.addEventListener('click', () => {
      const url = window.location.origin + window.location.pathname + '#' + h.id;
      if (navigator.clipboard) {
        navigator.clipboard.writeText(url).catch(() => {});
      }
      // Brief visual feedback
      anchor.innerHTML = '&#10003;';
      setTimeout(() => { anchor.innerHTML = '&#182;'; }, 1500);
    });
    h.appendChild(anchor);
  });
})();
