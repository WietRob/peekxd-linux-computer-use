# Test Plan and Results

Candidate: cli-click-type-on-element

## RED
- Command: `pytest tests/test_cli.py::TestCLI::test_click_on_element_uses_semantic_bbox_center tests/test_cli.py::TestCLI::test_type_on_element_clicks_semantic_bbox_center_then_types -q`
- Result before implementation: 2 failed.
- Expected failure: Click rejected `--on` for both `click` and `type` commands (`No such option: --on`).

## GREEN / Regression
- Command: `pytest tests/test_cli.py::TestCLI::test_click_on_element_uses_semantic_bbox_center tests/test_cli.py::TestCLI::test_type_on_element_clicks_semantic_bbox_center_then_types -q`
- Result after implementation: 2 passed in 0.07s.

- Command: `pytest tests/test_cli.py -q`
- Result: 30 passed in 0.12s.

- Command: `pytest tests/test_cli.py tests/test_agent_hermes_tools.py tests/test_semantic_action_mapping.py -q`
- Result: 46 passed in 0.20s.

- Command: `pytest tests/ -q`
- Result: 480 passed in 2.66s.
