"""Retrieval that corrects itself: a worked solution."""

from __future__ import annotations

import re

from mockllm import cosine_similarity, embed_text

CONVERSATIONAL = {
    "thanks",
    "thank",
    "hello",
    "hi",
    "bye",
    "goodbye",
    "ok",
    "okay",
    "great",
    "helped",
    "cheers",
    "sorry",
}

# Function words that carry no content of their own. "thank you" and "that
# helped" are conversational; the second word in each is doing nothing.
FILLER = {"you", "that", "this", "it", "was", "very", "much", "so", "really", "a"}


def retrieve(question: str, corpus: list[str], k: int = 3) -> list[dict]:
    if not corpus:
        return []

    query = embed_text(question)
    scored = [
        {"text": chunk, "score": cosine_similarity(query, embed_text(chunk)), "_at": index}
        for index, chunk in enumerate(corpus)
    ]
    # Position breaks a tie, so two runs agree.
    scored.sort(key=lambda row: (-row["score"], row["_at"]))
    return [{"text": row["text"], "score": row["score"]} for row in scored[:k]]


def grade(question: str, chunk: str, relevant: float = 0.45, ambiguous: float = 0.3) -> str:
    score = cosine_similarity(embed_text(question), embed_text(chunk))
    if score >= relevant:
        return "relevant"
    if score >= ambiguous:
        return "ambiguous"
    return "irrelevant"


def filter_results(question: str, results: list[dict]) -> dict:
    kept: list[dict] = []
    dropped = 0

    for result in results:
        verdict = grade(question, result["text"])
        if verdict == "irrelevant":
            dropped += 1
            continue
        kept.append({**result, "grade": verdict})

    return {
        "kept": kept,
        "dropped": dropped,
        # Empty results are not all_irrelevant: nothing was retrieved, which is
        # a different fact from everything retrieved being useless.
        "all_irrelevant": bool(results) and not kept,
    }


def rewrite_query(question: str, vocabulary: dict) -> str:
    rewritten = question
    for user_phrase, corpus_phrase in vocabulary.items():
        rewritten = re.sub(re.escape(user_phrase), corpus_phrase, rewritten, flags=re.IGNORECASE)
    return rewritten


def needs_retrieval(question: str) -> bool:
    words = re.findall(r"[a-z']+", question.lower())
    if not words or len(words) > 3:
        return True

    # Narrow on purpose: when unsure, retrieve. Every word has to be either
    # conversational or filler, and at least one has to actually be
    # conversational, so a short real question is never mistaken for chat.
    known = all(word in CONVERSATIONAL or word in FILLER for word in words)
    greeting = any(word in CONVERSATIONAL for word in words)
    return not (known and greeting)


def answer(question: str, corpus: list[str], vocabulary: dict, max_attempts: int = 2) -> dict:
    if not needs_retrieval(question):
        return {"status": "skipped", "chunks": [], "attempts": 0, "queries": []}

    query = question
    queries: list[str] = []

    for attempt in range(1, max_attempts + 1):
        queries.append(query)
        # Graded against the query that retrieved them, not the original
        # question. That is the point of the rewrite: it expresses the question
        # in the vocabulary the corpus uses, so grading against the original
        # would throw away exactly what the second attempt bought.
        filtered = filter_results(query, retrieve(query, corpus))

        if filtered["kept"]:
            return {
                "status": "answered",
                "chunks": filtered["kept"],
                "attempts": attempt,
                "queries": queries,
            }

        rewritten = rewrite_query(question, vocabulary)
        if rewritten == query:
            # Nothing left to try: searching the same thing again would give the
            # same nothing.
            break
        query = rewritten

    return {"status": "no_answer", "chunks": [], "attempts": len(queries), "queries": queries}
