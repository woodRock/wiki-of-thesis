#!/usr/bin/env python3
"""
Thesis Wiki Generator
Generates a Wikipedia-like static website from LaTeX thesis files.
Fetches paper metadata from Semantic Scholar API.
"""

import os, re, json, time, shutil, requests, html, sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

# ── Configuration ──────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.resolve()
THESIS_DIR = BASE_DIR / "thesis-src"
SITE_DIR   = BASE_DIR / "site"
CACHE_FILE = BASE_DIR / "ss_cache.json"
SS_API_KEY = os.environ.get("SS_API_KEY", "APORisAAR355u0HFw6y1F2xmpPwqRX9H4xyA04aQ")
SS_BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"
SS_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
SS_FIELDS = "title,authors,year,abstract,citationCount,venue,externalIds,openAccessPdf"

CHAPTERS = [
    ("chapter-0", "Acknowledgements"),
    ("chapter-1", "Introduction"),
    ("chapter-2", "Literature Survey"),
    ("chapter-3", "Datasets and Processing"),
    ("chapter-4", "Fish Species and Part Identification"),
    ("chapter-5", "Oil Contamination and Cross-Species Adulteration"),
    ("chapter-6", "Contrastive Learning for Batch Detection"),
    ("chapter-7", "Conclusions"),
]

THESIS_META = {
    "title": "Machine Learning for Rapid Evaporative Ionization Mass Spectrometry for Marine Biomass Analysis",
    "author": "Jesse Wood",
    "university": "Victoria University of Wellington",
    "year": "2025",
    "subject": "Artificial Intelligence / Food Science",
    "abstract": (
        "This thesis advances seafood processing by applying deep learning to Rapid Evaporative "
        "Ionization Mass Spectrometry (REIMS) data, enabling automated and accurate marine biomass analysis. "
        "It addresses critical industry challenges including species identification to combat mislabeling fraud, "
        "body part classification for by-product utilization, oil contamination detection, cross-species "
        "adulteration detection, and batch traceability. Key contributions include Transformer and Mixture of "
        "Experts (MoE) architectures achieving up to 100% accuracy in species identification, SpectroSim — a "
        "self-supervised contrastive learning framework for label-free batch traceability (70.8% accuracy) — "
        "and explainable AI integration via LIME and Grad-CAM for interpretable predictions."
    ),
    "key_methods": ["Transformer", "Mixture of Experts", "Transfer Learning", "Contrastive Learning",
                    "LIME", "Grad-CAM", "Masked Spectra Modelling", "OPLS-DA"],
    "key_topics": ["REIMS", "Marine Biomass", "Species Identification", "Food Fraud Detection",
                   "Oil Contamination", "Batch Traceability", "Explainable AI"],
    "results": [
        ("Fish Species", "OPLS-DA: 96.39%", "MoE Transformer: 100.00%", "+3.61%"),
        ("Fish Body Part", "OPLS-DA: 51.17%", "Ensemble Transformer: 74.13%", "+22.96%"),
        ("Oil Contamination", "OPLS-DA: 26.43%", "TL MoE Transformer: 49.10%", "+22.67%"),
        ("Cross-species Adulteration", "OPLS-DA: 79.96%", "Pre-trained Transformer: 91.97%", "+12.01%"),
        ("Batch Detection", "OPLS-DA: 53.19%", "SpectroSim (Transformer): 70.80%", "+17.61%"),
    ],
}


# ── BibTeX Parser ──────────────────────────────────────────────────────────────

def clean_tex(text: str) -> str:
    """Strip LaTeX formatting from text."""
    text = re.sub(r"\\'\{?([aeiouAEIOUcnszCNSZ])\}?", r'\1', text)
    text = re.sub(r'\\`\{?([aeiouAEIOU])\}?', r'\1', text)
    text = re.sub(r'\\"\\{?([aeiouAEIOU])\\}?', r'\1', text)
    text = re.sub(r'\\"([a-zA-Z])', r'\1', text)
    text = re.sub(r"\\~\{?([nN])\}?", r'\1', text)
    text = re.sub(r'\\c\{?([cCsS])\}?', r'\1', text)
    text = re.sub(r'\\v\{?([a-zA-Z])\}?', r'\1', text)
    text = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\[a-zA-Z]+', ' ', text)
    text = text.replace('\\&', '&').replace('\\%', '%').replace('---', '—').replace('--', '–')
    text = re.sub(r'[{}]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def parse_bibtex(filepath: Path) -> Dict[str, Dict]:
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    entries = {}
    # Match @Type{key, fields...}
    for m in re.finditer(r'@(\w+)\s*\{\s*([^,\s]+)\s*,\s*(.*?)\n\}', content, re.DOTALL):
        etype, key, body = m.group(1).lower(), m.group(2).strip(), m.group(3)
        entry = {'type': etype, 'key': key}
        for fm in re.finditer(r'(\w+)\s*=\s*(?:\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}|"([^"]*)"|([\w\d]+))', body):
            fname = fm.group(1).lower()
            val = (fm.group(2) or fm.group(3) or fm.group(4) or '').strip()
            entry[fname] = clean_tex(val)
        entries[key] = entry

    print(f"  Parsed {len(entries)} BibTeX entries")
    return entries


def get_first_author_surname(author_str: str) -> str:
    """Extract first author's surname from BibTeX author field."""
    if not author_str:
        return "Unknown"
    first = author_str.split(' and ')[0].strip()
    if ',' in first:
        return first.split(',')[0].strip()
    parts = first.split()
    return parts[-1] if parts else first


def format_authors(author_str: str, max_authors: int = 3) -> str:
    """Format author list for display."""
    if not author_str:
        return "Unknown"
    authors = [a.strip() for a in author_str.split(' and ')]
    formatted = []
    for a in authors[:max_authors]:
        if ',' in a:
            parts = a.split(',', 1)
            formatted.append(f"{parts[1].strip()} {parts[0].strip()}")
        else:
            formatted.append(a)
    result = ', '.join(formatted)
    if len(authors) > max_authors:
        result += f' et al.'
    return result


# ── Semantic Scholar Fetcher ────────────────────────────────────────────────────

def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {}


def save_cache(cache: dict):
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)


def _has_tool(*cmds) -> Optional[str]:
    """Return the first command that exists on PATH, or None."""
    import shutil as _sh
    for cmd in cmds:
        if _sh.which(cmd):
            return cmd
    return None


def convert_pdf_to_png(pdf_path: Path, out_path: Path, resolution: int = 200) -> bool:
    """Convert a single PDF file to PNG, auto-cropping to content bounds."""
    import subprocess, tempfile, platform
    try:
        # Step 1: pdfcrop to trim whitespace (if available)
        cropped_pdf = pdf_path
        if _has_tool('pdfcrop'):
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                tmp_path = Path(tmp.name)
            r = subprocess.run(['pdfcrop', str(pdf_path), str(tmp_path)],
                               capture_output=True, timeout=30)
            if r.returncode == 0 and tmp_path.exists():
                cropped_pdf = tmp_path

        # Step 2: convert to PNG
        stem = str(out_path.with_suffix(''))

        # pdftoppm (Linux / available via poppler-utils)
        if _has_tool('pdftoppm'):
            r = subprocess.run(
                ['pdftoppm', '-png', '-r', str(resolution), '-singlefile',
                 str(cropped_pdf), stem],
                capture_output=True, timeout=30
            )
            if r.returncode == 0 and out_path.exists():
                return True

        # sips (macOS fallback)
        if platform.system() == 'Darwin' and _has_tool('sips'):
            r = subprocess.run(
                ['sips', '-s', 'format', 'png', str(cropped_pdf), '--out', str(out_path)],
                capture_output=True, timeout=30
            )
            if r.returncode == 0 and out_path.exists():
                return True

        return False
    except Exception:
        return False


# Standalone LaTeX wrapper for rendering a table as an image
_TABLE_TEX_TEMPLATE = r"""\documentclass[border=4pt,varwidth=\maxdimen]{standalone}
\usepackage{booktabs}
\usepackage{multirow}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{xcolor}
\usepackage{colortbl}
\usepackage{tabularx}
\usepackage{makecell}
\usepackage{arydshln}
\usepackage[para,online,flushleft]{threeparttable}
\usepackage{caption}
\captionsetup{font=small,labelfont=bf}
\begin{document}
%CONTENT%
\end{document}
"""


def compile_table_to_png(table_latex: str, out_path: Path) -> bool:
    """Compile a LaTeX table float to a PNG image via pdflatex."""
    import subprocess, tempfile
    if not _has_tool('pdflatex'):
        return False

    doc = _TABLE_TEX_TEMPLATE.replace('%CONTENT%', table_latex)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tex_file = os.path.join(tmpdir, 'table.tex')
            pdf_file = Path(tmpdir) / 'table.pdf'

            with open(tex_file, 'w') as f:
                f.write(doc)

            r = subprocess.run(
                ['pdflatex', '-interaction=batchmode', '-halt-on-error',
                 '-output-directory', tmpdir, tex_file],
                capture_output=True, timeout=60
            )
            if r.returncode != 0 or not pdf_file.exists():
                return False

            return convert_pdf_to_png(pdf_file, out_path, resolution=200)
    except Exception:
        return False


