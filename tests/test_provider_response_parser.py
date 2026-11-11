import pytest
from model_providers.response_parser import ResponseParser

def test_parse_valid_markdown_json():
    parser = ResponseParser()
    raw = """
Here is my plan:
```json
{
  "plan_id": "p1",
  "actions": [{"action_id": "a1", "worker": "ShellWorker", "type": "run"}]
}
```
"""
    status, plan, err = parser.parse(raw)
    assert status == "parsed"
    assert plan["plan_id"] == "p1"

def test_parse_invalid_json():
    parser = ResponseParser()
    raw = """```json { "plan_id": "p1", "actions": [ ```"""
    status, plan, err = parser.parse(raw)
    assert status == "failed"

def test_parse_ambiguous_json():
    parser = ResponseParser()
    raw = """
```json
{ "plan_id": "p1", "actions": [] }
```
```json
{ "plan_id": "p2", "actions": [] }
```
"""
    status, plan, err = parser.parse(raw)
    assert status == "ambiguous"
