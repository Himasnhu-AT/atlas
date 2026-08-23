"""
Tests for: the verification pass.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import MockClient, text, tool_call

from solution import (
    VERDICTS,
    Budget,
    Claim,
    Doc,
    Note,
    Report,
    Research,
    Verification,
    locate,
    normalise,
    number_notes,
    redact_unverified,
    verify_brief,
    verify_claim,
    write_brief,
)

# The line breaks in these documents are deliberate. A quote taken from a
# wrapped paragraph carries different whitespace from the source, and a matcher
# that cannot see past that fails every honest citation.
CORPUS = [
    Doc(
        "d-solar",
        "Solar module prices",
        "Solar module prices fell 41 percent last year, as polysilicon supply\n"
        "expanded. Installers passed roughly half of that decline on to customers.",
    ),
    Doc(
        "d-storage",
        "Grid battery storage",
        "Grid battery storage additions doubled, and four hour lithium systems now\n"
        "clear the capacity auctions in three markets.",
    ),
    Doc(
        "d-queue",
        "Interconnection queue",
        "The interconnection queue holds 2.6 terawatts of projects. The median wait\n"
        "from application to agreement is now five years.",
    ),
    # Ordinary prose, with punctuation inside words rather than between them.
    # normalise() drops an apostrophe and a hyphen without leaving a gap, so
    # locate() has to drop them the same way or it will fail to find quotes
    # normalise() says are present.
    Doc(
        "d-policy",
        "Grid connection policy",
        "The operator's co-operation agreement runs to 2031, and state-level\n"
        "rules were re-issued in March.",
    ),
]

# S1 is the queue note and its quote is invented. S2 and S3 are real, and both
# differ from the source by punctuation or a line break.
NOTES = [
    Note("solar prices", "d-solar", "Solar module prices fell 41 percent last year", "w1"),
    Note(
        "storage",
        "d-storage",
        "storage additions doubled and four hour lithium systems now clear the "
        "capacity auctions",
        "w2",
    ),
    Note("queue", "d-queue", "the median wait is eighteen months", "w3"),
]

QUESTION = "What happened to renewable project economics last year?"

PROSE = (
    "Module prices fell 41 percent last year [S2]. "
    "Storage additions doubled and now clear the capacity auctions [S3]. "
    "The median wait is eighteen months [S1]. "
    "Policy changes are not covered by the notes."
)

CLEAN_PROSE = (
    "Module prices fell 41 percent last year [S2]. "
    "Storage additions doubled and now clear the capacity auctions [S3]. "
    "Policy changes are not covered by the notes."
)

TAGGED = number_notes(NOTES)


def judge(verdict, reason="because the passage says so"):
    return tool_call("judge", {"verdict": verdict, "reason": reason})


def build_brief(prose):
    research = Research(
        question=QUESTION,
        sub_queries=["solar prices", "storage", "queue"],
        notes=NOTES,
        budget=Budget(limit=100_000),
        corpus=CORPUS,
    )
    return write_brief(MockClient([text(prose)]), research)


def doc(doc_id):
    return next(document for document in CORPUS if document.id == doc_id)


def note_for(tag):
    return dict(TAGGED)[tag]


class TestNormalise(unittest.TestCase):
    def test_lowercases_and_drops_punctuation(self):
        self.assertEqual(normalise("Prices Fell, sharply!"), "prices fell sharply")

    def test_collapses_whitespace_including_newlines(self):
        self.assertEqual(normalise("  four hour\n lithium  systems "), "four hour lithium systems")

    def test_two_spellings_of_the_same_words_normalise_alike(self):
        self.assertEqual(
            normalise("systems now clear\nthe capacity auctions,"),
            normalise("systems now clear the capacity auctions"),
        )


class TestLocate(unittest.TestCase):
    def test_finds_a_quote_that_differs_by_punctuation_and_wrapping(self):
        span = locate(note_for("S3").quote, doc("d-storage"))
        self.assertIsNotNone(
            span,
            "the quote is in the document. Only a comma and a line break differ, and "
            "a matcher that gives up on those rejects honest citations",
        )

    def test_the_span_indexes_back_into_the_original_text(self):
        source = doc("d-storage")
        start, end = locate(note_for("S3").quote, source)
        self.assertEqual(
            normalise(source.text[start:end]),
            normalise(note_for("S3").quote),
            "the span must cut the quote out of the ORIGINAL text, not the normalised one",
        )

    def test_returns_none_for_a_fabricated_quote(self):
        self.assertIsNone(locate(note_for("S1").quote, doc("d-queue")))

    def test_returns_none_for_an_empty_quote(self):
        self.assertIsNone(locate("   ", doc("d-solar")))

    def test_a_quote_at_the_very_start_locates_at_zero(self):
        start, _ = locate("Solar module prices", doc("d-solar"))
        self.assertEqual(start, 0)

    def test_punctuation_inside_a_word_locates_the_same_way_normalise_reads_it(self):
        source = doc("d-policy")
        quote = "the operator's co-operation agreement"

        self.assertIn(
            normalise(quote),
            normalise(source.text),
            "fixture check: normalise says this quote is in this document",
        )

        span = locate(quote, source)
        self.assertIsNotNone(
            span,
            "normalise() and locate() have to agree on the same normalised form. "
            "Rebuilding the rule inside locate() and treating dropped punctuation as "
            "a separator makes \"co-operation\" two words there and one word in "
            "normalise(), and then an honest citation is reported NOT_IN_SOURCE and "
            "redacted out of the brief as though it were a fabrication",
        )

        start, end = span
        self.assertEqual(
            normalise(source.text[start:end]),
            normalise(quote),
            "the span must still cut the original text, apostrophes and hyphens and all",
        )


class TestVerifyClaim(unittest.TestCase):
    def test_the_verdict_list_is_the_agreed_one(self):
        self.assertEqual(tuple(VERDICTS), ("SUPPORTED", "UNSUPPORTED", "NOT_IN_SOURCE"))

    def test_a_missing_quote_never_reaches_the_model(self):
        client = MockClient([judge("SUPPORTED")])
        claim = Claim("The median wait is eighteen months [S1].", ["S1"], [])
        result = verify_claim(client, claim, "S1", note_for("S1"), doc("d-queue"), Budget(limit=100_000))

        self.assertEqual(result.verdict, "NOT_IN_SOURCE")
        self.assertIsNone(result.span)
        self.assertEqual(
            client.call_count,
            0,
            "the free check has to run before the paid one. There is nothing to judge "
            "when the quote is not in the document",
        )

    def test_the_located_passage_is_what_the_model_judges(self):
        client = MockClient([judge("SUPPORTED")])
        claim = Claim("Storage additions doubled [S3].", ["S3"], [])
        result = verify_claim(client, claim, "S3", note_for("S3"), doc("d-storage"), Budget(limit=100_000))

        start, end = result.span
        passage = doc("d-storage").text[start:end]
        sent = "\n".join(
            str(message.get("content") or "") for message in client.requests[0]["messages"]
        )
        self.assertIn(passage, sent, "the model must be shown the passage that was located")
        self.assertIn(claim.sentence, sent)

    def test_a_supported_verdict_comes_back_whole(self):
        client = MockClient([judge("SUPPORTED", "the passage states it")])
        claim = Claim("Module prices fell 41 percent last year [S2].", ["S2"], [])
        result = verify_claim(client, claim, "S2", note_for("S2"), doc("d-solar"), Budget(limit=100_000))

        self.assertIsInstance(result, Verification)
        self.assertEqual(result.verdict, "SUPPORTED")
        self.assertEqual(result.reason, "the passage states it")
        self.assertEqual(result.doc_id, "d-solar")
        self.assertEqual(result.tag, "S2")

    def test_an_unknown_verdict_becomes_unsupported(self):
        client = MockClient([judge("MAYBE", "it is sort of implied")])
        claim = Claim("Module prices fell 41 percent last year [S2].", ["S2"], [])
        result = verify_claim(client, claim, "S2", note_for("S2"), doc("d-solar"), Budget(limit=100_000))

        self.assertEqual(
            result.verdict,
            "UNSUPPORTED",
            "a verdict off the list is a failed judgement, not a pass",
        )
        self.assertEqual(
            result.reason,
            "it is sort of implied",
            "keep the model's reason. It is the only record of what it actually said",
        )


class TestVerifyBrief(unittest.TestCase):
    def test_counts_sum_to_the_number_of_markers(self):
        brief = build_brief(PROSE)
        client = MockClient([judge("SUPPORTED"), judge("SUPPORTED")])
        report = verify_brief(client, brief, TAGGED, CORPUS, Budget(limit=100_000))

        markers = sum(len(claim.tags) + len(claim.unknown_tags) for claim in brief.claims)
        self.assertIsInstance(report, Report)
        self.assertEqual(len(report.verifications), markers)
        self.assertEqual(
            report.supported + report.unsupported + report.not_in_source,
            markers,
            "every marker gets exactly one verdict, and the counts have to add up",
        )

    def test_a_fabricated_quote_fails_the_brief(self):
        brief = build_brief(PROSE)
        client = MockClient([judge("SUPPORTED"), judge("SUPPORTED")])
        report = verify_brief(client, brief, TAGGED, CORPUS, Budget(limit=100_000))

        self.assertEqual(report.not_in_source, 1)
        self.assertEqual(report.supported, 2)
        self.assertFalse(report.ok)
        self.assertEqual(
            client.call_count, 2, "only the two locatable quotes should cost a model call"
        )

    def test_an_unsupported_verdict_fails_the_brief(self):
        brief = build_brief(CLEAN_PROSE)
        client = MockClient([judge("UNSUPPORTED", "the passage says nothing of the kind"), judge("SUPPORTED")])
        report = verify_brief(client, brief, TAGGED, CORPUS, Budget(limit=100_000), require_all_cited=False)

        self.assertEqual(report.unsupported, 1)
        self.assertFalse(report.ok)

    def test_an_uncited_sentence_fails_the_brief_when_required(self):
        brief = build_brief(CLEAN_PROSE)
        client = MockClient([judge("SUPPORTED"), judge("SUPPORTED")])
        report = verify_brief(client, brief, TAGGED, CORPUS, Budget(limit=100_000), require_all_cited=True)

        self.assertEqual(report.uncited, ["Policy changes are not covered by the notes."])
        self.assertFalse(report.ok, "require_all_cited means an untagged sentence is a failure")

    def test_an_uncited_sentence_is_allowed_when_not_required(self):
        brief = build_brief(CLEAN_PROSE)
        client = MockClient([judge("SUPPORTED"), judge("SUPPORTED")])
        report = verify_brief(client, brief, TAGGED, CORPUS, Budget(limit=100_000), require_all_cited=False)

        self.assertTrue(
            report.ok,
            "every citation checks out and the only untagged sentence was allowed, so "
            "this brief passes",
        )
        self.assertTrue(report.uncited, "it is still reported, just not fatal")

    def test_the_judged_calls_go_on_the_meter(self):
        brief = build_brief(PROSE)
        client = MockClient([judge("SUPPORTED"), judge("SUPPORTED")])
        budget = Budget(limit=100_000)
        verify_brief(client, brief, TAGGED, CORPUS, budget)

        self.assertIn(
            "verify",
            budget.by_stage,
            "verification is a model call per judged claim, and it is the stage that "
            "grows with the size of the brief. A run that does not meter it reports a "
            "total smaller than the invoice",
        )
        self.assertGreater(budget.by_stage["verify"], 0)
        self.assertEqual(
            budget.spent,
            sum(budget.by_stage.values()),
            "the total and the per stage figures must describe the same run",
        )

    def test_the_free_check_charges_nothing(self):
        brief = build_brief("The median wait is eighteen months [S1].")
        budget = Budget(limit=100_000)
        verify_brief(MockClient([]), brief, TAGGED, CORPUS, budget, require_all_cited=False)

        self.assertEqual(
            budget.by_stage.get("verify", 0),
            0,
            "the quote was not in the document, so no call was made and nothing is "
            "owed. by_stage is only worth reading if it counts calls rather than claims",
        )

    def test_an_unknown_tag_is_not_in_source_and_costs_nothing(self):
        brief = build_brief("Wind costs rose sharply [S9].")
        client = MockClient([])
        report = verify_brief(client, brief, TAGGED, CORPUS, Budget(limit=100_000), require_all_cited=False)

        self.assertEqual(report.not_in_source, 1)
        self.assertEqual(client.call_count, 0)
        self.assertFalse(report.ok)


class TestRedact(unittest.TestCase):
    def setUp(self):
        self.brief = build_brief(PROSE)
        client = MockClient([judge("SUPPORTED"), judge("SUPPORTED")])
        self.report = verify_brief(client, self.brief, TAGGED, CORPUS, Budget(limit=100_000))
        self.redacted = redact_unverified(self.brief, self.report)

    def test_the_failed_sentence_is_replaced(self):
        self.assertNotIn("The median wait is eighteen months [S1].", self.redacted)
        self.assertIn("[removed: NOT_IN_SOURCE]", self.redacted)

    def test_supported_sentences_are_byte_identical(self):
        self.assertIn("Module prices fell 41 percent last year [S2].", self.redacted)
        self.assertIn(
            "Storage additions doubled and now clear the capacity auctions [S3].",
            self.redacted,
        )

    def test_the_rest_of_the_document_is_untouched(self):
        self.assertIn(f"Research brief: {QUESTION}", self.redacted)
        self.assertIn("Sources", self.redacted)
        self.assertEqual(
            len(self.redacted.splitlines()),
            len(self.brief.text.splitlines()),
            "redaction replaces sentences in place. It does not reflow the document",
        )

    def test_a_clean_brief_is_returned_unchanged(self):
        brief = build_brief(CLEAN_PROSE)
        client = MockClient([judge("SUPPORTED"), judge("SUPPORTED")])
        report = verify_brief(client, brief, TAGGED, CORPUS, Budget(limit=100_000), require_all_cited=False)
        self.assertEqual(redact_unverified(brief, report), brief.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
