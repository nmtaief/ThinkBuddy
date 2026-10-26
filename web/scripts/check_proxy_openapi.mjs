import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Path to openapi.json
const openApiPath = path.resolve(__dirname, "../../docs-generated/openapi.json");
if (!fs.existsSync(openApiPath)) {
  console.error(`ERROR: OpenAPI spec not found at: ${openApiPath}`);
  process.exit(1);
}

const openapi = JSON.parse(fs.readFileSync(openApiPath, "utf-8"));
const openApiPaths = openapi.paths || {};

// Normalise OpenAPI paths by stripping /v1/ and converting {param} to [^/]+
const normalizedOpenApiRoutes = [];
for (const [routePath, methodsObj] of Object.entries(openApiPaths)) {
  if (!routePath.startsWith("/v1/")) continue;
  const subPath = routePath.replace(/^\/v1\//, "");
  // Regex that matches concrete instances
  const regexStr = "^" + subPath.replace(/{[^}]+}/g, "[^/]+") + "$";
  const regex = new RegExp(regexStr);
  const methods = Object.keys(methodsObj)
    .filter((m) => ["get", "post", "put", "patch", "delete"].includes(m.toLowerCase()))
    .map((m) => m.toUpperCase());

  normalizedOpenApiRoutes.push({
    originalPath: routePath,
    regex,
    methods,
  });
}

// Read proxy route.ts directly to extract rules or define the canonical rules to verify
const proxyRoutePath = path.resolve(__dirname, "../src/app/api/proxy/[...path]/route.ts");
const proxySource = fs.readFileSync(proxyRoutePath, "utf-8");

// Parse ALLOWED_ENDPOINT_RULES from route.ts
const rulesMatch = proxySource.match(/export const ALLOWED_ENDPOINT_RULES: EndpointRule\[\] = (\[[\s\S]*?\]);/);
if (!rulesMatch) {
  console.error("ERROR: Could not extract ALLOWED_ENDPOINT_RULES from route.ts");
  process.exit(1);
}

// Parse each line within rulesRaw
const rulesRaw = rulesMatch[1];
const ruleEntries = [];
const lines = rulesRaw.split("\n");
for (const line of lines) {
  const lineMatch = line.match(/name:\s*"([^"]+)",\s*pattern:\s*\/(.*)\/,\s*methods:\s*(\[.*?\])/);
  if (lineMatch) {
    const name = lineMatch[1];
    const patternSource = lineMatch[2];
    const methods = JSON.parse(lineMatch[3].replace(/'/g, '"'));
    ruleEntries.push({
      name,
      patternSource,
      pattern: new RegExp(patternSource),
      methods,
    });
  }
}

if (ruleEntries.length === 0) {
  console.error("ERROR: No rules parsed from ALLOWED_ENDPOINT_RULES");
  process.exit(1);
}

console.log(`Checking ${ruleEntries.length} proxy allow-list rules against OpenAPI spec...`);

let hasError = false;

for (const rule of ruleEntries) {
  // Check that the pattern is strictly anchored
  if (!rule.patternSource.startsWith("^") || !rule.patternSource.endsWith("$")) {
    console.error(`FAIL: Rule '${rule.name}' regex /${rule.patternSource}/ is not strictly anchored with ^ and $`);
    hasError = true;
    continue;
  }

  // Find matching OpenAPI path
  // Create a sample path that matches the rule's regex
  const samplePath = rule.patternSource
    .replace(/^\^/, "")
    .replace(/\$$/, "")
    .replace(/\\/g, "")
    .replace(/\[\^\/\]\+/g, "test-id-123");

  const matchingOpenApiRoute = normalizedOpenApiRoutes.find((o) => o.regex.test(samplePath));

  if (!matchingOpenApiRoute) {
    console.error(`FAIL: Rule '${rule.name}' (sample: '${samplePath}') does not match any endpoint in OpenAPI /v1/`);
    hasError = true;
    continue;
  }

  // Check methods
  for (const method of rule.methods) {
    if (!matchingOpenApiRoute.methods.includes(method)) {
      console.error(
        `FAIL: Rule '${rule.name}' allows method ${method}, but OpenAPI path '${matchingOpenApiRoute.originalPath}' only permits: ${matchingOpenApiRoute.methods.join(", ")}`
      );
      hasError = true;
    }
  }

  console.log(`✓ Rule '${rule.name}' verified against ${matchingOpenApiRoute.originalPath} [${rule.methods.join(", ")}]`);
}

if (hasError) {
  console.error("\nProxy allow-list CI verification FAILED.");
  process.exit(1);
}

console.log(`\nALL ${ruleEntries.length} proxy allow-list rules successfully verified against OpenAPI spec.`);