def fetch_semantic_scholar(bib_entries: Dict[str, Dict]) -> Dict[str, dict]:
    """Fetch paper metadata from Semantic Scholar. Returns {key: ss_data}."""
    cache = load_cache()
    headers = {"x-api-key": SS_API_KEY}
    results = {}

    # Separate entries: those with DOI (batch lookup) vs those with only title (search)
    doi_entries = {}     # {key: doi}
    title_entries = {}   # {key: title}

    for key, entry in bib_entries.items():
        if key in cache:
            results[key] = cache[key]
            continue
        doi = entry.get('doi', '').strip()
        if doi:
            doi_entries[key] = doi
        elif entry.get('title'):
            title_entries[key] = entry['title']

    # --- Batch DOI lookup ---
    if doi_entries:
        print(f"  Fetching {len(doi_entries)} papers by DOI (batch)...")
        keys = list(doi_entries.keys())
        ids = [f"DOI:{doi_entries[k]}" for k in keys]
        # Process in chunks of 100
        for i in range(0, len(ids), 100):
            chunk_keys = keys[i:i+100]
            chunk_ids = ids[i:i+100]
            try:
                r = requests.post(
                    SS_BATCH_URL,
                    headers=headers,
                    params={"fields": SS_FIELDS},
                    json={"ids": chunk_ids},
                    timeout=30
                )
                if r.status_code == 200:
                    data = r.json()
                    for k, d in zip(chunk_keys, data):
                        if d:
                            results[k] = d
                            cache[k] = d
                        else:
                            results[k] = None
                            cache[k] = None
                else:
                    print(f"    DOI batch failed: {r.status_code}")
            except Exception as e:
                print(f"    DOI batch error: {e}")
            time.sleep(0.5)
        save_cache(cache)

    # --- Title search for remaining ---
    if title_entries:
        print(f"  Fetching {len(title_entries)} papers by title search...")
        for i, (key, title) in enumerate(title_entries.items()):
            if i % 20 == 0:
                print(f"    Progress: {i}/{len(title_entries)}")
            try:
                r = requests.get(
                    SS_SEARCH_URL,
                    headers=headers,
                    params={"query": title[:200], "fields": SS_FIELDS, "limit": 1},
                    timeout=15
                )
                if r.status_code == 200:
                    data = r.json()
                    papers = data.get('data', [])
                    if papers:
                        results[key] = papers[0]
                        cache[key] = papers[0]
                    else:
                        results[key] = None
                        cache[key] = None
                else:
                    results[key] = None
                    cache[key] = None
            except Exception as e:
                results[key] = None
                cache[key] = None
            time.sleep(0.15)  # Be respectful

        save_cache(cache)

    # Merge cache hits
    for key in bib_entries:
        if key not in results:
            results[key] = cache.get(key)

    fetched = sum(1 for v in results.values() if v)
    print(f"  Semantic Scholar: {fetched}/{len(bib_entries)} papers found")
    return results


# ── LaTeX → HTML Converter ─────────────────────────────────────────────────────

