from __future__ import annotations

import unittest
from solution import ObjectInstance, VTable, define_class, instantiate


class TestVTableDispatchEngine(unittest.TestCase):
    def test_single_class_method_invocation(self):
        def area(instance):
            return instance.fields["width"] * instance.fields["height"]

        rect_class = define_class("Rectangle", methods={"area": area})
        rect = instantiate(rect_class, width=10, height=5)

        self.assertEqual(rect.vptr.name, "Rectangle")
        self.assertEqual(rect.fields["width"], 10)
        self.assertEqual(rect.fields["height"], 5)
        self.assertEqual(rect.invoke("area"), 50)

    def test_inheritance_and_fallback_to_base_method(self):
        def describe(instance):
            return f"Shape({instance.fields.get('name', 'unnamed')})"

        shape_class = define_class("Shape", methods={"describe": describe})
        circle_class = define_class("Circle", parent=shape_class)

        circle = instantiate(circle_class, name="PrimaryCircle", radius=4.0)
        self.assertEqual(circle.invoke("describe"), "Shape(PrimaryCircle)")

    def test_method_overriding(self):
        def base_render(instance):
            return "Render: Base"

        def circle_render(instance):
            return f"Render: Circle with radius {instance.fields['radius']}"

        shape_class = define_class("Shape", methods={"render": base_render})
        circle_class = define_class("Circle", parent=shape_class, methods={"render": circle_render})

        base_inst = instantiate(shape_class)
        circle_inst = instantiate(circle_class, radius=7)

        self.assertEqual(base_inst.invoke("render"), "Render: Base")
        self.assertEqual(circle_inst.invoke("render"), "Render: Circle with radius 7")

    def test_multi_level_inheritance(self):
        def level_a(instance):
            return "A"

        def level_b(instance):
            return "B"

        class_a = define_class("ClassA", methods={"level_a": level_a})
        class_b = define_class("ClassB", parent=class_a, methods={"level_b": level_b})
        class_c = define_class("ClassC", parent=class_b)

        inst_c = instantiate(class_c)
        self.assertEqual(inst_c.invoke("level_a"), "A")
        self.assertEqual(inst_c.invoke("level_b"), "B")

    def test_missing_method_raises_attribute_error(self):
        empty_class = define_class("Empty")
        inst = instantiate(empty_class)

        with self.assertRaises(AttributeError):
            inst.invoke("non_existent_method")

    def test_field_mutation_via_method(self):
        def set_x(instance, val):
            instance.fields["x"] = val

        def get_x(instance):
            return instance.fields["x"]

        point_class = define_class("Point", methods={"set_x": set_x, "get_x": get_x})
        p = instantiate(point_class, x=0)

        self.assertEqual(p.invoke("get_x"), 0)
        p.invoke("set_x", 42)
        self.assertEqual(p.invoke("get_x"), 42)
        self.assertEqual(p.fields["x"], 42)

    def test_polymorphic_collection_dispatch(self):
        def speak_dog(instance):
            return "Woof"

        def speak_cat(instance):
            return "Meow"

        animal_class = define_class("Animal")
        dog_class = define_class("Dog", parent=animal_class, methods={"speak": speak_dog})
        cat_class = define_class("Cat", parent=animal_class, methods={"speak": speak_cat})

        animals: list[ObjectInstance] = [
            instantiate(dog_class),
            instantiate(cat_class),
            instantiate(dog_class),
        ]

        results = [a.invoke("speak") for a in animals]
        self.assertEqual(results, ["Woof", "Meow", "Woof"])

    def test_method_with_multiple_arguments(self):
        def add_three(instance, a, b, c):
            return instance.fields["base"] + a + b + c

        calc_class = define_class("Calculator", methods={"add_three": add_three})
        calc = instantiate(calc_class, base=100)

        self.assertEqual(calc.invoke("add_three", 1, 2, 3), 106)


if __name__ == "__main__":
    unittest.main()
