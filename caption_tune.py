# -*- coding: utf-8 -*-
"""Caption fixes applied at PUBLISH time, so a schedule.csv rebuild can never
drop them (build_web_assets.py regenerates every caption from the content
plan - see the rebuild traps in SETUP/memory).

  A. questions.csv (post_id,question): that post ends with a specific question
     instead of the generic "Thinking about buying or selling..." line.
     Comments are what push reach on Instagram and Threads.
  B. Reels: "Swipe through all 8." / "Desliza para ver los 8." make no sense on
     a video (IG reel, Facebook video, YouTube Short) - replaced.
  C. YouTube titles get a place keyword - see channels.yt_title_from_caption.

The row dict is copied, never modified in place; schedule.csv is untouched.
"""
import os, io, csv, re

HERE = os.path.dirname(os.path.abspath(__file__))
QUESTIONS = os.path.join(HERE, "questions.csv")

CTA_EN = "Thinking about buying or selling in the Fraser Valley? Send me a message and let's review your options."
CTA_ES = "¿Estás pensando en comprar o vender en el Fraser Valley? Escríbeme y revisamos tus opciones."
ASK_EN = "Tell me in the comments 👇"
ASK_ES = "Cuéntame en los comentarios 👇"

SWIPE = [(re.compile(r"Swipe through all \d+\.?"), "Watch to the end - and save it for later."),
         (re.compile(r"Desliza para ver los \d+\.?"), "Míralo hasta el final y guárdalo para después.")]

_q = None


def questions():
    global _q
    if _q is None:
        _q = {}
        if os.path.exists(QUESTIONS):
            for r in csv.DictReader(io.open(QUESTIONS, encoding="utf-8-sig")):
                if r.get("post_id") and (r.get("question") or "").strip():
                    _q[r["post_id"].strip()] = r["question"].strip()
    return _q


def _spanish(text):
    return CTA_ES in text or "Escríbeme" in text or "#BienesRaicesBC" in text


def _ask(text, q):
    ask = ASK_ES if _spanish(text) else ASK_EN
    line = "%s\n%s" % (q, ask)
    for cta in (CTA_EN, CTA_ES):
        if cta in text:
            return text.replace(cta, line, 1)
    # no standard CTA - put the question before the signature / hashtag block
    m = re.search(r"\n\s*\n(?=(Ramon Gutierrez|#))", text)
    if m:
        return text[:m.start()] + "\n\n" + line + text[m.start():]
    return text.rstrip() + "\n\n" + line


def tune_text(text, post_id, media):
    if not text:
        return text
    if media == "reel":
        for rx, new in SWIPE:
            text = rx.sub(new, text)
    q = questions().get(post_id)
    if q and q not in text:
        text = _ask(text, q)
    return text


def tune(row):
    r = dict(row)
    media = (r.get("media") or "").strip().lower()
    for k in ("caption", "caption_fb", "caption_li"):
        if r.get(k):
            r[k] = tune_text(r[k], r.get("post_id", ""), media)
    return r


def upcoming_questions(rows, today):
    """How many future rows still have a question - the brief flags when this runs low."""
    q = questions()
    return sorted(r["post_date"] for r in rows if r["post_id"] in q and r["post_date"] >= today)
