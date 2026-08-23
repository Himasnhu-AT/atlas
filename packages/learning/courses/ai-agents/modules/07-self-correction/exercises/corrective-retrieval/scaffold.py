"""
Retrieval that corrects itself.

Grade what came back, re-query when it does not answer the question, and decide
whether to retrieve at all. Three decisions around the pipeline you already
built, and the only self-correction in this module that can actually go and find
the missing fact.

`mockllm` gives you `embed_text` and `cosine_similarity`, the same ones the RAG
pipeline used.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

from mockllm import cosine_similarity, embed_text

# A question is conversational when it is short and carries no content word the
# corpus could answer from.
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
    """
    The plain pipeline: embed, score, take the top k.

    Args:
        question: what was asked.
        corpus: the chunks available.
        k: how many to take.

    Returns:
        The top k chunks, best first:

            [{"text": "...", "score": 0.81}]

        Similarity search always returns something. On a question the corpus does
        not cover it returns the least irrelevant chunks with no signal that this
        is what happened, which is what the grader below exists to notice.

        Ties break on the chunk's position in the corpus, so two runs agree.
        An empty corpus gives [].
    """
    raise NotImplementedError


def grade(question: str, chunk: str, relevant: float = 0.45, ambiguous: float = 0.3) -> str:
    """
    Does this chunk help answer this question?

    Per chunk, not per result set, and the judgement reads the chunk and the
    question and nothing else.

    Args:
        question: what was asked.
        chunk: one retrieved chunk.
        relevant: at or above this similarity, "relevant".
        ambiguous: at or above this and below `relevant`, "ambiguous".

    Returns:
        "relevant", "ambiguous" or "irrelevant".

        A chunk that scored well on embedding similarity and does not answer the
        question is noise, and noise in the context makes the answer worse rather
        than merely not better.
    """
    raise NotImplementedError


def filter_results(question: str, results: list[dict]) -> dict:
    """
    Keep what helps, and notice when nothing does.

    Args:
        question: what was asked.
        results: the output of retrieve.

    Returns:
        A dict shaped:

            {
                "kept": [{"text": ..., "score": ..., "grade": "relevant"}],
                "dropped": 2,
                "all_irrelevant": False,
            }

        `kept` holds the relevant and ambiguous chunks, in their original order,
        each carrying its grade. Ambiguous ones are kept and marked, exactly like
        the unsupported claims in the verification exercise.

        `all_irrelevant` is True when there were results and none survived. That
        is the pipeline discovering its corpus does not cover the question, which
        the plain version could never find out. Empty results are not
        `all_irrelevant`: nothing was retrieved, which is a different fact.
    """
    raise NotImplementedError


def rewrite_query(question: str, vocabulary: dict) -> str:
    """
    Say the question the way the documents say it.

    The commonest reason for a bad result set is that the question is not phrased
    the way the corpus is. A user asks "why did my card get declined"; the
    documentation says "error 402: payment method rejected".

    Args:
        question: the original.
        vocabulary: maps a user phrase to the corpus's phrase, for example
            {"card get declined": "error 402 payment method rejected"}.

    Returns:
        The question with every matching phrase replaced, case-insensitively.
        Unchanged when nothing matches: returning something different anyway
        would send the second attempt somewhere arbitrary.
    """
    raise NotImplementedError


def needs_retrieval(question: str) -> bool:
    """
    Does answering this need the corpus at all?

    Args:
        question: the incoming message.

    Returns:
        False when the question is conversational: three words or fewer, every
        word in CONVERSATIONAL or FILLER, and at least one in CONVERSATIONAL.
        Case and punctuation are ignored. True otherwise.

        The "at least one" clause is what stops a short real question being
        mistaken for chat.

    WHEN UNSURE, RETRIEVE. An unnecessary retrieval costs tokens. A skipped
    necessary one costs a wrong answer delivered confidently, so the test is
    deliberately narrow and only skips what is obviously not a question.
    """
    raise NotImplementedError


def answer(question: str, corpus: list[str], vocabulary: dict, max_attempts: int = 2) -> dict:
    """
    The corrective loop, end to end.

    Args:
        question: what was asked.
        corpus: the chunks available.
        vocabulary: for rewrite_query.
        max_attempts: how many times to search before giving up. Bound it: a
            loop that keeps rewriting until it finds something will eventually
            find something, and what it finds will be whatever matched the query
            it drifted into.

    Returns:
        A dict shaped:

            {
                "status": "answered" | "skipped" | "no_answer",
                "chunks": [...],
                "attempts": 1,
                "queries": ["the original", "the rewritten one"],
            }

        "skipped"    needs_retrieval said no. No attempts, no chunks.
        "answered"   something survived grading.
        "no_answer"  every attempt came back all irrelevant.

        `queries` records what was actually searched for, in order, which is the
        only way to see afterwards what the loop drifted into.

        Grade the results against the QUERY THAT RETRIEVED THEM, not the
        original question. That is the point of the rewrite: it expresses the
        question in the vocabulary the corpus uses, and grading against the
        original throws away exactly what the second attempt bought.

        Saying you do not know is the answer nobody implements and the correct
        one when the corpus lacks the fact. It is much better than answering
        anyway from whatever was in the context.
    """
    raise NotImplementedError
