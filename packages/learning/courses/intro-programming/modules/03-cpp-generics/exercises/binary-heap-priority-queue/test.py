from __future__ import annotations

import unittest
from solution import MinHeapPriorityQueue


class TestMinHeapPriorityQueue(unittest.TestCase):
    def test_empty_heap_state(self):
        pq = MinHeapPriorityQueue()
        self.assertEqual(pq.size(), 0)
        self.assertTrue(pq.is_empty())

        with self.assertRaises(IndexError):
            pq.peek()

        with self.assertRaises(IndexError):
            pq.pop()

    def test_single_element(self):
        pq = MinHeapPriorityQueue()
        pq.push(10.5, "task1")
        self.assertEqual(pq.size(), 1)
        self.assertFalse(pq.is_empty())

        self.assertEqual(pq.peek(), (10.5, "task1"))
        item = pq.pop()
        self.assertEqual(item, (10.5, "task1"))
        self.assertEqual(pq.size(), 0)
        self.assertTrue(pq.is_empty())

    def test_priority_ordering_multiple_pushes(self):
        pq = MinHeapPriorityQueue()
        data = [(5.0, "e"), (1.0, "a"), (9.0, "i"), (3.0, "c"), (2.0, "b"), (8.0, "h")]
        for prio, val in data:
            pq.push(prio, val)

        self.assertEqual(pq.size(), 6)
        popped = []
        while not pq.is_empty():
            popped.append(pq.pop())

        expected = [(1.0, "a"), (2.0, "b"), (3.0, "c"), (5.0, "e"), (8.0, "h"), (9.0, "i")]
        self.assertEqual(popped, expected)

    def test_negative_and_duplicate_priorities(self):
        pq = MinHeapPriorityQueue()
        pq.push(-10.0, "neg10")
        pq.push(0.0, "zero")
        pq.push(-50.0, "neg50")
        pq.push(0.0, "zero2")

        self.assertEqual(pq.pop(), (-50.0, "neg50"))
        self.assertEqual(pq.pop(), (-10.0, "neg10"))

        # Next two have priority 0.0
        p1 = pq.pop()
        p2 = pq.pop()
        self.assertEqual(p1[0], 0.0)
        self.assertEqual(p2[0], 0.0)
        self.assertTrue(pq.is_empty())

    def test_uncomparable_payload_objects(self):
        # Payloads that cannot be compared directly with < (e.g. dicts)
        pq = MinHeapPriorityQueue()
        pq.push(1.0, {"id": 1})
        pq.push(1.0, {"id": 2})
        pq.push(0.5, {"id": 0})

        first = pq.pop()
        self.assertEqual(first[0], 0.5)
        self.assertEqual(first[1], {"id": 0})

        second = pq.pop()
        self.assertEqual(second[0], 1.0)
        third = pq.pop()
        self.assertEqual(third[0], 1.0)

    def test_heapify_linear_build(self):
        items = [
            (42.0, "val42"),
            (10.0, "val10"),
            (15.0, "val15"),
            (5.0, "val5"),
            (30.0, "val30"),
            (2.0, "val2"),
            (8.0, "val8"),
        ]

        pq = MinHeapPriorityQueue()
        pq.heapify(items)

        self.assertEqual(pq.size(), 7)
        self.assertEqual(pq.peek(), (2.0, "val2"))

        extracted_priorities = []
        while not pq.is_empty():
            extracted_priorities.append(pq.pop()[0])

        self.assertEqual(extracted_priorities, [2.0, 5.0, 8.0, 10.0, 15.0, 30.0, 42.0])

    def test_heapify_empty(self):
        pq = MinHeapPriorityQueue()
        pq.heapify([])
        self.assertEqual(pq.size(), 0)
        self.assertTrue(pq.is_empty())

    def test_interleaved_push_and_pop(self):
        pq = MinHeapPriorityQueue()
        pq.push(20.0, "20")
        pq.push(10.0, "10")
        self.assertEqual(pq.pop(), (10.0, "10"))

        pq.push(5.0, "5")
        pq.push(30.0, "30")
        self.assertEqual(pq.pop(), (5.0, "5"))
        self.assertEqual(pq.pop(), (20.0, "20"))
        self.assertEqual(pq.pop(), (30.0, "30"))
        self.assertTrue(pq.is_empty())


if __name__ == "__main__":
    unittest.main()
