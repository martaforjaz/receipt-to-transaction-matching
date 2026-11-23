import unittest

from matching import DATA, Fields, extract_ocr, load, match, parse_text


class MatchingTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_text("Atlas Coffee\n2026-03-08\nTOTAL EUR 12,50"),
                         Fields("Atlas Coffee", "2026-03-08", 1250))
        self.assertIsNone(parse_text("Atlas Coffee\n2026-02-30\nTOTAL 7.00").date)

    def test_fixture_policy(self):
        ledger = load("ledger")
        for case in load("cases"):
            with self.subTest(receipt=case["id"]):
                actual = match(Fields(case["merchant"], case["date"], case["cents"]), ledger)
                self.assertEqual(actual["status"], case["expected_status"])
                self.assertEqual(actual["transaction"], case["expected"])

    def test_ocr_match_and_ambiguous_receipt(self):
        ledger = load("ledger")
        for receipt, outcome, transaction in (("r01", "matched", "T01A"), ("r13", "ambiguous", None)):
            with self.subTest(receipt=receipt):
                fields, _ = extract_ocr(DATA / "receipts" / f"{receipt}.png")
                result = match(fields, ledger)
                self.assertEqual(result["status"], outcome)
                self.assertEqual(result["transaction"], transaction)

    def test_missing_fields(self):
        self.assertEqual(match(Fields("ATLAS COFFEE", None, 300), load("ledger"))["status"], "needs_review")

    def test_blur_does_not_need_a_forced_match(self):
        # Exact date and amount never override a merchant mismatch.
        ledger = [{"merchant": "Atlas Coffee", "date": "2026-03-08", "cents": 300, "id": "X"}]
        self.assertEqual(match(Fields("North Books", "2026-03-08", 300), ledger)["status"], "no_match")


if __name__ == "__main__":
    unittest.main()
