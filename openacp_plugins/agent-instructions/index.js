import { readFile } from "node:fs/promises";
import path from "node:path";

import { createBeforePromptHandler } from "./src/inject.js";

const PLUGIN_NAME = "@dqmc-agent/openacp-agent-instructions";
const HOOK_AGENT_BEFORE_PROMPT = "agent:beforePrompt";

function resolveWorkspaceRoot(instanceRoot) {
  return path.dirname(path.resolve(instanceRoot));
}

export default {
  name: PLUGIN_NAME,
  version: "0.1.0",
  description:
    "Injects the workspace AGENTS.md into the first prompt of each OpenACP session.",
  permissions: ["middleware:register"],

  async setup(ctx) {
    const workspaceRoot = resolveWorkspaceRoot(ctx.instanceRoot);
    const agentsPath = path.join(workspaceRoot, "AGENTS.md");
    const injectedSessions = new Set();

    ctx.registerMiddleware(HOOK_AGENT_BEFORE_PROMPT, {
      priority: -1000,
      handler: createBeforePromptHandler({
        injectedSessions,
        log: ctx.log,
        readInstructions: () => readFile(agentsPath, "utf8"),
      }),
    });

    ctx.log?.info?.(
      { agentsPath },
      "AGENTS.md injection middleware registered",
    );
  },
};

export { resolveWorkspaceRoot };
