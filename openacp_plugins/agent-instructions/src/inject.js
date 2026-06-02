export const PROJECT_INSTRUCTIONS_OPEN =
  '<project_instructions source="AGENTS.md">';
export const PROJECT_INSTRUCTIONS_CLOSE = "</project_instructions>";

export function buildInjectedPrompt({ instructionsText, promptText }) {
  const instructions = String(instructionsText ?? "").trim();
  const prompt = String(promptText ?? "");

  if (!instructions) {
    return prompt;
  }

  return `${PROJECT_INSTRUCTIONS_OPEN}
${instructions}
${PROJECT_INSTRUCTIONS_CLOSE}

User request:
${prompt}`;
}

export function shouldInjectSession(injectedSessions, sessionId) {
  if (!sessionId || injectedSessions.has(sessionId)) {
    return false;
  }

  injectedSessions.add(sessionId);
  return true;
}

export function createBeforePromptHandler({
  readInstructions,
  injectedSessions = new Set(),
  log,
}) {
  return async (payload, next) => {
    if (!shouldInjectSession(injectedSessions, payload.sessionId)) {
      return next(payload);
    }

    let instructionsText = "";
    try {
      instructionsText = await readInstructions();
    } catch (error) {
      log?.warn?.(
        { err: error },
        "Could not read AGENTS.md; forwarding prompt without project instructions",
      );
    }

    const text = buildInjectedPrompt({
      instructionsText,
      promptText: payload.text,
    });

    return next({
      ...payload,
      text,
    });
  };
}
