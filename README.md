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

A Wikipedia-style static site generated from a PhD thesis LaTeX source. Every chapter, paper, figure, author, method, and glossary term is cross-linked, hover-annotated, and browsable — like a personal Wikipedia for a PhD.

**Live example:** Jesse Wood's thesis — *Machine Learning for Rapid Evaporative Ionization Mass Spectrometry for Marine Biomass Analysis* (Victoria University of Wellington, 2025).

---

## Features

### Content Pages
- **Chapters** — All thesis chapters rendered as HTML with LaTeX math (MathJax 3), figures, tables, and internal cross-references
- **Papers** — Individual pages for every cited paper, enriched via the Semantic Scholar API with abstracts, authors, year, venue, and citation counts
- **Glossary** — Wikipedia-style definitions for every key term, with hover cards on every occurrence across the entire site
- **Figure Gallery** — All thesis figures in one place, with deep links that jump directly to the figure in its chapter

### Navigation & Discovery
- **Citation Network Graph** — D3.js force-directed graph of all papers and their co-citation relationships
- **Author Index** — Every author in the bibliography, deduplicated and linked to their papers
- **Timeline** — Papers organised by publication year and decade
- **Methods Comparison** — Side-by-side table of all ML models evaluated in the thesis
- **Search** — Full-text search across chapters, papers, and glossary terms, with section-level deep links and highlighted snippets (client-side, no server required)

### Reading Experience
- **Citation hover cards** — Hover any `[Author, Year]` citation to see title, venue, year, and abstract
- **Glossary hover cards** — Hover any annotated term to see its definition inline
- **Sticky TOC** — Table of contents that follows you as you scroll, with active section highlighted
- **Reading progress bar** — Thin bar at the top of every page
- **Reading time estimates** — Displayed at the top of each chapter
- **Hatnotes & navboxes** — Contextual cross-links and footer navigation (Wikipedia-style)
- **Keyboard shortcuts** — `s` / `/` opens search; `g h` goes home
- **Dark mode** — Toggle in the navigation bar

---

## Using this tool for your own thesis

`generate.py` is a generic engine. All thesis-specific content lives in `thesis.yml`. You do not need to edit any Python code.

### 1. Install dependencies

```bash
pip install requests pyyaml
```

### 2. Organise your LaTeX source

The tool expects this folder structure:

```
your-thesis/
├── generate.py
├── thesis.yml
├── thesis-src/
│   ├── chapter-1/
│   │   ├── main.tex
│   │   └── assets/          # figures for this chapter
│   ├── chapter-2/
│   │   ├── main.tex
│   │   └── assets/
│   └── ...
└── refs/
    └── references.bib       # BibTeX bibliography (any .bib file)
```

Each chapter is a separate folder containing a `main.tex` file. The folder name becomes the chapter slug (used in URLs). Assets (images, PDFs) go in an `assets/` subfolder alongside `main.tex`.

### 3. Edit `thesis.yml`

This is the only file you need to edit. It contains everything thesis-specific:

```yaml
# Core metadata
title: "Your Thesis Title"
author: Your Name
university: Your University
year: "2025"
degree: Doctor of Philosophy in Your Field
school: Your School or Department
supervisors:
  - Prof. Supervisor One
  - Dr. Supervisor Two

abstract: >
  Your abstract text here...

# List your chapters (must match folder names in thesis-src/)
chapters:
  - slug: chapter-1
    title: Introduction
    hatnote: 'Optional note shown at top of chapter page (HTML allowed).'
    see_also:
      - [chapter-2, Literature Review]

# Key results table on home page
results:
  - task: Task Name
    baseline: "Baseline: 80%"
    best: "Your Model: 95%"
    gain: "+15%"

# Glossary terms — as many as you like
glossary:
  BERT:
    full: Bidirectional Encoder Representations from Transformers
    category: model        # instrument / method / model / task / domain / contribution
    definition: >
      A pre-training language model using masked language modeling...
```

A fully annotated example covering every option is in `thesis.yml` in this repo.

### 4. Build

```bash
python3 generate.py
```

Output is written to `site/`. Open `site/index.html` directly in a browser, or serve it locally:

```bash
cd site && python3 -m http.server 8000
```

A cold build fetches paper metadata from Semantic Scholar (~1 API call per cited paper). Results are cached in `ss_cache.json` so subsequent builds are near-instant. Set `SS_API_KEY` as an environment variable to avoid rate limits.

### 5. Deploy to GitHub Pages

The included `.github/workflows/deploy.yml` builds the site on every push to `main` and deploys it automatically. No configuration needed — just push.

If you fork this repo, enable GitHub Pages in your repository settings (Settings → Pages → Source: GitHub Actions).

---

## LaTeX compatibility

The generator handles standard LaTeX thesis conventions:

| LaTeX | Rendered as |
|---|---|
| `\section`, `\subsection`, `\subsubsection` | Headings with anchor links |
| `\begin{figure}`, `\subfloat` | Figures with captions; multiple images per figure supported |
| `\begin{table}`, `\begin{tabular}` | HTML tables (or PNG via pdflatex if available) |
| `\begin{equation}`, `\begin{align}`, `$$`, `\[` | Display math via MathJax 3 |
| `$...$`, `\(...\)` | Inline math |
| `\cite{key}`, `\citep{key}`, `\citet{key}` | Citation links with hover cards |
| `\Cref{label}`, `\cref{label}`, `\ref{label}` | Cross-reference links to figures and sections |
| `\begin{enumerate}`, `\begin{itemize}` | Ordered and unordered lists |
| `\textbf`, `\textit`, `\emph`, `\texttt` | Bold, italic, monospace |
| `\footnote` | Inline footnote text |
| PDF figures | Auto-converted to PNG at build time (requires `poppler-utils`) |

Chapters that use non-standard packages or heavily custom macros may need minor preprocessing. The generator silently skips environments it does not recognise rather than crashing.

---

## Project structure

```
wiki-of-thesis/
├── generate.py              # Static site generator — the engine
├── thesis.yml               # Your thesis content — edit this
├── thesis-src/              # LaTeX source (one folder per chapter)
├── refs/                    # BibTeX bibliography
├── ss_cache.json            # Semantic Scholar API cache (auto-generated)
├── site/                    # Generated site output (do not edit by hand)
│   ├── index.html
│   ├── chapters/
│   ├── papers/
│   ├── glossary.html
│   ├── figures.html
│   ├── graph.html
│   ├── authors.html
│   ├── timeline.html
│   ├── methods.html
│   ├── js/
│   └── css/
└── .github/workflows/
    └── deploy.yml           # GitHub Pages CI/CD
```

---

## Inspiration

Inspired by the idea that a PhD thesis deserves the same rich, interconnected reading experience as a Wikipedia article — where every term, citation, author, and figure is one click away.

Tweet that sparked it: [@karpathy](https://x.com/karpathy/status/2039805659525644595?s=20)
