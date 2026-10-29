# Changelog

## 0.1.0 (2026-10-29)

First release.

- `ai-register scan`: finds LLM SDK imports and calls (OpenAI, Azure OpenAI, Anthropic, Bedrock, Vertex AI / Gemini, Hugging Face, LangChain, LlamaIndex) in Python, notebooks and JavaScript/TypeScript, plus model files, prompt templates, vector stores and MCP configs.
- Groups findings into systems by the nearest project manifest.
- Writes `ai-register.yaml` with a draft EU AI Act risk tier (with the matched evidence) and a starter ISO/IEC 42001 Annex A checklist per system.
- Keeps owner, purpose, reviewed tier, reviewer notes and control evidence when the register is regenerated. Systems that disappear are kept as `not-detected`.
- `ai-register diff` and `scan --check` for CI.
- `ai-register report` for Markdown or single-file HTML.
