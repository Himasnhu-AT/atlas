from __future__ import annotations

import unittest
from solution import Node, DoublyLinkedList


class TestDoublyLinkedList(unittest.TestCase):
    def test_empty_list(self):
        dll = DoublyLinkedList()
        self.assertEqual(dll.size(), 0)
        self.assertEqual(dll.to_list(), [])
        self.assertIsNone(dll.head)
        self.assertIsNone(dll.tail)

        with self.assertRaises(IndexError):
            dll.pop_front()
        with self.assertRaises(IndexError):
            dll.pop_back()

    def test_push_and_pop_front(self):
        dll = DoublyLinkedList()
        n1 = dll.push_front(10)
        self.assertIsInstance(n1, Node)
        self.assertEqual(dll.size(), 1)
        self.assertEqual(dll.to_list(), [10])
        self.assertIs(dll.head, n1)
        self.assertIs(dll.tail, n1)

        n2 = dll.push_front(20)
        self.assertEqual(dll.size(), 2)
        self.assertEqual(dll.to_list(), [20, 10])
        self.assertIs(dll.head, n2)
        self.assertIs(dll.tail, n1)
        self.assertIs(n2.next, n1)
        self.assertIs(n1.prev, n2)

        val = dll.pop_front()
        self.assertEqual(val, 20)
        self.assertEqual(dll.size(), 1)
        self.assertEqual(dll.to_list(), [10])
        self.assertIs(dll.head, n1)
        self.assertIs(dll.tail, n1)
        self.assertIsNone(n1.prev)
        self.assertIsNone(n1.next)

        val = dll.pop_front()
        self.assertEqual(val, 10)
        self.assertEqual(dll.size(), 0)
        self.assertEqual(dll.to_list(), [])
        self.assertIsNone(dll.head)
        self.assertIsNone(dll.tail)

    def test_push_and_pop_back(self):
        dll = DoublyLinkedList()
        n1 = dll.push_back(100)
        n2 = dll.push_back(200)
        n3 = dll.push_back(300)

        self.assertEqual(dll.size(), 3)
        self.assertEqual(dll.to_list(), [100, 200, 300])
        self.assertIs(dll.head, n1)
        self.assertIs(dll.tail, n3)
        self.assertIs(n1.next, n2)
        self.assertIs(n2.prev, n1)
        self.assertIs(n2.next, n3)
        self.assertIs(n3.prev, n2)

        self.assertEqual(dll.pop_back(), 300)
        self.assertEqual(dll.size(), 2)
        self.assertEqual(dll.to_list(), [100, 200])
        self.assertIs(dll.tail, n2)
        self.assertIsNone(n2.next)

        self.assertEqual(dll.pop_back(), 200)
        self.assertEqual(dll.pop_back(), 100)
        self.assertEqual(dll.size(), 0)
        self.assertIsNone(dll.head)
        self.assertIsNone(dll.tail)

    def test_remove_middle_node(self):
        dll = DoublyLinkedList()
        n1 = dll.push_back("A")
        n2 = dll.push_back("B")
        n3 = dll.push_back("C")

        dll.remove_node(n2)
        self.assertEqual(dll.size(), 2)
        self.assertEqual(dll.to_list(), ["A", "C"])
        self.assertIs(n1.next, n3)
        self.assertIs(n3.prev, n1)
        self.assertIsNone(n2.prev)
        self.assertIsNone(n2.next)

    def test_remove_head_and_tail(self):
        dll = DoublyLinkedList()
        n1 = dll.push_back(1)
        n2 = dll.push_back(2)
        n3 = dll.push_back(3)

        # Remove head
        dll.remove_node(n1)
        self.assertEqual(dll.size(), 2)
        self.assertEqual(dll.to_list(), [2, 3])
        self.assertIs(dll.head, n2)
        self.assertIsNone(n2.prev)

        # Remove tail
        dll.remove_node(n3)
        self.assertEqual(dll.size(), 1)
        self.assertEqual(dll.to_list(), [2])
        self.assertIs(dll.head, n2)
        self.assertIs(dll.tail, n2)
        self.assertIsNone(n2.next)
        self.assertIsNone(n2.prev)

        # Remove sole remaining node
        dll.remove_node(n2)
        self.assertEqual(dll.size(), 0)
        self.assertEqual(dll.to_list(), [])
        self.assertIsNone(dll.head)
        self.assertIsNone(dll.tail)

    def test_move_to_front(self):
        dll = DoublyLinkedList()
        n1 = dll.push_back("X")
        n2 = dll.push_back("Y")
        n3 = dll.push_back("Z")

        # Move tail node (n3) to front
        dll.move_to_front(n3)
        self.assertEqual(dll.to_list(), ["Z", "X", "Y"])
        self.assertEqual(dll.size(), 3)
        self.assertIs(dll.head, n3)
        self.assertIs(dll.tail, n2)
        self.assertIs(n3.next, n1)
        self.assertIs(n1.prev, n3)
        self.assertIs(n1.next, n2)
        self.assertIs(n2.prev, n1)
        self.assertIsNone(n2.next)

        # Move middle node (n1) to front
        dll.move_to_front(n1)
        self.assertEqual(dll.to_list(), ["X", "Z", "Y"])
        self.assertIs(dll.head, n1)
        self.assertIs(dll.tail, n2)

        # Move already-head node (n1) to front (no-op)
        dll.move_to_front(n1)
        self.assertEqual(dll.to_list(), ["X", "Z", "Y"])
        self.assertIs(dll.head, n1)


if __name__ == "__main__":
    unittest.main()