class LatexConverter:
    def __init__(self, bib: Dict, chapter_slug: str):
        self.bib = bib
        self.chapter_slug = chapter_slug
        self.citations_used: Set[str] = set()
        self.toc: List[Tuple[int, str, str]] = []  # (level, title, id)

    def convert(self, latex: str) -> str:
        t = self._preprocess(latex)
        t = self._environments(t)
        t = self._sections(t)
        t = self._citations(t)   # Must come before _inline() which strips \commands
        t = self._inline(t)
        t = self._paragraphs(t)
        return t

    def _preprocess(self, t: str) -> str:
        t = re.sub(r'(?m)(?<!\\)%.*$', '', t)
        t = re.sub(r'\\chapter\*?\{[^}]*\}', '', t)
        t = re.sub(r'\\label\{[^}]*\}', '', t)
        t = re.sub(r'\\vspace\{[^}]*\}', '', t)
        t = re.sub(r'\\hspace\{[^}]*\}', '', t)
        t = re.sub(r'\\newpage', '', t)
        t = re.sub(r'\\clearpage', '', t)
        t = re.sub(r'\\raggedbottom', '', t)
        t = re.sub(r'\\noindent', '', t)
        return t

    def _slug(self, title: str) -> str:
        s = re.sub(r'[^\w\s-]', '', title.lower())
        return re.sub(r'[\s_]+', '-', s).strip('-')[:60]

    def _sections(self, t: str) -> str:
        def sec(level, m):
            title = self._inline_simple(m.group(1))
            sid = self._slug(re.sub(r'<[^>]+>', '', title))
            self.toc.append((level, re.sub(r'<[^>]+>', '', title), sid))
            return f'\n<h{level} id="{sid}">{title}</h{level}>\n'

        t = re.sub(r'\\section\*?\{((?:[^{}]|\{[^{}]*\})*)\}', lambda m: sec(2, m), t)
        t = re.sub(r'\\subsection\*?\{((?:[^{}]|\{[^{}]*\})*)\}', lambda m: sec(3, m), t)
        t = re.sub(r'\\subsubsection\*?\{((?:[^{}]|\{[^{}]*\})*)\}', lambda m: sec(4, m), t)
        return t

    def _environments(self, t: str) -> str:
        # Figures
        t = re.sub(r'\\begin\{figure\}(?:\[.*?\])?(.*?)\\end\{figure\}',
                   self._figure, t, flags=re.DOTALL)
        # Tables → parse into HTML
        t = re.sub(r'\\begin\{table\*?\}(.*?)\\end\{table\*?\}',
                   self._table, t, flags=re.DOTALL)
        # Algorithms → remove
        t = re.sub(r'\\begin\{algorithm\}.*?\\end\{algorithm\}', '', t, flags=re.DOTALL)
        t = re.sub(r'\\begin\{algorithmic\}.*?\\end\{algorithmic\}', '', t, flags=re.DOTALL)
        # Enumerate
        t = re.sub(r'\\begin\{enumerate\}(.*?)\\end\{enumerate\}',
                   self._enumerate, t, flags=re.DOTALL)
        # Itemize
        t = re.sub(r'\\begin\{itemize\}(.*?)\\end\{itemize\}',
                   self._itemize, t, flags=re.DOTALL)
        # Display math
        t = re.sub(r'\\begin\{equation\*?\}(.*?)\\end\{equation\*?\}',
                   r'<div class="math-display">\\[\1\\]</div>', t, flags=re.DOTALL)
        t = re.sub(r'\\begin\{align\*?\}(.*?)\\end\{align\*?\}',
                   lambda m: f'<div class="math-display">\\[\\begin{{aligned}}{m.group(1)}\\end{{aligned}}\\]</div>',
                   t, flags=re.DOTALL)
        t = re.sub(r'\\\[(.*?)\\\]',
                   r'<div class="math-display">\\[\1\\]</div>', t, flags=re.DOTALL)
        # Quoting/quote
        t = re.sub(r'\\begin\{(?:quoting|quote)\}(.*?)\\end\{(?:quoting|quote)\}',
                   r'<blockquote>\1</blockquote>', t, flags=re.DOTALL)
        # Abstract
        t = re.sub(r'\\begin\{abstract\}.*?\\end\{abstract\}', '', t, flags=re.DOTALL)
        # Multicol, minipage etc
        t = re.sub(r'\\begin\{(?:multicol|minipage|center|flushleft|flushright)\}(?:\{[^}]*\})?(.*?)\\end\{(?:multicol|minipage|center|flushleft|flushright)\}',
                   r'\1', t, flags=re.DOTALL)
        # Rotating
        t = re.sub(r'\\begin\{(?:sideways|rotate)\}.*?\\end\{(?:sideways|rotate)\}', '', t, flags=re.DOTALL)
        return t

    def _figure(self, m) -> str:
        content = m.group(1)
        img_m = re.search(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}', content)
        cap_m = re.search(r'\\caption\{((?:[^{}]|\{[^{}]*\})*)\}', content)
        if not img_m:
            return ''
        img_name = os.path.basename(img_m.group(1))
        caption = self._inline_simple(cap_m.group(1)) if cap_m else ''
        alt = html.escape(re.sub(r'<[^>]+>', '', caption))
        # PDF figures are converted to PNG at build time
        if img_name.lower().endswith('.pdf'):
            img_name = os.path.splitext(img_name)[0] + '.png'
        # Single-line <img> — no multi-line attributes that confuse _paragraphs
        return f'<figure class="thesis-figure"><img src="../assets/{html.escape(img_name)}" alt="{alt}" loading="lazy" class="thesis-img"><figcaption>{caption}</figcaption></figure>\n'

    def _table(self, m) -> str:
        """Convert a LaTeX table float into HTML (or PNG image if pdflatex available)."""
        raw_content = m.group(0)  # full \begin{table}...\end{table} including wrapper
        content = m.group(1)

        # Extract caption for alt text / fallback
        cap_m = re.search(r'\\caption\{((?:[^{}]|\{[^{}]*\})*)\}', content)
        caption = self._inline_simple(cap_m.group(1)) if cap_m else ''

        # --- Try PNG rendering via pdflatex (perfect output) ---
        if hasattr(self, '_table_assets_dir') and _has_tool('pdflatex'):
            import hashlib
            table_hash = hashlib.md5(raw_content.encode()).hexdigest()[:12]
            png_name = f'table_{self.chapter_slug}_{table_hash}.png'
            png_path = Path(self._table_assets_dir) / png_name

            if not png_path.exists():
                # Reconstruct the full table float with proper formatting for standalone
                compile_table_to_png(raw_content, png_path)

            if png_path.exists():
                alt = html.escape(re.sub(r'<[^>]+>', '', caption))
                cap_html = f'<figcaption>{caption}</figcaption>' if caption else ''
                return (f'<figure class="thesis-figure thesis-table-img">'
                        f'<img src="../assets/{html.escape(png_name)}" alt="{alt}" '
                        f'loading="lazy" class="thesis-img">'
                        f'{cap_html}</figure>\n')

        # --- Fallback: HTML table parser ---
        content_clean = re.sub(r'(?<!\\)%.*$', '', content, flags=re.MULTILINE)
        content_clean = re.sub(r'\\rowcolors\{[^}]*\}\{[^}]*\}\{[^}]*\}', '', content_clean)
        content_clean = re.sub(r'\\(?:small|footnotesize|large|Large|centering|raggedright|raggedleft)\b\s*', '', content_clean)

        # Column spec may contain @{} so use one-level nested brace matching
        tab_m = re.search(
            r'\\begin\{tabular[*]?\}\{((?:[^{}]|\{[^{}]*\})*)\}(.*?)\\end\{tabular[*]?\}',
            content_clean, re.DOTALL)
        if not tab_m:
            return f'<div class="table-note">📊 {caption}</div>\n' if caption else ''

        num_cols = len(re.findall(r'[lrcpXSm]', tab_m.group(1)))
        return self._tabular(tab_m.group(2), caption, num_cols) + '\n'

    def _tabular(self, body: str, caption: str, num_cols: int) -> str:
        """Parse LaTeX tabular body → HTML table."""
        body = body.replace('\r\n', '\n').replace('\r', '\n')
        # Only strip REAL LaTeX comments — % NOT preceded by backslash
        body = re.sub(r'(?<!\\)%.*$', '', body, flags=re.MULTILINE)

        # Protect escaped specials before splitting on & and //
        body = body.replace(r'\&', '\x01AMP\x01')
        body = body.replace(r'\%', '\x01PCT\x01')
        body = body.replace(r'\$', '\x01DOL\x01')

        # Replace rule commands with unique markers so we can split cleanly
        # \midrule (exact, not \cmidrule) marks header→body boundary
        body = re.sub(r'\\midrule\b', '\x00MID\x00', body)
        # \cmidrule is purely decorative — remove
        body = re.sub(r'\\cmidrule\s*(?:\([^)]*\))?\s*\{[^}]*\}', '', body)
        # \toprule / \bottomrule → remove (just visual decoration)
        body = re.sub(r'\\(?:toprule|bottomrule)\b', '', body)
        # \hline → mark
        body = re.sub(r'\\hline\b', '\x00HLINE\x00', body)

        # Decide header/body split
        has_midrule = '\x00MID\x00' in body
        has_hline   = '\x00HLINE\x00' in body

        if has_midrule:
            # Booktabs style: everything before first \midrule = header
            parts = body.split('\x00MID\x00', 1)
            header_text = parts[0].replace('\x00HLINE\x00', '').strip()
            body_text   = parts[1].replace('\x00MID\x00','').replace('\x00HLINE\x00','').strip() if len(parts) > 1 else ''
        elif has_hline:
            # hline style: chunks[0]=before first hline (skip), chunks[1]=header, chunks[2+]=body
            chunks = body.split('\x00HLINE\x00')
            header_text = chunks[1].strip() if len(chunks) > 1 else ''
            body_text   = '\n'.join(chunks[2:]).strip() if len(chunks) > 2 else ''
        else:
            header_text = ''
            body_text   = body.strip()

        def parse_rows(text: str, is_header: bool) -> List[str]:
            result = []
            for row in re.split(r'\\\\(?:\[[^\]]*\])?', text):
                row = row.strip()
                if not row:
                    continue
                cells = row.split('&')
                cell_tags = []
                for cell in cells:
                    cell = (cell.strip()
                            .replace('\x01AMP\x01', '&amp;')
                            .replace('\x01PCT\x01', '%')
                            .replace('\x01DOL\x01', '$'))
                    # \multicolumn{n}{spec}{content}
                    mc = re.match(
                        r'\\multicolumn\s*\{(\d+)\}\s*\{[^}]*\}\s*\{((?:[^{}]|\{[^{}]*\})*)\}',
                        cell
                    )
                    if mc:
                        span, content = mc.group(1), self._cell(mc.group(2))
                        tag = 'th' if is_header else 'td'
                        cell_tags.append(f'<{tag} colspan="{span}">{content}</{tag}>')
                    else:
                        content = self._cell(cell)
                        tag = 'th' if is_header else 'td'
                        cell_tags.append(f'<{tag}>{content}</{tag}>')
                if cell_tags:
                    result.append('<tr>' + ''.join(cell_tags) + '</tr>')
            return result

        header_rows = parse_rows(header_text, is_header=True)
        body_rows   = parse_rows(body_text,   is_header=False)

        if not header_rows and not body_rows:
            return ''

        cap_html = f'<caption>{caption}</caption>' if caption else ''
        thead = f'<thead>{"".join(header_rows)}</thead>' if header_rows else ''
        tbody = f'<tbody>{"".join(body_rows)}</tbody>' if body_rows else ''
        return (f'<div class="table-wrap">\n'
                f'<table class="thesis-table">{cap_html}{thead}{tbody}</table>\n'
                f'</div>')

    def _cell(self, text: str) -> str:
        """Convert a single table cell."""
        text = text.strip()
        # \multirow — extract inner content
        mr = re.match(r'\\multirow\s*\{[^}]*\}\s*\{[^}]*\}\s*\{((?:[^{}]|\{[^{}]*\})*)\}', text)
        if mr:
            text = mr.group(1)
        return self._inline_simple(text)

    def _enumerate(self, m) -> str:
        items = self._split_items(m.group(1))
        lis = '\n'.join(f'  <li>{self._inline(item.strip())}</li>' for item in items if item.strip())
        return f'<ol>\n{lis}\n</ol>\n'

    def _itemize(self, m) -> str:
        items = self._split_items(m.group(1))
        lis = '\n'.join(f'  <li>{self._inline(item.strip())}</li>' for item in items if item.strip())
        return f'<ul>\n{lis}\n</ul>\n'

    def _split_items(self, content: str) -> List[str]:
        return [p for p in re.split(r'\\item(?:\[[^\]]*\])?', content)[1:] if p.strip()]

    def _inline_simple(self, t: str) -> str:
        """Lightweight inline converter for titles/captions (no citation tracking)."""
        # Protect math FIRST so subsequent stripping doesn't destroy \pm, \times etc.
        maths: dict = {}
        def _prot(m):
            k = f'\x00S{len(maths)}\x00'
            maths[k] = f'<span class="math">\\({m.group(1)}\\)</span>'
            return k
        t = re.sub(r'\$([^\$\n]+?)\$', _prot, t)

        # Strip citation commands
        t = re.sub(r'\\cite[a-z]*\{[^}]+\}', '', t)
        # Formatting
        t = re.sub(r'\\textbf\{([^}]+)\}', r'<strong>\1</strong>', t)
        t = re.sub(r'\\textit\{([^}]+)\}', r'<em>\1</em>', t)
        t = re.sub(r'\\emph\{([^}]+)\}', r'<em>\1</em>', t)
        t = re.sub(r'\\texttt\{([^}]+)\}', r'<code>\1</code>', t)
        t = re.sub(r'\\text\{([^}]+)\}', r'\1', t)
        t = t.replace('---', '—').replace('--', '–')
        t = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', t)
        t = re.sub(r'\\[a-zA-Z]+\*?\s*', '', t)
        t = re.sub(r'[{}]', '', t)

        # Restore math
        for k, v in maths.items():
            t = t.replace(k, v)
        return t.strip()

    def _inline(self, t: str) -> str:
        # Protect inline math
        maths = {}
        def _protect(m):
            k = f'\x00M{len(maths)}\x00'
            maths[k] = f'<span class="math">\\({m.group(1)}\\)</span>'
            return k
        t = re.sub(r'\$([^\$\n]+?)\$', _protect, t)

        # Formatting (handle nested braces one level)
        for cmd, tag in [('textbf','strong'), ('textit','em'), ('emph','em')]:
            t = re.sub(rf'\\{cmd}\{{((?:[^{{}}]|\{{[^{{}}]*\}})*)\}}', rf'<{tag}>\1</{tag}>', t)
        t = re.sub(r'\\texttt\{((?:[^{}]|\{[^{}]*\})*)\}', r'<code>\1</code>', t)
        t = re.sub(r'\\text\{((?:[^{}]|\{[^{}]*\})*)\}', r'\1', t)
        t = re.sub(r'\\textsc\{([^}]+)\}', r'\1', t)
        t = re.sub(r'\\mathbf\{([^}]+)\}', r'<strong>\1</strong>', t)
        t = re.sub(r'\\boldsymbol\{([^}]+)\}', r'\1', t)
        t = re.sub(r'\\bm\{([^}]+)\}', r'\1', t)
        t = re.sub(r'\\mathbb\{([^}]+)\}', r'\1', t)
        t = re.sub(r'\\mathrm\{([^}]+)\}', r'\1', t)

        # URLs / links
        t = re.sub(r'\\url\{([^}]+)\}',
                   lambda m: f'<a href="{m.group(1)}" target="_blank" rel="noopener">{m.group(1)}</a>', t)
        t = re.sub(r'\\href\{([^}]+)\}\{([^}]+)\}',
                   lambda m: f'<a href="{m.group(1)}" target="_blank" rel="noopener">{m.group(2)}</a>', t)

        # Quotes
        t = re.sub(r"``(.*?)''", r'"\1"', t, flags=re.DOTALL)
        t = re.sub(r'`([^`\']+)\'', r'"\1"', t)

        # Cross-references (simplified)
        t = re.sub(r'\\[Cc]ref\{([^}]+)\}', self._cref, t)
        t = re.sub(r'\\[Cc]refrange\{([^}]+)\}\{([^}]+)\}',
                   lambda m: f'Chapters {m.group(1)}–{m.group(2)}', t)
        t = re.sub(r'\\ref\{([^}]+)\}', lambda m: f'<a href="#{m.group(1)}">[ref]</a>', t)

        # Misc formatting
        t = t.replace('---', '—').replace('--', '–')
        t = t.replace('\\&', '&amp;').replace('\\%', '%')
        t = t.replace('\\$', '$').replace('\\_', '_').replace('\\#', '#')
        t = re.sub(r'(?<!\\)~', '\u00a0', t)

        # Remove remaining commands
        t = re.sub(r'\\[a-zA-Z]+\*?\{((?:[^{}]|\{[^{}]*\})*)\}', r'\1', t)
        t = re.sub(r'\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\s*', '', t)
        t = re.sub(r'[{}]', '', t)

        # Restore math
        for k, v in maths.items():
            t = t.replace(k, v)
        return t

    def _cref(self, m) -> str:
        labels = [l.strip() for l in m.group(1).split(',')]
        parts = []
        for lab in labels:
            # Map chapter labels to chapter pages
            for ch_slug, ch_title in CHAPTERS:
                if ch_slug.replace('chapter-', '') in lab or lab in ch_slug:
                    parts.append(f'<a href="../chapters/{ch_slug}.html" class="internal-ref">{ch_title}</a>')
                    break
            else:
                clean = lab.replace(':', '-').replace('_', '-')
                parts.append(f'<a href="#{clean}" class="internal-ref">{lab}</a>')
        return ', '.join(parts)

    def _citations(self, t: str) -> str:
        def link(key: str) -> str:
            self.citations_used.add(key)
            e = self.bib.get(key, {})
            surname = get_first_author_surname(e.get('author', ''))
            year = e.get('year', '')
            title = html.escape(e.get('title', key)[:80])
            label = f"{surname}, {year}" if surname != 'Unknown' and year else key
            return (f'<a href="../papers/{html.escape(key)}.html" '
                    f'class="cite" title="{title}">[{html.escape(label)}]</a>')

        def cite_group(m):
            keys = [k.strip() for k in m.group(1).split(',')]
            return '<span class="cite-group">' + ''.join(link(k) for k in keys if k) + '</span>'

        def cite_t(m):
            keys = [k.strip() for k in m.group(1).split(',')]
            parts = []
            for key in keys:
                self.citations_used.add(key)
                e = self.bib.get(key, {})
                surname = get_first_author_surname(e.get('author', ''))
                year = e.get('year', '')
                title = html.escape(e.get('title', key)[:80])
                display = f"{surname} ({year})" if surname != 'Unknown' and year else key
                parts.append(f'<a href="../papers/{html.escape(key)}.html" class="cite" title="{title}">{html.escape(display)}</a>')
            return ', '.join(parts)

        t = re.sub(r'\\citep\{([^}]+)\}', cite_group, t)
        t = re.sub(r'\\cite\{([^}]+)\}', cite_group, t)
        t = re.sub(r'\\citealp\{([^}]+)\}', cite_group, t)
        t = re.sub(r'\\citealt\{([^}]+)\}', cite_group, t)
        t = re.sub(r'\\citet\{([^}]+)\}', cite_t, t)
        t = re.sub(r'\\citeauthor\{([^}]+)\}', cite_t, t)
        t = re.sub(r'\\citeyear\{([^}]+)\}', lambda m: self.bib.get(m.group(1), {}).get('year', m.group(1)), t)
        return t

    def _paragraphs(self, t: str) -> str:
        # Recognize all block-level elements so they don't get wrapped in <p>
        BLOCK = re.compile(
            r'^<(?:h[2-6]|figure|img\b|figcaption|ul|ol|li\b|blockquote|div|table|thead|tbody|tr\b|td\b|th\b|p\b|pre\b|details|summary)',
            re.I
        )
        CLOSE = re.compile(r'^</', re.I)
        buf, out = [], []

        def flush():
            s = ' '.join(buf).strip()
            if s:
                out.append(f'<p>{s}</p>')
            buf.clear()

        for line in t.split('\n'):
            s = line.strip()
            if not s:
                flush()
            elif BLOCK.match(s) or CLOSE.match(s):
                flush()
                out.append(s)
            else:
                buf.append(s)

        flush()
        return '\n'.join(out)


