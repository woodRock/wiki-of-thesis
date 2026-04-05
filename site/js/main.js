
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

// Search toggle
const searchToggle = document.getElementById('search-toggle');
const searchBar = document.getElementById('search-bar');
const searchInput = document.getElementById('search-input');
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

// Global search (nav search bar)
if (searchInput) {
  // Build search index from all paper cards if on papers page
  let paperIndex = [];
  const allCards = document.querySelectorAll('.paper-card');
  allCards.forEach(card => {
    paperIndex.push({
      title: card.dataset.title || '',
      author: card.dataset.author || '',
      year: card.dataset.year || '',
      href: card.querySelector('a')?.href || ''
    });
  });

  const resultsDiv = document.getElementById('search-results');
  searchInput.addEventListener('input', () => {
    if (!resultsDiv) return;
    const q = searchInput.value.toLowerCase().trim();
    if (!q) { resultsDiv.innerHTML = ''; return; }

    // Simple search
    const matches = paperIndex.filter(p =>
      p.title.includes(q) || p.author.includes(q) || p.year.includes(q)
    ).slice(0, 8);

    if (!matches.length) {
      resultsDiv.innerHTML = '<div class="search-result-item"><div class="sri-meta">No results found</div></div>';
    } else {
      resultsDiv.innerHTML = matches.map(p =>
        `<div class="search-result-item" onclick="window.location='${p.href}'">
          <div class="sri-title">${p.title.slice(0,80)}</div>
          <div class="sri-meta">${p.author} · ${p.year}</div>
        </div>`
      ).join('');
    }
  });

  document.addEventListener('click', e => {
    if (!searchBar?.contains(e.target) && !searchToggle?.contains(e.target)) {
      searchBar?.classList.add('hidden');
    }
  });
}

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
