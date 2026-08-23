"""
Tests for: tool schemas.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from solution import (
    Tool,
    ToolError,
    build_registry,
    build_schema,
    dispatch,
    split_docstring,
    validate_arguments,
)


def get_weather(city: str, unit: str = "celsius") -> str:
    """Look up the current weather for a city.

    Args:
        city: City name on its own, in English. For example "Paris", not
            "Paris, France".
        unit: Temperature unit to report in.

    Returns:
        A one line summary. Should not appear in any description.
    """
    return f"18 degrees {unit} in {city}"


def search_orders(customer_id: str, limit: int = 10, refunded_only: bool = False) -> str:
    """Search a customer's orders, newest first.

    Args:
        customer_id: The account id, not the email address.
        limit: How many orders to return.
        refunded_only: Return only orders that were refunded.
    """
    return f"{limit} orders for {customer_id} (refunded_only={refunded_only})"


def set_thermostat(ratio: float) -> str:
    """Set the thermostat.

    Args:
        ratio: Fraction of maximum output, from 0 to 1.
    """
    return f"set to {ratio}"


def ping() -> str:
    """Check that the service is reachable."""
    return "pong"


def undocumented(x):
    return x


def always_fails() -> str:
    """Raise, to prove dispatch does not swallow the tool's own errors."""
    raise RuntimeError("the orders database is on fire")


WEATHER_ENUMS = {"get_weather": {"unit": ["celsius", "fahrenheit"]}}


class TestSplitDocstring(unittest.TestCase):
    def test_summary_is_everything_before_args(self):
        summary, _ = split_docstring(get_weather.__doc__)
        self.assertEqual(summary, "Look up the current weather for a city.")

    def test_descriptions_are_keyed_by_parameter(self):
        _, descriptions = split_docstring(search_orders.__doc__)
        self.assertEqual(
            sorted(descriptions), ["customer_id", "limit", "refunded_only"]
        )

    def test_a_wrapped_description_stays_one_string(self):
        _, descriptions = split_docstring(get_weather.__doc__)
        self.assertEqual(
            descriptions["city"],
            'City name on its own, in English. For example "Paris", not "Paris, France".',
            "a continuation line belongs to the parameter above it",
        )

    def test_a_later_section_is_not_a_parameter(self):
        _, descriptions = split_docstring(get_weather.__doc__)
        self.assertNotIn(
            "Returns",
            descriptions,
            "stop at the next section heading or Returns: becomes a parameter",
        )

    def test_no_args_section(self):
        summary, descriptions = split_docstring(ping.__doc__)
        self.assertEqual(summary, "Check that the service is reachable.")
        self.assertEqual(descriptions, {})

    def test_no_docstring(self):
        self.assertEqual(split_docstring(None), ("", {}))


class TestBuildSchema(unittest.TestCase):
    def test_top_level_shape(self):
        schema = build_schema(get_weather)
        self.assertEqual(schema["type"], "function")
        self.assertEqual(schema["function"]["name"], "get_weather")
        self.assertEqual(schema["function"]["parameters"]["type"], "object")

    def test_the_description_comes_from_the_docstring(self):
        schema = build_schema(get_weather)
        self.assertEqual(
            schema["function"]["description"], "Look up the current weather for a city."
        )

    def test_parameter_descriptions_reach_the_schema(self):
        properties = build_schema(search_orders)["function"]["parameters"]["properties"]
        self.assertEqual(
            properties["customer_id"]["description"],
            "The account id, not the email address.",
            "the parameter description is the prompt: it has to survive into the schema",
        )

    def test_annotations_become_json_types(self):
        properties = build_schema(search_orders)["function"]["parameters"]["properties"]
        self.assertEqual(properties["customer_id"]["type"], "string")
        self.assertEqual(properties["limit"]["type"], "integer")
        self.assertEqual(
            properties["refunded_only"]["type"],
            "boolean",
            "PEP 563 stores annotations as strings; resolve them before the lookup",
        )

    def test_required_excludes_anything_with_a_default(self):
        parameters = build_schema(search_orders)["function"]["parameters"]
        self.assertEqual(parameters["required"], ["customer_id"])
        self.assertIn("limit", parameters["properties"], "optional is not absent")

    def test_enums_are_merged_in(self):
        properties = build_schema(get_weather, {"unit": ["celsius", "fahrenheit"]})[
            "function"
        ]["parameters"]["properties"]
        self.assertEqual(properties["unit"]["enum"], ["celsius", "fahrenheit"])
        self.assertNotIn("enum", properties["city"])

    def test_an_enum_for_a_parameter_that_does_not_exist_raises(self):
        with self.assertRaises(ValueError):
            build_schema(get_weather, {"units": ["celsius"]})

    def test_additional_properties_is_false(self):
        parameters = build_schema(ping)["function"]["parameters"]
        self.assertIs(parameters["additionalProperties"], False)

    def test_a_function_with_no_parameters(self):
        parameters = build_schema(ping)["function"]["parameters"]
        self.assertEqual(parameters["properties"], {})
        self.assertEqual(parameters["required"], [])

    def test_an_unannotated_parameter_falls_back_to_string(self):
        schema = build_schema(undocumented)
        self.assertEqual(
            schema["function"]["parameters"]["properties"]["x"]["type"], "string"
        )
        self.assertEqual(schema["function"]["description"], "")