# ── HTML Templates ─────────────────────────────────────────────────────────────

def page_shell(title: str, content: str, extra_head: str = "", root: str = "..") -> str:
    """Wrap content in full HTML page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="{root}/css/style.css">
  <script>
    // Apply saved theme before render
    (function(){{
      const t = localStorage.getItem('theme');
      if(t === 'dark') document.documentElement.classList.add('dark');
    }})();
  </script>
  {extra_head}
</head>
<body>
{_navbar(root)}
<div id="page-wrapper">
{content}
</div>
{_footer()}
<script src="{root}/js/main.js"></script>
</body>
</html>"""


def _navbar(root: str) -> str:
    return f"""<nav class="site-nav">
  <div class="nav-inner">
    <a href="{root}/index.html" class="nav-brand">
      <img src="{root}/assets/university-logo.png" alt="University Logo" class="nav-logo" onerror="this.style.display='none'">
      <span class="nav-title">ML for REIMS</span>
    </a>
    <div class="nav-links">
      <a href="{root}/index.html">Home</a>
      <a href="{root}/chapters/chapter-1.html">Chapters</a>
      <a href="{root}/papers.html">Papers</a>
    </div>
    <div class="nav-actions">
      <button id="search-toggle" class="icon-btn" aria-label="Search">🔍</button>
      <button id="theme-toggle" class="icon-btn" aria-label="Toggle theme">🌙</button>
      <button id="menu-toggle" class="icon-btn" aria-label="Menu">☰</button>
    </div>
  </div>
  <div id="mobile-menu" class="mobile-menu hidden">
    <a href="{root}/index.html">Home</a>
    <a href="{root}/chapters/chapter-1.html">Chapters</a>
    <a href="{root}/papers.html">All Papers</a>
  </div>
  <div id="search-bar" class="search-bar hidden">
    <input type="text" id="search-input" placeholder="Search papers, concepts, authors…" autocomplete="off">
    <div id="search-results" class="search-results"></div>
  </div>
</nav>"""


def _footer() -> str:
    return """<footer class="site-footer">
  <div class="footer-inner">
    <p>
      <strong>Jesse Wood</strong> · PhD Thesis · Victoria University of Wellington · 2025
    </p>
    <p class="footer-sub">Machine Learning for Rapid Evaporative Ionization Mass Spectrometry for Marine Biomass Analysis</p>
  </div>
</footer>"""


def toc_html(items: List[Tuple[int, str, str]]) -> str:
    if not items:
        return ""
    lines = ['<nav class="toc"><h4>Contents</h4><ol class="toc-list">']
    for level, title, sid in items:
        indent = "toc-l2" if level == 2 else ("toc-l3" if level == 3 else "toc-l4")
        lines.append(f'  <li class="{indent}"><a href="#{sid}">{html.escape(title)}</a></li>')
    lines.append('</ol></nav>')
    return '\n'.join(lines)


# ── Page Generators ────────────────────────────────────────────────────────────

def build_index(bib: Dict, ss: Dict, chapter_citations: Dict[str, Set[str]]) -> str:
    """Generate homepage."""
    m = THESIS_META

    # Chapter cards
    chapter_cards = ""
    for i, (slug, title) in enumerate(CHAPTERS):
        num = slug.replace('chapter-', '')
        label = f"Ch. {num}" if num.isdigit() else "Preface"
        cites = len(chapter_citations.get(slug, set()))
        chapter_cards += f"""
    <a href="chapters/{slug}.html" class="chapter-card">
      <div class="chapter-num">{label}</div>
      <div class="chapter-card-title">{html.escape(title)}</div>
      <div class="chapter-meta">{cites} citations</div>
    </a>"""

    # Results table
    results_rows = ""
    for task, baseline, best, gain in m['results']:
        results_rows += f"""
      <tr>
        <td>{html.escape(task)}</td>
        <td class="text-muted">{html.escape(baseline)}</td>
        <td><strong>{html.escape(best)}</strong></td>
        <td class="gain">{html.escape(gain)}</td>
      </tr>"""

    # Method tags
    method_tags = ''.join(f'<span class="tag">{html.escape(t)}</span>' for t in m['key_methods'])
    topic_tags = ''.join(f'<span class="tag tag-blue">{html.escape(t)}</span>' for t in m['key_topics'])

    content = f"""
<div class="hero">
  <div class="hero-inner">
    <div class="hero-badge">PhD Thesis · 2025</div>
    <h1 class="hero-title">{html.escape(m['title'])}</h1>
    <p class="hero-author">by <strong>{html.escape(m['author'])}</strong> · {html.escape(m['university'])}</p>
    <div class="hero-tags">{topic_tags}</div>
  </div>
</div>

<div class="main-content">
  <div class="content-cols">
    <main class="content-main">

      <section class="wiki-section">
        <h2>Abstract</h2>
        <p class="abstract-text">{html.escape(m['abstract'])}</p>
      </section>

      <section class="wiki-section">
        <h2>Key Results</h2>
        <p>Deep learning methods consistently outperform the OPLS-DA baseline across all five analytical tasks:</p>
        <div class="table-wrap">
        <table class="results-table">
          <thead><tr><th>Task</th><th>Baseline (OPLS-DA)</th><th>Best Model</th><th>Gain</th></tr></thead>
          <tbody>{results_rows}</tbody>
        </table>
        </div>
      </section>

      <section class="wiki-section">
        <h2>Methods &amp; Approaches</h2>
        <div class="tags-block">{method_tags}</div>
      </section>

      <section class="wiki-section">
        <h2>Chapters</h2>
        <div class="chapter-grid">{chapter_cards}
        </div>
      </section>

    </main>

    <aside class="content-aside">
      <div class="info-box">
        <h4>Thesis at a Glance</h4>
        <dl>
          <dt>Author</dt><dd>{html.escape(m['author'])}</dd>
          <dt>Institution</dt><dd>{html.escape(m['university'])}</dd>
          <dt>Year</dt><dd>{html.escape(m['year'])}</dd>
          <dt>Subject</dt><dd>{html.escape(m['subject'])}</dd>
          <dt>Chapters</dt><dd>{len(CHAPTERS)}</dd>
          <dt>References</dt><dd>{len(bib)}</dd>
        </dl>
      </div>
      <div class="info-box">
        <h4>Quick Links</h4>
        <ul class="quick-links">
          <li><a href="chapters/chapter-1.html">→ Introduction</a></li>
          <li><a href="chapters/chapter-2.html">→ Literature Survey</a></li>
          <li><a href="chapters/chapter-4.html">→ Species Identification</a></li>
          <li><a href="chapters/chapter-5.html">→ Contamination Detection</a></li>
          <li><a href="chapters/chapter-6.html">→ Batch Traceability</a></li>
          <li><a href="papers.html">→ All 374 Papers</a></li>
        </ul>
      </div>
      <div class="info-box">
        <h4>Novel Contributions</h4>
        <ul class="contrib-list">
          <li>First Transformer application to REIMS biomass analysis</li>
          <li>First MoE Transformer for REIMS data</li>
          <li>SpectroSim: self-supervised batch traceability</li>
          <li>First REIMS-based oil contamination detection</li>
          <li>First REIMS-based cross-species adulteration detection</li>
        </ul>
      </div>
    </aside>
  </div>
</div>
"""
    return page_shell(f"{m['title']}", content, root=".")


