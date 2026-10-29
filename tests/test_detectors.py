from ai_register.detectors import classify_path, find_models, mcp_servers, provider_for_model, scan_text


def kinds(findings):
    return {(f.kind, f.provider) for f in findings}


def test_python_sdks_and_calls_are_found():
    code = "\n".join(
        [
            "from openai import OpenAI",
            "import anthropic",
            "from langchain_openai import ChatOpenAI",
            "from llama_index.core import VectorStoreIndex",
            "client.chat.completions.create(model='gpt-4.1-mini', messages=[])",
            "client.messages.create(model='claude-haiku-4-5', max_tokens=10)",
        ]
    )
    found = kinds(scan_text("app.py", code))
    assert ("llm-sdk", "openai") in found
    assert ("llm-sdk", "anthropic") in found
    assert ("llm-sdk", "langchain") in found
    assert ("llm-sdk", "llamaindex") in found
    assert ("llm-call", "openai") in found
    assert ("llm-call", "anthropic") in found


def test_azure_and_bedrock_python():
    code = 'from openai import AzureOpenAI\nbr = boto3.client("bedrock-runtime")\nbr.invoke_model(modelId="x")\n'
    found = kinds(scan_text("svc.py", code))
    assert ("llm-sdk", "azure-openai") in found
    assert ("llm-sdk", "bedrock") in found
    assert ("llm-call", "bedrock") in found


def test_javascript_imports():
    code = "\n".join(
        [
            'import OpenAI from "openai";',
            'const Anthropic = require("@anthropic-ai/sdk");',
            'import { ChatOpenAI } from "@langchain/openai";',
            'import { VertexAI } from "@google-cloud/vertexai";',
        ]
    )
    found = kinds(scan_text("index.ts", code))
    assert {("llm-sdk", "openai"), ("llm-sdk", "anthropic"), ("llm-sdk", "langchain"), ("llm-sdk", "vertex")} <= found


def test_model_name_attached_to_nearest_call():
    code = "resp = client.chat.completions.create(\n    model='gpt-4o-mini',\n    messages=[],\n)\n"
    calls = [f for f in scan_text("a.py", code) if f.kind == "llm-call"]
    assert calls and calls[0].model == "gpt-4o-mini"


def test_generic_ids_need_model_context():
    assert find_models('repo = "acme/widgets"') == []
    assert find_models('model_id = "acme/widget-classifier"') == ["acme/widget-classifier"]
    assert find_models('x = "o3"') == []
    assert find_models('model="o3"') == ["o3"]


def test_plain_text_mentions_are_not_findings():
    code = "# we compared openai and anthropic last year\nprint('hello')\n"
    assert scan_text("notes.py", code) == []
    assert scan_text("README.md", "from openai import OpenAI") == []


def test_pii_and_external_call_hints_are_nearby_only():
    near = "from openai import OpenAI\nemail = user['email']\nrequests.post(url)\n"
    finding = scan_text("a.py", near)[0]
    assert "pii:email" in finding.hints
    assert "external-call" in finding.hints
    far = "from openai import OpenAI\n" + "x = 1\n" * 60 + "email = 'a'\n"
    assert scan_text("b.py", far)[0].hints == []


def test_file_level_findings():
    assert classify_path("models/m.gguf").kind == "model-file"
    assert classify_path(".mcp.json").kind == "mcp-config"
    assert classify_path("config/tools.json", '{"mcpServers": {}}').kind == "mcp-config"
    assert classify_path("prompts/system.md").kind == "prompt-template"
    assert classify_path("docs/system.md") is None
    assert classify_path("src/app.py") is None


def test_mcp_server_names_and_bad_json():
    assert mcp_servers('{"mcpServers": {"b": {}, "a": {}}}') == ["a", "b"]
    assert mcp_servers("not json") == []


def test_provider_for_model():
    assert provider_for_model("gpt-4o") == "openai"
    assert provider_for_model("claude-sonnet-4-5") == "anthropic"
    assert provider_for_model("anthropic.claude-3-5-haiku-20241022-v1:0") == "bedrock"
    assert provider_for_model("gemini-2.5-flash") == "vertex"
    assert provider_for_model("org/model") == "huggingface"


def test_comment_lines_and_bare_words_are_ignored():
    code = "\n".join(
        [
            "# from openai import OpenAI",
            "// import OpenAI from 'openai';",
            "stores = ['chromadb', 'pinecone']",
            "region = 'bedrock'",
            "def converse(): pass",
        ]
    )
    assert scan_text("x.py", code) == []


def test_vector_store_imports():
    found = kinds(scan_text("a.py", "import chromadb\nfrom qdrant_client import QdrantClient\n"))
    assert found == {("vector-store", "chroma"), ("vector-store", "qdrant")}
    js = kinds(scan_text("a.ts", 'import { Pinecone } from "@pinecone-database/pinecone";'))
    assert js == {("vector-store", "pinecone")}
