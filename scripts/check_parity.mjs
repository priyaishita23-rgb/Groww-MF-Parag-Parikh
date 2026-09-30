/**
 * Parity check: the hosted page carries a JavaScript port of the Python
 * assistant, so the two can drift. This runs the built page's own script under
 * a minimal DOM stub and compares its answers with the Python ones.
 *
 *   python scripts/check_parity.py      # writes scratch/python-answers.json
 *   node scripts/check_parity.mjs       # compares
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const html = readFileSync(join(root, "dist", "index.html"), "utf8");

const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
if (scripts.length !== 1) throw new Error(`expected 1 inline script, found ${scripts.length}`);

// Minimal DOM: enough for the view code at the bottom of the page to run once.
const node = () => ({
  className: "", textContent: "", type: "", href: "", target: "", rel: "", value: "",
  appendChild(){}, addEventListener(){}, scrollIntoView(){},
});
const sandbox = {
  document: {
    createElement: node,
    createTextNode: () => ({}),
    getElementById: node,
  },
  console,
};
const context = vm.createContext(sandbox);
vm.runInContext(scripts[0] + "\n;globalThis.__ask = ask;", context);

const expected = JSON.parse(readFileSync(join(root, "scratch", "python-answers.json"), "utf8"));
let failures = 0;
for (const row of expected) {
  const got = vm.runInContext("__ask(" + JSON.stringify(row.question) + ")", context) || {};
  const mismatch = [];
  if ((got.kind || null) !== row.kind) mismatch.push(`kind ${got.kind} != ${row.kind}`);
  if ((got.chunk_id || null) !== row.chunk_id) mismatch.push(`chunk ${got.chunk_id} != ${row.chunk_id}`);
  if ((got.source_url || null) !== row.source_url) mismatch.push("source_url differs");
  if (row.score != null && got.score != null && Math.abs(got.score - row.score) > 1e-3) {
    mismatch.push(`score ${got.score} != ${row.score}`);
  }
  if (mismatch.length) {
    failures++;
    console.log(`MISMATCH  ${row.question}\n          ${mismatch.join("; ")}`);
  }
}
console.log(`${expected.length - failures}/${expected.length} questions match the Python assistant`);
process.exit(failures ? 1 : 0);
