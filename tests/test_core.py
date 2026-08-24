import unittest
from cafa_ivr.core import attribution, critical_entity_error_rate, word_error_rate, cafa_score_row, summarize

class CoreTests(unittest.TestCase):
    def test_wer(self):
        self.assertAlmostEqual(word_error_rate("what is my balance", "what if my balance"), 0.25)

    def test_attribution(self):
        self.assertEqual(attribution(True, False), "SPEECH_ATTRIBUTABLE")
        self.assertEqual(attribution(False, False), "DOWNSTREAM_OR_TEST")
        self.assertEqual(attribution(True, True), "HEALTHY")

    def test_ceer(self):
        self.assertEqual(critical_entity_error_rate('{"amount":[500]}', '{"amount":[500]}'), 0.0)
        self.assertEqual(critical_entity_error_rate('{"amount":[500]}', '{"amount":[5000]}'), 2.0)

    def test_summary_ceer_uses_published_micro_average(self):
        rows = [
            cafa_score_row({
                "expected_entities_json": '{"amount":[500]}',
                "predicted_entities_json": '{"amount":[5000]}',
                "text_control_pass": 1,
                "audio_task_success": 0,
            }),
            cafa_score_row({
                "expected_entities_json": '{"date":["monday","tuesday","wednesday"]}',
                "predicted_entities_json": '{"date":["monday","tuesday","wednesday"]}',
                "text_control_pass": 1,
                "audio_task_success": 1,
            }),
        ]
        self.assertEqual(summarize(rows)["ceer"], 0.5)

    def test_cier_measures_realized_consequence(self):
        successful_l4 = cafa_score_row({
            "text_control_pass": 1,
            "audio_task_success": 1,
            "impact_level": "L4",
        })
        failed_l4 = cafa_score_row({
            "text_control_pass": 1,
            "audio_task_success": 0,
            "impact_level": "L4",
        })
        failed_l3 = cafa_score_row({
            "text_control_pass": 1,
            "audio_task_success": 0,
            "impact_level": "L3",
        })

        self.assertEqual(successful_l4["cier_contrib"], 0.0)
        self.assertEqual(failed_l4["cier_contrib"], 1.0)
        self.assertEqual(failed_l3["cier_contrib"], 0.65)
        self.assertEqual(summarize([successful_l4, failed_l4])["cier"], 0.5)

    def test_row(self):
        r = cafa_score_row({
            "reference_text": "lock my card",
            "asr_transcript": "look my card",
            "expected_intent": "lock_card",
            "predicted_intent": "card_info",
            "text_control_pass": "1",
        })
        self.assertEqual(r["asr_ifr_contrib"], 1)
        self.assertEqual(r["attribution"], "SPEECH_ATTRIBUTABLE")

if __name__ == "__main__":
    unittest.main()
