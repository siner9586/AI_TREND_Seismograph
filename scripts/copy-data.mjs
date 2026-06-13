import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(scriptDir, "..");
const source = path.join(root, "data");
const target = path.join(root, "web", "public", "data");

fs.rmSync(target, { recursive: true, force: true });
fs.mkdirSync(target, { recursive: true });

function copyDir(from, to) {
  for (const entry of fs.readdirSync(from, { withFileTypes: true })) {
    const src = path.join(from, entry.name);
    const dst = path.join(to, entry.name);
    const relative = path.relative(source, src);
    if (relative === "raw" || relative.startsWith(`raw${path.sep}`) || relative === "push_events.json") {
      continue;
    }
    if (entry.isDirectory()) {
      fs.mkdirSync(dst, { recursive: true });
      copyDir(src, dst);
    } else if (entry.isFile() && /\.(json|md|xml)$/.test(entry.name)) {
      fs.copyFileSync(src, dst);
    }
  }
}

if (fs.existsSync(source)) copyDir(source, target);
console.log(`Copied data assets to ${target}`);
