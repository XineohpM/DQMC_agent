import assert from "node:assert/strict";
import test from "node:test";

import {
  buildInjectedPrompt,
  createBeforePromptHandler,
  shouldInjectSession,
} from "../src/inject.js";

test("buildInjectedPrompt prepends AGENTS.md instructions to the user prompt", () => {
  const result = buildInjectedPrompt({
    instructionsText: "# AGENTS.md\n\nFollow project rules.",
    promptText: "Check the latest run status.",
  });

  assert.equal(
    result,
    `<project_instructions source="AGENTS.md">
# AGENTS.md

Follow project rules.
</project_instructions>

User request:
Check the latest run status.`,
  );
});

test("buildInjectedPrompt leaves the prompt unchanged when instructions are blank", () => {
  const result = buildInjectedPrompt({
    instructionsText: "  \n\t",
    promptText: "No instructions available.",
  });

  assert.equal(result, "No instructions available.");
});

test("shouldInjectSession only injects once per session id", () => {
  const injectedSessions = new Set();

  assert.equal(shouldInjectSession(injectedSessions, "session-1"), true);
  assert.equal(shouldInjectSession(injectedSessions, "session-1"), false);
  assert.equal(shouldInjectSession(injectedSessions, "session-2"), true);
});

test("createBeforePromptHandler injects before passing payload to next", async () => {
  const handler = createBeforePromptHandler({
    readInstructions: async () => "# AGENTS.md\n\nFollow project rules.",
    injectedSessions: new Set(),
  });

  let forwardedPayload;
  const result = await handler(
    {
      sessionId: "session-1",
      text: "Start a new diagnostic task.",
      attachments: [],
      sourceAdapterId: "slack",
    },
    async (payload) => {
      forwardedPayload = payload;
      return payload;
    },
  );

  assert.equal(result, forwardedPayload);
  assert.match(forwardedPayload.text, /^<project_instructions source="AGENTS\.md">/);
  assert.match(forwardedPayload.text, /User request:\nStart a new diagnostic task\.$/);
});

test("createBeforePromptHandler leaves later prompts in the same session unchanged", async () => {
  const injectedSessions = new Set(["session-1"]);
  const handler = createBeforePromptHandler({
    readInstructions: async () => {
      throw new Error("readInstructions should not run for injected sessions");
    },
    injectedSessions,
  });

  const result = await handler(
    {
      sessionId: "session-1",
      text: "Follow-up prompt.",
    },
    async (payload) => payload,
  );

  assert.equal(result.text, "Follow-up prompt.");
});
