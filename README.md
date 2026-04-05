# wiki-of-thesis

> **LLM Knowledge Bases**
>
> Something I'm finding very useful recently: using LLMs to build personal knowledge bases for various topics of research interest. In this way, a large fraction of my recent token throughput is going less into manipulating code, and more into manipulating knowledge (stored as markdown and images). The latest LLMs are quite good at it. So:
>
> **Data ingest:** I index source documents (articles, papers, repos, datasets, images, etc.) into a `raw/` directory, then I use an LLM to incrementally "compile" a wiki, which is just a collection of `.md` files in a directory structure. The wiki includes summaries of all the data in `raw/`, backlinks, and then it categorizes data into concepts, writes articles for them, and links them all.
>
> **IDE:** I use Obsidian as the IDE "frontend" where I can view the raw data, the compiled wiki, and the derived visualizations. Important to note that the LLM writes and maintains all of the data of the wiki, I rarely touch it directly.
>
> **Q&A:** Where things get interesting is that once your wiki is big enough (e.g. mine on some recent research is ~100 articles and ~400K words), you can ask your LLM agent all kinds of complex questions against the wiki, and it will go off, research the answers, etc.
>
> **Output:** Instead of getting answers in text/terminal, I like to have it render markdown files for me, or slide shows (Marp format), or matplotlib images, all of which I then view again in Obsidian.
>
> **TLDR:** raw data from a given number of sources is collected, then compiled by an LLM into a `.md` wiki, then operated on by various CLIs by the LLM to do Q&A and to incrementally enhance the wiki, and all of it viewable in Obsidian. You rarely ever write or edit the wiki manually, it's the domain of the LLM. I think there is room here for an incredible new product instead of a hacky collection of scripts.
>
> — [@karpathy](https://x.com/karpathy/status/2039805659525644595?s=20), Apr 3, 2026

A Wikipedia-style static site generated from Jesse Wood's PhD thesis: **"Machine Learning for Rapid Evaporative Ionization Mass Spectrometry for Marine Biomass Analysis"** (Victoria University of Wellington, 2025).

Every chapter, paper, figure, author, method, and glossary term from the thesis is cross-linked, hover-annotated, and browsable — like a personal Wikipedia for a PhD.

---

## Features

### Content Pages
- **Chapters** — All thesis chapters rendered as HTML with LaTeX math (MathJax 3), figures, tables, and internal cross-references
- **Papers** — Individual pages for every cited paper, fetched via the Semantic Scholar API with abstracts, authors, year, venue, and citation counts
- **Glossary** — Wikipedia-style definitions for every key term (models, datasets, techniques), with hover cards on every occurrence across the entire site
- **Figure Gallery** — All thesis figures in one place, with deep links that jump directly to the figure in its chapter

### Navigation & Discovery
- **Citation Network Graph** — D3.js force-directed graph of all papers and their co-citation relationships
- **Author Index** — Every author who appears in the bibliography, deduplicated and linked to their papers
- **Timeline** — Papers organised by publication year and decade
- **Methods Comparison** — Side-by-side table of all ML models evaluated in the thesis
- **Search** — Full-text search across chapters, papers, and glossary terms (client-side, no server required)

### Reading Experience
- **Citation hover cards** — Hover any `[Author, Year]` citation to see the paper title, venue, year, and abstract without leaving the page
- **Glossary hover cards** — Hover any annotated term to see its definition; click "View in Glossary" to go to the full entry
- **Reading progress bar** — Thin bar at the top of every page showing scroll progress
- **Reading time estimates** — Estimated reading time displayed at the top of each chapter
- **Hatnotes** — Contextual "Main article:" and "See also:" notes linking related pages
- **Navboxes** — Footer navigation boxes grouping related chapters and tasks (Wikipedia-style)
- **Back-to-top button** — Appears after scrolling down; returns to top
- **Anchor copy links** — Every heading has a `§` link to copy a direct URL
- **Keyboard shortcuts** — `s` focuses search; `/` opens search; `g h` goes home

### "Did you know?"
Random interesting facts from the thesis surface on the home page, refreshed on each visit.

---

## Build

```bash
python3 generate.py
```

Output is written to `site/`. Open `site/index.html` in a browser, or serve with any static file server:

```bash
cd site && python3 -m http.server 8000
```

### Requirements

```
pip install bibtexparser
```

The Semantic Scholar API is used to enrich paper metadata. Results are cached in `ss_cache.json` so subsequent builds are fast. A cold build fetches ~400 papers; a warm build is near-instant.

---

## Structure

```
wiki-of-thesis/
├── generate.py          # Static site generator (single file)
├── thesis-src/          # LaTeX source chapters + figures
│   ├── chapter-1/
│   ├── chapter-2/
│   └── ...
├── refs/                # BibTeX bibliography
├── ss_cache.json        # Semantic Scholar API cache
└── site/                # Generated output (GitHub Pages)
    ├── index.html
    ├── chapters/
    ├── papers/
    ├── js/
    └── css/
```

---

## Deployment

The `site/` directory is deployed to GitHub Pages. Push to `main` and it's live.

---

## Inspiration

Inspired by the idea that a PhD thesis deserves the same rich, interconnected reading experience as a Wikipedia article — where every term, citation, author, and figure is one click away.

Tweet that sparked it: [@karpathy](https://x.com/karpathy/status/2039805659525644595?s=20)
