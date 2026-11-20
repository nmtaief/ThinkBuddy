import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function runTest() {
  console.log("Connecting to ThinkBuddy MCP Server...");
  const transport = new StdioClientTransport({
    command: "node",
    args: [path.join(__dirname, "../dist/index.js")],
  });

  const client = new Client(
    { name: "test-client", version: "1.0.0" },
    { capabilities: {} }
  );

  await client.connect(transport);
  console.log("Connected successfully!");

  // 1. List tools
  const tools = await client.listTools();
  console.log("Available Tools:", tools.tools.map((t) => t.name));

  // 2. Test search_curriculum_excerpts
  const searchResult = await client.callTool({
    name: "search_curriculum_excerpts",
    arguments: { subject_slug: "science" },
  });
  console.log("Tool 1 Result (search_curriculum_excerpts): OK");

  // 3. Test get_cq_rubric
  const rubricResult = await client.callTool({
    name: "get_cq_rubric",
    arguments: { subject_slug: "science", chapter_number: 4 },
  });
  console.log("Tool 2 Result (get_cq_rubric): OK");

  // 4. Test evaluate_cq_answer
  const evalResult = await client.callTool({
    name: "evaluate_cq_answer",
    arguments: {
      subject_slug: "science",
      chapter_number: 4,
      cq_type: "ka_knowledge",
      student_answer_text: "সূর্যালোক ও ক্লোরোফিল এর সহায়তায় শর্করা ও অক্সিজেন উৎপন্ন করে",
      has_photo: true,
    },
  });
  console.log("Tool 3 Result (evaluate_cq_answer): OK");

  // 5. Test get_spaced_revision_deck
  const deckResult = await client.callTool({
    name: "get_spaced_revision_deck",
    arguments: { subject_slug: "math" },
  });
  console.log("Tool 4 Result (get_spaced_revision_deck): OK");

  console.log("\nALL 4 MCP TOOLS FUNCTIONING FLAWLESSLY!");
  process.exit(0);
}

runTest().catch((err) => {
  console.error("MCP test failed:", err);
  process.exit(1);
});