def build_chapter(slug: str, title: str, latex: str, bib: Dict,
                  ss: Dict, all_citations: Dict[str, Set[str]]) -> str:
    """Generate a chapter page."""
    idx = [i for i, (s, _) in enumerate(CHAPTERS) if s == slug][0]
    converter = LatexConverter(bib, slug)
    # Tell the converter where to write table PNG images
    converter._table_assets_dir = str(SITE_DIR / "assets")
    body_html = converter.convert(latex)
    cites_used = converter.citations_used

    # Prev/Next
    prev_link = next_link = ""
    if idx > 0:
        ps, pt = CHAPTERS[idx - 1]
        prev_link = f'<a href="{ps}.html" class="nav-btn">← {html.escape(pt)}</a>'
    if idx < len(CHAPTERS) - 1:
        ns, nt = CHAPTERS[idx + 1]
        next_link = f'<a href="{ns}.html" class="nav-btn">{html.escape(nt)} →</a>'

    # References used in this chapter
    ref_items = ""
    sorted_cites = sorted(cites_used, key=lambda k: (
        get_first_author_surname(bib.get(k, {}).get('author', '')),
        bib.get(k, {}).get('year', '')
    ))
    for key in sorted_cites:
        e = bib.get(key, {})
        surname = get_first_author_surname(e.get('author', ''))
        year = e.get('year', '')
        etitle = html.escape(e.get('title', key))
        ss_data = ss.get(key)
        cc = ss_data.get('citationCount', '') if ss_data else ''
        cc_txt = f' · {cc:,} citations' if isinstance(cc, int) else ''
        ref_items += f'<li><a href="../papers/{html.escape(key)}.html">{html.escape(surname)} ({html.escape(year)})</a> — {etitle}{cc_txt}</li>\n'

    toc = toc_html(converter.toc)
    num = slug.replace('chapter-', '')

    mathjax = """<script>
  window.MathJax = {
    tex: {
      inlineMath: [['\\\\(', '\\\\)']],
      displayMath: [['\\\\[', '\\\\]']],
      processEscapes: true
    },
    options: { skipHtmlTags: ['script','noscript','style','textarea','pre'] },
    startup: { typeset: true }
  };
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js" id="MathJax-script" async></script>"""

    content = f"""
<div class="chapter-layout">
  <aside class="chapter-sidebar">
    <div class="sidebar-sticky">
      <div class="chapter-info">
        <div class="chapter-num-badge">Chapter {html.escape(num)}</div>
        <div class="back-link"><a href="../index.html">← Home</a></div>
      </div>
      {toc}
      <div class="chapter-nav">
        {prev_link}
        {next_link}
      </div>
    </div>
  </aside>

  <main class="chapter-main">
    <header class="chapter-header">
      <div class="chapter-label">Chapter {html.escape(num)}</div>
      <h1>{html.escape(title)}</h1>
    </header>

    <article class="chapter-content">
      {body_html}
    </article>

    <section class="chapter-references">
      <h2>References ({len(sorted_cites)})</h2>
      <ol class="ref-list">
        {ref_items}
      </ol>
    </section>

    <div class="chapter-nav-bottom">
      {prev_link}
      {next_link}
    </div>
  </main>
</div>
"""
    return page_shell(f"{title} — ML for REIMS", content, extra_head=mathjax)


def build_paper(key: str, entry: Dict, ss_data: Optional[dict],
                cited_in: Dict[str, str]) -> str:
    """Generate a paper detail page."""
    title = ss_data.get('title', entry.get('title', key)) if ss_data else entry.get('title', key)
    year = entry.get('year', '')

    # Authors
    if ss_data and ss_data.get('authors'):
        authors_list = [a.get('name', '') for a in ss_data['authors']]
        if len(authors_list) > 6:
            authors_str = ', '.join(authors_list[:6]) + ' et al.'
        else:
            authors_str = ', '.join(authors_list)
    else:
        authors_str = format_authors(entry.get('author', ''))

    venue = ''
    if ss_data:
        venue = ss_data.get('venue', '') or ''
    if not venue:
        venue = entry.get('journal', '') or entry.get('booktitle', '') or entry.get('howpublished', '')
    venue = venue[:100]

    abstract = ''
    if ss_data and ss_data.get('abstract'):
        abstract = ss_data['abstract']
    elif entry.get('abstract'):
        abstract = entry['abstract']

    cc = ss_data.get('citationCount', None) if ss_data else None

    # External links
    ext_links = []
    if ss_data and ss_data.get('externalIds'):
        eids = ss_data['externalIds']
        if eids.get('DOI'):
            ext_links.append(f'<a href="https://doi.org/{eids["DOI"]}" target="_blank" class="ext-link">DOI ↗</a>')
        if eids.get('ArXiv'):
            ext_links.append(f'<a href="https://arxiv.org/abs/{eids["ArXiv"]}" target="_blank" class="ext-link">arXiv ↗</a>')
    elif entry.get('doi'):
        ext_links.append(f'<a href="https://doi.org/{entry["doi"]}" target="_blank" class="ext-link">DOI ↗</a>')
    if ss_data and ss_data.get('openAccessPdf') and ss_data['openAccessPdf'].get('url'):
        ext_links.append(f'<a href="{ss_data["openAccessPdf"]["url"]}" target="_blank" class="ext-link pdf-link">PDF ↗</a>')

    # Chapters that cite this paper
    cite_chips = ''
    for ch_slug, ch_title in cited_in.items():
        cite_chips += f'<a href="../chapters/{ch_slug}.html" class="cite-chip">{html.escape(ch_title)}</a>'

    # BibTeX
    bibtex_lines = [f'@{entry.get("type","misc")}{{{key},']
    skip = {'type', 'key'}
    for k, v in entry.items():
        if k not in skip:
            bibtex_lines.append(f'  {k} = {{{v}}},')
    bibtex_lines.append('}')
    bibtex_str = '\n'.join(bibtex_lines)

    abstract_block = f'<div class="abstract-block"><h3>Abstract</h3><p>{html.escape(abstract)}</p></div>' if abstract else ''
    cc_block = f'<span class="cite-count">Cited {cc:,} times</span>' if isinstance(cc, int) else ''
    links_block = ' '.join(ext_links)

    content = f"""
<div class="paper-layout">
  <main class="paper-main">
    <div class="breadcrumb"><a href="../index.html">Home</a> / <a href="../papers.html">Papers</a> / {html.escape(key)}</div>

    <article class="paper-article">
      <header class="paper-header">
        <h1 class="paper-title">{html.escape(title)}</h1>
        <p class="paper-authors">{html.escape(authors_str)}</p>
        <div class="paper-meta">
          {f'<span class="paper-year">{html.escape(year)}</span>' if year else ''}
          {f'<span class="paper-venue">{html.escape(venue)}</span>' if venue else ''}
          {cc_block}
        </div>
        <div class="paper-links">{links_block}</div>
      </header>

      {abstract_block}

      {f'<div class="cited-in-block"><h3>Cited in this thesis</h3><div class="cite-chips">{cite_chips}</div></div>' if cite_chips else ''}

      <details class="bibtex-block">
        <summary>BibTeX</summary>
        <pre><code>{html.escape(bibtex_str)}</code></pre>
      </details>
    </article>
  </main>
</div>
"""
    return page_shell(f"{title[:60]}… — ML for REIMS", content)


