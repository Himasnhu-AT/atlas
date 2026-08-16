"""
Tests for: structured output.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import MockClient, text, truncated

from solution import (
    ExtractionError,
    ValidationError,
    extract_json,
    extract_with_retry,
    find_json_object,
    validate,
)

ORDER_SCHEMA = {
    "customer_name": {"type": "string"},
    "order_id": {"type": "string", "nullable": True},
    "quantity": {"type": "integer"},
    "urgent": {"type": "boolean", "required": False},
    "status": {"type": "string", "enum": ["open", "shipped", "closed"], "required": False},
}

VALID = '{"customer_name": "Ana", "order_id": "A-1", "quantity": 2}'

WRONG_TYPE = '{"customer_name": "Ana", "order_id": "A-1", "quantity": "two"}'


class TestExtraction(unittest.TestCase):
    def test_finds_a_bare_object(self):
        self.assertEqual(find_json_object('{"a": 1}'), '{"a": 1}')

    def test_ignores_surrounding_prose(self):
        self.assertEqual(find_json_object('Sure! {"a": 1} hope that helps'), '{"a": 1}')

    def test_handles_nested_objects(self):
        source = '{"a": {"b": {"c": 1}}}'
        self.assertEqual(
            find_json_object(f"prefix {source} suffix"),
            source,
            "stop at the brace that closes the OUTER object, not the first one you see",
        )

    def test_ignores_braces_inside_strings(self):
        source = '{"note": "a } inside a string", "b": 2}'
        self.assertEqual(
            find_json_object(source),
            source,
            "a brace inside a string literal is text, not structure",
        )

    def test_ignores_escaped_quotes(self):
        source = '{"note": "he said \\"} \\" loudly", "b": 2}'
        self.assertEqual(find_json_object(source), source)

    def test_raises_when_there_is_no_brace(self):
        with self.assertRaises(ExtractionError):
            find_json_object("there is no json here")

    def test_raises_when_the_object_never_closes(self):
        with self.assertRaises(ExtractionError):
            find_json_object('{"a": 1')

    def test_plain_json(self):
        self.assertEqual(extract_json(VALID)["customer_name"], "Ana")

    def test_surrounding_whitespace(self):
        self.assertEqual(extract_json(f"\n\n  {VALID}  \n")["quantity"], 2)

    def test_fenced_with_a_language_tag(self):
        self.assertEqual(extract_json(f"```json\n{VALID}\n```")["order_id"], "A-1")

    def test_fenced_without_a_language_tag(self):
        self.assertEqual(extract_json(f"```\n{VALID}\n```")["order_id"], "A-1")

    def test_wrapped_in_prose(self):
        wrapped = f"Here is the data you asked for:\n\n{VALID}\n\nLet me know!"
        self.assertEqual(extract_json(wrapped)["customer_name"], "Ana")

    def test_rejects_a_json_array(self):
        with self.assertRaises(ExtractionError):
            extract_json("[1, 2, 3]")

    def test_rejects_text_with_no_json_in_it(self):
        with self.assertRaises(ExtractionError):
            extract_json("I could not complete that request.")


class TestValidate(unittest.TestCase):
    def test_accepts_a_valid_object(self):
        validate({"customer_name": "Ana", "order_id": "A-1", "quantity": 2}, ORDER_SCHEMA)

    def test_missing_required_field(self):
        with self.assertRaises(ValidationError) as caught:
            validate({"order_id": "A-1", "quantity": 2}, ORDER_SCHEMA)
        self.assertIn(
            "customer_name",
            str(caught.exception),
            "the message is fed back to the model, so it has to name the field",
        )

    def test_absent_optional_field_is_fine(self):
        validate({"customer_name": "Ana", "order_id": "A-1", "quantity": 1}, ORDER_SCHEMA)

    def test_null_allowed_when_nullable(self):
        validate({"customer_name": "Ana", "order_id": None, "quantity": 1}, ORDER_SCHEMA)

    def test_null_rejected_when_not_nullable(self):
        with self.assertRaises(ValidationError):
            validate({"customer_name": None, "order_id": "A-1", "quantity": 1}, ORDER_SCHEMA)

    def test_wrong_type(self):
        with self.assertRaises(ValidationError) as caught:
            validate({"customer_name": "Ana", "order_id": "A-1", "quantity": "two"}, ORDER_SCHEMA)
        self.assertIn("quantity", str(caught.exception))

    def test_bool_is_not_an_integer(self):
        with self.assertRaises(ValidationError):
            validate(
                {"customer_name": "Ana", "order_id": "A-1", "quantity": True},
                ORDER_SCHEMA,
            )

    def test_bool_still_satisfies_boolean(self):
        validate(
            {"customer_name": "Ana", "order_id": "A-1", "quantity": 1, "urgent": True},
            ORDER_SCHEMA,
        )

    def test_an_integer_satisfies_number(self):
        validate({"score": 3}, {"score": {"type": "number"}})

    def test_a_float_does_not_satisfy_integer(self):
        with self.assertRaises(ValidationError):
            validate({"quantity": 1.5}, {"quantity": {"type": "integer"}})

    def test_enum_accepts_an_allowed_value(self):
        validate(
            {"customer_name": "A", "order_id": None, "quantity": 1, "status": "shipped"},
            ORDER_SCHEMA,
        )

    def test_enum_rejects_anything_else(self):
        with self.assertRaises(ValidationError) as caught:
            validate(
                {"customer_name": "A", "order_id": None, "quantity": 1, "status": "pending"},
                ORDER_SCHEMA,
            )
        self.assertIn("status", str(caught.exception))

    def test_fields_outside_the_schema_are_ignored(self):
        validate(
            {"customer_name": "A", "order_id": None, "quantity": 1, "extra": "whatever"},
            ORDER_SCHEMA,
        )


class TestRetryLoop(unittest.TestCase):
    def test_succeeds_on_the_first_try(self):
        client = MockClient([text(VALID)])
        result = extract_with_retry(client, "extract it", ORDER_SCHEMA)
        self.assertEqual(result["customer_name"], "Ana")
        self.assertEqual(client.call_count, 1, "a usable reply costs exactly one call")

    def test_recovers_from_an_unparseable_reply(self):
        client = MockClient([text("I cannot do that."), text(VALID)])
        self.assertEqual(extract_with_retry(client, "extract it", ORDER_SCHEMA)["quantity"], 2)
        self.assertEqual(client.call_count, 2)

    def test_recovers_from_a_validation_failure(self):
        client = MockClient([text(WRONG_TYPE), text(VALID)])
        self.assertEqual(extract_with_retry(client, "extract it", ORDER_SCHEMA)["quantity"], 2)

    def test_feeds_the_reply_and_the_error_back(self):
        client = MockClient([text("nope"), text(VALID)])
        extract_with_retry(client, "extract it", ORDER_SCHEMA)

        second = client.requests[1]["messages"]
        self.assertEqual(len(second), 3, "prompt, the bad reply, then the correction")
        self.assertEqual(second[1]["role"], "assistant")
        self.assertEqual(second[1]["content"], "nope", "the model needs its own reply back")
        self.assertEqual(second[2]["role"], "user")
        self.assertIn("not usable", second[2]["content"])

    def test_a_truncated_reply_is_rejected_even_when_it_parses(self):
        # The content here is complete, valid JSON. Only finish_reason says it
        # was cut off, and that is the signal that has to be checked.
        client = MockClient([truncated(VALID)])
        with self.assertRaises(
            ExtractionError,
            msg="check finish_reason before parsing: a cut off document that happens "
            "to close its braces parses into an object missing fields",
        ):
            extract_with_retry(client, "extract it", ORDER_SCHEMA, max_attempts=1)

    def test_retries_after_a_truncated_reply(self):
        client = MockClient([truncated('{"customer_name": "Ana", "quan'), text(VALID)])
        self.assertEqual(extract_with_retry(client, "extract it", ORDER_SCHEMA)["quantity"], 2)
        self.assertEqual(client.call_count, 2)

    def test_respects_the_attempt_budget(self):
        client = MockClient([text("nope"), text("still nope"), text("nope again")])
        with self.assertRaises((ExtractionError, ValidationError)):
            extract_with_retry(client, "extract it", ORDER_SCHEMA, max_attempts=3)
        self.assertEqual(
            client.call_count,
            3,
            "max_attempts is the total number of calls, not retries after the first",
        )

    def test_one_attempt_makes_one_call(self):
        client = MockClient([text("nope")])
        with self.assertRaises((ExtractionError, ValidationError)):
            extract_with_retry(client, "extract it", ORDER_SCHEMA, max_attempts=1)
        self.assertEqual(client.call_count, 1)

    def test_rejects_a_nonsense_budget(self):
        with self.assertRaises(ValueError):
            extract_with_retry(MockClient([text(VALID)]), "p", ORDER_SCHEMA, max_attempts=0)

    def test_raises_the_error_from_the_final_attempt(self):
        client = MockClient([text("not json at all"), text(WRONG_TYPE)])
        with self.assertRaises(ValidationError):
            extract_with_retry(client, "extract it", ORDER_SCHEMA, max_attempts=2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
