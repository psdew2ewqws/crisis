"""Arabic-aware sub-theme extractor for the voc360 why-chain / cluster drill-down.

Pure-python (stdlib only — `collections`, `re`). Import-safe: no torch / timesfm /
llm / db hard dependency, so a box without those still imports this module.

Given a list of REAL `segment_text` strings (from `ril_text_segments`, joined via
`ril_cluster_members`), it counts the dominant Arabic keyword n-grams (unigrams or
adjacent bigrams) and returns ranked themes, each carrying its real supporting
count, document-share weight, and up to a couple of verbatim sample segments as
grounded evidence. Nothing is fabricated — every theme + sample traces to an input
row.

Two public entry points (both back the same engine, different consumer contracts):

- `extract_subthemes(segments, n=8, ngram=1) -> [{term, count, weight, samples}]`
  The D-whys contract used by `whys.py` (depth-2 unigram, depth-3 bigram).

- `extract(segments, top_k=6, ngram=1, sample_ids=None) -> [{theme, count, share,
  samples, sample_ids}]`
  The QA / suggest contract (`subthemes.extract(...)`), optionally threading the
  per-segment `segment_id` through so each theme carries citable ids.

AEGIS tokens / Arabic dir='rtl' are a frontend concern; this module only returns
the raw retrieved Arabic text verbatim so the UI can render it.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable, Sequence

# ---------------------------------------------------------------------------
# Arabic normalization
# ---------------------------------------------------------------------------

# Tashkeel (harakat) + tatweel — strip diacritics and the kashida elongation.
_TASHKEEL = re.compile(r"[ؗ-ًؚ-ْٰـ]")
# Keep Arabic letters + ASCII letters/digits; everything else -> separator.
_NON_TOKEN = re.compile(r"[^ء-ي٠-٩a-z0-9]+")
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _normalize(text: str) -> str:
    """Strip tashkeel/tatweel, unify alef/ya/ta-marbuta, lowercase latin."""
    if not text:
        return ""
    t = str(text)
    t = _TASHKEEL.sub("", t)
    t = t.translate(_ARABIC_DIGITS)
    # unify alef variants -> ا, ya/alef-maqsura -> ي, ta-marbuta -> ه, hamza-on-w/y
    t = (
        t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
        .replace("ى", "ي").replace("ئ", "ي")
        .replace("ة", "ه")
        .replace("ؤ", "و")
    )
    return t.lower()


# ---------------------------------------------------------------------------
# Stopwords — common Arabic function words + a few latin glue words.
# ---------------------------------------------------------------------------

_STOPWORDS: set[str] = {
    # particles / pronouns / conjunctions (already alef-normalized form)
    "في", "من", "على", "الى", "عن", "مع", "هذا", "هذه", "ذلك", "تلك",
    "التي", "الذي", "الذين", "اللذين", "كان", "كانت", "يكون", "تكون",
    "قد", "لقد", "لا", "ما", "ماذا", "لماذا", "كيف", "اين", "متى", "هل",
    "ان", "انه", "انها", "الا", "ال", "يا", "هو", "هي", "هم", "هن", "نحن",
    "انت", "انتم", "انا", "كل", "بعض", "كما", "ايضا", "ثم", "او", "ام",
    "بل", "حتى", "اذا", "لكن", "لان", "لانه", "عند", "عندما", "بين", "خلال",
    "بعد", "قبل", "فقط", "جدا", "غير", "دون", "بدون", "نفس", "حول", "ضد",
    "وهو", "وهي", "وان", "وقد", "ولا", "فلا", "فان", "وكان", "كذلك",
    "اي", "به", "بها", "له", "لها", "منه", "منها", "فيه", "فيها", "عليه",
    "عليها", "اليه", "اليها", "هناك", "هنا", "حيث", "لدى", "لدي", "اكثر",
    "اقل", "جميع", "اول", "اخر", "اخرى", "شيء", "شي", "يتم", "تم",
    # extremely generic civic words that add no theme signal on their own
    "خدمه", "خدمات", "تطبيق", "موضوع", "مشكله", "شكوى", "شكوي",
    # latin glue
    "the", "and", "for", "with", "this", "that", "are", "was", "you",
    "not", "but", "all", "any", "service", "app", "from",
}


def _tokens(norm: str) -> list[str]:
    """Tokenize a normalized string: split on non-token chars, drop short tokens
    (len<3, after stripping pure-digit noise) and stopwords."""
    out: list[str] = []
    for tok in _NON_TOKEN.split(norm):
        if len(tok) < 3:
            continue
        if tok.isdigit():
            continue
        if tok in _STOPWORDS:
            continue
        out.append(tok)
    return out


def _grams(tokens: Sequence[str], ngram: int) -> list[str]:
    """Unigrams (ngram=1) or adjacent bigrams (ngram>=2). Bigram parts must each
    survive the stopword/length filter (they already did via `_tokens`)."""
    if ngram <= 1:
        return list(tokens)
    grams: list[str] = []
    for i in range(len(tokens) - ngram + 1):
        grams.append(" ".join(tokens[i : i + ngram]))
    return grams


# ---------------------------------------------------------------------------
# Core ranking
# ---------------------------------------------------------------------------


def _rank(
    segments: Sequence[str],
    top_k: int,
    ngram: int,
    extra_stop: Iterable[str] | None,
    sample_ids: Sequence[Any] | None,
) -> list[dict[str, Any]]:
    """Shared engine: count n-grams across segments, attach verbatim samples.

    Returns rows: {term, count, weight, samples, sample_ids}. `weight` is the
    document-share (#segments containing the term / total segments), capped 1.0.
    """
    # Coerce to a clean list of non-empty strings; remember each segment's id.
    rows: list[tuple[str, Any]] = []
    for i, seg in enumerate(segments or []):
        if not seg:
            continue
        s = str(seg).strip()
        if not s:
            continue
        sid = sample_ids[i] if (sample_ids is not None and i < len(sample_ids)) else None
        rows.append((s, sid))

    total = len(rows)
    if total == 0:
        return []

    stop = set(_STOPWORDS)
    if extra_stop:
        for w in extra_stop:
            n = _normalize(w)
            if n:
                stop.add(n)
                stop.update(_tokens(n))  # multi-word service names -> token parts

    # Document-frequency: how many distinct segments each term appears in (more
    # robust against one ranty segment than a raw term count).
    doc_freq: Counter = Counter()
    # First verbatim sample(s) + ids per term, in input order.
    term_samples: dict[str, list[str]] = {}
    term_sample_ids: dict[str, list[Any]] = {}

    for raw, sid in rows:
        norm = _normalize(raw)
        toks = [t for t in _tokens(norm) if t not in stop]
        grams = _grams(toks, ngram)
        seen_here = set(grams)  # count each term once per segment
        for term in seen_here:
            doc_freq[term] += 1
            if term not in term_samples:
                term_samples[term] = [raw]
                term_sample_ids[term] = [sid] if sid is not None else []
            elif len(term_samples[term]) < 2 and raw not in term_samples[term]:
                term_samples[term].append(raw)
                if sid is not None:
                    term_sample_ids[term].append(sid)

    ranked = doc_freq.most_common()
    out: list[dict[str, Any]] = []
    for term, count in ranked:
        if len(out) >= top_k:
            break
        weight = round(min(1.0, count / total), 4)
        out.append(
            {
                "term": term,
                "count": int(count),
                "weight": weight,
                "samples": term_samples.get(term, [])[:2],
                "sample_ids": term_sample_ids.get(term, [])[:2],
            }
        )
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_subthemes(
    segments: Sequence[str],
    n: int = 8,
    ngram: int = 1,
    extra_stop: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """D-whys contract. Frequency over Arabic `segment_text`.

    Returns ``[{term, count, weight, samples:[<=2 verbatim segment_text]}]`` sorted
    by descending support. `weight` = document-share (0..1). Used at depth-2
    (ngram=1) and depth-3 (ngram=2) of the why-chain. `extra_stop` lets the caller
    drop service-name tokens so the service's own name isn't a "theme".

    Never raises on bad input; an empty / all-blank list yields ``[]``.
    """
    try:
        rows = _rank(segments, top_k=n, ngram=ngram, extra_stop=extra_stop, sample_ids=None)
    except Exception:
        return []
    # D-whys shape: drop the QA-only sample_ids key.
    return [
        {"term": r["term"], "count": r["count"], "weight": r["weight"], "samples": r["samples"]}
        for r in rows
    ]


def extract(
    segments: Sequence[str],
    top_k: int = 6,
    ngram: int = 1,
    sample_ids: Sequence[Any] | None = None,
    extra_stop: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """QA / suggest contract (`subthemes.extract(...)`).

    Returns ``[{theme, count, share, samples:[<=2 verbatim], sample_ids:[<=2]}]``
    sorted by descending support. `share` is the document-share (alias of
    `weight`). Pass `sample_ids` (parallel to `segments`, e.g. the `segment_id`
    column) to thread citable ids through each theme. Import-safe; degrades to
    ``[]`` on any failure.
    """
    try:
        rows = _rank(
            segments, top_k=top_k, ngram=ngram, extra_stop=extra_stop, sample_ids=sample_ids
        )
    except Exception:
        return []
    return [
        {
            "theme": r["term"],
            "count": r["count"],
            "share": r["weight"],
            "samples": r["samples"],
            "sample_ids": r["sample_ids"],
        }
        for r in rows
    ]


# Convenience: a quick self-check when run directly (no DB, grounded sample text).
if __name__ == "__main__":  # pragma: no cover
    demo = [
        "تأخير في صرف دعم صندوق المعونة الوطنية منذ شهرين",
        "تأخير صرف الدعم ولا يوجد رد من صندوق المعونة",
        "رسوم الخدمة المستعجلة مرتفعة جدا في مراكز الخدمة",
        "الباص السريع متأخر دائما ولا يلتزم بالمواعيد",
        "تأخير في الرد على الشكاوى عبر التطبيق",
    ]
    import json as _json

    print(_json.dumps(extract_subthemes(demo, n=6, ngram=1), ensure_ascii=False, indent=2))
    print("---bigrams---")
    print(_json.dumps(extract_subthemes(demo, n=6, ngram=2), ensure_ascii=False, indent=2))