def build_papers_index(bib: Dict, ss: Dict, chapter_citations: Dict[str, Set[str]]) -> str:
    """Generate papers index page."""
    # Build reverse map: key → list of (chapter_slug, chapter_title)
    paper_chapters: Dict[str, List[Tuple[str, str]]] = {}
    for ch_slug, ch_title in CHAPTERS:
        for key in chapter_citations.get(ch_slug, set()):
            paper_chapters.setdefault(key, []).append((ch_slug, ch_title))

    # Sort alphabetically by first author surname
    sorted_keys = sorted(bib.keys(), key=lambda k: (
        get_first_author_surname(bib[k].get('author', '')).lower(),
        bib[k].get('year', '')
    ))

    cards = ""
    for key in sorted_keys:
        e = bib[key]
        ss_d = ss.get(key)
        title = ss_d.get('title', e.get('title', key)) if ss_d else e.get('title', key)
        surname = get_first_author_surname(e.get('author', ''))
        year = e.get('year', '')
        venue = ''
        if ss_d:
            venue = ss_d.get('venue', '') or ''
        if not venue:
            venue = e.get('journal', '') or e.get('booktitle', '') or ''
        venue = venue[:60]
        cc = ss_d.get('citationCount', None) if ss_d else None

        ch_links = ''
        for cs, ct in paper_chapters.get(key, []):
            ch_links += f'<a href="chapters/{cs}.html" class="mini-chip">{html.escape(ct[:20])}</a>'

        cc_str = f'<span class="cc">{cc:,} cites</span>' if isinstance(cc, int) else ''

        cards += f"""
<div class="paper-card" data-title="{html.escape(title.lower())}" data-author="{html.escape(surname.lower())}" data-year="{html.escape(year)}">
  <a href="papers/{html.escape(key)}.html" class="paper-card-link">
    <div class="paper-card-title">{html.escape(title[:120])}</div>
    <div class="paper-card-meta">
      <span class="pc-author">{html.escape(surname)}</span>
      {f'<span class="pc-year">({html.escape(year)})</span>' if year else ''}
      {f'<span class="pc-venue">{html.escape(venue)}</span>' if venue else ''}
      {cc_str}
    </div>
    <div class="paper-card-chips">{ch_links}</div>
  </a>
</div>"""

    content = f"""
<div class="papers-page">
  <header class="papers-header">
    <h1>All References ({len(bib)})</h1>
    <p>Papers, books, and other sources cited in the thesis.</p>
    <input type="text" id="paper-filter" placeholder="Filter by title, author, year…" class="filter-input" autocomplete="off">
    <div class="filter-stats" id="filter-stats">{len(bib)} papers</div>
  </header>
  <div class="papers-grid" id="papers-grid">
    {cards}
  </div>
</div>
"""
    return page_shell("All References — ML for REIMS", content, root=".")


# ── CSS ────────────────────────────────────────────────────────────────────────

