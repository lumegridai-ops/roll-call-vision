"""Fail-closed regression tests (Pika #2381). No video pipeline required."""
import os, sys, unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rcv import agent


class TestDecisionHelpers(unittest.TestCase):
    def test_should_confirm_requires_frames(self):
        # Zero frames + matching count must NOT confirm (ayes_said == 0 was the bug).
        self.assertFalse(agent.should_confirm({"count": 0, "unsure_seats": [], "frames": 0}, 0))
        self.assertFalse(agent.should_confirm({"count": 0, "unsure_seats": [], "frames": 0}, 3))
        self.assertFalse(agent.should_confirm({}, 0))
        self.assertFalse(agent.should_confirm(None, 0))

    def test_should_confirm_match_with_frames(self):
        self.assertTrue(agent.should_confirm({"count": 3, "unsure_seats": [], "frames": 12}, 3))
        self.assertFalse(agent.should_confirm({"count": 2, "unsure_seats": [], "frames": 12}, 3))
        self.assertFalse(agent.should_confirm({"count": 3, "unsure_seats": [1], "frames": 12}, 3))

    def test_empty_votes_not_approvable(self):
        self.assertFalse(agent.compute_minutes_approvable([], []))
        self.assertFalse(agent.compute_minutes_approvable([], None))
        self.assertFalse(agent.compute_minutes_approvable(
            [{"action": "mark_vision_confirmed"}], []))
        # all([]) was True — empty results with a non-empty votes list still fail closed.
        self.assertFalse(agent.compute_minutes_approvable([], [{"motion": "M1"}]))

    def test_results_all_confirmed_approvable(self):
        votes = [{"motion": "M1"}]
        results = [{"action": "mark_vision_confirmed"}]
        self.assertTrue(agent.compute_minutes_approvable(results, votes))
        results_mixed = [{"action": "mark_vision_confirmed"},
                         {"action": "hold_approval_request_human"}]
        self.assertFalse(agent.compute_minutes_approvable(results_mixed, [{"m": 1}, {"m": 2}]))


class TestCheckMeetingFailClosed(unittest.TestCase):
    def test_missing_votes_key(self):
        out = agent.check_meeting("unused.mp4", {}, 5)
        self.assertFalse(out["minutes_approvable"])
        self.assertEqual(out["results"], [])
        self.assertEqual(out.get("error"), "empty_or_missing_votes")

    def test_empty_votes_list(self):
        out = agent.check_meeting("unused.mp4", {"votes": []}, 5)
        self.assertFalse(out["minutes_approvable"])
        self.assertEqual(out["results"], [])
        self.assertEqual(out.get("error"), "empty_or_missing_votes")

    def test_none_transcript(self):
        out = agent.check_meeting("unused.mp4", None, 5)
        self.assertFalse(out["minutes_approvable"])
        self.assertEqual(out.get("error"), "empty_or_missing_votes")

    @patch("rcv.agent.vision.baseline", return_value="base")
    @patch("rcv.agent.vision.count_hands")
    def test_zero_frames_holds_even_when_ayes_said_zero(self, mock_count, _base):
        mock_count.return_value = {
            "ayes_seen": [], "count": 0, "unsure_seats": [], "frames": 0, "stride": 5, "thresh": 35,
        }
        tr = {"votes": [{"motion": "M1", "start": 2.0, "end": 4.0, "ayes_said": 0}]}
        out = agent.check_meeting("unused.mp4", tr, 5)
        self.assertEqual(len(out["results"]), 1)
        self.assertEqual(out["results"][0]["action"], "hold_approval_request_human")
        self.assertFalse(out["minutes_approvable"])
        self.assertIn("zero frames", out["results"][0]["message"])

    @patch("rcv.agent.vision.baseline", return_value="base")
    @patch("rcv.agent.vision.count_hands")
    def test_zero_frames_does_not_confirm_matching_nonzero(self, mock_count, _base):
        mock_count.return_value = {
            "ayes_seen": [], "count": 2, "unsure_seats": [], "frames": 0, "stride": 5, "thresh": 35,
        }
        tr = {"votes": [{"motion": "M1", "start": 9.0, "end": 9.0, "ayes_said": 2}]}
        out = agent.check_meeting("unused.mp4", tr, 7)
        self.assertEqual(out["results"][0]["action"], "hold_approval_request_human")
        self.assertFalse(out["minutes_approvable"])

    @patch("rcv.agent.vision.baseline", return_value="base")
    @patch("rcv.agent.vision.count_hands")
    def test_match_with_frames_confirms(self, mock_count, _base):
        mock_count.return_value = {
            "ayes_seen": [0, 1, 2], "count": 3, "unsure_seats": [], "frames": 10, "stride": 5, "thresh": 35,
        }
        tr = {"votes": [{"motion": "M1", "start": 2.0, "end": 4.0, "ayes_said": 3}]}
        out = agent.check_meeting("unused.mp4", tr, 5)
        self.assertEqual(out["results"][0]["action"], "mark_vision_confirmed")
        self.assertTrue(out["minutes_approvable"])


class TestScorerExemptions(unittest.TestCase):
    """Half-raise exemption must cover M2/M3 when the half seat is in those aye sets."""

    def test_half_raise_any_motion_with_half_seat(self):
        # Inline the same logic as eval/run_eval.should_confirm (keep test free of running eval).
        def should_confirm(said, truth, vote, occ, half):
            if said != truth:
                return False
            if occ and vote["motion"] == "M1":
                return False
            if half and any(a in half for a in vote["ayes"]):
                return False
            return True

        half = (3,)
        # m06-style: seat 3 half-raises on M1, M2, M3
        self.assertFalse(should_confirm(1, 1, {"motion": "M1", "ayes": [3]}, None, half))
        self.assertFalse(should_confirm(1, 1, {"motion": "M2", "ayes": [3]}, None, half))
        self.assertFalse(should_confirm(4, 4, {"motion": "M3", "ayes": [0, 1, 3, 4]}, None, half))
        # Motion without the half seat still expected to confirm when counts match
        self.assertTrue(should_confirm(2, 2, {"motion": "M2", "ayes": [0, 1]}, None, half))

    def test_txerr_shapes_are_mixed(self):
        def inject_txerr(truth_count, n_seats, meeting_id):
            shape = (meeting_id // 8) % 4
            s = truth_count
            if shape == 0:
                return s + 1 if s < n_seats else s - 1
            if shape == 1:
                return max(0, s - 1)
            if shape == 2:
                return min(n_seats, s + 2) if s + 2 <= n_seats else max(0, s - 2)
            return 0 if s > 0 else min(n_seats, 1)

        # Meetings 4,12,20,28 → shapes 0..3
        self.assertEqual(inject_txerr(5, 7, 4), 6)   # overcount
        self.assertEqual(inject_txerr(3, 7, 12), 2)  # undercount
        self.assertEqual(inject_txerr(2, 7, 20), 4)  # +2
        self.assertEqual(inject_txerr(2, 7, 28), 0)  # zero vs nonzero


if __name__ == "__main__":
    unittest.main()
