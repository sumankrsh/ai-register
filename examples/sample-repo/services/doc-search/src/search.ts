// Internal policy document search for staff (synthetic example).
import { BedrockRuntimeClient, InvokeModelCommand } from "@aws-sdk/client-bedrock-runtime";
import { Pinecone } from "@pinecone-database/pinecone";

const bedrock = new BedrockRuntimeClient({ region: "eu-west-1" });
const index = new Pinecone().index("policy-docs");

export async function search(question: string, vector: number[]): Promise<string> {
  const hits = await index.query({ vector, topK: 5, includeMetadata: true });
  const context = hits.matches.map((m) => String(m.metadata?.text)).join("\n");
  const command = new InvokeModelCommand({
    modelId: "anthropic.claude-3-5-haiku-20241022-v1:0",
    body: JSON.stringify({ messages: [{ role: "user", content: context + "\n\n" + question }], max_tokens: 300 }),
  });
  const response = await bedrock.send(command);
  return new TextDecoder().decode(response.body);
}
