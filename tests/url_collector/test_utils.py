from unittest import TestCase

import welearn_datastack.utils_.database_utils


class Test(TestCase):
    def setUp(self) -> None:
        self.to_batch_list = [
            "https://www.example.org/talks/ted_talk_1",
            "https://www.example.org/talks/ted_talk_2",
            "https://www.example.org/talks/ted_talk_3",
            "https://www.example.org/talks/ted_talk_4",
            "https://www.example.org/talks/ted_talk_5",
            "https://www.example.org/talks/ted_talk_6",
            "https://www.example.org/talks/ted_talk_7",
            "https://www.example.org/talks/ted_talk_8",
            "https://www.example.org/talks/ted_talk_9",
            "https://www.example.org/talks/ted_talk_10",
        ]

    def test_create_batches(self):
        """
        Test the create_batches method
        """
        batch_list = (
            welearn_datastack.utils_.database_utils.create_specific_batches_quantity(
                to_batch_list=self.to_batch_list, qty_batch=4
            )
        )
        self.assertEqual(4, len(batch_list))
        self.assertEqual(3, len(batch_list[0]))
        self.assertEqual(3, len(batch_list[1]))
        self.assertEqual(3, len(batch_list[2]))
        self.assertEqual(1, len(batch_list[3]))

        # Check method determininism
        self.assertEqual(batch_list[0][1], self.to_batch_list[1])
        self.assertEqual(batch_list[0][2], self.to_batch_list[2])
        self.assertEqual(batch_list[1][0], self.to_batch_list[3])
        self.assertEqual(batch_list[1][1], self.to_batch_list[4])
        self.assertEqual(batch_list[1][2], self.to_batch_list[5])
        self.assertEqual(batch_list[2][0], self.to_batch_list[6])
        self.assertEqual(batch_list[2][1], self.to_batch_list[7])
        self.assertEqual(batch_list[2][2], self.to_batch_list[8])
        self.assertEqual(batch_list[3][0], self.to_batch_list[9])

        batch_list = (
            welearn_datastack.utils_.database_utils.create_specific_batches_quantity(
                to_batch_list=self.to_batch_list, qty_batch=1
            )
        )
        self.assertEqual(1, len(batch_list))
        self.assertEqual(10, len(batch_list[0]))
