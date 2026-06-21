# Test Plan and Results

Candidate: semantic-element-action-mapping
Branch: autonomy/peekxd/semantic-element-action-mapping-20260621

## RED

Command:

```bash
pytest tests/test_semantic_action_mapping.py tests/test_agent_hermes_tools.py::TestToolDefinitions::test_semantic_safe_tools_exist_and_screenshot_tools_removed tests/test_agent_hermes_tools.py::TestActionExecution::test_click_element_looks_up_semantic_bbox_and_clicks_center tests/test_agent_hermes_tools.py::TestActionExecution::test_type_into_element_clicks_semantic_center_then_types_text -q
```

Result: failed during collection because `find_semantic_element` did not exist in `peekxd.semantic`, proving the new tests covered missing behavior before implementation.

## GREEN / targeted verification

Command:

```bash
pytest tests/test_semantic_action_mapping.py tests/test_agent_hermes_tools.py::TestToolDefinitions::test_semantic_safe_tools_exist_and_screenshot_tools_removed tests/test_agent_hermes_tools.py::TestActionExecution::test_click_element_looks_up_semantic_bbox_and_clicks_center tests/test_agent_hermes_tools.py::TestActionExecution::test_type_into_element_clicks_semantic_center_then_types_text -q
```

Result:

```text
........                                                                 [100%]
8 passed in 0.11s
```

Command:

```bash
pytest tests/test_semantic_action_mapping.py tests/test_agent_hermes_tools.py -q
```

Result:

```text
................                                                         [100%]
16 passed in 0.09s
```

## Full regression suite

Command:

```bash
pytest tests/ -q
```

Result:

```text
........................................................................ [ 15%]
........................................................................ [ 30%]
........................................................................ [ 45%]
........................................................................ [ 60%]
........................................................................ [ 75%]
........................................................................ [ 90%]
..............................................                           [100%]
478 passed in 2.52s
```
