import logging
import re
from dataclasses import dataclass
from difflib import get_close_matches, SequenceMatcher
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple

logger = logging.getLogger("PPOCRLabel")


@dataclass
class LexiconSuggestion:
    text: str
    score: float
    reason: str


class LexiconLanguageModel:
    """
    Lightweight lexicon + character bigram scorer.

    - Lexicon: words/phrases stored line-by-line.
    - LM: character bigram counts from confirmed sentences.
    Both files are append-only and reloaded on demand.
    """

    def __init__(
        self,
        words_path: Path,
        corpus_path: Path,
        min_word_len: int = 1,
    ):
        self.words_path = Path(words_path)
        self.corpus_path = Path(corpus_path)
        self.min_word_len = max(1, int(min_word_len))
        self.words: List[str] = []
        self.word_set: Set[str] = set()
        self.corpus_lines: Set[str] = set()
        self.unigram = {}
        self.bigram = {}
        self._load_files()

    # -------------------- public API -------------------- #
    def ingest_text(self, text: str) -> None:
        """
        Persist user-confirmed text into lexicon and LM corpus.
        """
        cleaned = self._normalize(text)
        if not cleaned:
            return

        tokens = self._split_tokens(cleaned)
        added = False
        for token in tokens:
            if len(token) < self.min_word_len:
                continue
            if token not in self.word_set:
                self.words.append(token)
                self.word_set.add(token)
                self._append_line(self.words_path, token)
                added = True

        # Always append the full sentence to the LM corpus
        if cleaned not in self.corpus_lines:
            self._append_line(self.corpus_path, cleaned)
            self.corpus_lines.add(cleaned)

        if added:
            logger.info("Lexicon updated with %d new token(s)", len(tokens))
        # rebuild LM every time to keep it in sync but keep cost low
        self._rebuild_lm()

    def suggest(
        self,
        text: str,
        base_score: float = 0.0,
        extra_candidates: Optional[Iterable[str]] = None,
    ) -> Optional[LexiconSuggestion]:
        """
        Return a better-matching lexicon phrase if available.
        """
        original = self._normalize(text)
        if not original or not self.words:
            return None

        base_score = float(base_score or 0.0)
        is_known = original in self.word_set

        pool = list(self._candidate_pool(original, extra_candidates or []))
        if not pool:
            return None

        best_text = original
        best_quality = self._quality(original, original)
        best_combined = self._combine_score(best_quality, base_score)

        for cand in pool:
            quality = self._quality(cand, original)
            combined = self._combine_score(quality, base_score)
            # Prefer lexicon words; require minimum similarity
            if quality["sim"] < 0.7:
                continue
            if is_known and cand == original:
                continue

            is_better = combined > best_combined + 0.05
            newly_known = not is_known and cand in self.word_set
            if is_better or newly_known:
                best_text = cand
                best_combined = combined
                best_quality = quality

        if best_text == original:
            return None

        reason = (
            f"lexicon '{best_text}' (sim={best_quality['sim']:.2f}, "
            f"lm={best_quality['lm']:.2f})"
        )
        suggested_score = max(base_score, min(1.0, best_combined))
        return LexiconSuggestion(best_text, suggested_score, reason)

    # -------------------- helpers -------------------- #
    def _load_files(self) -> None:
        self.words_path.parent.mkdir(parents=True, exist_ok=True)
        self.corpus_path.parent.mkdir(parents=True, exist_ok=True)
        self.words = []
        self.word_set = set()
        if self.words_path.exists():
            for line in self.words_path.read_text(encoding="utf-8").splitlines():
                token = self._normalize(line)
                if token:
                    self.words.append(token)
                    self.word_set.add(token)
        if self.corpus_path.exists():
            for line in self.corpus_path.read_text(encoding="utf-8").splitlines():
                token = self._normalize(line)
                if token:
                    self.corpus_lines.add(token)
        self._rebuild_lm()

    def _rebuild_lm(self) -> None:
        self.unigram = {}
        self.bigram = {}
        try:
            lines = self.corpus_path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return
        for line in lines:
            chars = list(self._normalize(line))
            if not chars:
                continue
            for idx, ch in enumerate(chars):
                self.unigram[ch] = self.unigram.get(ch, 0) + 1
                if idx == 0:
                    continue
                prev = chars[idx - 1]
                key = (prev, ch)
                self.bigram[key] = self.bigram.get(key, 0) + 1

    def _append_line(self, path: Path, line: str) -> None:
        try:
            with path.open("a", encoding="utf-8") as fp:
                fp.write(line + "\n")
        except OSError as exc:
            logger.warning("Failed to append to %s: %s", path, exc)

    def _split_tokens(self, text: str) -> List[str]:
        # Split by whitespace; fall back to the full string if there is no separator
        parts = [p.strip() for p in re.split(r"\\s+", text) if p.strip()]
        return parts or [text]

    def _normalize(self, text: str) -> str:
        return (text or "").strip()

    def _candidate_pool(
        self, text: str, extra_candidates: Iterable[str]
    ) -> List[str]:
        pool = []
        close = get_close_matches(text, self.words, n=8, cutoff=0.6)
        pool.extend(close)
        for cand in extra_candidates:
            norm = self._normalize(cand)
            if norm:
                pool.append(norm)
        # Deduplicate while keeping order
        deduped = []
        seen = set()
        for item in pool:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        return deduped

    def _lm_score(self, text: str) -> float:
        # Simple add-one smoothed bigram log probability
        chars = list(text)
        if not chars:
            return 0.0
        vocab = max(len(self.unigram), 1)
        score = 0.0
        for idx, ch in enumerate(chars):
            if idx == 0:
                count = self.unigram.get(ch, 0)
                total = sum(self.unigram.values()) or vocab
                prob = (count + 1) / (total + vocab)
            else:
                prev = chars[idx - 1]
                count = self.bigram.get((prev, ch), 0)
                prev_total = self.unigram.get(prev, 0)
                prob = (count + 1) / (prev_total + vocab)
            score += float(prob)
        return score / len(chars)

    def _quality(self, candidate: str, reference: Optional[str] = None) -> dict:
        sim = SequenceMatcher(None, reference or candidate, candidate).ratio()
        return {"sim": sim, "lm": self._lm_score(candidate)}

    def _combine_score(self, quality: dict, base_score: float) -> float:
        # Weighted mix: similarity term dominates, LM adds a gentle bias
        return 0.7 * quality["sim"] + 0.3 * min(1.0, quality["lm"]) + 0.25 * base_score
