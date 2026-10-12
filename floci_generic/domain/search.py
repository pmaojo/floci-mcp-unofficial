"""Finding an operation from what a person says: BM25 over names and first sentences, with a few boosts."""
import math
import re
from collections import Counter
from dataclasses import dataclass

from floci_generic.domain.classify import split_name

# Plain-English verbs a user writes, mapped to the verbs APIs use.
SYNONYMS = {
    "show": ["list", "describe", "get"], "see": ["list", "describe", "get"], "find": ["list", "search", "describe"],
    "which": ["list"], "all": ["list"], "read": ["get", "list", "receive"], "fetch": ["get"], "inspect": ["describe", "get"],
    "make": ["create"], "new": ["create"], "add": ["create", "put"], "remove": ["delete"], "drop": ["delete"],
    "upload": ["put"], "store": ["put", "create"], "write": ["put"], "run": ["start", "invoke", "execute"],
    "call": ["invoke"], "publish": ["publish", "send"], "send": ["send", "publish"], "tag": ["tag"],
    "bucket": ["bucket", "s3"], "queue": ["queue", "sqs"], "topic": ["topic", "sns"],
    "secret": ["secret", "secretsmanager"], "function": ["function", "lambda"], "table": ["table", "dynamodb"],
    "email": ["email", "ses"], "key": ["key", "kms"], "file": ["object"], "text": ["object"],
    "eventbridge": ["events", "rule"], "cloudwatch": ["logs"], "log": ["logs"],
}


def stem(token: str) -> str:
    """messages -> message, queues -> queue, policies -> policy. Crude on purpose."""
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def tokens(text: str) -> list[str]:
    """Lowercase, stemmed words of a text."""
    return [stem(t) for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def expand(query: str) -> list[str]:
    """The query's words plus the API verbs and service names they usually mean, without repeats."""
    out: list[str] = []
    for token in tokens(query):
        for t in [token, *(stem(x) for x in SYNONYMS.get(token, []))]:
            if t not in out:
                out.append(t)
    return out


class BM25:
    """Okapi BM25 over pre-tokenized documents."""

    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.avg = sum(len(d) for d in docs) / max(len(docs), 1)
        df: Counter = Counter()
        for doc in docs:
            df.update(set(doc))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.tf = [Counter(d) for d in docs]

    def scores(self, query: list[str]) -> list[float]:
        """One score per document."""
        out = []
        for doc, tf in zip(self.docs, self.tf):
            score = 0.0
            for term in query:
                freq = tf.get(term)
                if freq:
                    norm = freq + self.k1 * (1 - self.b + self.b * len(doc) / self.avg)
                    score += self.idf.get(term, 0.0) * freq * (self.k1 + 1) / norm
            out.append(score)
        return out


@dataclass
class Index:
    """The searchable entries of one cloud (or one service) and their BM25 index."""

    entries: list[dict]
    bm25: BM25


def aws_entry(service: str, operation: str, sentence: str) -> dict:
    """A searchable entry for one AWS operation: its name words and the opening of its documentation."""
    words = split_name(operation)
    return {"cloud": "aws", "service": service, "operation": operation, "name_tokens": [stem(t) for t in words],
            "text": f"{service} {service} " + " ".join(words * 2) + " " + sentence}


def recipe_entry(name: str, kind: str, summary: str) -> dict:
    """A searchable entry for one recipe operation."""
    words = split_name(name)
    return {"cloud": "recipes", "service": "marketplace", "operation": name, "summary": summary, "kind": kind,
            "name_tokens": [stem(t) for t in words],
            "text": f"recipe recipes marketplace docker local stack {' '.join(words)} {summary}"}


def _name_words(name: str) -> list[str]:
    words: list[str] = []
    for part in name.split("."):
        words.extend(split_name(part))
    return words


def rest_entry(cloud: str, service: str, op: dict) -> dict:
    """A searchable entry for one catalogued REST operation."""
    name = op["name"]
    words = _name_words(name)
    summary = op.get("summary", "")
    return {"cloud": cloud, "service": service, "operation": name, "summary": summary, "method": op["method"],
            "path": op["path"], "name_tokens": [stem(t) for t in words],
            "text": f"{service} {service} {' '.join(words * 2)} {summary} {op['path']}"}


def build_index(entries: list[dict]) -> Index:
    """Index entries for ranking."""
    return Index(entries, BM25([tokens(e["text"]) for e in entries]))


def _boost(entry: dict, wanted: set[str], flat: str) -> float:
    """How much to multiply an entry's score by: name coverage, and a named service."""
    words = entry["name_tokens"]
    # The whole name covered by the query: "invoke a function" means Invoke, not PutFunctionEventInvokeConfig.
    factor = 0.4 + 0.6 * (sum(w in wanted for w in words) / max(len(words), 1))
    # The person named the service ("an athena query", "step functions"): the strongest signal.
    service = entry["service"].replace("-", "")
    if service in wanted or stem(service) in wanted or (len(service) >= 6 and service in flat):
        factor *= 2.5
    return factor


def rank(index: Index, query: str, limit: int) -> list[dict]:
    """The best-matching entries, best first, without those that matched nothing."""
    expanded = expand(query)
    wanted = set(expanded)
    flat = "".join(tokens(query))
    scores = index.bm25.scores(expanded)
    scored = [(score * _boost(entry, wanted, flat), i) for i, (score, entry) in enumerate(zip(scores, index.entries))]
    scored.sort(key=lambda pair: -pair[0])
    return [index.entries[i] for score, i in scored[:limit] if score > 0]