CSS = r"""
/* ── Reset & Base ───────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #ffffff;
  --bg-alt: #f8f9fa;
  --bg-card: #ffffff;
  --border: #e0e0e0;
  --text: #202122;
  --text-muted: #54595d;
  --accent: #1a73e8;
  --accent-hover: #1557b0;
  --accent-light: #e8f0fe;
  --green: #1e7e34;
  --red: #c0392b;
  --nav-bg: #1e2a3a;
  --nav-text: #e8eaed;
  --hero-bg: linear-gradient(135deg, #1e2a3a 0%, #2c4a6e 100%);
  --shadow: 0 1px 3px rgba(0,0,0,0.1);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.12);
  --radius: 8px;
  --font: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  --font-mono: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
}

.dark {
  --bg: #0d1117;
  --bg-alt: #161b22;
  --bg-card: #1c2128;
  --border: #30363d;
  --text: #e6edf3;
  --text-muted: #8b949e;
  --accent: #58a6ff;
  --accent-hover: #79b8ff;
  --accent-light: #1c2a3c;
  --nav-bg: #010409;
  --nav-text: #e6edf3;
  --hero-bg: linear-gradient(135deg, #010409 0%, #0d1117 100%);
}

html { scroll-behavior: smooth; }

body {
  font-family: var(--font);
  font-size: 16px;
  line-height: 1.7;
  color: var(--text);
  background: var(--bg);
  transition: background 0.2s, color 0.2s;
}

a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; color: var(--accent-hover); }

/* ── Nav ────────────────────────────────────────────────────── */
.site-nav {
  background: var(--nav-bg);
  color: var(--nav-text);
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}

.nav-inner {
  max-width: 1300px;
  margin: 0 auto;
  padding: 0 1rem;
  height: 56px;
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--nav-text);
  text-decoration: none;
  flex-shrink: 0;
}
.nav-logo { height: 28px; width: auto; border-radius: 3px; }
.nav-title { font-weight: 700; font-size: 1rem; letter-spacing: -0.02em; }

.nav-links {
  display: flex;
  gap: 0.25rem;
  flex: 1;
}
.nav-links a {
  color: rgba(255,255,255,0.8);
  padding: 0.4rem 0.75rem;
  border-radius: 4px;
  font-size: 0.9rem;
  text-decoration: none;
  transition: background 0.15s, color 0.15s;
}
.nav-links a:hover { background: rgba(255,255,255,0.1); color: #fff; text-decoration: none; }

.nav-actions { display: flex; gap: 0.25rem; margin-left: auto; }
.icon-btn {
  background: none;
  border: none;
  color: rgba(255,255,255,0.8);
  cursor: pointer;
  padding: 0.4rem 0.5rem;
  border-radius: 4px;
  font-size: 1rem;
  line-height: 1;
  transition: background 0.15s;
}
.icon-btn:hover { background: rgba(255,255,255,0.1); }
#menu-toggle { display: none; }

.mobile-menu {
  background: var(--nav-bg);
  border-top: 1px solid rgba(255,255,255,0.1);
  padding: 0.5rem 1rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.mobile-menu a {
  color: rgba(255,255,255,0.85);
  padding: 0.5rem 0.5rem;
  border-radius: 4px;
  font-size: 0.95rem;
}
.mobile-menu a:hover { background: rgba(255,255,255,0.08); text-decoration: none; }

.search-bar {
  background: var(--nav-bg);
  border-top: 1px solid rgba(255,255,255,0.1);
  padding: 0.75rem 1rem;
  position: relative;
}
.search-bar input {
  width: 100%;
  max-width: 600px;
  padding: 0.5rem 1rem;
  border-radius: 24px;
  border: 1px solid rgba(255,255,255,0.2);
  background: rgba(255,255,255,0.08);
  color: var(--nav-text);
  font-size: 0.95rem;
  outline: none;
}
.search-bar input:focus { border-color: var(--accent); background: rgba(255,255,255,0.12); }
.search-results {
  position: absolute;
  top: calc(100% + 4px);
  left: 1rem;
  right: 1rem;
  max-width: 600px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-md);
  max-height: 400px;
  overflow-y: auto;
  z-index: 200;
}
.search-result-item {
  padding: 0.6rem 1rem;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
}
.search-result-item:hover { background: var(--bg-alt); }
.search-result-item:last-child { border-bottom: none; }
.sri-title { font-size: 0.9rem; font-weight: 500; color: var(--text); }
.sri-meta { font-size: 0.8rem; color: var(--text-muted); }

.hidden { display: none !important; }

/* ── Hero ────────────────────────────────────────────────────── */
.hero {
  background: var(--hero-bg);
  color: #fff;
  padding: 4rem 1rem 3rem;
}
.hero-inner {
  max-width: 900px;
  margin: 0 auto;
}
.hero-badge {
  display: inline-block;
  background: rgba(255,255,255,0.15);
  border: 1px solid rgba(255,255,255,0.25);
  padding: 0.25rem 0.75rem;
  border-radius: 20px;
  font-size: 0.8rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  margin-bottom: 1rem;
}
.hero-title {
  font-size: clamp(1.4rem, 4vw, 2.4rem);
  font-weight: 800;
  line-height: 1.25;
  margin-bottom: 0.75rem;
  letter-spacing: -0.03em;
}
.hero-author {
  font-size: 1rem;
  opacity: 0.85;
  margin-bottom: 1rem;
}
.hero-tags { display: flex; flex-wrap: wrap; gap: 0.4rem; }

/* ── Tags ───────────────────────────────────────────────────── */
.tag {
  display: inline-block;
  background: rgba(255,255,255,0.15);
  border: 1px solid rgba(255,255,255,0.2);
  color: rgba(255,255,255,0.9);
  padding: 0.2rem 0.65rem;
  border-radius: 20px;
  font-size: 0.78rem;
  font-weight: 500;
}
.tags-block .tag {
  background: var(--accent-light);
  border: 1px solid rgba(26,115,232,0.3);
  color: var(--accent);
}
.tag-blue {
  background: rgba(26,115,232,0.12);
  border-color: rgba(26,115,232,0.3);
  color: var(--accent);
}

/* ── Layout ─────────────────────────────────────────────────── */
#page-wrapper { min-height: calc(100vh - 56px - 80px); }

.main-content {
  max-width: 1300px;
  margin: 0 auto;
  padding: 2rem 1rem;
}
.content-cols {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 2rem;
  align-items: start;
}

/* ── Wiki Sections ───────────────────────────────────────────── */
.wiki-section {
  margin-bottom: 2.5rem;
}
.wiki-section h2 {
  font-size: 1.3rem;
  font-weight: 700;
  border-bottom: 2px solid var(--border);
  padding-bottom: 0.4rem;
  margin-bottom: 1rem;
}

/* ── Chapter Grid ─────────────────────────────────────────────── */
.chapter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.75rem;
}
.chapter-card {
  display: block;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem;
  text-decoration: none;
  transition: box-shadow 0.2s, transform 0.15s, border-color 0.2s;
}
.chapter-card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--accent);
  transform: translateY(-2px);
  text-decoration: none;
}
.chapter-num {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--accent);
  margin-bottom: 0.35rem;
}
.chapter-card-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text);
  line-height: 1.4;
  margin-bottom: 0.35rem;
}
.chapter-meta {
  font-size: 0.75rem;
  color: var(--text-muted);
}

/* ── Results Table ─────────────────────────────────────────── */
.table-wrap { overflow-x: auto; }
.results-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}
.results-table th {
  background: var(--bg-alt);
  border: 1px solid var(--border);
  padding: 0.6rem 0.75rem;
  text-align: left;
  font-weight: 600;
}
.results-table td {
  border: 1px solid var(--border);
  padding: 0.55rem 0.75rem;
}
.results-table tr:nth-child(even) td { background: var(--bg-alt); }
.text-muted { color: var(--text-muted); }
.gain { color: var(--green); font-weight: 700; }

/* ── Info Box / Aside ─────────────────────────────────────── */
.info-box {
  background: var(--bg-alt);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem 1.25rem;
  margin-bottom: 1rem;
}
.info-box h4 {
  font-size: 0.85rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  margin-bottom: 0.75rem;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.5rem;
}
.info-box dl { display: grid; grid-template-columns: auto 1fr; gap: 0.3rem 0.75rem; font-size: 0.88rem; }
.info-box dt { font-weight: 600; color: var(--text-muted); white-space: nowrap; }
.info-box dd { color: var(--text); }
.quick-links, .contrib-list { list-style: none; font-size: 0.88rem; }
.quick-links li, .contrib-list li { padding: 0.2rem 0; }
.contrib-list li { padding-left: 1rem; position: relative; font-size: 0.85rem; color: var(--text-muted); }
.contrib-list li::before { content: '✓'; position: absolute; left: 0; color: var(--green); font-weight: 700; }

/* ── Chapter Page ─────────────────────────────────────────── */
.chapter-layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  max-width: 1200px;
  margin: 0 auto;
  align-items: start;
  min-height: calc(100vh - 56px);
}
.chapter-sidebar {
  border-right: 1px solid var(--border);
  background: var(--bg-alt);
  min-height: calc(100vh - 56px);
}
.sidebar-sticky {
  position: sticky;
  top: 56px;
  padding: 1.5rem 1rem;
  max-height: calc(100vh - 56px);
  overflow-y: auto;
}
.chapter-info { margin-bottom: 1rem; }
.chapter-num-badge {
  display: inline-block;
  background: var(--accent);
  color: #fff;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.15rem 0.5rem;
  border-radius: 3px;
  margin-bottom: 0.5rem;
}
.back-link { font-size: 0.85rem; }

.toc { margin-bottom: 1.5rem; }
.toc h4 {
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--text-muted);
  margin-bottom: 0.5rem;
}
.toc-list { list-style: none; font-size: 0.85rem; }
.toc-list li { margin: 0.15rem 0; }
.toc-list a {
  color: var(--text-muted);
  text-decoration: none;
  display: block;
  padding: 0.15rem 0;
  border-left: 2px solid transparent;
  padding-left: 0.5rem;
  transition: color 0.15s, border-color 0.15s;
  line-height: 1.4;
}
.toc-list a:hover { color: var(--accent); border-color: var(--accent); text-decoration: none; }
.toc-l3 a { padding-left: 1.25rem; font-size: 0.82rem; }
.toc-l4 a { padding-left: 2rem; font-size: 0.8rem; }

.chapter-nav { display: flex; flex-direction: column; gap: 0.4rem; padding-top: 1rem; border-top: 1px solid var(--border); }
.nav-btn {
  display: block;
  padding: 0.4rem 0.6rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 0.82rem;
  color: var(--text);
  text-decoration: none;
  transition: background 0.15s;
}
.nav-btn:hover { background: var(--accent-light); border-color: var(--accent); text-decoration: none; }

.chapter-main {
  padding: 2rem 2.5rem 3rem;
  max-width: 820px;
}
.chapter-header {
  margin-bottom: 2rem;
  padding-bottom: 1rem;
  border-bottom: 3px solid var(--accent);
}
.chapter-label {
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--accent);
  margin-bottom: 0.4rem;
}
.chapter-header h1 {
  font-size: clamp(1.5rem, 3vw, 2.2rem);
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: -0.03em;
}

/* ── Chapter Content ─────────────────────────────────────── */
.chapter-content h2 {
  font-size: 1.4rem;
  font-weight: 700;
  margin: 2rem 0 0.75rem;
  padding-bottom: 0.3rem;
  border-bottom: 1px solid var(--border);
  color: var(--text);
}
.chapter-content h3 {
  font-size: 1.15rem;
  font-weight: 700;
  margin: 1.5rem 0 0.6rem;
  color: var(--text);
}
.chapter-content h4 {
  font-size: 1rem;
  font-weight: 700;
  margin: 1.25rem 0 0.5rem;
  color: var(--text-muted);
}
.chapter-content p {
  margin-bottom: 1rem;
  color: var(--text);
}
.chapter-content ul, .chapter-content ol {
  margin: 0.75rem 0 1rem 1.5rem;
}
.chapter-content li { margin-bottom: 0.4rem; }
.chapter-content blockquote {
  border-left: 3px solid var(--accent);
  padding: 0.5rem 1rem;
  margin: 1rem 0;
  color: var(--text-muted);
  background: var(--bg-alt);
  border-radius: 0 4px 4px 0;
}
.chapter-content strong { font-weight: 700; }
.chapter-content em { font-style: italic; }
.chapter-content code {
  background: var(--bg-alt);
  border: 1px solid var(--border);
  border-radius: 3px;
  padding: 0.1em 0.4em;
  font-family: var(--font-mono);
  font-size: 0.88em;
}
.chapter-content .math { font-style: italic; }
.chapter-content .math-display {
  overflow-x: auto;
  margin: 1rem 0;
  padding: 0.5rem;
  background: var(--bg-alt);
  border-radius: 4px;
  text-align: center;
}

/* Citations */
.cite {
  color: var(--accent);
  font-size: 0.8em;
  text-decoration: none;
  vertical-align: super;
  line-height: 0;
}
.cite:hover { text-decoration: underline; }
.cite-group { white-space: nowrap; }
.internal-ref { color: var(--accent); }

/* Figures */
.thesis-figure {
  margin: 1.5rem 0;
  text-align: center;
  background: var(--bg-alt);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem;
}
.thesis-figure img {
  max-width: 100%;
  height: auto;
  border-radius: 4px;
}
.thesis-figure figcaption {
  margin-top: 0.5rem;
  font-size: 0.85rem;
  color: var(--text-muted);
  line-height: 1.5;
}
.pdf-figure-note, .img-missing {
  background: var(--bg-alt);
  border: 1px dashed var(--border);
  border-radius: 4px;
  padding: 1rem;
  color: var(--text-muted);
  font-size: 0.88rem;
}

/* Tables note */
.table-note {
  background: var(--bg-alt);
  border: 1px dashed var(--border);
  border-radius: 4px;
  padding: 0.75rem 1rem;
  color: var(--text-muted);
  font-size: 0.88rem;
  margin: 1rem 0;
}

/* ── Chapter References ───────────────────────────────────── */
.chapter-references {
  margin-top: 3rem;
  padding-top: 1.5rem;
  border-top: 2px solid var(--border);
}
.chapter-references h2 {
  font-size: 1.2rem;
  margin-bottom: 1rem;
  font-weight: 700;
}
.ref-list {
  list-style: decimal;
  margin-left: 1.5rem;
  font-size: 0.88rem;
  line-height: 1.7;
}
.ref-list li { margin-bottom: 0.25rem; }
.ref-list a { color: var(--accent); }

.chapter-nav-bottom {
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

/* ── Paper Page ───────────────────────────────────────────── */
.paper-layout { max-width: 860px; margin: 0 auto; padding: 2rem 1rem 3rem; }
.paper-main { }
.breadcrumb { font-size: 0.82rem; color: var(--text-muted); margin-bottom: 1.5rem; }
.breadcrumb a { color: var(--text-muted); }
.paper-article { }
.paper-header { margin-bottom: 1.5rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border); }
.paper-title { font-size: clamp(1.2rem, 2.5vw, 1.8rem); font-weight: 800; line-height: 1.3; margin-bottom: 0.5rem; }
.paper-authors { font-size: 0.92rem; color: var(--text-muted); margin-bottom: 0.5rem; }
.paper-meta { display: flex; flex-wrap: wrap; gap: 0.5rem; font-size: 0.85rem; margin-bottom: 0.75rem; }
.paper-year { font-weight: 700; color: var(--text); }
.paper-venue { color: var(--text-muted); font-style: italic; }
.cite-count { background: var(--accent-light); color: var(--accent); padding: 0.15rem 0.5rem; border-radius: 3px; font-weight: 600; font-size: 0.82rem; }
.paper-links { display: flex; flex-wrap: wrap; gap: 0.5rem; }
.ext-link {
  display: inline-block;
  padding: 0.3rem 0.8rem;
  border: 1px solid var(--accent);
  border-radius: 4px;
  font-size: 0.83rem;
  font-weight: 600;
  color: var(--accent);
  text-decoration: none;
  transition: background 0.15s;
}
.ext-link:hover { background: var(--accent-light); text-decoration: none; }
.pdf-link { background: var(--green); border-color: var(--green); color: #fff; }
.pdf-link:hover { background: #155724; }
.abstract-block { margin: 1.5rem 0; }
.abstract-block h3 { font-size: 1rem; font-weight: 700; margin-bottom: 0.5rem; }
.abstract-block p { font-size: 0.92rem; line-height: 1.7; color: var(--text-muted); }
.cited-in-block { margin: 1.5rem 0; }
.cited-in-block h3 { font-size: 1rem; font-weight: 700; margin-bottom: 0.5rem; }
.cite-chips { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.cite-chip {
  display: inline-block;
  padding: 0.25rem 0.65rem;
  background: var(--accent-light);
  color: var(--accent);
  border-radius: 20px;
  font-size: 0.82rem;
  font-weight: 500;
  text-decoration: none;
}
.cite-chip:hover { background: var(--accent); color: #fff; text-decoration: none; }
.bibtex-block {
  margin-top: 1.5rem;
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.bibtex-block summary {
  padding: 0.6rem 1rem;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.88rem;
  background: var(--bg-alt);
  border-radius: var(--radius);
  user-select: none;
}
.bibtex-block[open] summary { border-radius: var(--radius) var(--radius) 0 0; }
.bibtex-block pre {
  margin: 0;
  padding: 1rem;
  background: var(--bg);
  font-family: var(--font-mono);
  font-size: 0.82rem;
  overflow-x: auto;
  border-radius: 0 0 var(--radius) var(--radius);
}

/* ── Thesis Tables ────────────────────────────────────────── */
.table-wrap {
  overflow-x: auto;
  margin: 1.5rem 0;
  border-radius: var(--radius);
  border: 1px solid var(--border);
}
.thesis-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
  line-height: 1.5;
  background: var(--bg-card);
}
.thesis-table caption {
  text-align: left;
  padding: 0.6rem 0.75rem;
  font-size: 0.82rem;
  color: var(--text-muted);
  font-style: italic;
  background: var(--bg-alt);
  border-bottom: 1px solid var(--border);
  caption-side: top;
}
.thesis-table thead th {
  background: var(--bg-alt);
  font-weight: 700;
  text-align: left;
  padding: 0.5rem 0.75rem;
  border-bottom: 2px solid var(--border);
  white-space: nowrap;
}
.thesis-table tbody td {
  padding: 0.45rem 0.75rem;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
}
.thesis-table tbody tr:last-child td { border-bottom: none; }
.thesis-table tbody tr:nth-child(even) td { background: var(--bg-alt); }
.thesis-table tbody tr:hover td { background: var(--accent-light); }
.thesis-table strong { font-weight: 700; }

/* ── Papers Index ─────────────────────────────────────────── */
.papers-page { max-width: 1200px; margin: 0 auto; padding: 2rem 1rem; }
.papers-header { margin-bottom: 2rem; }
.papers-header h1 { font-size: 2rem; font-weight: 800; margin-bottom: 0.5rem; }
.papers-header p { color: var(--text-muted); margin-bottom: 1rem; }
.filter-input {
  width: 100%;
  max-width: 500px;
  padding: 0.6rem 1rem;
  border: 1px solid var(--border);
  border-radius: 24px;
  font-size: 0.95rem;
  background: var(--bg-alt);
  color: var(--text);
  outline: none;
  transition: border-color 0.15s;
}
.filter-input:focus { border-color: var(--accent); }
.filter-stats { font-size: 0.82rem; color: var(--text-muted); margin-top: 0.5rem; }

.papers-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 0.75rem;
}
.paper-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  transition: box-shadow 0.2s, border-color 0.2s;
}
.paper-card:hover { box-shadow: var(--shadow-md); border-color: var(--accent); }
.paper-card-link { display: block; padding: 0.9rem 1rem; text-decoration: none; }
.paper-card-link:hover { text-decoration: none; }
.paper-card-title {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text);
  line-height: 1.4;
  margin-bottom: 0.35rem;
}
.paper-card-meta { font-size: 0.78rem; color: var(--text-muted); display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 0.35rem; align-items: center; }
.pc-author { font-weight: 600; color: var(--text-muted); }
.pc-year { }
.pc-venue { font-style: italic; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cc { background: var(--accent-light); color: var(--accent); padding: 0.1rem 0.4rem; border-radius: 3px; font-weight: 600; white-space: nowrap; }
.paper-card-chips { display: flex; flex-wrap: wrap; gap: 0.25rem; }
.mini-chip {
  display: inline-block;
  padding: 0.1rem 0.4rem;
  background: var(--bg-alt);
  border: 1px solid var(--border);
  border-radius: 3px;
  font-size: 0.72rem;
  color: var(--text-muted);
  text-decoration: none;
}
.mini-chip:hover { background: var(--accent-light); border-color: var(--accent); color: var(--accent); text-decoration: none; }

/* ── Abstract ─────────────────────────────────────────────── */
.abstract-text {
  line-height: 1.75;
  font-size: 0.97rem;
  color: var(--text);
}

/* ── Footer ───────────────────────────────────────────────── */
.site-footer {
  background: var(--bg-alt);
  border-top: 1px solid var(--border);
  padding: 1.5rem 1rem;
  margin-top: 2rem;
}
.footer-inner {
  max-width: 1300px;
  margin: 0 auto;
  text-align: center;
  font-size: 0.85rem;
  color: var(--text-muted);
}
.footer-sub { font-size: 0.78rem; margin-top: 0.25rem; }

/* ── Tags block ───────────────────────────────────────────── */
.tags-block { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.tags-block .tag {
  background: var(--accent-light);
  border-color: rgba(26,115,232,0.3);
  color: var(--accent);
  font-size: 0.83rem;
}

/* ── Responsive ───────────────────────────────────────────── */
@media (max-width: 900px) {
  .content-cols { grid-template-columns: 1fr; }
  .content-aside { order: -1; }
  .chapter-layout { grid-template-columns: 1fr; }
  .chapter-sidebar { display: none; }
  .chapter-sidebar.open { display: block; border-right: none; border-bottom: 1px solid var(--border); }
  .chapter-main { padding: 1.5rem 1rem; }
  #menu-toggle { display: flex; }
  .nav-links { display: none; }
}
@media (max-width: 600px) {
  .hero { padding: 2.5rem 1rem 2rem; }
  .chapter-grid { grid-template-columns: 1fr 1fr; }
  .papers-grid { grid-template-columns: 1fr; }
  .paper-layout { padding: 1.5rem 0.75rem; }
}
"""

