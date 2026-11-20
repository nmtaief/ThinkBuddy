# ThinkBuddy MCP (Model Context Protocol) Server

A production-grade Model Context Protocol (MCP) server providing external AI hosts (Claude Desktop, Cursor, Antigravity, and custom LLM agents) with direct access to ThinkBuddy's authentic NCTB curriculum dataset, Creative Question (CQ) rubrics, and automated grading engines.

## Overview
- **Transport**: Standard Input/Output (`stdio`)
- **Protocol**: Model Context Protocol (MCP) Specification
- **Engine**: TypeScript / Node.js ES2022 (`@modelcontextprotocol/sdk`)

## Features & Exposed Tools

| Tool Name | Description | Key Arguments | Output |
| :--- | :--- | :--- | :--- |
| `search_curriculum_excerpts` | Search verified NCTB textbook excerpts with printed page citations. | `subject_slug`, `query` | Book, Chapter, Printed Page, Core Concepts |
| `get_cq_rubric` | Fetch authentic 4-tier CQ homework rubrics (ক, খ, গ, ঘ) totaling 10 marks. | `subject_slug`, `chapter_number` | 4-tier tasks, model answers, printed page citations |
| `evaluate_cq_answer` | Grade student written answers against rubrics with dimensional scoring. | `subject_slug`, `chapter_number`, `cq_type`, `student_answer_text`, `has_photo` | Score, Percentage, Grade (A+), Dimension scores, Feedback |
| `get_spaced_revision_deck` | Retrieve Leitner spaced-revision schedules (1, 3, 7, 14, 30 days). | `subject_slug` | Leitner boxes and review topics |

## Installation & Build

```bash
cd mcp-server
npm install
npm run build
```

## Running the Server

```bash
npm start
```

## Configuration for Claude Desktop

Add this configuration to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "thinkbuddy-curriculum": {
      "command": "node",
      "args": ["E:\\ThinkBuddy Arc\\mcp-server\\dist\\index.js"]
    }
  }
}
```

## Running the Integration Test

```bash
node dist/test_mcp.js
```
