from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import yaml
from rapidfuzz import fuzz, process

from app.models import Rule, TransactionIn, TransactionOut
from app.normalization.cleaner import normalize_description
from app.rules.schema import RulesConfig


class RuleEngine:
    def __init__(self, rules: list[Rule], merchant_memory: Optional[dict[str, str]] = None):
        self.rules = rules
        self._merchant_memory = merchant_memory or {}
        self._fuzzy_threshold = 88.0
        self._contains_pattern_rules: dict[str, list[Rule]] = {}
        self._contains_goto: list[dict[str, int]] = [{}]
        self._contains_fail: list[int] = [0]
        self._contains_out: list[list[str]] = [[]]
        self._fuzzy_category_by_term: dict[str, str] = {}
        self._fuzzy_terms: list[str] = []
        self._build_contains_automaton()
        self._build_fuzzy_dictionary()

    @classmethod
    def from_yaml(
        cls,
        path: Path,
        merchant_memory_path: Optional[Path] = None,
    ) -> "RuleEngine":
        payload = yaml.safe_load(path.read_text()) or {}
        config = RulesConfig.model_validate(payload)
        memory_path = merchant_memory_path or (path.parent / "merchant_memory.yaml")
        memory_payload = {}
        if memory_path.exists():
            memory_payload = yaml.safe_load(memory_path.read_text()) or {}
        merchant_memory = memory_payload.get("merchant_memory", {})
        normalized_memory = {normalize_description(k): v for k, v in merchant_memory.items() if k and v}
        return cls(config.rules, normalized_memory)

    def categorize(self, tx: TransactionIn) -> TransactionOut:
        normalized = normalize_description(tx.description)
        candidates: list[Rule] = []

        for rule in self._matched_contains_rules(normalized):
            if self._is_rule_applicable(rule, tx.amount):
                candidates.append(rule)

        for rule in self.rules:
            if rule.match_type == "contains":
                continue
            if not self._is_rule_applicable(rule, tx.amount):
                continue

            if self._matches(rule, normalized):
                candidates.append(rule)

        chosen = self._choose_best(candidates)
        if chosen is None:
            memory_category = self._merchant_memory.get(normalized)
            if memory_category:
                return TransactionOut(
                    date=tx.date,
                    raw_description=tx.description,
                    normalized_description=normalized,
                    amount=tx.amount,
                    currency=tx.currency,
                    predicted_category=memory_category,
                    matched_rule_id="merchant_memory_exact",
                    status="categorized",
                )

            fuzzy_category, fuzzy_id = self._fuzzy_category(normalized)
            if fuzzy_category:
                return TransactionOut(
                    date=tx.date,
                    raw_description=tx.description,
                    normalized_description=normalized,
                    amount=tx.amount,
                    currency=tx.currency,
                    predicted_category=fuzzy_category,
                    matched_rule_id=fuzzy_id,
                    status="categorized",
                )

            return TransactionOut(
                date=tx.date,
                raw_description=tx.description,
                normalized_description=normalized,
                amount=tx.amount,
                currency=tx.currency,
                predicted_category="Uncategorized",
                matched_rule_id=None,
                status="uncategorized",
            )

        return TransactionOut(
            date=tx.date,
            raw_description=tx.description,
            normalized_description=normalized,
            amount=tx.amount,
            currency=tx.currency,
            predicted_category=chosen.category,
            matched_rule_id=chosen.rule_id,
            status="categorized",
        )

    def _matches(self, rule: Rule, normalized_description: str) -> bool:
        pattern = rule.pattern.lower()
        if rule.match_type == "exact":
            return normalized_description == pattern
        if rule.match_type == "regex":
            return re.search(pattern, normalized_description) is not None
        return False

    def _is_rule_applicable(self, rule: Rule, amount: float) -> bool:
        if not rule.active:
            return False
        if rule.amount_min is not None and amount < rule.amount_min:
            return False
        if rule.amount_max is not None and amount > rule.amount_max:
            return False
        return True

    def _build_contains_automaton(self) -> None:
        for rule in self.rules:
            if rule.match_type != "contains":
                continue
            pattern = rule.pattern.lower()
            if not pattern:
                continue
            self._contains_pattern_rules.setdefault(pattern, []).append(rule)

        for pattern in self._contains_pattern_rules:
            state = 0
            for ch in pattern:
                nxt = self._contains_goto[state].get(ch)
                if nxt is None:
                    self._contains_goto.append({})
                    self._contains_fail.append(0)
                    self._contains_out.append([])
                    nxt = len(self._contains_goto) - 1
                    self._contains_goto[state][ch] = nxt
                state = nxt
            self._contains_out[state].append(pattern)

        queue: list[int] = []
        for _, state in self._contains_goto[0].items():
            queue.append(state)
            self._contains_fail[state] = 0

        while queue:
            state = queue.pop(0)
            for ch, nxt in self._contains_goto[state].items():
                queue.append(nxt)
                fail_state = self._contains_fail[state]
                while fail_state and ch not in self._contains_goto[fail_state]:
                    fail_state = self._contains_fail[fail_state]
                self._contains_fail[nxt] = self._contains_goto[fail_state].get(ch, 0)
                self._contains_out[nxt].extend(self._contains_out[self._contains_fail[nxt]])

    def _matched_contains_rules(self, text: str) -> list[Rule]:
        if not self._contains_pattern_rules:
            return []

        matched_patterns: set[str] = set()
        state = 0
        for ch in text:
            while state and ch not in self._contains_goto[state]:
                state = self._contains_fail[state]
            state = self._contains_goto[state].get(ch, 0)
            for pattern in self._contains_out[state]:
                matched_patterns.add(pattern)

        matched_rules: list[Rule] = []
        for pattern in matched_patterns:
            matched_rules.extend(self._contains_pattern_rules.get(pattern, []))
        return matched_rules

    def _build_fuzzy_dictionary(self) -> None:
        fuzzy_category_by_term: dict[str, str] = {}
        for merchant_term, category in self._merchant_memory.items():
            fuzzy_category_by_term[merchant_term] = category

        for rule in self.rules:
            if rule.match_type != "contains" or not rule.active:
                continue
            term = normalize_description(rule.pattern)
            if not term:
                continue
            # Keep the first category assignment for stability unless explicit memory overrides it.
            fuzzy_category_by_term.setdefault(term, rule.category)

        self._fuzzy_category_by_term = fuzzy_category_by_term
        self._fuzzy_terms = list(fuzzy_category_by_term.keys())

    def _fuzzy_category(self, normalized_description: str) -> tuple[Optional[str], Optional[str]]:
        if not self._fuzzy_terms:
            return None, None

        match = process.extractOne(
            normalized_description,
            self._fuzzy_terms,
            scorer=fuzz.token_set_ratio,
        )
        if not match:
            return None, None

        matched_term, score, _ = match
        if score < self._fuzzy_threshold:
            return None, None

        category = self._fuzzy_category_by_term.get(matched_term)
        if not category:
            return None, None
        return category, f"fuzzy:{matched_term}:{score:.1f}"

    def _match_rank(self, rule: Rule) -> int:
        if rule.match_type == "exact":
            return 3
        if rule.match_type == "contains":
            return 2
        return 1

    def _choose_best(self, candidates: list[Rule]) -> Optional[Rule]:
        if not candidates:
            return None
        ordered = sorted(
            candidates,
            key=lambda r: (self._match_rank(r), r.priority, len(r.pattern)),
            reverse=True,
        )
        return ordered[0]
