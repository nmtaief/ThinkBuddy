import test from "node:test";
import assert from "node:assert/strict";

// Helper functions under test
function toBengaliDigits(num) {
  const bnDigits = ["০", "১", "২", "৩", "৪", "৫", "৬", "৭", "৮", "৯"];
  return String(num).replace(/\d/g, (d) => bnDigits[Number(d)]);
}

function hasPathTraversal(pathSegments) {
  for (const seg of pathSegments) {
    const decoded = decodeURIComponent(seg);
    if (
      decoded.includes("..") ||
      decoded.includes("/") ||
      decoded.includes("\\") ||
      decoded.includes("\0")
    ) {
      return true;
    }
  }
  return false;
}

const ALLOWED_ENDPOINT_PATTERNS = [
  /^client\/config$/,
  /^quizzes\/[^/]+\/attempts$/,
  /^attempts\/[^/]+\/items\/[^/]+\/answer$/,
  /^attempts\/[^/]+\/submit$/,
  /^attempts\/[^/]+\/review$/,
  /^students\/[^/]+\/plan$/,
  /^students\/[^/]+\/study-settings$/,
  /^students\/[^/]+\/suggestions$/,
  /^suggestions\/[^/]+\/approve$/,
  /^suggestions\/[^/]+\/decline$/,
  /^students\/[^/]+\/auto-adjustments$/,
  /^auto-adjustments\/[^/]+\/undo$/,
  /^students\/[^/]+\/change-requests$/,
  /^parents\/me\/students$/,
  /^parents\/me\/notifications\/preferences$/,
  /^uploads\/sign$/,
  /^tasks\/[^/]+$/,
];

function isPathAllowed(endpoint) {
  return ALLOWED_ENDPOINT_PATTERNS.some((pattern) => pattern.test(endpoint));
}

function validateOrigin(origin, host) {
  if (!origin || !host) return true;
  try {
    const originHost = new URL(origin).host;
    return originHost === host;
  } catch {
    return false;
  }
}

test("Bengali digits formatting converts ASCII numbers accurately", () => {
  assert.equal(toBengaliDigits(0), "০");
  assert.equal(toBengaliDigits(12345), "১২৩৪৫");
  assert.equal(toBengaliDigits(67890), "৬৭৮৯০");
  assert.equal(toBengaliDigits("page 42"), "page ৪২");
});

test("Path traversal sequences are strictly rejected", () => {
  assert.equal(hasPathTraversal(["students", "101"]), false);
  assert.equal(hasPathTraversal(["..", "internal"]), true);
  assert.equal(hasPathTraversal(["%2e%2e", "admin"]), true);
  assert.equal(hasPathTraversal(["foo/bar"]), true);
  assert.equal(hasPathTraversal(["foo\\bar"]), true);
  assert.equal(hasPathTraversal(["foo\0bar"]), true);
});

test("Proxy allow-list permits legitimate endpoints and rejects unauthorized ones", () => {
  assert.equal(isPathAllowed("client/config"), true);
  assert.equal(isPathAllowed("students/stu_1/plan"), true);
  assert.equal(isPathAllowed("quizzes/q1/attempts"), true);
  assert.equal(isPathAllowed("parents/me/notifications/preferences"), true);

  // Rejected endpoints
  assert.equal(isPathAllowed("admin/users"), false);
  assert.equal(isPathAllowed("v1/admin/drop_db"), false);
  assert.equal(isPathAllowed("internal/metrics"), false);
  assert.equal(isPathAllowed("arbitrary/upstream"), false);
});

test("Origin validation matches host and prevents cross-site request forgery", () => {
  assert.equal(validateOrigin("http://localhost:3000", "localhost:3000"), true);
  assert.equal(validateOrigin("https://app.thinkbuddy.com", "app.thinkbuddy.com"), true);
  assert.equal(validateOrigin("http://evil-attacker.com", "localhost:3000"), false);
  assert.equal(validateOrigin("malformed-url", "localhost:3000"), false);
});

test("Session timeouts enforce 30m idle and 7d absolute ceilings", () => {
  const IDLE_TIMEOUT_SECONDS = 30 * 60; // 1800s
  const ABSOLUTE_TIMEOUT_SECONDS = 7 * 24 * 60 * 60; // 604800s
  const now = 10000000;
  
  const isIdleExpired = (lastActivity) => (now - lastActivity) > IDLE_TIMEOUT_SECONDS * 1000;
  const isAbsoluteExpired = (absoluteExpiry) => now > absoluteExpiry;

  // Active session
  assert.equal(isIdleExpired(now - 10 * 60 * 1000), false);
  assert.equal(isAbsoluteExpired(now + 10000), false);

  // Expired by idle
  assert.equal(isIdleExpired(now - 31 * 60 * 1000), true);

  // Expired by absolute
  assert.equal(isAbsoluteExpired(now - 1000), true);
});
