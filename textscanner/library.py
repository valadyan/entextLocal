from collections import Counter

from .documents import extract_words


class WordLibrary:
    def __init__(self, counts=None, learned=None):
        if not isinstance(counts, dict):
            counts = {}
        if not isinstance(learned, (list, set, tuple)):
            learned = []
        self.counts = {}
        for word, count in counts.items():
            try:
                value = max(0, int(count))
            except (TypeError, ValueError):
                value = 1
            self.counts[str(word).lower()] = value
        self.learned = {
            str(word).lower() for word in learned if str(word).lower() in self.counts
        }

    def replace_text(self, text):
        previous_learned = self.learned
        self.counts = dict(Counter(extract_words(text)))
        self.learned = previous_learned.intersection(self.counts)
        return len(self.counts)

    def merge_counts(self, counts, learned=False):
        for word, count in counts.items():
            word = str(word).strip().lower()
            if not word:
                continue
            self.counts[word] = max(self.counts.get(word, 0), count)
            if learned:
                self.learned.add(word)
            else:
                self.learned.discard(word)

    def entries(self, tab="all", query="", translations=None, sort="count", reverse=True):
        translations = translations or {}
        if tab == "learned":
            pool = ((word, self.counts[word]) for word in self.learned)
        else:
            pool = (
                (word, count) for word, count in self.counts.items()
                if word not in self.learned
            )
        query = query.strip().casefold()
        if query:
            pool = (
                (word, count) for word, count in pool
                if query in word.casefold()
                or query in translations.get(word, "").casefold()
            )
        if sort == "word":
            return sorted(pool, key=lambda item: item[0], reverse=reverse)
        if sort == "translation":
            key = lambda item: (translations.get(item[0], "").casefold(), item[0])
            return sorted(pool, key=key, reverse=reverse)
        by_word = sorted(pool, key=lambda item: item[0])
        return sorted(by_word, key=lambda item: item[1], reverse=reverse)

    def mark_learned(self, words):
        self.learned.update(word for word in words if word in self.counts)

    def mark_unlearned(self, words):
        self.learned.difference_update(words)

    def remove(self, words):
        for word in words:
            self.counts.pop(word, None)
            self.learned.discard(word)

    def clear(self):
        self.counts.clear()
        self.learned.clear()

    def tab_entries(self, tab="all", translations=None):
        return self.entries(tab, translations=translations, sort="count", reverse=True)

    def totals(self, tab="all", query="", translations=None):
        visible = self.entries(tab, query, translations)
        return {
            "visible_words": len(visible),
            "visible_occurrences": sum(count for _, count in visible),
            "total_words": len(self.counts),
            "total_occurrences": sum(self.counts.values()),
            "learned_words": len(self.learned),
        }
