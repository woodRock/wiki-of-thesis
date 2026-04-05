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

GLOSSARY = {
    "REIMS": {
        "full": "Rapid Evaporative Ionization Mass Spectrometry",
        "definition": "A direct-to-analysis technique that allows near-instantaneous chemical analysis of a sample with minimal to no preparation. A heated blade vaporizes tissue, and the resulting aerosol is directed into a mass spectrometer, producing a chemical fingerprint in seconds.",
        "category": "instrument",
    },
    "m/z": {
        "full": "Mass-to-Charge Ratio",
        "definition": "The x-axis of a mass spectrum, representing the ratio of an ion's mass to its charge. The REIMS dataset spans 2,080 distinct m/z features from approximately 77.04 to 999.32 m/z, each corresponding to a different molecular ion.",
        "category": "instrument",
    },
    "TIC": {
        "full": "Total Ion Current",
        "definition": "The sum of all detected ion intensities across all m/z values in a single mass spectrum. TIC normalization divides each feature by the total ion current to remove inter-sample variation in overall signal intensity.",
        "category": "instrument",
    },
    "OPLS-DA": {
        "full": "Orthogonal Partial Least Squares Discriminant Analysis",
        "definition": "A supervised chemometrics classification method that separates variation correlated with class labels (predictive) from orthogonal variation. Used as the primary baseline in this thesis, achieving up to 96% accuracy on species identification.",
        "category": "method",
    },
    "Batch Detection": {
        "full": "Batch Detection",
        "definition": "The task of determining whether two fish samples originate from the same processing batch. Enables rapid recalls if contamination is discovered. Formulated as a pairwise classification task using contrastive learning in this thesis.",
        "category": "task",
    },
    "Cross-species Adulteration": {
        "full": "Cross-species Adulteration",
        "definition": "Food fraud where a high-value fish species (Hoki) is mixed with a cheaper species (Mackerel). Formulated as a 3-class problem: pure Hoki, pure Mackerel, or a 50/50 mixture. Deep learning achieves 91.97% accuracy vs. 79.96% for OPLS-DA.",
        "category": "task",
    },
    "Oil Contamination": {
        "full": "Oil Contamination Detection",
        "definition": "Detection and quantification of oil (e.g., engine or processing equipment oil) introduced into fish samples. Formulated as a 7-class ordinal classification problem with oil concentrations from 0% to 50% in 10% increments.",
        "category": "task",
    },
    "Species Identification": {
        "full": "Fish Species Identification",
        "definition": "Classifying a REIMS spectrum to determine the fish species. A 2-class problem (Hoki vs. Mackerel) in this thesis, where MoE Transformer achieves 100% accuracy vs. 96.39% for OPLS-DA.",
        "category": "task",
    },
    "Body Part Identification": {
        "full": "Fish Body Part Identification",
        "definition": "Classifying which anatomical body part a fish sample originates from (e.g., fillet, frame, offal). A multi-class problem where Ensemble Transformer achieves 74.13% accuracy vs. 51.17% for OPLS-DA.",
        "category": "task",
    },
    "Marine Biomass": {
        "full": "Marine Biomass",
        "definition": "The total mass of all living marine organisms within a given area or ecosystem. In the context of this thesis, refers to the biological material (fish and shellfish) analyzed using REIMS for food quality and traceability applications.",
        "category": "domain",
    },
    "Transformer": {
        "full": "Transformer Neural Network",
        "definition": "A deep learning architecture based on self-attention mechanisms, introduced by Vaswani et al. (2017). Processes all elements of a sequence in parallel, capturing long-range dependencies. Applied to REIMS spectra as sequences of m/z values in this thesis.",
        "category": "model",
    },
    "MoE": {
        "full": "Mixture of Experts",
        "definition": "A neural network architecture where multiple specialized sub-networks (experts) process different inputs, gated by a learned router. The MoE Transformer achieves 100% species identification accuracy by routing different spectral regions to specialized expert networks.",
        "category": "model",
    },
    "SpectroSim": {
        "full": "SpectroSim",
        "definition": "A novel contrastive learning framework introduced in this thesis for label-free batch traceability. Uses a Transformer encoder within the SimCLR framework to learn pairwise similarity between mass spectra, achieving 70.8% batch detection accuracy without labeled data.",
        "category": "contribution",
    },
    "MSM": {
        "full": "Masked Spectra Modelling",
        "definition": "A novel self-supervised pre-training technique introduced in this thesis, adapting BERT's masked language modeling to sequential REIMS data. Random m/z features are masked and the model learns to reconstruct them, providing a useful initialization for downstream tasks.",
        "category": "contribution",
    },
    "Gone Phishing": {
        "full": "Gone Phishing (MoE Transformer)",
        "definition": "A novel Mixture of Experts (MoE) Transformer architecture introduced in this thesis for REIMS-based fish fraud detection — the name is a pun on fish and phishing. It replaces the standard feed-forward networks inside each Transformer encoder block with MoE layers: a learned gating mechanism routes each input token to the Top-k most relevant expert sub-networks, whose outputs are combined by a weighted sum. This allows the model to scale capacity without proportionally increasing compute. Achieves 100% accuracy on fish species identification.",
        "category": "contribution",
    },
    "Autobots": {
        "full": "Autobots (Multi-scale Ensemble Transformer)",
        "definition": "A stacked voting ensemble of multi-scale Transformers introduced in this thesis — the name is a pun on the Autobots, a team of diverse Transformers. Three independent Transformer models with 2, 4, and 8 layers/heads respectively act as level-0 base classifiers analyzing the spectrum at low, medium, and high resolution. Their outputs are fed into a learned weighted combination meta-model (level-1) that optimally combines each model's predictions. Achieves 74.13% accuracy on fish body part identification.",
        "category": "contribution",
    },
    "Ensemble Transformer": {
        "full": "Ensemble Transformer",
        "definition": "An architecture combining multiple Transformer models trained with different initializations or configurations. Achieves 74.13% body part identification accuracy by aggregating predictions from multiple specialized models.",
        "category": "model",
    },
    "LIME": {
        "full": "Local Interpretable Model-agnostic Explanations",
        "definition": "An explainability technique that approximates any black-box model locally with an interpretable surrogate. Applied to REIMS models in this thesis to identify which m/z features most influence individual predictions.",
        "category": "method",
    },
    "Grad-CAM": {
        "full": "Gradient-weighted Class Activation Mapping",
        "definition": "An explainability technique that uses gradients flowing into the final convolutional or attention layer to produce a saliency map. Applied to Transformer models in this thesis to visualize spectral regions important for classification.",
        "category": "method",
    },
    "Transfer Learning": {
        "full": "Transfer Learning",
        "definition": "A machine learning approach where a model pre-trained on one task or dataset is fine-tuned on a different but related task. In this thesis, models trained on species identification are adapted to oil contamination detection, improving accuracy by up to 22.67%.",
        "category": "method",
    },
    "Contrastive Learning": {
        "full": "Contrastive Learning",
        "definition": "A self-supervised learning paradigm that trains models to pull representations of similar samples together and push dissimilar samples apart. Used in SpectroSim for batch traceability without requiring labeled batch data.",
        "category": "method",
    },
    "SimCLR": {
        "full": "Simple Contrastive Learning of Representations",
        "definition": "A contrastive learning framework by Chen et al. (2020) that learns representations by maximizing agreement between differently augmented views of the same sample. SpectroSim adapts this framework for mass spectra.",
        "category": "method",
    },
    "BERT": {
        "full": "Bidirectional Encoder Representations from Transformers",
        "definition": "A pre-training language model using masked language modeling. Its masked-token objective inspired the Masked Spectra Modelling (MSM) technique in this thesis.",
        "category": "model",
    },
    "Self-supervised Learning": {
        "full": "Self-supervised Learning",
        "definition": "A machine learning paradigm that generates supervisory signals from the data itself, without human-labeled annotations. Used in this thesis for MSM pre-training and SpectroSim contrastive learning on REIMS spectra.",
        "category": "method",
    },
    "Hoki": {
        "full": "Hoki (Macruronus novaezelandiae)",
        "definition": "A deep-sea fish species native to New Zealand waters, used as the high-value species in cross-species adulteration experiments. New Zealand is the world's largest exporter of Hoki, making it a target for seafood fraud.",
        "category": "domain",
    },
    "Mackerel": {
        "full": "Mackerel (Scomber japonicus)",
        "definition": "A pelagic fish species used as the adulterant in cross-species adulteration experiments. Less expensive than Hoki but with a similar appearance when processed, making it a common seafood fraud target.",
        "category": "domain",
    },
    "Food Fraud": {
        "full": "Food Fraud",
        "definition": "Deliberate adulteration, mislabeling, or misrepresentation of food products for economic gain. Seafood fraud is estimated to affect 30% of commercially sold seafood globally, driving the need for rapid verification tools like REIMS.",
        "category": "domain",
    },
    "Species Substitution": {
        "full": "Species Substitution",
        "definition": "A form of food fraud where a premium fish species is replaced with a cheaper alternative. Detected in this thesis using REIMS-based classification, achieving up to 100% accuracy with Transformer models.",
        "category": "domain",
    },
    "IUU Fishing": {
        "full": "Illegal, Unreported and Unregulated Fishing",
        "definition": "Fishing activities that contravene national and international laws, including fishing without authorization, under-reporting catches, and operating in restricted areas. REIMS-based species identification can help verify the provenance of seafood products.",
        "category": "domain",
    },
    "Chemical Fingerprint": {
        "full": "Chemical Fingerprint",
        "definition": "The characteristic pattern of molecular ions detected in a mass spectrum, unique to a given biological sample. REIMS produces chemical fingerprints of tissue that encode species, body part, and contamination information.",
        "category": "instrument",
    },
    "Ordinal Classification": {
        "full": "Ordinal Classification",
        "definition": "Classification where the target classes have a natural ordering (e.g., 0%, 10%, 20% oil concentration). Standard classification ignores this ordering; ordinal methods exploit it. Used for oil contamination detection in this thesis.",
        "category": "method",
    },
    "BCA": {
        "full": "Balanced Classification Accuracy",
        "definition": "An accuracy metric that averages per-class recall, compensating for class imbalance. Used as the primary evaluation metric in this thesis to fairly compare models across unbalanced datasets.",
        "category": "method",
    },
    "MAE": {
        "full": "Mean Absolute Error",
        "definition": "The average absolute difference between predicted and true values. Used alongside BCA for ordinal classification tasks (oil contamination, adulteration) where the magnitude of classification error matters.",
        "category": "method",
    },
    "Negative Ionization Mode": {
        "full": "Negative Ionization Mode",
        "definition": "A mass spectrometry acquisition mode in which negatively charged ions are detected. REIMS in negative ionization mode primarily detects lipid-related compounds (fatty acids, phospholipids) that form the chemical fingerprint of fish tissue.",
        "category": "instrument",
    },
    "PCA": {
        "full": "Principal Component Analysis",
        "definition": "A linear dimensionality reduction technique that projects data onto axes of maximum variance. Used for visualization and as a preprocessing step, but outperformed by deep learning methods on REIMS classification tasks.",
        "category": "method",
    },
    "SVM": {
        "full": "Support Vector Machine",
        "definition": "A supervised learning algorithm that finds the optimal hyperplane separating classes in a high-dimensional feature space. Used as a baseline classifier in this thesis.",
        "category": "model",
    },
    "KNN": {
        "full": "K-Nearest Neighbours",
        "definition": "A non-parametric classification algorithm that assigns a label based on the majority class among the k nearest training samples. Used as a baseline classifier in this thesis.",
        "category": "model",
    },
}

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
    "subject": "Artificial Intelligence",
    "degree": "Doctor of Philosophy in Artificial Intelligence",
    "course_code": "AIML 694",
    "school": "Te Whiri Kawe | Centre for Data Science and Artificial Intelligence",
    "supervisors": [
        "Dr. Bach Nguyen",
        "Prof. Bing Xue",
        "Prof. Mengjie Zhang",
        "Dr. Daniel Killeen",
    ],
    "duration": "3.5 years",
    "experiments": "3,000+",
    "tasks": 5,
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

    # Normalize entries where the closing } is on the same line as the last field
    # e.g. "  month={Oct},}" → "  month={Oct},\n}"
    content = re.sub(r'\},\}(\s*\n)', r'},\n}\1', content)

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

        # sips (macOS fallback) — use -Z 2000 to ensure high-res output
        if platform.system() == 'Darwin' and _has_tool('sips'):
            r = subprocess.run(
                ['sips', '-s', 'format', 'png', '-Z', '2000', str(cropped_pdf), '--out', str(out_path)],
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

    # Separate entries: those with DOI/CorpusID (batch lookup) vs those with only title (search)
    doi_entries = {}     # {key: id_string}  e.g. "DOI:10.x/y" or "CorpusID:12345"
    title_entries = {}   # {key: title}

    for key, entry in bib_entries.items():
        if key in cache:
            results[key] = cache[key]
            continue
        doi = entry.get('doi', '').strip()
        url = entry.get('url', '').strip()
        # Extract Semantic Scholar CorpusID from url field if present
        corpus_m = re.search(r'semanticscholar\.org/CorpusID:(\d+)', url)
        if doi:
            doi_entries[key] = f"DOI:{doi}"
        elif corpus_m:
            doi_entries[key] = f"CorpusID:{corpus_m.group(1)}"
        elif entry.get('title'):
            title_entries[key] = entry['title']

    # --- Batch DOI lookup ---
    if doi_entries:
        print(f"  Fetching {len(doi_entries)} papers by DOI/CorpusID (batch)...")
        keys = list(doi_entries.keys())
        ids = [doi_entries[k] for k in keys]  # already prefixed with DOI: or CorpusID:
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
        self.figures: List[dict] = []  # {src, caption, chapter_slug}

    def convert(self, latex: str) -> str:
        self._build_label_map(latex)   # Must run before _preprocess strips \label{}
        t = self._preprocess(latex)
        t = self._environments(t)
        t = self._sections(t)
        t = self._citations(t)   # Must come before _inline() which strips \commands
        t = self._inline(t)
        t = self._paragraphs(t)
        return t

    def _build_label_map(self, latex: str) -> None:
        """Pre-scan raw LaTeX to build label→HTML-anchor map before labels are stripped."""
        self._label_map: Dict[str, str] = {}
        # Figure labels → fig-{stem} anchors
        for fig_m in re.finditer(
                r'\\begin\{figure\*?\}(.*?)\\end\{figure\*?\}', latex, re.DOTALL):
            fig_content = fig_m.group(1)
            img_paths = re.findall(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}', fig_content)
            label_m = re.search(r'\\label\{([^}]+)\}', fig_content)
            if img_paths and label_m:
                img_name = os.path.basename(img_paths[0])
                stem = re.sub(r'[^a-z0-9]+', '-',
                              os.path.splitext(img_name)[0].lower()).strip('-')
                self._label_map[label_m.group(1)] = f'fig-{stem}'
        # Section labels → section slug anchors
        for sec_m in re.finditer(
                r'\\(?:subsubsection|subsection|section)\*?\{((?:[^{}]|\{[^{}]*\})*)\}',
                latex):
            after = latex[sec_m.end():sec_m.end() + 300]
            label_m = re.search(r'\\label\{([^}]+)\}', after)
            if label_m:
                raw_title = sec_m.group(1)
                clean = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', raw_title)
                clean = re.sub(r'\\[a-zA-Z]+', '', clean)
                self._label_map[label_m.group(1)] = self._slug(clean)

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
        _level_map = {'section': 2, 'subsection': 3, 'subsubsection': 4}

        def sec(m):
            level = _level_map[m.group(1)]
            title = self._inline_simple(m.group(2))
            sid = self._slug(re.sub(r'<[^>]+>', '', title))
            self.toc.append((level, re.sub(r'<[^>]+>', '', title), sid))
            return f'\n<h{level} id="{sid}">{title}</h{level}>\n'

        # Single pass — preserves document order for TOC
        t = re.sub(
            r'\\(subsubsection|subsection|section)\*?\{((?:[^{}]|\{[^{}]*\})*)\}',
            sec, t)
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
        # Display math — collapse to single line so _paragraphs() won't split
        # the \[...\] delimiters across lines and inject <p> tags inside them.
        def _math_div(content: str) -> str:
            return '<div class="math-display">\\[' + content.replace('\n', ' ').strip() + '\\]</div>'

        t = re.sub(r'\\begin\{equation\*?\}(.*?)\\end\{equation\*?\}',
                   lambda m: _math_div(m.group(1)), t, flags=re.DOTALL)
        t = re.sub(r'\\begin\{align\*?\}(.*?)\\end\{align\*?\}',
                   lambda m: _math_div(r'\begin{aligned}' + m.group(1) + r'\end{aligned}'),
                   t, flags=re.DOTALL)
        # $$...$$ display math (LaTeX / common web notation)
        t = re.sub(r'\$\$(.*?)\$\$',
                   lambda m: _math_div(m.group(1)), t, flags=re.DOTALL)
        # Protect already-wrapped display math before matching bare \[...\]
        _dm_store: Dict[str, str] = {}
        def _dm_protect(m):
            k = f'\x00DMATH{len(_dm_store)}\x00'
            _dm_store[k] = m.group(0)
            return k
        t = re.sub(r'<div class="math-display">.*?</div>', _dm_protect, t, flags=re.DOTALL)
        t = re.sub(r'\\\[(.*?)\\\]',
                   lambda m: _math_div(m.group(1)), t, flags=re.DOTALL)
        # Restore protected blocks
        for k, v in _dm_store.items():
            t = t.replace(k, v)
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
        cap_m = re.search(r'\\caption\{((?:[^{}]|\{[^{}]*\})*)\}', content)
        caption = self._inline_simple(cap_m.group(1)) if cap_m else ''

        # Collect all \includegraphics paths (handles \subfloat with multiple images)
        img_paths = re.findall(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}', content)
        if not img_paths:
            return ''

        # Also collect per-subfloat captions if present
        subfloat_caps = re.findall(
            r'\\subfloat\[(?:\\centering\s*)?(.*?)\]', content)

        result = ''
        for i, raw_path in enumerate(img_paths):
            img_name = os.path.basename(raw_path)
            if img_name.lower().endswith('.pdf'):
                img_name = os.path.splitext(img_name)[0] + '.png'
            stem = re.sub(r'[^a-z0-9]+', '-', os.path.splitext(img_name)[0].lower()).strip('-')
            fig_id = f'fig-{stem}'

            # Caption: use shared caption for single images; subfloat label + shared for multiples
            if len(img_paths) == 1:
                fig_caption = caption
            else:
                sub_label = self._inline_simple(subfloat_caps[i]) if i < len(subfloat_caps) else ''
                fig_caption = f'{sub_label} — {caption}' if sub_label else caption

            alt = html.escape(re.sub(r'<[^>]+>', '', fig_caption))
            self.figures.append({
                'src': img_name, 'caption': fig_caption,
                'chapter_slug': self.chapter_slug, 'fig_id': fig_id,
            })
            result += (f'<figure class="thesis-figure" id="{html.escape(fig_id)}">'
                       f'<img src="../assets/{html.escape(img_name)}" alt="{alt}" '
                       f'loading="lazy" class="thesis-img">'
                       f'<figcaption>{fig_caption}</figcaption></figure>\n')

        return result

    def _table(self, m) -> str:
        """Convert a LaTeX table float into HTML (or PNG image if pdflatex available)."""
        raw_content = m.group(0)  # full \begin{table}...\end{table} including wrapper
        content = m.group(1)

        # Extract caption for alt text / fallback
        cap_m = re.search(r'\\caption\{((?:[^{}]|\{[^{}]*\})*)\}', content)
        caption = self._inline_simple(cap_m.group(1)) if cap_m else ''

        # --- Try PNG rendering via pdflatex (perfect output) ---
        if getattr(self, '_table_assets_dir', None) is not None and _has_tool('pdflatex'):
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
        # Strip \resizebox{width}{height}{% inner %} wrapper — extract the inner content
        # Pattern: \resizebox{..}{..}{% content \end{tabular}% }
        # Replace entire \resizebox{..}{..}{...} with just the inner content
        content_clean = re.sub(
            r'\\resizebox\{[^}]*\}\{[^}]*\}\{%?\s*(.*?)\s*%?\s*\}(\s*)$',
            r'\1\2', content_clean, flags=re.DOTALL)

        # Protect nested \begin{tabular}...\end{tabular} environments BEFORE searching
        # for the outer tabular, so (.*?) doesn't stop at an inner \end{tabular}.
        # Strategy: repeatedly match the INNERMOST tabular (one whose body contains
        # no further \begin{tabular}) and replace with a placeholder.
        # Store on self so _cell() can expand them later.
        if not hasattr(self, '_nested_tab_store'):
            self._nested_tab_store = {}
        def _protect_nested_table(m):
            k = f'\x02NESTED{len(self._nested_tab_store)}\x02'
            self._nested_tab_store[k] = m.group(0)
            return k
        # Single pass: protect each innermost tabular (body contains no \begin{tabular}).
        # This leaves exactly the outermost \begin{tabular} visible for the search below.
        # Match innermost tabular (body contains no \begin{tabular}).
        # Run passes until only one \begin{tabular} remains (the outer one).
        _innermost_tab = (r'\\begin\{tabular\}(?:\[[^\]]*\])?\{(?:[^{}]|\{[^{}]*\})*\}'
                          r'((?:(?!\\begin\{tabular\})[\s\S])*?)\\end\{tabular\}')
        while content_clean.count(r'\begin{tabular}') > 1:
            content_clean = re.sub(_innermost_tab, _protect_nested_table, content_clean)

        # Column spec may contain @{} so use one-level nested brace matching
        # Also support tabularx and tabulary (second arg is width, third is col spec)
        # For tabularx: \begin{tabularx}{\textwidth}{col_spec}
        tab_m = re.search(
            r'\\begin\{tabular[*]?\}\{((?:[^{}]|\{[^{}]*\})*)\}(.*?)\\end\{tabular[*]?\}',
            content_clean, re.DOTALL)
        if not tab_m:
            # Try tabularx / tabulary which have an extra {width} argument
            tab_m = re.search(
                r'\\begin\{tabular[xy]\}\{[^}]*\}\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}(.*?)\\end\{tabular[xy]\}',
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

        # Note: nested \begin{tabular} protection is done in _table() before calling
        # us, so self._nested_tab_store is already populated.

        # Protect escaped specials before splitting on & and //
        body = body.replace(r'\&', '\x01AMP\x01')
        body = body.replace(r'\%', '\x01PCT\x01')
        body = body.replace(r'\$', '\x01DOL\x01')

        # Replace rule commands with unique markers so we can split cleanly
        # \midrule (exact, not \cmidrule) marks header→body boundary
        body = re.sub(r'\\midrule\b', '\x00MID\x00', body)
        # \cmidrule is purely decorative — remove
        body = re.sub(r'\\cmidrule\s*(?:\([^)]*\))?\s*\{[^}]*\}', '', body)
        # \toprule / \bottomrule / \addlinespace → remove (just visual decoration)
        body = re.sub(r'\\(?:toprule|bottomrule|addlinespace)\b(?:\[[^\]]*\])?', '', body)
        # \hline → mark
        body = re.sub(r'\\hline\b', '\x00HLINE\x00', body)
        # \thead{...} → extract content (used for multi-line headers)
        body = re.sub(r'\\thead\{((?:[^{}]|\{[^{}]*\})*)\}', lambda m: m.group(1).replace(r'\\', ' '), body)

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
        """Convert a single table cell, expanding any nested tabular placeholders."""
        text = text.strip()
        # \multirow — extract inner content
        mr = re.match(r'\\multirow\s*\{[^}]*\}\s*\{[^}]*\}\s*\{((?:[^{}]|\{[^{}]*\})*)\}', text)
        if mr:
            text = mr.group(1)
        # Expand nested tabular placeholders stored by _tabular on self._nested_tab_store.
        # Each nested \begin{tabular}...\end{tabular} becomes an <ul> bullet list.
        store = getattr(self, '_nested_tab_store', {})
        for k, raw in store.items():
            if k not in text:
                continue
            body_m = re.search(
                r'\\begin\{tabular\}(?:\[[^\]]*\])?\{(?:[^{}]|\{[^{}]*\})*\}(.*?)\\end\{tabular\}',
                raw, re.DOTALL)
            inner = body_m.group(1) if body_m else raw
            rows = [r.strip() for r in re.split(r'\\\\', inner) if r.strip()]
            items = [self._inline_simple(r) for r in rows if r]
            html = ('<ul class="cell-list">'
                    + ''.join(f'<li>{it}</li>' for it in items)
                    + '</ul>') if items else ''
            text = text.replace(k, html)
        return self._inline_simple(text)

    def _item_html(self, text: str) -> str:
        """Process a single list item: citations first, then inline formatting."""
        return self._inline(self._citations(text.strip()))

    def _enumerate(self, m) -> str:
        items = self._split_items(m.group(1))
        lis = '\n'.join(f'  <li>{self._item_html(item)}</li>' for item in items if item.strip())
        return f'<ol>\n{lis}\n</ol>\n'

    def _itemize(self, m) -> str:
        items = self._split_items(m.group(1))
        lis = '\n'.join(f'  <li>{self._item_html(item)}</li>' for item in items if item.strip())
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
        # Protect display math blocks (already wrapped by _environments) from HTML processing
        display_maths = {}
        def _protect_display(m):
            k = f'\x00D{len(display_maths)}\x00'
            display_maths[k] = m.group(0)
            return k
        t = re.sub(r'<div class="math-display">.*?</div>', _protect_display, t, flags=re.DOTALL)

        # Protect already-converted inline math spans (from _inline_simple in table cells)
        # so their \pm, \times etc. don't get stripped
        def _protect_span(m):
            k = f'\x00D{len(display_maths)}\x00'
            display_maths[k] = m.group(0)
            return k
        t = re.sub(r'<span class="math">.*?</span>', _protect_span, t, flags=re.DOTALL)

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
        # Restore display math blocks
        for k, v in display_maths.items():
            t = t.replace(k, v)
        return t

    def _cref(self, m) -> str:
        label_map = getattr(self, '_label_map', {})
        labels = [l.strip() for l in m.group(1).split(',')]
        parts = []
        for lab in labels:
            # Chapter references
            for ch_slug, ch_title in CHAPTERS:
                if ch_slug.replace('chapter-', '') in lab or lab in ch_slug:
                    parts.append(f'<a href="../chapters/{ch_slug}.html" class="internal-ref">{ch_title}</a>')
                    break
            else:
                # Use pre-scanned label map for precise anchors
                if lab in label_map:
                    anchor = label_map[lab]
                    display = 'Figure' if anchor.startswith('fig-') else 'Section'
                    parts.append(f'<a href="#{anchor}" class="internal-ref">{display}</a>')
                else:
                    # Fallback: normalise label to a best-guess anchor
                    clean = re.sub(r'^assets/', '', lab)
                    clean = clean.replace(':', '-').replace('_', '-').replace('/', '-')
                    if 'fig' in lab.lower():
                        display = 'Figure'
                    elif lab.startswith('eq:'):
                        display = 'Equation'
                    elif lab.startswith('tab:'):
                        display = 'Table'
                    elif lab.startswith('sec:') or lab.startswith('chapter:'):
                        display = 'Section'
                    else:
                        display = lab
                    parts.append(f'<a href="#{clean}" class="internal-ref">{display}</a>')
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
                    f'class="cite" data-key="{html.escape(key)}" title="{title}">[{html.escape(label)}]</a>')

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
                parts.append(f'<a href="../papers/{html.escape(key)}.html" class="cite" data-key="{html.escape(key)}" title="{title}">{html.escape(display)}</a>')
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


# ── Helper: compute co-citations ──────────────────────────────────────────────

def compute_co_citations(chapter_citations: Dict[str, Set[str]]) -> Dict[str, List[Tuple[str, int]]]:
    """For each paper key, return sorted list of (co_key, chapter_count) tuples."""
    from collections import defaultdict
    co: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for ch_slug, keys in chapter_citations.items():
        keys_list = list(keys)
        for i, k1 in enumerate(keys_list):
            for k2 in keys_list[i+1:]:
                co[k1][k2] += 1
                co[k2][k1] += 1
    result = {}
    for key, partners in co.items():
        result[key] = sorted(partners.items(), key=lambda x: x[1], reverse=True)
    return result


def build_papers_meta_js(bib: Dict, ss: Dict) -> str:
    """Return a <script> block embedding PAPERS_META for citation hover cards."""
    meta = {}
    for key, entry in bib.items():
        ss_d = ss.get(key)
        if ss_d:
            authors_list = [a.get('name', '') for a in ss_d.get('authors', [])]
            authors_str = ', '.join(authors_list[:4])
            if len(authors_list) > 4:
                authors_str += ' et al.'
            meta[key] = {
                'title': ss_d.get('title', entry.get('title', key))[:120],
                'authors': authors_str[:100],
                'year': entry.get('year', ''),
                'venue': (ss_d.get('venue', '') or '')[:60],
                'cc': ss_d.get('citationCount'),
                'abstract': (ss_d.get('abstract', '') or '')[:280],
            }
        else:
            meta[key] = {
                'title': entry.get('title', key)[:120],
                'authors': format_authors(entry.get('author', ''), 3)[:100],
                'year': entry.get('year', ''),
                'venue': (entry.get('journal', '') or entry.get('booktitle', '') or '')[:60],
                'cc': None,
                'abstract': '',
            }
    return f'<script>window.PAPERS_META = {json.dumps(meta, ensure_ascii=False)};</script>'


def build_glossary_js() -> str:
    """Return a <script> block embedding GLOSSARY_DATA for hover cards."""
    data = {k: {'full': v['full'], 'definition': v['definition'], 'category': v['category']}
            for k, v in GLOSSARY.items()}
    return f'<script>window.GLOSSARY_DATA = {json.dumps(data, ensure_ascii=False)};</script>'


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
  <script src="{root}/js/search-index.js"></script>
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
<div id="reading-progress"></div>
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
      <a href="{root}/glossary.html">Glossary</a>
      <a href="{root}/figures.html">Figures</a>
      <div class="nav-more">
        <button class="nav-more-btn" id="nav-more-btn">More ▾</button>
        <div class="nav-more-dropdown" id="nav-more-dropdown">
          <a href="{root}/graph.html">Citation Graph</a>
          <a href="{root}/authors.html">Authors</a>
          <a href="{root}/timeline.html">Timeline</a>
          <a href="{root}/methods.html">Methods</a>
        </div>
      </div>
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
    <a href="{root}/glossary.html">Glossary</a>
    <a href="{root}/figures.html">Figures</a>
    <div class="mobile-menu-divider"></div>
    <a href="{root}/graph.html">Citation Graph</a>
    <a href="{root}/authors.html">Authors</a>
    <a href="{root}/timeline.html">Timeline</a>
    <a href="{root}/methods.html">Methods</a>
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

def build_index(bib: Dict, ss: Dict, chapter_citations: Dict[str, Set[str]],
                thesis_stats: Dict = None) -> str:
    """Generate homepage."""
    m = THESIS_META
    stats = thesis_stats or {}

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

    # Did You Know facts
    dyk_facts = [
        "Gone Phishing (MoE Transformer) achieves 100% accuracy on fish species identification — a perfect score.",
        "The thesis analyzes 2,080 distinct m/z features spanning 77.04 to 999.32 m/z per spectrum.",
        "SpectroSim achieves 70.8% batch detection accuracy without any labeled training data.",
        "REIMS produces a chemical fingerprint in under 3 seconds, compared to hours for traditional methods.",
        "The Ensemble Transformer (Autobots) combines models at 2, 4, and 8 Transformer layers simultaneously.",
        "Seafood fraud affects an estimated 30% of commercially sold seafood globally.",
        "Masked Spectra Modelling (MSM) adapts BERT's masked language modeling to 1D mass spectra.",
        "The thesis cites 373 papers spanning over 50 years of research, from 1970 to 2025.",
        "Transfer Learning from species identification to oil contamination detection improves accuracy by +22.67%.",
        "New Zealand is the world's largest exporter of Hoki — the premium species in adulteration experiments.",
    ]
    dyk_items = ''.join(f'<div class="dyk-fact" style="display:none">{html.escape(f)}</div>' for f in dyk_facts)
    dyk_first = html.escape(dyk_facts[0])

    words_k = f"{stats.get('words', 0) // 1000}K" if stats.get('words', 0) >= 1000 else str(stats.get('words', 0))
    stat_items = [
        (str(stats.get('chapters', len(CHAPTERS))), 'Chapters'),
        (f"{stats.get('papers', len(bib)):,}", 'Papers Cited'),
        (str(stats.get('figures', 0)), 'Figures'),
        (str(stats.get('equations', 0)), 'Equations'),
        (str(stats.get('glossary', len(GLOSSARY))), 'Glossary Terms'),
        (f'~{words_k}', 'Words'),
    ]
    stats_html = ''.join(
        f'<div class="stat-item"><span class="stat-num">{n}</span>'
        f'<span class="stat-label">{l}</span></div>'
        for n, l in stat_items
    )

    content = f"""
<div class="hero">
  <div class="hero-inner">
    <div class="hero-badge">PhD Thesis · 2025</div>
    <h1 class="hero-title">{html.escape(m['title'])}</h1>
    <p class="hero-author">by <strong>{html.escape(m['author'])}</strong> · {html.escape(m['university'])}</p>
    <div class="hero-tags">{topic_tags}</div>
  </div>
</div>
<div class="thesis-stats-bar">{stats_html}</div>

<div class="main-content">
  <div class="content-cols">
    <main class="content-main">

      <div class="did-you-know" id="dyk-box">
        <strong>Did you know?</strong>
        <span id="dyk-text">{dyk_first}</span>
        <button class="dyk-next" onclick="dykNext()" aria-label="Next fact">&#8594;</button>
      </div>
      <script>
        var _dykFacts = {json.dumps(dyk_facts)};
        var _dykIdx = 0;
        function dykNext() {{
          _dykIdx = (_dykIdx + 1) % _dykFacts.length;
          document.getElementById('dyk-text').textContent = _dykFacts[_dykIdx];
        }}
        // Auto-rotate every 8 seconds
        setInterval(dykNext, 8000);
      </script>

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
          <dt>Degree</dt><dd>{html.escape(m['degree'])}</dd>
          <dt>Course Code</dt><dd>{html.escape(m['course_code'])}</dd>
          <dt>School</dt><dd>{html.escape(m['school'])}</dd>
          <dt>Institution</dt><dd>{html.escape(m['university'])}</dd>
          <dt>Year</dt><dd>{html.escape(m['year'])}</dd>
          <dt>Duration</dt><dd>{html.escape(m['duration'])}</dd>
          <dt>Supervisors</dt><dd>{'<br>'.join(html.escape(s) for s in m['supervisors'])}</dd>
          <dt>Tasks</dt><dd>{m['tasks']} classification tasks</dd>
          <dt>Experiments</dt><dd>{html.escape(m['experiments'])} run</dd>
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
      <div class="info-box">
        <h4>Cite This Thesis</h4>
        <pre class="bibtex-mini">@phdthesis{{Wood2025,
  author = {{Jesse Wood}},
  title  = {{{m['title']}}},
  school = {{{m['university']}}},
  year   = {{{m['year']}}},
}}</pre>
        <button class="bibtex-copy-btn" id="bibtex-copy-btn"
          data-bibtex="@phdthesis{{Wood2025,\n  author = {{Jesse Wood}},\n  title  = {{{m['title']}}},\n  school = {{{m['university']}}},\n  year   = {{{m['year']}}},\n}}">
          📋 Copy BibTeX
        </button>
      </div>
    </aside>
  </div>
</div>
"""
    return page_shell(f"{m['title']}", content, root=".")


CHAPTER_HATNOTES = {
    "chapter-1": 'Introduction to the thesis. For methodology, see <a href="chapter-3.html">Chapter 3: Datasets and Processing</a>.',
    "chapter-2": 'Survey of prior work. For novel methods proposed in this thesis, see <a href="chapter-4.html">Chapter 4</a>.',
    "chapter-3": 'Covers REIMS datasets and preprocessing. For models trained on these datasets, see <a href="chapter-4.html">Chapter 4</a>.',
    "chapter-4": 'Covers fish species and body part identification. For contamination detection, see <a href="chapter-5.html">Chapter 5</a>.',
    "chapter-5": 'Covers oil contamination and adulteration. For batch traceability, see <a href="chapter-6.html">Chapter 6</a>.',
    "chapter-6": 'Covers self-supervised batch detection (SpectroSim). For prior supervised tasks, see <a href="chapter-4.html">Chapter 4</a>.',
    "chapter-7": 'Thesis conclusions and future work. For full results, see <a href="chapter-4.html">Ch. 4</a>, <a href="chapter-5.html">Ch. 5</a>, and <a href="chapter-6.html">Ch. 6</a>.',
}

CHAPTER_SEE_ALSO = {
    "chapter-1": [("chapter-2", "Literature Survey"), ("chapter-7", "Conclusions")],
    "chapter-2": [("chapter-1", "Introduction"), ("chapter-4", "Fish Species & Part Identification")],
    "chapter-3": [("chapter-4", "Fish Species & Part Identification"), ("chapter-5", "Oil Contamination")],
    "chapter-4": [("chapter-3", "Datasets and Processing"), ("chapter-5", "Oil Contamination & Adulteration")],
    "chapter-5": [("chapter-4", "Fish Species & Part Identification"), ("chapter-6", "Contrastive Learning")],
    "chapter-6": [("chapter-5", "Oil Contamination & Adulteration"), ("chapter-7", "Conclusions")],
    "chapter-7": [("chapter-4", "Species & Part ID"), ("chapter-5", "Contamination"), ("chapter-6", "Batch Detection")],
}


def _build_navbox() -> str:
    """Build the Wikipedia-style navbox for chapter pages."""
    task_links = ' · '.join([
        '<a href="../chapters/chapter-4.html">Species ID</a>',
        '<a href="../chapters/chapter-4.html">Body Part ID</a>',
        '<a href="../chapters/chapter-5.html">Oil Contamination</a>',
        '<a href="../chapters/chapter-5.html">Adulteration</a>',
        '<a href="../chapters/chapter-6.html">Batch Detection</a>',
    ])

    model_links = ' · '.join([
        '<a href="../glossary.html#gone-phishing">Gone Phishing</a>',
        '<a href="../glossary.html#autobots">Autobots</a>',
        '<a href="../glossary.html#spectrosim">SpectroSim</a>',
        '<a href="../glossary.html#msm">MSM</a>',
    ])

    chapter_links = ' · '.join(
        f'<a href="{slug}.html">Ch.{slug.replace("chapter-","")}: {html.escape(title[:20])}</a>'
        for slug, title in CHAPTERS
    )

    return f"""<details class="navbox" open>
  <summary>This Thesis</summary>
  <div class="navbox-body">
    <div class="navbox-group"><strong>Tasks</strong>: {task_links}</div>
    <div class="navbox-group"><strong>Novel Models</strong>: {model_links}</div>
    <div class="navbox-group"><strong>Chapters</strong>: {chapter_links}</div>
  </div>
</details>"""


def build_chapter(slug: str, title: str, latex: str, bib: Dict,
                  ss: Dict, all_citations: Dict[str, Set[str]],
                  papers_meta_js: str = "") -> Tuple[str, List[dict]]:
    """Generate a chapter page. Returns (html, figures_list)."""
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

    # Reading time estimate (~200 words per minute)
    plain_text = re.sub(r'<[^>]+>', ' ', body_html)
    word_count = len(plain_text.split())
    reading_min = max(1, round(word_count / 200))

    # Hatnote
    hatnote_html = ''
    if slug in CHAPTER_HATNOTES:
        hatnote_html = f'<div class="hatnote">{CHAPTER_HATNOTES[slug]}</div>'

    # See also
    see_also_html = ''
    if slug in CHAPTER_SEE_ALSO:
        links = ' · '.join(
            f'<a href="{s}.html">{html.escape(t)}</a>'
            for s, t in CHAPTER_SEE_ALSO[slug]
        )
        see_also_html = f'<div class="see-also"><strong>See also:</strong> {links}</div>'

    # Navbox
    navbox_html = _build_navbox()

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
      <div class="reading-time">~{reading_min} min read · {len(sorted_cites)} references</div>
    </header>

    {hatnote_html}

    <article class="chapter-content">
      {body_html}
    </article>

    {see_also_html}

    <section class="chapter-references">
      <h2>References ({len(sorted_cites)})</h2>
      <ol class="ref-list">
        {ref_items}
      </ol>
    </section>

    {navbox_html}

    <div class="chapter-nav-bottom">
      {prev_link}
      {next_link}
    </div>
  </main>
</div>
"""
    extra_head = mathjax + "\n" + papers_meta_js + "\n" + build_glossary_js()
    return page_shell(f"{title} — ML for REIMS", content, extra_head=extra_head), converter.figures


def _build_co_cited_html(key: str, co_cited: List[Tuple[str, int]], bib: Dict) -> str:
    """Build HTML for the cited-together section on a paper page."""
    if not co_cited or not bib:
        return ''
    items = co_cited[:6]  # Top 6
    li_items = ''
    for co_key, count in items:
        e = bib.get(co_key, {})
        co_title = html.escape(e.get('title', co_key)[:80])
        surname = html.escape(get_first_author_surname(e.get('author', '')))
        year = html.escape(e.get('year', ''))
        ch_label = f"{count} chapter{'s' if count != 1 else ''}"
        li_items += (f'<li>'
                     f'<a href="{html.escape(co_key)}.html" class="co-cite-link">{co_title}</a>'
                     f'<span class="co-cite-meta">{surname} {year}</span>'
                     f'<span class="co-cite-count">{ch_label}</span>'
                     f'</li>\n')
    return (f'<div class="cited-together-block">'
            f'<h3>Frequently Cited Together</h3>'
            f'<ul class="cited-together-list">{li_items}</ul>'
            f'</div>')


def build_paper(key: str, entry: Dict, ss_data: Optional[dict],
                cited_in: Dict[str, str], bib: Dict = None,
                co_cited: List[Tuple[str, int]] = None,
                papers_meta_js: str = "") -> str:
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

    # Stub notice: shown when no abstract or SS data available
    stub_notice = ''
    if not abstract and not ss_data:
        stub_notice = '<div class="stub-notice">This paper entry has limited metadata. Abstract and citation data could not be retrieved automatically.</div>'

    content = f"""
<div class="paper-layout">
  <main class="paper-main">
    <div class="breadcrumb"><a href="../index.html">Home</a> / <a href="../papers.html">Papers</a> / {html.escape(key)}</div>

    {stub_notice}

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

      {_build_co_cited_html(key, co_cited, bib) if co_cited else ''}

      <details class="bibtex-block">
        <summary>BibTeX</summary>
        <pre><code>{html.escape(bibtex_str)}</code></pre>
      </details>
    </article>
  </main>
</div>
"""
    return page_shell(f"{title[:60]}… — ML for REIMS", content, extra_head=papers_meta_js)


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


def build_glossary() -> str:
    """Generate the glossary page."""
    def term_slug(t: str) -> str:
        return re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-')

    # Group by first letter
    from collections import defaultdict
    by_letter: Dict[str, list] = defaultdict(list)
    for term, data in sorted(GLOSSARY.items(), key=lambda x: x[0].upper()):
        letter = term[0].upper()
        by_letter[letter].append((term, data))

    alpha_links = ''.join(
        f'<a class="alpha-link" href="#{L}">{L}</a>'
        for L in sorted(by_letter.keys())
    )

    category_labels = {
        'instrument': 'Instrumentation',
        'method': 'Method',
        'model': 'Model',
        'task': 'Analysis Task',
        'domain': 'Domain',
        'contribution': 'Novel Contribution',
    }

    sections_html = ''
    for letter in sorted(by_letter.keys()):
        entries_html = ''
        for term, data in by_letter[letter]:
            slug = term_slug(term)
            cat = category_labels.get(data['category'], data['category'])
            entries_html += f"""
<div class="glossary-entry" id="{html.escape(slug)}">
  <div class="glossary-entry-term">{html.escape(term)}</div>
  {f'<div class="glossary-entry-full">{html.escape(data["full"])}</div>' if data["full"] != term else ''}
  <div class="glossary-entry-def">{html.escape(data["definition"])}</div>
  <span class="glossary-entry-cat">{html.escape(cat)}</span>
</div>"""
        sections_html += f"""
<div class="alpha-section">
  <h2 id="{letter}">{letter}</h2>
  {entries_html}
</div>"""

    content = f"""
<div class="glossary-page">
  <header class="glossary-header">
    <h1>Glossary</h1>
    <p>Key terms, methods, and concepts from the thesis on Machine Learning for REIMS Marine Biomass Analysis.</p>
  </header>
  <nav class="glossary-alpha-nav">{alpha_links}</nav>
  {sections_html}
</div>
"""
    return page_shell("Glossary — ML for REIMS", content, root=".")


def build_figure_gallery(all_figures: List[dict]) -> str:
    """Generate the figure gallery page."""
    # Chapter title lookup
    ch_titles = dict(CHAPTERS)

    # Filter buttons
    filter_btns = '<button class="gallery-filter-btn active" data-ch="all">All</button>'
    seen_chapters = []
    for fig in all_figures:
        cs = fig['chapter_slug']
        if cs not in seen_chapters:
            seen_chapters.append(cs)
            ct = ch_titles.get(cs, cs)
            filter_btns += f'<button class="gallery-filter-btn" data-ch="{html.escape(cs)}">{html.escape(ct)}</button>'

    items_html = ''
    for fig in all_figures:
        cs = fig['chapter_slug']
        ct = ch_titles.get(cs, cs)
        ch_num = cs.replace('chapter-', '')
        cap = fig['caption']
        src = fig['src']
        cap_plain = re.sub(r'<[^>]+>', '', cap)[:120]
        fig_id = fig.get('fig_id', '')
        anchor = f'#{html.escape(fig_id)}' if fig_id else ''
        items_html += f"""
<div class="gallery-item" data-ch="{html.escape(cs)}">
  <a href="chapters/{html.escape(cs)}.html{anchor}">
    <img src="assets/{html.escape(src)}" alt="{html.escape(cap_plain)}" loading="lazy" onerror="this.closest('.gallery-item').style.display='none'">
  </a>
  <div class="gallery-item-caption">
    <span class="gallery-item-chapter">Ch. {html.escape(ch_num)}: {html.escape(ct[:30])}</span><br>
    {cap_plain}
  </div>
</div>"""

    content = f"""
<div class="gallery-page">
  <header class="gallery-header">
    <h1>Figure Gallery</h1>
    <p>{len(all_figures)} figures from the thesis, filterable by chapter.</p>
  </header>
  <div class="gallery-filter-bar" id="gallery-filters">
    {filter_btns}
  </div>
  <div class="gallery-grid" id="gallery-grid">
    {items_html}
  </div>
</div>
"""
    return page_shell("Figure Gallery — ML for REIMS", content, root=".")


# ── New Build Functions ────────────────────────────────────────────────────────

def build_search_index(bib: Dict, ss: Dict, chapter_citations: Dict[str, Set[str]],
                       chapter_latex: Dict[str, str]) -> None:
    """Write site/search-index.json with papers, chapters, and glossary entries."""
    index = []

    # Papers
    for key, entry in bib.items():
        ss_d = ss.get(key)
        title = (ss_d.get('title') if ss_d else None) or entry.get('title', key)
        authors_str = ''
        if ss_d and ss_d.get('authors'):
            authors_str = ', '.join(a.get('name', '') for a in ss_d['authors'][:4])
        else:
            authors_str = format_authors(entry.get('author', ''), 3)
        abstract = (ss_d.get('abstract') or '') if ss_d else ''
        year = entry.get('year', '')
        index.append({
            'type': 'paper',
            'title': title[:200],
            'text': (abstract[:400] if abstract else ''),
            'snippet': (abstract[:160] if abstract else ''),
            'url': f'papers/{key}.html',
            'meta': f'{authors_str} · {year}'.strip(' ·'),
        })

    def _strip_latex(t: str) -> str:
        t = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', t)
        t = re.sub(r'\\[a-zA-Z]+', ' ', t)
        t = re.sub(r'[{}%$\\]', ' ', t)
        return re.sub(r'\s+', ' ', t).strip()

    # Chapters — one top-level entry + one entry per section for deep-link search
    for slug, title in CHAPTERS:
        latex = chapter_latex.get(slug, '')
        num = slug.replace('chapter-', '')
        plain_chapter = _strip_latex(latex[:600])

        index.append({
            'type': 'chapter',
            'title': f'Chapter {num}: {title}',
            'text': plain_chapter,
            'snippet': plain_chapter[:160],
            'url': f'chapters/{slug}.html',
            'meta': f'Chapter {num}',
        })

        # Split into sections and add a searchable entry per section
        sec_pattern = re.compile(
            r'\\(subsubsection|subsection|section)\*?\{((?:[^{}]|\{[^{}]*\})*)\}')
        positions = [(m.start(), m) for m in sec_pattern.finditer(latex)]
        for i, (pos, sec_m) in enumerate(positions):
            sec_title_raw = sec_m.group(2)
            sec_title = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', sec_title_raw)
            sec_title = re.sub(r'\\[a-zA-Z]+', '', sec_title).strip()
            sid = re.sub(r'[^a-z0-9]+', '-', sec_title.lower()).strip('-')
            # Body text of this section (up to next section or 600 chars)
            body_start = pos + len(sec_m.group(0))
            body_end = positions[i + 1][0] if i + 1 < len(positions) else body_start + 600
            body_plain = _strip_latex(latex[body_start:min(body_end, body_start + 600)])
            index.append({
                'type': 'chapter',
                'title': sec_title,
                'text': body_plain,
                'snippet': body_plain[:160],
                'url': f'chapters/{slug}.html#{sid}',
                'meta': f'Chapter {num}: {title}',
            })

    # Glossary
    for term, data in GLOSSARY.items():
        defn = data['definition']
        index.append({
            'type': 'glossary',
            'title': term,
            'text': defn,
            'snippet': defn[:160],
            'url': f'glossary.html#{re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")}',
            'meta': data.get('full', term),
        })

    # Write as a JS file so it works on file:// and http:// without fetch()
    js_content = 'window.SEARCH_INDEX=' + json.dumps(index, ensure_ascii=False, separators=(',', ':')) + ';'
    (SITE_DIR / 'js' / 'search-index.js').write_text(js_content)
    print(f"  search-index.js written ({len(index)} entries)")


def build_citation_graph(bib: Dict, ss: Dict, chapter_citations: Dict[str, Set[str]]) -> str:
    """Generate citation network graph page using D3.js v7."""
    # Collect all cited keys
    all_cited: Set[str] = set()
    for keys in chapter_citations.values():
        all_cited.update(keys)

    # Determine primary chapter for each paper (chapter where it's cited most)
    key_chapter_count: Dict[str, Dict[str, int]] = {}
    for ch_slug, keys in chapter_citations.items():
        for k in keys:
            key_chapter_count.setdefault(k, {})[ch_slug] = key_chapter_count.get(k, {}).get(ch_slug, 0) + 1

    chapter_colors = {
        'chapter-1': '#4e79a7',
        'chapter-2': '#f28e2b',
        'chapter-3': '#e15759',
        'chapter-4': '#76b7b2',
        'chapter-5': '#59a14f',
        'chapter-6': '#edc948',
        'chapter-7': '#b07aa1',
        'chapter-0': '#ff9da7',
    }

    nodes = []
    for k in all_cited:
        e = bib.get(k, {})
        ss_d = ss.get(k)
        title = (ss_d.get('title') if ss_d else None) or e.get('title', k)
        year = e.get('year', '')
        cc = (ss_d.get('citationCount') or 0) if ss_d else 0
        # Primary chapter
        ch_counts = key_chapter_count.get(k, {})
        primary_ch = max(ch_counts, key=ch_counts.get) if ch_counts else 'chapter-1'
        nodes.append({
            'id': k,
            'title': title[:80],
            'year': year,
            'cc': cc,
            'chapter': primary_ch,
            'color': chapter_colors.get(primary_ch, '#999'),
            'url': f'papers/{k}.html',
        })

    # Edges: co-citations with count >= 2
    co = compute_co_citations(chapter_citations)
    seen_edges = set()
    edges = []
    for k1, partners in co.items():
        if k1 not in all_cited:
            continue
        for k2, count in partners:
            if count < 2:
                continue
            if k2 not in all_cited:
                continue
            edge_key = tuple(sorted([k1, k2]))
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            edges.append({'source': k1, 'target': k2, 'count': count})

    graph_data = json.dumps({'nodes': nodes, 'edges': edges}, ensure_ascii=False)

    # Legend HTML
    legend_items = ''.join(
        f'<div class="graph-legend-item"><span class="graph-legend-dot" style="background:{color}"></span>{slug.replace("chapter-","Ch.")}</div>'
        for slug, color in chapter_colors.items()
        if slug != 'chapter-0'
    )

    content = f"""
<div class="graph-page">
  <div class="graph-header">
    <h1>Citation Network Graph</h1>
    <p>Force-directed graph of {len(nodes)} cited papers and {len(edges)} co-citation edges (count ≥ 2). Node size = citation count (log scale). Color = primary chapter. Hover for details, click to open paper.</p>
    <div class="graph-legend">{legend_items}</div>
  </div>
  <div id="graph-container"></div>
</div>
<script>window.GRAPH_DATA = {graph_data};</script>
<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
<script>
(function() {{
  const data = window.GRAPH_DATA;
  const container = document.getElementById('graph-container');
  const W = container.clientWidth || window.innerWidth;
  const H = Math.max(600, window.innerHeight - 200);

  const svg = d3.select('#graph-container').append('svg')
    .attr('width', '100%').attr('height', H)
    .style('display','block');

  const g = svg.append('g');

  // Zoom/pan
  svg.call(d3.zoom().scaleExtent([0.1, 8]).on('zoom', e => g.attr('transform', e.transform)));

  // Radius scale: log(cc+1), min 4 max 20
  const maxCC = d3.max(data.nodes, d => d.cc) || 1;
  const rScale = d3.scaleLog().domain([1, maxCC + 1]).range([4, 20]).clamp(true);
  const radius = d => rScale(d.cc + 1);

  const simulation = d3.forceSimulation(data.nodes)
    .force('link', d3.forceLink(data.edges).id(d => d.id).distance(60).strength(0.3))
    .force('charge', d3.forceManyBody().strength(-80))
    .force('center', d3.forceCenter(W / 2, H / 2))
    .force('collision', d3.forceCollide().radius(d => radius(d) + 2));

  const link = g.append('g').attr('stroke', '#ccc').attr('stroke-opacity', 0.5)
    .selectAll('line').data(data.edges).join('line')
    .attr('stroke-width', d => Math.min(3, d.count * 0.5));

  const node = g.append('g').selectAll('circle').data(data.nodes).join('circle')
    .attr('r', radius)
    .attr('fill', d => d.color)
    .attr('stroke', '#fff').attr('stroke-width', 1.5)
    .style('cursor', 'pointer')
    .call(d3.drag()
      .on('start', (e,d) => {{ if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; }})
      .on('drag',  (e,d) => {{ d.fx=e.x; d.fy=e.y; }})
      .on('end',   (e,d) => {{ if (!e.active) simulation.alphaTarget(0); d.fx=null; d.fy=null; }}));

  node.on('click', (e, d) => {{ window.location.href = d.url; }});

  // Tooltip
  const tip = d3.select('body').append('div').attr('class','graph-tooltip').style('opacity',0);
  node.on('mouseenter', (e, d) => {{
    tip.html(`<strong>${{d.title}}</strong><br>${{d.year}} · ${{d.cc.toLocaleString()}} citations`)
       .style('left', (e.pageX+12)+'px').style('top',(e.pageY-28)+'px').style('opacity',1);
  }}).on('mouseleave', () => tip.style('opacity',0));

  simulation.on('tick', () => {{
    link.attr('x1', d=>d.source.x).attr('y1',d=>d.source.y)
        .attr('x2', d=>d.target.x).attr('y2',d=>d.target.y);
    node.attr('cx', d=>d.x).attr('cy',d=>d.y);
  }});
}})();
</script>
"""
    return page_shell("Citation Network Graph — ML for REIMS", content, root=".")


def _parse_bib_authors(author_field: str) -> List[str]:
    """Parse BibTeX author field into list of 'Firstname Lastname' strings."""
    names = []
    for a in author_field.split(' and '):
        a = a.strip()
        if not a:
            continue
        if ',' in a:
            parts = a.split(',', 1)
            names.append(f"{parts[1].strip()} {parts[0].strip()}")
        else:
            names.append(a)
    return names


def _normalize_author_name(name: str) -> str:
    """Normalize a name for deduplication: lowercase, remove dots, collapse spaces."""
    return re.sub(r'\s+', ' ', name.lower().replace('.', '').replace('-', ' ')).strip()


def _author_surname_initial(name: str):
    """Return (surname_lower, first_initial_lower) for fuzzy matching."""
    parts = name.strip().split()
    if not parts:
        return ('', '')
    surname = parts[-1].lower().rstrip('.')
    initial = parts[0].lstrip('.')[0].lower() if parts[0] else ''
    return (surname, initial)


def build_author_index(bib: Dict, ss: Dict) -> str:
    """Generate author index page with deduplicated authors.

    Dedup priority (three lookups before creating a new record):
      1. SS authorId (stable, cross-paper identity)
      2. Normalized name string (handles 'T.' vs 'T', case differences)
      3. Surname + first initial (handles 'D. Killeen' vs 'Daniel Killeen')
    """
    records: Dict[str, dict] = {}       # canonical_key → {name, papers}
    id_to_key:   Dict[str, str] = {}    # ss_authorId   → canonical_key
    norm_to_key: Dict[str, str] = {}    # normalized_name → canonical_key
    si_to_key:   Dict[tuple, str] = {}  # (surname, initial) → canonical_key

    def _register_name(ckey: str, display_name: str):
        """Register all lookup indices for a canonical key."""
        norm = _normalize_author_name(display_name)
        si   = _author_surname_initial(display_name)
        if norm not in norm_to_key:
            norm_to_key[norm] = ckey
        if si not in si_to_key:
            si_to_key[si] = ckey

    def _resolve_key(author_id: str, display_name: str) -> str:
        """Find existing canonical key or create a new one."""
        # 1. authorId
        if author_id and author_id in id_to_key:
            return id_to_key[author_id]
        # 2. exact normalized name
        norm = _normalize_author_name(display_name)
        if norm in norm_to_key:
            return norm_to_key[norm]
        # 3. surname + initial
        si = _author_surname_initial(display_name)
        if si[0] and si in si_to_key:
            return si_to_key[si]
        # Create new
        ckey = f'ss:{author_id}' if author_id else f'norm:{norm}'
        return ckey

    def add_author(author_id: str, display_name: str, paper_key: str):
        if not display_name:
            return
        ckey = _resolve_key(author_id, display_name)

        if ckey not in records:
            records[ckey] = {'name': display_name, 'papers': []}
            if author_id:
                id_to_key[author_id] = ckey
            _register_name(ckey, display_name)
        else:
            # Update authorId index if we now have one
            if author_id and author_id not in id_to_key:
                id_to_key[author_id] = ckey
            # Prefer the longer/fuller display name
            existing = records[ckey]['name']
            if len(display_name) > len(existing):
                records[ckey]['name'] = display_name
                _register_name(ckey, display_name)

        if paper_key not in records[ckey]['papers']:
            records[ckey]['papers'].append(paper_key)

    for bib_key, entry in bib.items():
        ss_d = ss.get(bib_key)
        bib_authors = _parse_bib_authors(entry.get('author', ''))

        if ss_d and ss_d.get('authors'):
            for ss_author in ss_d['authors']:
                author_id = (ss_author.get('authorId') or '').strip()
                ss_name   = (ss_author.get('name') or '').strip()
                if not ss_name:
                    continue
                # Prefer BibTeX full name when surname+initial matches
                ss_si = _author_surname_initial(ss_name)
                display = ss_name
                for bn in bib_authors:
                    if _author_surname_initial(bn) == ss_si:
                        display = bn  # e.g. "Daniel P Killeen" instead of "D. Killeen"
                        break
                add_author(author_id, display, bib_key)
        else:
            for bib_name in bib_authors:
                add_author('', bib_name, bib_key)

    # Sort by paper count desc, then display name
    sorted_authors = sorted(records.values(), key=lambda r: (-len(r['papers']), r['name']))

    cards_html = ''
    for rec in sorted_authors[:500]:
        author = rec['name']
        keys = rec['papers']
        count = len(keys)
        papers_links = ' '.join(
            f'<a href="papers/{k}.html" class="mini-chip" title="{html.escape(bib.get(k,{}).get("title","")[:60])}">{html.escape(k)}</a>'
            for k in keys[:6]
        )
        more = f'<span class="mini-chip text-muted">+{count-6} more</span>' if count > 6 else ''
        cards_html += f"""
<div class="author-card" data-name="{html.escape(author.lower())}">
  <div class="author-name">{html.escape(author)}</div>
  <div class="author-count">{count} paper{'s' if count != 1 else ''}</div>
  <div class="author-papers">{papers_links}{more}</div>
</div>"""

    content = f"""
<div class="authors-page">
  <header class="authors-header">
    <h1>Author Index</h1>
    <p>{len(sorted_authors)} unique authors from {len(bib)} bibliography entries, sorted by paper count.</p>
    <input type="text" id="author-filter" placeholder="Filter authors…" class="filter-input" autocomplete="off">
  </header>
  <div class="authors-grid" id="authors-grid">
    {cards_html}
  </div>
</div>
<script>
const af = document.getElementById('author-filter');
const ag = document.getElementById('authors-grid');
if (af && ag) {{
  af.addEventListener('input', () => {{
    const q = af.value.toLowerCase();
    ag.querySelectorAll('.author-card').forEach(card => {{
      card.style.display = card.querySelector('.author-name').textContent.toLowerCase().includes(q) ? '' : 'none';
    }});
  }});
}}
</script>
"""
    return page_shell("Author Index — ML for REIMS", content, root=".")


def build_timeline(bib: Dict, ss: Dict, chapter_citations: Dict[str, Set[str]]) -> str:
    """Generate timeline page grouping papers by decade/year."""
    from collections import defaultdict

    # Only include cited papers
    all_cited: Set[str] = set()
    for keys in chapter_citations.values():
        all_cited.update(keys)

    by_year: Dict[str, List[str]] = defaultdict(list)
    for key in all_cited:
        e = bib.get(key, {})
        year = e.get('year', 'Unknown')
        by_year[year].append(key)

    # Sort years
    def year_sort_key(y):
        try: return int(y)
        except: return 9999

    sorted_years = sorted(by_year.keys(), key=year_sort_key)

    # Group into decades
    decades: Dict[str, Dict[str, List[str]]] = defaultdict(dict)
    for year in sorted_years:
        try:
            decade = f"{int(year)//10*10}s"
        except:
            decade = "Unknown"
        decades[decade][year] = by_year[year]

    timeline_html = ''
    for decade in sorted(decades.keys(), key=lambda d: (9999 if d == 'Unknown' else int(d[:4]))):
        year_items = ''
        for year, keys in sorted(decades[decade].items(), key=lambda x: year_sort_key(x[0])):
            paper_items = ''
            for key in sorted(keys, key=lambda k: bib.get(k, {}).get('title', k)):
                e = bib.get(key, {})
                ss_d = ss.get(key)
                title = (ss_d.get('title') if ss_d else None) or e.get('title', key)
                authors = format_authors(e.get('author', ''), 2)
                cc = (ss_d.get('citationCount') or 0) if ss_d else 0
                cc_txt = f' · {cc:,} cites' if cc else ''
                paper_items += f'<li class="timeline-item"><a href="papers/{html.escape(key)}.html">{html.escape(title[:100])}</a><span class="timeline-meta">{html.escape(authors)}{cc_txt}</span></li>'

            year_items += f'<div class="timeline-year" id="year-{html.escape(year)}"><div class="timeline-year-label">{html.escape(year)}</div><ul class="timeline-papers">{paper_items}</ul></div>'

        timeline_html += f'<div class="timeline-decade"><h2 class="decade-label">{html.escape(decade)}</h2>{year_items}</div>'

    content = f"""
<div class="timeline-page">
  <header class="timeline-header">
    <h1>Publication Timeline</h1>
    <p>{len(all_cited)} cited papers spanning from {sorted_years[0] if sorted_years else '?'} to {sorted_years[-1] if sorted_years else '?'}.</p>
  </header>
  {timeline_html}
</div>
"""
    return page_shell("Publication Timeline — ML for REIMS", content, root=".")


def build_methods_page() -> str:
    """Generate the methods comparison page with thesis results."""
    m = THESIS_META

    rows = ''
    for task, baseline, best, gain in m['results']:
        rows += f"""
      <tr>
        <td><strong>{html.escape(task)}</strong></td>
        <td class="text-muted">{html.escape(baseline)}</td>
        <td class="methods-best">{html.escape(best)}</td>
        <td class="gain">{html.escape(gain)}</td>
      </tr>"""

    method_details = [
        ("MoE Transformer (Gone Phishing)", "Fish Species", "100.00%",
         "Mixture of Experts Transformer replacing FFN layers with gated expert sub-networks. Routes different spectral regions to specialized experts.",
         "chapter-4"),
        ("Ensemble Transformer (Autobots)", "Fish Body Part", "74.13%",
         "Multi-scale stacked ensemble: three Transformers with 2, 4, and 8 layers act as level-0 classifiers, combined by a meta-learner.",
         "chapter-4"),
        ("TL MoE Transformer", "Oil Contamination", "49.10%",
         "Transfer Learning applied to MoE Transformer: pre-trained on species identification, fine-tuned for ordinal oil contamination detection.",
         "chapter-5"),
        ("Pre-trained Transformer", "Cross-species Adulteration", "91.97%",
         "Transformer pre-trained with Masked Spectra Modelling (MSM), then fine-tuned for 3-class adulteration detection (Hoki/Mackerel/mixture).",
         "chapter-5"),
        ("SpectroSim (Transformer)", "Batch Detection", "70.80%",
         "Self-supervised contrastive framework (SimCLR adaptation) using a Transformer encoder to learn pairwise mass spectra similarity without labels.",
         "chapter-6"),
    ]

    detail_cards = ''
    for name, task, acc, desc, chapter in method_details:
        ch_num = chapter.replace('chapter-', '')
        detail_cards += f"""
<div class="method-card">
  <div class="method-card-header">
    <div class="method-name">{html.escape(name)}</div>
    <div class="method-task">{html.escape(task)}</div>
    <div class="method-acc">{html.escape(acc)}</div>
  </div>
  <p class="method-desc">{html.escape(desc)}</p>
  <a href="chapters/{html.escape(chapter)}.html" class="method-link">See Chapter {html.escape(ch_num)} →</a>
</div>"""

    content = f"""
<div class="methods-page">
  <header class="methods-header">
    <h1>Methods Comparison</h1>
    <p>Cross-chapter comparison of all analytical tasks, baselines, and best-performing models from the thesis.</p>
  </header>

  <section class="wiki-section">
    <h2>Summary Results</h2>
    <div class="table-wrap">
    <table class="methods-table">
      <thead>
        <tr>
          <th>Task</th>
          <th>Baseline (OPLS-DA)</th>
          <th>Best Deep Learning Model</th>
          <th>Improvement</th>
        </tr>
      </thead>
      <tbody>{rows}
      </tbody>
    </table>
    </div>
  </section>

  <section class="wiki-section">
    <h2>Model Details</h2>
    <div class="method-cards-grid">
      {detail_cards}
    </div>
  </section>

  <section class="wiki-section">
    <h2>Common Methods</h2>
    <p>All models are evaluated using <strong>Balanced Classification Accuracy (BCA)</strong> to handle class imbalance. The baseline throughout is <strong>OPLS-DA</strong> (Orthogonal Partial Least Squares Discriminant Analysis), the standard chemometrics method. Deep learning architectures are all based on the <strong>Transformer</strong> with various enhancements (MoE, ensembling, transfer learning, contrastive learning).</p>
    <p>Explainability is provided via <strong>LIME</strong> and <strong>Grad-CAM</strong>, identifying which m/z spectral features drive each prediction.</p>
  </section>
</div>
"""
    return page_shell("Methods Comparison — ML for REIMS", content, root=".")


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

/* More dropdown */
.nav-more { position: relative; display: flex; align-items: center; }
.nav-more-btn {
  background: none;
  border: none;
  color: rgba(255,255,255,0.8);
  cursor: pointer;
  padding: 0.4rem 0.75rem;
  border-radius: 4px;
  font-size: 0.9rem;
  line-height: inherit;
  font-family: inherit;
  vertical-align: middle;
  transition: background 0.15s, color 0.15s;
}
.nav-more-btn:hover { background: rgba(255,255,255,0.1); color: #fff; }
.nav-more-dropdown {
  display: none;
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  background: var(--nav-bg);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: var(--radius);
  box-shadow: var(--shadow-md);
  min-width: 160px;
  z-index: 200;
  padding: 0.35rem 0;
}
.nav-more-dropdown.open { display: block; }
.nav-more-dropdown a {
  display: block;
  padding: 0.45rem 1rem;
  color: rgba(255,255,255,0.85);
  font-size: 0.88rem;
  text-decoration: none;
  transition: background 0.12s;
}
.nav-more-dropdown a:hover { background: rgba(255,255,255,0.08); color: #fff; text-decoration: none; }
.mobile-menu-divider { height: 1px; background: rgba(255,255,255,0.1); margin: 0.35rem 0; }

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
.sri-snippet { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem; line-height: 1.4; }
.sri-snippet mark { background: rgba(59,130,246,0.25); color: var(--text); border-radius: 2px; padding: 0 1px; }
.search-results { max-height: 500px; }

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

/* ── Thesis Stats Bar ───────────────────────────────────────── */
.thesis-stats-bar {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0;
  background: var(--bg-alt);
  border-bottom: 1px solid var(--border);
}
.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.9rem 1.5rem;
  border-right: 1px solid var(--border);
}
.stat-item:last-child { border-right: none; }
.stat-num {
  font-size: 1.4rem;
  font-weight: 800;
  color: var(--accent);
  line-height: 1.1;
  letter-spacing: -0.03em;
}
.stat-label {
  font-size: 0.72rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-top: 0.15rem;
}

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
.toc-list a.toc-active { color: var(--accent); border-color: var(--accent); font-weight: 600; }
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

/* Nested bullet lists inside table cells */
.cell-list {
  list-style: none;
  margin: 0;
  padding: 0;
  font-size: inherit;
}
.cell-list li {
  padding: 0.1rem 0;
  line-height: 1.5;
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

/* ── Reading Progress Bar ─────────────────────────────────── */
#reading-progress {
  position: fixed;
  top: 0;
  left: 0;
  height: 3px;
  background: var(--accent);
  z-index: 9999;
  width: 0%;
  transition: width 0.08s linear;
  pointer-events: none;
}

/* ── Citation Hover Card ──────────────────────────────────── */
.cite-card {
  position: fixed;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-md);
  padding: 0.9rem 1rem;
  max-width: 360px;
  min-width: 240px;
  z-index: 1000;
  font-size: 0.84rem;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.15s;
  line-height: 1.5;
}
.cite-card.visible { opacity: 1; pointer-events: auto; }
.cite-card-title { font-weight: 700; color: var(--text); margin-bottom: 0.3rem; line-height: 1.4; }
.cite-card-authors { color: var(--text-muted); font-size: 0.79rem; margin-bottom: 0.2rem; }
.cite-card-meta { display: flex; gap: 0.5rem; flex-wrap: wrap; font-size: 0.77rem; color: var(--text-muted); margin-bottom: 0.35rem; }
.cite-card-abstract { font-size: 0.79rem; color: var(--text-muted); line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.cite-card-cc { background: var(--accent-light); color: var(--accent); padding: 0.1rem 0.35rem; border-radius: 3px; font-weight: 600; }

/* ── Glossary Term Hover ──────────────────────────────────── */
.glossary-term {
  border-bottom: 1px dotted var(--accent);
  cursor: help;
  color: inherit;
  text-decoration: none;
}
.glossary-term:hover { color: var(--accent); text-decoration: none; }

.glossary-card {
  position: fixed;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-md);
  padding: 0.9rem 1rem;
  max-width: 340px;
  min-width: 220px;
  z-index: 1001;
  font-size: 0.84rem;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.15s;
  line-height: 1.5;
}
.glossary-card.visible { opacity: 1; pointer-events: auto; }
.glossary-card-term { font-weight: 700; font-size: 0.9rem; color: var(--accent); margin-bottom: 0.1rem; }
.glossary-card-full { font-size: 0.77rem; color: var(--text-muted); font-style: italic; margin-bottom: 0.35rem; }
.glossary-card-def { font-size: 0.81rem; color: var(--text); line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
.glossary-card-link { font-size: 0.77rem; color: var(--accent); margin-top: 0.4rem; display: block; }

/* ── Glossary Page ────────────────────────────────────────── */
.glossary-page { max-width: 860px; margin: 0 auto; padding: 2rem 1rem 3rem; }
.glossary-header { margin-bottom: 1.5rem; }
.glossary-header h1 { font-size: 2rem; font-weight: 800; margin-bottom: 0.4rem; }
.glossary-header p { color: var(--text-muted); }
.glossary-alpha-nav { display: flex; flex-wrap: wrap; gap: 0.25rem; margin-bottom: 2rem; }
.alpha-link {
  display: inline-block;
  padding: 0.2rem 0.5rem;
  background: var(--bg-alt);
  border: 1px solid var(--border);
  border-radius: 3px;
  font-size: 0.82rem;
  color: var(--text-muted);
  font-weight: 600;
  text-decoration: none;
}
.alpha-link:hover { background: var(--accent-light); border-color: var(--accent); color: var(--accent); text-decoration: none; }
.alpha-section { margin-bottom: 2rem; }
.alpha-section > h2 {
  font-size: 1.4rem;
  font-weight: 800;
  color: var(--accent);
  border-bottom: 2px solid var(--border);
  padding-bottom: 0.3rem;
  margin-bottom: 1rem;
}
.glossary-entry { margin-bottom: 1.25rem; padding-bottom: 1.25rem; border-bottom: 1px solid var(--border); }
.glossary-entry:last-child { border-bottom: none; }
.glossary-entry-term { font-size: 1rem; font-weight: 700; color: var(--text); }
.glossary-entry-full { font-size: 0.83rem; color: var(--text-muted); font-style: italic; margin: 0.1rem 0 0.4rem; }
.glossary-entry-def { font-size: 0.92rem; color: var(--text); line-height: 1.65; }
.glossary-entry-cat {
  display: inline-block;
  margin-top: 0.35rem;
  padding: 0.1rem 0.4rem;
  background: var(--bg-alt);
  border: 1px solid var(--border);
  border-radius: 3px;
  font-size: 0.72rem;
  color: var(--text-muted);
}

/* ── Figure Gallery ───────────────────────────────────────── */
.gallery-page { max-width: 1200px; margin: 0 auto; padding: 2rem 1rem 3rem; }
.gallery-header { margin-bottom: 1.5rem; }
.gallery-header h1 { font-size: 2rem; font-weight: 800; margin-bottom: 0.4rem; }
.gallery-header p { color: var(--text-muted); }
.gallery-filter-bar { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 1.5rem; }
.gallery-filter-btn {
  padding: 0.3rem 0.85rem;
  background: var(--bg-alt);
  border: 1px solid var(--border);
  border-radius: 20px;
  font-size: 0.82rem;
  color: var(--text-muted);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.gallery-filter-btn.active, .gallery-filter-btn:hover {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1rem;
}
.gallery-item {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  transition: box-shadow 0.2s, transform 0.15s;
}
.gallery-item:hover { box-shadow: var(--shadow-md); transform: translateY(-2px); }
.gallery-item a { display: block; }
.gallery-item img {
  width: 100%;
  height: 175px;
  object-fit: contain;
  background: var(--bg-alt);
  padding: 0.5rem;
}
.gallery-item-caption {
  padding: 0.55rem 0.75rem;
  font-size: 0.79rem;
  color: var(--text-muted);
  line-height: 1.4;
  border-top: 1px solid var(--border);
}
.gallery-item-chapter {
  display: inline-block;
  padding: 0.1rem 0.35rem;
  background: var(--accent-light);
  color: var(--accent);
  border-radius: 3px;
  font-size: 0.7rem;
  font-weight: 600;
  margin-bottom: 0.2rem;
}

/* ── Cited Together ───────────────────────────────────────── */
.cited-together-block { margin: 1.5rem 0; }
.cited-together-block h3 { font-size: 1rem; font-weight: 700; margin-bottom: 0.5rem; }
.cited-together-list { list-style: none; font-size: 0.87rem; }
.cited-together-list li {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  flex-wrap: wrap;
  padding: 0.35rem 0;
  border-bottom: 1px solid var(--border);
}
.cited-together-list li:last-child { border-bottom: none; }
.co-cite-link { color: var(--accent); flex: 1; min-width: 0; }
.co-cite-meta { color: var(--text-muted); font-size: 0.78rem; white-space: nowrap; }
.co-cite-count {
  background: var(--bg-alt);
  border: 1px solid var(--border);
  border-radius: 3px;
  padding: 0.1rem 0.35rem;
  font-size: 0.74rem;
  color: var(--text-muted);
  white-space: nowrap;
}

/* ── BibTeX Copy Button ───────────────────────────────────── */
.bibtex-mini {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0.6rem;
  white-space: pre;
  overflow-x: auto;
  margin-bottom: 0.5rem;
  color: var(--text-muted);
}
.bibtex-copy-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.85rem;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
  width: 100%;
  justify-content: center;
}
.bibtex-copy-btn:hover { background: var(--accent-hover); }
.bibtex-copy-btn.copied { background: var(--green); }

/* ── Hatnote ──────────────────────────────────────────────── */
.hatnote {
  font-style: italic;
  font-size: 0.88rem;
  color: var(--text-muted);
  background: var(--bg-alt);
  border-left: 3px solid var(--accent);
  padding: 0.5rem 0.9rem;
  border-radius: 0 4px 4px 0;
  margin-bottom: 1.25rem;
}
.hatnote a { color: var(--accent); }

/* ── Reading Time ─────────────────────────────────────────── */
.reading-time {
  font-size: 0.78rem;
  color: var(--text-muted);
  margin-top: 0.4rem;
}

/* ── See Also ─────────────────────────────────────────────── */
.see-also {
  font-size: 0.88rem;
  background: var(--bg-alt);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0.55rem 0.9rem;
  margin: 1.5rem 0;
  color: var(--text-muted);
}
.see-also a { color: var(--accent); }

/* ── Did You Know ─────────────────────────────────────────── */
.did-you-know {
  background: var(--accent-light);
  border: 1px solid rgba(26,115,232,0.25);
  border-radius: var(--radius);
  padding: 0.75rem 1rem;
  margin-bottom: 1.5rem;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.did-you-know strong { color: var(--accent); white-space: nowrap; }
.did-you-know span { flex: 1; }
.dyk-next {
  background: none;
  border: 1px solid var(--accent);
  color: var(--accent);
  border-radius: 50%;
  width: 28px;
  height: 28px;
  cursor: pointer;
  font-size: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.15s;
}
.dyk-next:hover { background: var(--accent); color: #fff; }

/* ── Navbox ───────────────────────────────────────────────── */
.navbox {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin: 2rem 0 1rem;
  background: var(--bg-alt);
  font-size: 0.85rem;
}
.navbox > summary {
  padding: 0.5rem 0.9rem;
  cursor: pointer;
  font-weight: 700;
  font-size: 0.82rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  user-select: none;
}
.navbox-body {
  padding: 0.5rem 0.9rem 0.75rem;
  border-top: 1px solid var(--border);
}
.navbox-group {
  margin: 0.3rem 0;
  line-height: 1.6;
}
.navbox-group a { color: var(--accent); font-size: 0.83rem; }

/* ── Stub Notice ─────────────────────────────────────────── */
.stub-notice {
  font-style: italic;
  font-size: 0.85rem;
  color: var(--text-muted);
  background: var(--bg-alt);
  border: 1px dashed var(--border);
  border-radius: 4px;
  padding: 0.5rem 0.9rem;
  margin-bottom: 1.25rem;
}

/* ── Back to Top ─────────────────────────────────────────── */
#back-to-top {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: 50%;
  width: 42px;
  height: 42px;
  font-size: 1.1rem;
  cursor: pointer;
  box-shadow: var(--shadow-md);
  display: none;
  align-items: center;
  justify-content: center;
  z-index: 500;
  transition: background 0.15s, opacity 0.2s;
}
#back-to-top:hover { background: var(--accent-hover); }
#back-to-top.visible { display: flex; }

/* ── Heading Anchor ──────────────────────────────────────── */
.heading-anchor {
  margin-left: 0.4rem;
  opacity: 0;
  font-size: 0.75em;
  color: var(--text-muted);
  cursor: pointer;
  user-select: none;
  transition: opacity 0.15s;
  text-decoration: none;
}
h2:hover .heading-anchor,
h3:hover .heading-anchor,
h4:hover .heading-anchor { opacity: 1; }

/* ── Search Result Groups ────────────────────────────────── */
.search-result-group {
  padding: 0.25rem 1rem;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--text-muted);
  background: var(--bg-alt);
  border-bottom: 1px solid var(--border);
}

/* ── Graph Page ──────────────────────────────────────────── */
.graph-page { display: flex; flex-direction: column; height: calc(100vh - 56px); }
.graph-header {
  padding: 1rem 1.5rem 0.75rem;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.graph-header h1 { font-size: 1.4rem; font-weight: 800; margin-bottom: 0.25rem; }
.graph-header p { font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.5rem; }
.graph-legend { display: flex; flex-wrap: wrap; gap: 0.5rem; font-size: 0.78rem; }
.graph-legend-item { display: flex; align-items: center; gap: 0.3rem; color: var(--text-muted); }
.graph-legend-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
#graph-container { flex: 1; overflow: hidden; background: var(--bg-alt); }
.graph-tooltip {
  position: absolute;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.5rem 0.75rem;
  font-size: 0.82rem;
  pointer-events: none;
  max-width: 280px;
  box-shadow: var(--shadow-md);
  z-index: 9999;
  color: var(--text);
}

/* ── Authors Page ────────────────────────────────────────── */
.authors-page { max-width: 1200px; margin: 0 auto; padding: 2rem 1rem 3rem; }
.authors-header { margin-bottom: 2rem; }
.authors-header h1 { font-size: 2rem; font-weight: 800; margin-bottom: 0.4rem; }
.authors-header p { color: var(--text-muted); margin-bottom: 1rem; }
.authors-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.75rem;
}
.author-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.85rem 1rem;
  transition: box-shadow 0.2s;
}
.author-card:hover { box-shadow: var(--shadow-md); }
.author-name { font-weight: 700; font-size: 0.92rem; margin-bottom: 0.2rem; }
.author-count { font-size: 0.78rem; color: var(--text-muted); margin-bottom: 0.4rem; }
.author-papers { display: flex; flex-wrap: wrap; gap: 0.25rem; }

/* ── Timeline Page ───────────────────────────────────────── */
.timeline-page { max-width: 900px; margin: 0 auto; padding: 2rem 1rem 3rem; }
.timeline-header { margin-bottom: 2rem; }
.timeline-header h1 { font-size: 2rem; font-weight: 800; margin-bottom: 0.4rem; }
.timeline-header p { color: var(--text-muted); }
.timeline-decade { margin-bottom: 2.5rem; }
.decade-label {
  font-size: 1.3rem;
  font-weight: 800;
  color: var(--accent);
  border-bottom: 2px solid var(--border);
  padding-bottom: 0.3rem;
  margin-bottom: 1rem;
}
.timeline-year { margin-bottom: 1.25rem; }
.timeline-year-label {
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.4rem;
}
.timeline-papers { list-style: none; }
.timeline-item {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.5rem;
  padding: 0.3rem 0;
  border-bottom: 1px solid var(--border);
  font-size: 0.88rem;
}
.timeline-item:last-child { border-bottom: none; }
.timeline-item a { color: var(--accent); flex: 1; }
.timeline-meta { font-size: 0.78rem; color: var(--text-muted); white-space: nowrap; }

/* ── Methods Page ────────────────────────────────────────── */
.methods-page { max-width: 1000px; margin: 0 auto; padding: 2rem 1rem 3rem; }
.methods-header { margin-bottom: 2rem; }
.methods-header h1 { font-size: 2rem; font-weight: 800; margin-bottom: 0.4rem; }
.methods-header p { color: var(--text-muted); }
.methods-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}
.methods-table th {
  background: var(--bg-alt);
  border: 1px solid var(--border);
  padding: 0.6rem 0.75rem;
  text-align: left;
  font-weight: 700;
}
.methods-table td {
  border: 1px solid var(--border);
  padding: 0.55rem 0.75rem;
  vertical-align: middle;
}
.methods-table tr:nth-child(even) td { background: var(--bg-alt); }
.methods-best { font-weight: 700; color: var(--text); }
.method-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
}
.method-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem 1.1rem;
  transition: box-shadow 0.2s;
}
.method-card:hover { box-shadow: var(--shadow-md); }
.method-card-header { margin-bottom: 0.6rem; }
.method-name { font-weight: 700; font-size: 0.95rem; }
.method-task { font-size: 0.8rem; color: var(--text-muted); }
.method-acc { font-size: 1.1rem; font-weight: 800; color: var(--green); margin: 0.2rem 0; }
.method-desc { font-size: 0.85rem; color: var(--text-muted); line-height: 1.55; margin-bottom: 0.75rem; }
.method-link { font-size: 0.83rem; color: var(--accent); font-weight: 600; }
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

  function highlightSnippet(text, q) {
    if (!text) return '';
    const idx = text.toLowerCase().indexOf(q.toLowerCase());
    let snip;
    if (idx < 0) {
      snip = text.slice(0, 130) + (text.length > 130 ? '…' : '');
    } else {
      const start = Math.max(0, idx - 40);
      const end = Math.min(text.length, idx + q.length + 80);
      snip = (start > 0 ? '…' : '') + text.slice(start, end) + (end < text.length ? '…' : '');
    }
    const escaped = escHtml(snip);
    const escapedQ = escHtml(q).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return escaped.replace(new RegExp('(' + escapedQ + ')', 'gi'), '<mark>$1</mark>');
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

    // Group by type, up to 5 per group
    const groups = { chapter: [], paper: [], glossary: [] };
    for (const item of matches) {
      const g = groups[item.type];
      if (g && g.length < 5) g.push(item);
    }

    const typeLabels = { chapter: 'Chapters', paper: 'Papers', glossary: 'Glossary' };
    let out = '';
    for (const [type, items] of Object.entries(groups)) {
      if (!items.length) continue;
      out += `<div class="search-result-group">${typeLabels[type]}</div>`;
      out += items.map(item => {
        const snippet = highlightSnippet(item.snippet || item.text || '', q);
        return `<div class="search-result-item" onclick="window.location='${siteUrl(item.url)}'">
          <div class="sri-title">${escHtml((item.title || '').slice(0, 90))}</div>
          <div class="sri-meta">${escHtml((item.meta || '').slice(0, 80))}</div>
          ${snippet ? `<div class="sri-snippet">${snippet}</div>` : ''}
        </div>`;
      }).join('');
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

// Active TOC highlighting with sidebar scroll-into-view
(function() {
  const sidebar = document.querySelector('.sidebar-sticky');
  const headings = Array.from(document.querySelectorAll('h2[id], h3[id], h4[id]'));
  if (!headings.length) return;

  // Build id → toc link map once
  const tocLinks = {};
  headings.forEach(h => {
    const a = document.querySelector(`.toc-list a[href="#${h.id}"]`);
    if (a) tocLinks[h.id] = a;
  });

  let activeLink = null;

  function scrollTocToLink(link) {
    if (!sidebar) return;
    const linkRect = link.getBoundingClientRect();
    const sbRect = sidebar.getBoundingClientRect();
    const relTop = linkRect.top - sbRect.top + sidebar.scrollTop;
    const target = relTop - sbRect.height / 3;
    sidebar.scrollTo({ top: target, behavior: 'smooth' });
  }

  function update() {
    // Find the last heading whose top is at or above 30% of the viewport
    const threshold = window.innerHeight * 0.3;
    let current = null;
    for (const h of headings) {
      if (h.getBoundingClientRect().top <= threshold) current = h;
      else break;
    }

    const link = current ? tocLinks[current.id] : null;
    if (link === activeLink) return;

    if (activeLink) activeLink.classList.remove('toc-active');
    if (link) {
      link.classList.add('toc-active');
      scrollTocToLink(link);
    }
    activeLink = link;
  }

  window.addEventListener('scroll', update, { passive: true });
  update();
})();

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

    # Pre-build shared JS snippets
    papers_meta_js = build_papers_meta_js(bib, ss_data)
    glossary_js = build_glossary_js()

    # Pre-compute thesis stats for homepage
    _total_words = 0
    _total_figs = 0
    _total_eqs = 0
    for _slug, _ in CHAPTERS:
        _ltx = chapter_latex.get(_slug, '')
        _plain = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', _ltx)
        _plain = re.sub(r'[\\{}%$]', ' ', _plain)
        _total_words += len(_plain.split())
        _total_figs += len(re.findall(r'\\includegraphics', _ltx))
        _total_eqs += len(re.findall(r'\\begin\{(?:equation|align)\*?\}|\$\$', _ltx))
    thesis_stats = {
        'words': _total_words,
        'figures': _total_figs,
        'equations': _total_eqs,
        'chapters': len(CHAPTERS),
        'papers': len(bib),
        'glossary': len(GLOSSARY),
    }

    # Homepage
    (SITE_DIR / "index.html").write_text(
        build_index(bib, ss_data, chapter_citations, thesis_stats))
    print("  index.html done")

    # Chapters — also collect all figures for gallery
    all_figures: List[dict] = []
    for slug, title in CHAPTERS:
        latex = chapter_latex.get(slug, "")
        html_out, figs = build_chapter(slug, title, latex, bib, ss_data,
                                       chapter_citations, papers_meta_js)
        (SITE_DIR / "chapters" / f"{slug}.html").write_text(html_out)
        all_figures.extend(figs)
        print(f"  chapters/{slug}.html done ({len(figs)} figures)")

    # Build reverse map for paper pages: key → {ch_slug: ch_title}
    paper_chapter_map: Dict[str, Dict[str, str]] = {}
    for ch_slug, ch_title in CHAPTERS:
        for key in chapter_citations.get(ch_slug, set()):
            paper_chapter_map.setdefault(key, {})[ch_slug] = ch_title

    # Compute co-citations
    co_citations = compute_co_citations(chapter_citations)

    # Paper pages
    print("  Generating paper pages...")
    for key, entry in bib.items():
        ss = ss_data.get(key)
        cited_in = paper_chapter_map.get(key, {})
        co_cited = co_citations.get(key, [])
        html_out = build_paper(key, entry, ss, cited_in,
                               bib=bib, co_cited=co_cited,
                               papers_meta_js=papers_meta_js)
        (SITE_DIR / "papers" / f"{key}.html").write_text(html_out)
    print(f"  {len(bib)} paper pages done")

    # Papers index
    (SITE_DIR / "papers.html").write_text(
        build_papers_index(bib, ss_data, chapter_citations))
    print("  papers.html done")

    # Glossary
    (SITE_DIR / "glossary.html").write_text(build_glossary())
    print("  glossary.html done")

    # Figure gallery
    (SITE_DIR / "figures.html").write_text(build_figure_gallery(all_figures))
    print(f"  figures.html done ({len(all_figures)} figures)")

    # Search index
    build_search_index(bib, ss_data, chapter_citations, chapter_latex)

    # Citation graph
    (SITE_DIR / "graph.html").write_text(
        build_citation_graph(bib, ss_data, chapter_citations))
    print("  graph.html done")

    # Author index
    (SITE_DIR / "authors.html").write_text(
        build_author_index(bib, ss_data))
    print("  authors.html done")

    # Timeline
    (SITE_DIR / "timeline.html").write_text(
        build_timeline(bib, ss_data, chapter_citations))
    print("  timeline.html done")

    # Methods comparison
    (SITE_DIR / "methods.html").write_text(build_methods_page())
    print("  methods.html done")

    print(f"\n✅ Site built at: {SITE_DIR}")
    print(f"   Open: {SITE_DIR / 'index.html'}")


if __name__ == "__main__":
    main()
