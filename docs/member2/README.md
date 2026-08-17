# Member 2

Run the offline safety and contract suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\chat tests\agent_v2 -q
.\.venv\Scripts\python.exe -m chat.evaluation
```

`handle_chat` validates contexts through Member 1's public `governance.api.validate_access_context` by default. Standalone tests inject only the offline fake validator and in-memory governed case data. An LLM is optional: with no configured provider/key, responses are explicitly labelled `approved_policy_fallback`.