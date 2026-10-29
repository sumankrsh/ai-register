"""Rules that recognise AI usage in source files.

Each rule is a plain regular expression applied line by line. The rules are
deliberately simple so that an auditor can read them and see why a finding
was raised.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

PY = (".py", ".ipynb")
JS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")
CODE = PY + JS


@dataclass(frozen=True)
class Rule:
    kind: str  # llm-sdk, llm-call, vector-store, prompt-template
    provider: str
    pattern: re.Pattern[str]
    suffixes: tuple[str, ...] = CODE


def _r(kind: str, provider: str, regex: str, suffixes: tuple[str, ...] = CODE) -> Rule:
    return Rule(kind, provider, re.compile(regex), suffixes)


# Order matters only for readability: every matching rule produces a finding,
# but a line is reported at most once per (kind, provider).
RULES: list[Rule] = [
    # SDK imports, Python
    _r("llm-sdk", "azure-openai", r"\bAzureOpenAI\b|\bAzureChatOpenAI\b", CODE),
    _r("llm-sdk", "openai", r"^\s*(import openai\b|from openai\b)", PY),
    _r("llm-sdk", "anthropic", r"^\s*(import anthropic\b|from anthropic\b)", PY),
    _r("llm-sdk", "bedrock", r"""(client\(|service_name\s*=)\s*["']bedrock(-runtime|-agent-runtime)?["']""", PY),
    _r(
        "llm-sdk",
        "vertex",
        r"^\s*(import vertexai\b|from vertexai\b|from google\.cloud import aiplatform\b|import google\.generativeai\b|from google import genai\b)",
        PY,
    ),
    _r(
        "llm-sdk",
        "huggingface",
        r"^\s*(import|from) (transformers|huggingface_hub|sentence_transformers|diffusers)\b",
        PY,
    ),
    _r("llm-sdk", "langchain", r"^\s*(import|from) langchain(_[a-z]+)?\b", PY),
    _r("llm-sdk", "llamaindex", r"^\s*(import|from) llama_index\b", PY),
    # SDK imports, JavaScript / TypeScript
    _r("llm-sdk", "openai", r"""(from\s+|require\()\s*["']openai["']""", JS),
    _r("llm-sdk", "anthropic", r"""(from\s+|require\()\s*["']@anthropic-ai/sdk["']""", JS),
    _r("llm-sdk", "bedrock", r"""["']@aws-sdk/client-bedrock(-runtime|-agent-runtime)?["']""", JS),
    _r("llm-sdk", "vertex", r"""["'](@google-cloud/vertexai|@google/generative-ai|@google/genai)["']""", JS),
    _r(
        "llm-sdk",
        "huggingface",
        r"""["'](@huggingface/inference|@huggingface/transformers|@xenova/transformers)["']""",
        JS,
    ),
    _r("llm-sdk", "langchain", r"""["'](langchain|@langchain/[a-z-]+)(/[^"']*)?["']""", JS),
    _r("llm-sdk", "llamaindex", r"""["']llamaindex["']""", JS),
    # Model calls
    _r("llm-call", "openai", r"\.(chat\.completions|completions|responses|embeddings)\.create\("),
    _r("llm-call", "anthropic", r"\.messages\.(create|stream)\("),
    _r(
        "llm-call",
        "bedrock",
        r"\.(invoke_model|invoke_model_with_response_stream|converse|converse_stream)\(|\bnew (InvokeModelCommand|ConverseCommand)\(",
    ),
    _r("llm-call", "vertex", r"\.generate_content\(|\bGenerativeModel\("),
    _r("llm-call", "huggingface", r"\.from_pretrained\(|\bpipeline\(\s*[\"']"),
    # Vector stores: Python imports and JavaScript package names
    *[
        rule
        for provider, module, package in (
            ("chroma", "chromadb", "chromadb"),
            ("pinecone", "pinecone", "@pinecone-database/pinecone"),
            ("faiss", "faiss", "faiss-node"),
            ("weaviate", "weaviate", "weaviate-client"),
            ("qdrant", "qdrant_client", "@qdrant/js-client-rest"),
            ("pgvector", "pgvector", "pgvector"),
            ("lancedb", "lancedb", "@lancedb/lancedb"),
            ("milvus", "pymilvus", "@zilliz/milvus2-sdk-node"),
        )
        for rule in (
            _r("vector-store", provider, rf"^\s*(import|from) {module}\b", PY),
            _r("vector-store", provider, rf"""["']{re.escape(package)}(/[^"']*)?["']""", JS),
        )
    ],
    # Prompts defined inline in code
    _r(
        "prompt-template",
        "inline",
        r"\b(SYSTEM_PROMPT|system_prompt|systemPrompt|PROMPT_TEMPLATE|ChatPromptTemplate|PromptTemplate)\s*(=|\(|\.from)",
    ),
]

# A model name that appears as a whole string literal, e.g. model="gpt-4o-mini".
MODEL_NAME = re.compile(
    r"""["']("""
    r"gpt-[0-9][\w.\-]*|chatgpt-[\w.\-]+|text-embedding-[\w\-]+|"
    r"claude-[\w.\-]+|(anthropic|meta|amazon|mistral|cohere)\.[\w.\-:]+|"
    r"gemini-[\w.\-]+|text-bison[\w@\-]*|"
    r"(meta-)?llama-?[0-9][\w.\-]*|mistral-[\w.\-]+|mixtral-[\w.\-]+"
    r""")["']"""
)
# Short or generic ids ("o3", "org/model") count only next to a model keyword.
CONTEXT_MODEL_NAME = re.compile(r"""["'](o[1-9](-mini|-pro)?|[A-Za-z0-9_\-]+/[A-Za-z0-9_.\-]+)["']""")
MODEL_CONTEXT = re.compile(r"from_pretrained\(|pipeline\(|\bmodel(_id|_name)?\s*[=:]", re.IGNORECASE)

MODEL_FILE_SUFFIXES = (
    ".gguf",
    ".safetensors",
    ".onnx",
    ".pt",
    ".pth",
    ".h5",
    ".keras",
    ".tflite",
    ".mlmodel",
)
PROMPT_FILE_SUFFIXES = (".prompt", ".prompty")
PROMPT_DIR_SUFFIXES = (".txt", ".md", ".yaml", ".yml", ".j2", ".jinja", ".jinja2", ".tmpl")
MCP_FILE_NAMES = ("mcp.json", ".mcp.json", "claude_desktop_config.json", "mcp_config.json")

PII_TERMS = re.compile(
    r"\b(e_?mail(_address)?|phone(_number)?|mobile|ssn|social_security|national_id|nino|"
    r"passport(_number)?|date_of_birth|dob|birth_?date|home_address|postcode|zip_?code|"
    r"iban|sort_code|account_number|card_number|credit_card|salary|"
    r"diagnosis|medical|health_record|nhs_number|patient|ethnicity|religion|"
    r"first_name|last_name|full_name|surname)\b",
    re.IGNORECASE,
)
EXTERNAL_CALL = re.compile(
    r"\b(requests|httpx|aiohttp|urllib\.request)\.(get|post|put|request|urlopen|AsyncClient|Client)\b"
    r"|\bfetch\(\s*[\"'`]https?://|\baxios\.(get|post|put)\("
)
COMMENT_PREFIXES = ("#", "//", "/*", "*")
HINT_WINDOW = 25  # lines either side of a finding that count as "nearby"


@dataclass
class Finding:
    kind: str
    provider: str
    file: str  # posix path relative to the scan root
    line: int
    evidence: str
    model: str | None = None
    hints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = {
            "kind": self.kind,
            "provider": self.provider,
            "file": self.file,
            "line": self.line,
            "evidence": self.evidence,
        }
        if self.model:
            data["model"] = self.model
        if self.hints:
            data["hints"] = list(self.hints)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> Finding:
        return cls(
            kind=data["kind"],
            provider=data["provider"],
            file=data["file"],
            line=int(data.get("line", 0)),
            evidence=data.get("evidence", ""),
            model=data.get("model"),
            hints=list(data.get("hints", [])),
        )

    def key(self) -> tuple:
        """Identity that survives code moving up or down the file."""
        return (self.kind, self.provider, self.file, self.model or "", self.evidence)


def find_models(line: str) -> list[str]:
    models = [m.group(1) for m in MODEL_NAME.finditer(line)]
    if MODEL_CONTEXT.search(line):
        for match in CONTEXT_MODEL_NAME.finditer(line):
            name = match.group(1)
            if name not in models and not name.startswith(("http", ".")):
                models.append(name)
    return models


def _hints(lines: list[str], index: int) -> list[str]:
    lo, hi = max(0, index - HINT_WINDOW), min(len(lines), index + HINT_WINDOW + 1)
    pii: set[str] = set()
    external = False
    for text in lines[lo:hi]:
        for match in PII_TERMS.finditer(text):
            pii.add(match.group(1).lower())
        if EXTERNAL_CALL.search(text):
            external = True
    hints = [f"pii:{term}" for term in sorted(pii)]
    if external:
        hints.append("external-call")
    return hints


def scan_text(rel_path: str, text: str) -> list[Finding]:
    """Find AI usage in the text of one source file."""
    suffix = PurePosixPath(rel_path).suffix.lower()
    if suffix not in CODE:
        return []
    lines = text.splitlines()
    findings: list[Finding] = []
    seen: set[tuple[int, str, str]] = set()
    pending_models: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith(COMMENT_PREFIXES):
            continue
        for rule in RULES:
            if suffix not in rule.suffixes or not rule.pattern.search(line):
                continue
            mark = (index, rule.kind, rule.provider)
            if mark in seen:
                continue
            seen.add(mark)
            findings.append(Finding(rule.kind, rule.provider, rel_path, index + 1, stripped[:160]))
        for model in find_models(line):
            pending_models.append((index, model))
    # Attach each model name to the closest call or SDK finding in the file.
    for index, model in pending_models:
        target = _closest(findings, index + 1)
        if target is not None and target.model is None:
            target.model = model
        elif target is not None and target.model != model:
            findings.append(
                Finding("model-ref", target.provider, rel_path, index + 1, lines[index].strip()[:160], model)
            )
        elif target is None:
            findings.append(
                Finding("model-ref", provider_for_model(model), rel_path, index + 1, lines[index].strip()[:160], model)
            )
    for finding in findings:
        finding.hints = _hints(lines, finding.line - 1)
    findings.sort(key=lambda f: (f.line, f.kind, f.provider))
    return findings


def _closest(findings: list[Finding], line_no: int) -> Finding | None:
    candidates = [f for f in findings if f.kind in ("llm-call", "llm-sdk") and abs(f.line - line_no) <= 15]
    if not candidates:
        return None
    calls = [f for f in candidates if f.kind == "llm-call"]
    pool = calls or candidates
    return min(pool, key=lambda f: abs(f.line - line_no))


def provider_for_model(model: str) -> str:
    name = model.lower()
    if name.startswith(("gpt-", "o1", "o3", "o4", "chatgpt-", "text-embedding-")):
        return "openai"
    if name.startswith("claude-"):
        return "anthropic"
    if name.startswith(("anthropic.", "meta.", "amazon.", "mistral.", "cohere.")):
        return "bedrock"
    if name.startswith(("gemini-", "text-bison")):
        return "vertex"
    if "/" in name:
        return "huggingface"
    return "unknown"


def classify_path(rel_path: str, first_bytes: str = "") -> Finding | None:
    """Findings that come from the file itself rather than its lines."""
    path = PurePosixPath(rel_path)
    name = path.name.lower()
    suffix = path.suffix.lower()
    if suffix in MODEL_FILE_SUFFIXES:
        return Finding("model-file", "local", rel_path, 0, f"model artefact ({suffix[1:]})")
    if name in MCP_FILE_NAMES or (suffix == ".json" and '"mcpServers"' in first_bytes):
        return Finding("mcp-config", "mcp", rel_path, 0, "MCP server configuration")
    if suffix in PROMPT_FILE_SUFFIXES:
        return Finding("prompt-template", "file", rel_path, 0, "prompt file")
    in_prompt_dir = any(part.lower() in ("prompts", "prompt_templates") for part in path.parts[:-1])
    if in_prompt_dir and suffix in PROMPT_DIR_SUFFIXES:
        return Finding("prompt-template", "file", rel_path, 0, "file in a prompts folder")
    return None


def mcp_servers(text: str) -> list[str]:
    """Server names declared in an MCP config file, best effort."""
    try:
        data = json.loads(text)
    except ValueError:
        return []
    servers = data.get("mcpServers") or data.get("servers") or {}
    return sorted(servers) if isinstance(servers, dict) else []
