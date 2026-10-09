# -*- coding: utf-8 -*-
"""RequestLetter_SampleNames_PublicReview 2.4 — no real company / brand names in the repository.

Every text file that git tracks (or will track: new files not ignored) is checked,
content and path, against two word lists:

  tests/data/real_name_denylist.txt   public list (widely known names)
  private/real_name_denylist.txt      the Owner's own list (git-ignored). Read when the
                                      file exists, skipped silently otherwise. Its words
                                      are never printed: a hit is shown as "word No. n of
                                      the private list".

Not checked: map data (data/worldmap_ne/), images and other binary files, the two
lists themselves. Format of the lists: see the header of the public list.
"""
from __future__ import annotations

import os
import re
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
PUBLIC_LIST = os.path.join(HERE, "data", "real_name_denylist.txt")
PRIVATE_LIST = os.path.join(REPO, "private", "real_name_denylist.txt")
SKIP_PREFIX = ("data/worldmap_ne/", "private/", "tests/data/real_name_denylist.txt")
BINARY_EXT = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".npz", ".db", ".docx", ".xlsx",
              ".pptx", ".pdf", ".zip", ".pyc")


def read_list(path):
    """-> (words, allowed phrases). Words keep their order (numbering of the private list)."""
    words, allowed = [], []
    with open(path, encoding="utf-8") as f:
        for line in f:
            t = line.strip()
            if not t or t.startswith("#"):
                continue
            (allowed if t.startswith("!") else words).append(t.lstrip("!") if t.startswith("!") else t)
    return words, allowed


def _pattern(word):
    p = re.escape(word)
    if word[0].isascii() and word[0].isalpha():
        p = r"(?<![A-Za-z])" + p
    if word[-1].isascii() and word[-1].isalpha():
        p = p + r"(?![A-Za-z])"
    return p


class Matcher:
    def __init__(self, words, allowed=()):
        self.words = list(words)
        self.allowed = [re.compile(re.escape(a), re.I) for a in allowed]
        self.rx = re.compile("|".join(f"(?P<w{i}>{_pattern(w)})" for i, w in enumerate(self.words)),
                             re.I) if self.words else None

    def find(self, text):
        """-> list of word indexes found in text."""
        if self.rx is None:
            return []
        for a in self.allowed:
            text = a.sub(" ", text)
        return [int(m.lastgroup[1:]) for m in self.rx.finditer(text)]


def tracked_text_files():
    out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                         cwd=REPO, capture_output=True, check=True).stdout.decode("utf-8")
    for rel in sorted(set(p for p in out.split("\0") if p)):
        if rel.startswith(SKIP_PREFIX) or rel.lower().endswith(BINARY_EXT):
            continue
        path = os.path.join(REPO, rel)
        if not os.path.isfile(path):
            continue          # deleted in the working tree
        with open(path, "rb") as f:
            data = f.read()
        if b"\0" in data[:8192]:
            continue
        yield rel, data.decode("utf-8", errors="replace")


def scan(matcher):
    """-> list of (file, line, word index). Line 0 = the file path itself."""
    hits = []
    for rel, text in tracked_text_files():
        hits += [(rel, 0, i) for i in matcher.find(rel)]
        if matcher.rx is None or not matcher.rx.search(text):
            continue      # allowed phrases are replaced by a space: they never create a hit
        for n, line in enumerate(text.splitlines(), 1):
            hits += [(rel, n, i) for i in matcher.find(line)]
    return hits


def _report(hits, label):
    shown = "\n".join(f"  {f}:{n}: {label(i)}" for f, n, i in hits[:40])
    more = f"\n  … and {len(hits) - 40} more" if len(hits) > 40 else ""
    return f"{len(hits)} real name(s) found (line 0 = file name):\n{shown}{more}"


def test_public_list_has_no_hits():
    words, allowed = read_list(PUBLIC_LIST)
    hits = scan(Matcher(words, allowed))
    assert not hits, _report(hits, lambda i: words[i])


def test_private_list_has_no_hits():
    if not os.path.exists(PRIVATE_LIST):
        return                                    # no private list: nothing to check
    words, allowed = read_list(PRIVATE_LIST)
    hits = scan(Matcher(words, allowed))
    # never print the private words themselves
    assert not hits, _report(hits, lambda i: f"word No. {i + 1} of the private list")


def test_private_list_is_ignored_by_git():
    r = subprocess.run(["git", "check-ignore", "-q", "private/real_name_denylist.txt"], cwd=REPO)
    assert r.returncode == 0, "/private/ must be in .gitignore"


@pytest.mark.parametrize("text", [
    "EMS_A_CN", "Foundry_A_TW", "Sensor_A_IN", "Phone16", "SP_Phone15", "Retailer_B型",
    "Retailer_A-inspired", "Coop_Seihaku", "産地の集荷団体（新潟）", "大手チェーン等",
    "欧州エントリDC(ロッテルダム)", "Zaragoza", "choreography", "font-family:-apple-system",
    "smartphone-global-2026-2029", "applesauce",
])
def test_generic_names_are_not_flagged(text):
    words, allowed = read_list(PUBLIC_LIST)
    assert Matcher(words, allowed).find(text) == []


def test_real_names_are_flagged():
    # built from the list itself, so this file holds no real name
    words, allowed = read_list(PUBLIC_LIST)
    m = Matcher(words, allowed)
    for w in words:
        for text in (w, w.lower(), w.upper(), f"SP_{w}16", f"{w}_TW", f"{w}型", f"the {w} plant"):
            assert m.find(text), text
