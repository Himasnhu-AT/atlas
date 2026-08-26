import unittest
from solution import GCNode, MarkAndSweepGC


class TestMarkAndSweepGC(unittest.TestCase):
    def setUp(self) -> None:
        self.gc = MarkAndSweepGC()

    def test_empty_collection(self) -> None:
        freed_count, freed_ids = self.gc.collect()
        self.assertEqual(freed_count, 0)
        self.assertEqual(freed_ids, [])
        self.assertEqual(self.gc.get_live_count(), 0)

    def test_direct_unreachable_cleanup(self) -> None:
        a = self.gc.allocate("node_a", 100)
        b = self.gc.allocate("node_b", 200)

        self.gc.add_root(a)
        self.assertEqual(self.gc.get_live_count(), 2)

        freed_count, freed_ids = self.gc.collect()
        self.assertEqual(freed_count, 1)
        self.assertEqual(freed_ids, ["node_b"])
        self.assertEqual(self.gc.get_live_count(), 1)
        self.assertEqual(a.payload, 100)

    def test_reachable_chain(self) -> None:
        a = self.gc.allocate("a")
        b = self.gc.allocate("b")
        c = self.gc.allocate("c")

        a.add_reference(b)
        b.add_reference(c)
        self.gc.add_root(a)

        freed_count, freed_ids = self.gc.collect()
        self.assertEqual(freed_count, 0)
        self.assertEqual(freed_ids, [])
        self.assertEqual(self.gc.get_live_count(), 3)

    def test_disconnect_chain(self) -> None:
        a = self.gc.allocate("a")
        b = self.gc.allocate("b")
        c = self.gc.allocate("c")

        a.add_reference(b)
        b.add_reference(c)
        self.gc.add_root(a)

        # Break connection between a and b
        a.remove_reference(b)

        freed_count, freed_ids = self.gc.collect()
        self.assertEqual(freed_count, 2)
        self.assertIn("b", freed_ids)
        self.assertIn("c", freed_ids)
        self.assertEqual(self.gc.get_live_count(), 1)

    def test_cyclic_graph_cleanup(self) -> None:
        # Create an isolated cycle: x -> y -> z -> x
        x = self.gc.allocate("x")
        y = self.gc.allocate("y")
        z = self.gc.allocate("z")

        x.add_reference(y)
        y.add_reference(z)
        z.add_reference(x)

        # Temporarily rooted
        self.gc.add_root(x)
        self.assertEqual(self.gc.get_live_count(), 3)

        # Remove root - whole cycle is now unreachable despite internal references
        self.gc.remove_root(x)

        freed_count, freed_ids = self.gc.collect()
        self.assertEqual(freed_count, 3)
        self.assertEqual(set(freed_ids), {"x", "y", "z"})
        self.assertEqual(self.gc.get_live_count(), 0)

    def test_mixed_cyclic_and_reachable(self) -> None:
        # Rooted cycle: a -> b -> a
        a = self.gc.allocate("a", "live_a")
        b = self.gc.allocate("b", "live_b")
        a.add_reference(b)
        b.add_reference(a)
        self.gc.add_root(a)

        # Unreachable cycle: c -> d -> c
        c = self.gc.allocate("c", "dead_c")
        d = self.gc.allocate("d", "dead_d")
        c.add_reference(d)
        d.add_reference(c)

        freed_count, freed_ids = self.gc.collect()
        self.assertEqual(freed_count, 2)
        self.assertEqual(set(freed_ids), {"c", "d"})
        self.assertEqual(self.gc.get_live_count(), 2)

    def test_multiple_collection_cycles(self) -> None:
        root = self.gc.allocate("root")
        self.gc.add_root(root)

        temp1 = self.gc.allocate("temp1")
        root.add_reference(temp1)
        self.gc.collect()
        self.assertEqual(self.gc.get_live_count(), 2)

        root.remove_reference(temp1)
        freed_count, freed_ids = self.gc.collect()
        self.assertEqual(freed_count, 1)
        self.assertEqual(freed_ids, ["temp1"])
        self.assertEqual(self.gc.get_live_count(), 1)


if __name__ == "__main__":
    unittest.main()