# ── JavaScript ─────────────────────────────────────────────────────────────────

JS = r"""
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
"""

# ── Main Build ─────────────────────────────────────────────────────────────────

def main():
    print("=== Thesis Wiki Generator ===\n")

    # 1. Parse BibTeX
    print("Step 1: Parsing BibTeX...")
    bib = parse_bibtex(THESIS_DIR / "refs.bib")

    # 2. Parse all chapters
    print("\nStep 2: Parsing chapter LaTeX...")
    chapter_latex = {}
    for slug, _ in CHAPTERS:
        path = THESIS_DIR / slug / "main.tex"
        if path.exists():
            chapter_latex[slug] = path.read_text(encoding='utf-8', errors='replace')
        else:
            chapter_latex[slug] = ""
            print(f"  Warning: {path} not found")

    # 3. Pre-run converters to collect citations per chapter
    print("\nStep 3: Collecting citations per chapter...")
    chapter_citations: Dict[str, Set[str]] = {}
    for slug, title in CHAPTERS:
        conv = LatexConverter(bib, slug)
        # Don't render table PNGs during the citation pre-pass
        conv._table_assets_dir = None
        conv.convert(chapter_latex.get(slug, ""))
        chapter_citations[slug] = conv.citations_used
        print(f"  {slug}: {len(conv.citations_used)} citations")

    # 4. Fetch Semantic Scholar data
    print("\nStep 4: Fetching Semantic Scholar metadata...")
    ss_data = fetch_semantic_scholar(bib)

    # 5. Build site
    print("\nStep 5: Building static site...")
    SITE_DIR.mkdir(exist_ok=True)
    (SITE_DIR / "chapters").mkdir(exist_ok=True)
    (SITE_DIR / "papers").mkdir(exist_ok=True)
    (SITE_DIR / "css").mkdir(exist_ok=True)
    (SITE_DIR / "js").mkdir(exist_ok=True)
    (SITE_DIR / "assets").mkdir(exist_ok=True)

    # Copy assets (PNG/JPG/etc.) and convert PDF figures → PNG
    assets_src = THESIS_DIR / "assets"
    assets_dst = SITE_DIR / "assets"
    if assets_src.exists():
        for f in assets_src.iterdir():
            if not f.is_file():
                continue
            if f.suffix.lower() == '.pdf':
                # Convert PDF to PNG (with pdfcrop to remove whitespace)
                out_png = assets_dst / (f.stem + '.png')
                if not out_png.exists():
                    if convert_pdf_to_png(f, out_png, resolution=200):
                        print(f"    Converted {f.name} → PNG")
                    else:
                        print(f"    Warning: could not convert {f.name} to PNG")
            else:
                shutil.copy2(f, assets_dst / f.name)
    print("  Assets copied (PDFs converted to PNG)")

    # Write CSS & JS
    (SITE_DIR / "css" / "style.css").write_text(CSS)
    (SITE_DIR / "js" / "main.js").write_text(JS)
    print("  CSS and JS written")

    # Homepage
    (SITE_DIR / "index.html").write_text(
        build_index(bib, ss_data, chapter_citations))
    print("  index.html done")

    # Chapters
    for slug, title in CHAPTERS:
        latex = chapter_latex.get(slug, "")
        html_out = build_chapter(slug, title, latex, bib, ss_data, chapter_citations)
        (SITE_DIR / "chapters" / f"{slug}.html").write_text(html_out)
        print(f"  chapters/{slug}.html done")

    # Build reverse map for paper pages: key → {ch_slug: ch_title}
    paper_chapter_map: Dict[str, Dict[str, str]] = {}
    for ch_slug, ch_title in CHAPTERS:
        for key in chapter_citations.get(ch_slug, set()):
            paper_chapter_map.setdefault(key, {})[ch_slug] = ch_title

    # Paper pages
    print("  Generating paper pages...")
    for i, (key, entry) in enumerate(bib.items()):
        ss = ss_data.get(key)
        cited_in = paper_chapter_map.get(key, {})
        html_out = build_paper(key, entry, ss, cited_in)
        (SITE_DIR / "papers" / f"{key}.html").write_text(html_out)
    print(f"  {len(bib)} paper pages done")

    # Papers index
    (SITE_DIR / "papers.html").write_text(
        build_papers_index(bib, ss_data, chapter_citations))
    print("  papers.html done")

    print(f"\n✅ Site built at: {SITE_DIR}")
    print(f"   Open: {SITE_DIR / 'index.html'}")


if __name__ == "__main__":
    main()