class TestBuildRegistry(unittest.TestCase):
    def test_indexes_by_name(self):
        registry = build_registry([get_weather, ping])
        self.assertEqual(sorted(registry), ["get_weather", "ping"])

    def test_holds_the_function_and_its_schema(self):
        registry = build_registry([ping])
        self.assertIsInstance(registry["ping"], Tool)
        self.assertIs(registry["ping"].fn, ping)
        self.assertEqual(registry["ping"].schema["function"]["name"], "ping")

    def test_enums_are_routed_by_function_name(self):
        registry = build_registry([get_weather, ping], WEATHER_ENUMS)
        properties = registry["get_weather"].schema["function"]["parameters"]["properties"]
        self.assertEqual(properties["unit"]["enum"], ["celsius", "fahrenheit"])

    def test_rejects_two_tools_with_one_name(self):
        with self.assertRaises(ValueError):
            build_registry([ping, ping])


class TestValidateArguments(unittest.TestCase):
    def setUp(self):
        self.schema = build_schema(get_weather, {"unit": ["celsius", "fahrenheit"]})
        self.orders = build_schema(search_orders)

    def test_returns_the_arguments(self):
        arguments = {"city": "Paris"}
        self.assertEqual(validate_arguments(self.schema, arguments), arguments)

    def test_missing_required_argument_names_it(self):
        with self.assertRaises(ToolError) as caught:
            validate_arguments(self.schema, {"unit": "celsius"})
        self.assertIn(
            "city",
            str(caught.exception),
            "the message must name the missing parameter, or the model cannot tell "
            "which one it left out",
        )

    def test_unexpected_argument_names_it(self):
        with self.assertRaises(ToolError) as caught:
            validate_arguments(self.schema, {"city": "Paris", "country": "France"})
        self.assertIn(
            "country",
            str(caught.exception),
            "the message must name the argument that was not accepted",
        )

    def test_wrong_type_is_rejected(self):
        with self.assertRaises(ToolError) as caught:
            validate_arguments(self.orders, {"customer_id": "c1", "limit": "ten"})
        self.assertIn(
            "limit",
            str(caught.exception),
            "the message must name the parameter whose type was wrong",
        )

    def test_a_bool_is_not_an_integer(self):
        with self.assertRaises(ToolError):
            validate_arguments(self.orders, {"customer_id": "c1", "limit": True})

    def test_an_int_is_an_acceptable_number(self):
        schema = build_schema(set_thermostat)
        self.assertEqual(
            validate_arguments(schema, {"ratio": 1}),
            {"ratio": 1},
            "JSON has one number type, so a model that means 1.0 writes 1",
        )

    def test_enum_violation_lists_the_allowed_values(self):
        with self.assertRaises(ToolError) as caught:
            validate_arguments(self.schema, {"city": "Paris", "unit": "kelvin"})
        message = str(caught.exception)
        self.assertIn(
            "celsius", message, "an enum violation must list the allowed values"
        )
        self.assertIn("fahrenheit", message, "all of them, not just the first")

    def test_a_valid_enum_value_passes(self):
        arguments = {"city": "Paris", "unit": "fahrenheit"}
        self.assertEqual(validate_arguments(self.schema, arguments), arguments)


class TestDispatch(unittest.TestCase):
    def setUp(self):
        self.registry = build_registry(
            [get_weather, search_orders, ping, always_fails], WEATHER_ENUMS
        )

    def test_calls_the_function(self):
        result = dispatch(self.registry, "get_weather", '{"city": "Paris"}')
        self.assertIn("Paris", result)

    def test_the_result_is_always_a_string(self):
        self.assertIsInstance(
            dispatch(self.registry, "search_orders", '{"customer_id": "c1", "limit": 3}'),
            str,
            "a tool result travels back to the model as text",
        )

    def test_omitted_optional_arguments_use_the_function_default(self):
        self.assertIn("celsius", dispatch(self.registry, "get_weather", '{"city": "Oslo"}'))

    def test_a_tool_with_no_arguments(self):
        self.assertEqual(dispatch(self.registry, "ping", "{}"), "pong")

    def test_unknown_tool_lists_what_exists(self):
        with self.assertRaises(ToolError) as caught:
            dispatch(self.registry, "launch_missiles", "{}")
        message = str(caught.exception)
        self.assertIn(
            "launch_missiles", message, "name the tool that was asked for and does not exist"
        )
        self.assertIn("ping", message, "tell the model what it could have called instead")

    def test_unparseable_arguments(self):
        with self.assertRaises(ToolError):
            dispatch(self.registry, "ping", "{not json")

    def test_arguments_that_are_not_an_object(self):
        with self.assertRaises(ToolError):
            dispatch(self.registry, "search_orders", '["c1", 3]')

    def test_schema_violations_never_reach_the_function(self):
        with self.assertRaises(ToolError):
            dispatch(self.registry, "get_weather", '{"city": "Paris", "unit": "kelvin"}')

    def test_the_tools_own_exception_is_not_swallowed(self):
        with self.assertRaises(RuntimeError):
            dispatch(self.registry, "always_fails", "{}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
