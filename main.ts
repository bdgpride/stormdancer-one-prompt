// main.ts — hands in the X post for this make.fun entry.
//
// The whole job: copy POST.json from the repository root into the output
// directory, byte for byte. The house reads the post itself from X; this
// program only delivers the file that names it.
//
//   MAKEFUN_BOT_DIR    repository root   (default /bot)
//   MAKEFUN_OUTPUT_DIR output directory  (default /output)
//
// Node 22, standard library only, no network. Silent on success; exits 1
// with a clear message when POST.json is not there.

import { copyFileSync, mkdirSync, statSync } from "node:fs";
import { join } from "node:path";

const botDir = process.env.MAKEFUN_BOT_DIR ?? "/bot";
const outputDir = process.env.MAKEFUN_OUTPUT_DIR ?? "/output";

const source = join(botDir, "POST.json");
const target = join(outputDir, "POST.json");

// POST.json must be there and be a plain file; say which is wrong, then stop.
let sourceSize: number;
try {
  const stat = statSync(source);
  if (!stat.isFile()) {
    console.error(`main.ts: ${source} exists but is not a file — nothing to hand in.`);
    process.exit(1);
  }
  sourceSize = stat.size;
} catch {
  console.error(`main.ts: POST.json not found at ${source} — nothing to hand in.`);
  process.exit(1);
}

// Create the output directory if it is missing; never remove or recreate it.
mkdirSync(outputDir, { recursive: true });

copyFileSync(source, target);

// The hand-in counts only if the copy landed whole.
if (statSync(target).size !== sourceSize) {
  console.error(`main.ts: copy to ${target} is incomplete — sizes differ.`);
  process.exit(1);
}
