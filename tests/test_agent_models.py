import unittest

from everstory.eval.agent_models import (
    ROLE_CANDIDATES,
    ROLE_CASES,
    RoleCase,
    recommended_routes,
    score_case,
)


class AgentModelEvalTest(unittest.TestCase):
    def test_every_agent_has_three_cases_and_multiple_candidates(self):
        counts = {
            role: sum(case.role == role for case in ROLE_CASES)
            for role in ROLE_CANDIDATES
        }
        self.assertTrue(all(count == 3 for count in counts.values()))
        self.assertTrue(all(len(candidates) >= 2 for candidates in ROLE_CANDIDATES.values()))

    def test_deterministic_case_scoring(self):
        case = RoleCase(
            id="sample", role="intent_parser", prompt="move",
            checks=(("action", "move", "eq"), ("target", "dock", "eq")),
            required_ids=("E1",), forbidden=("cave",), language="en",
        )
        scores = score_case(
            case,
            '{"action":"move","target":"dock","evidence_ids":["E1"],"reason":"Use the dock route."}',
        )
        self.assertEqual(scores, (1.0, 1.0, 1.0, 1.0, 1.0))

    def test_invalid_json_scores_zero(self):
        case = ROLE_CASES[0]
        self.assertEqual(score_case(case, "not-json"), (0, 0, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
