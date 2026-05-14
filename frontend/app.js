const API_BASE = "http://127.0.0.1:8000";

const messagesEl = document.getElementById("messages");
const eventLogEl = document.getElementById("event-log");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("message-input");
const stopBtn = document.getElementById("stop-btn");

let currentAssistantEl = null;
let currentAbortController = null;
let currentThreadId = "thread-1";

function appendMessage(role, text = "") {
    const el = document.createElement("div");
    el.className = `message ${role}`;
    el.textContent = text;
    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return el;
}

function appendEvent(text) {
    const el = document.createElement("div");
    el.className = "event-item";
    el.textContent = text;
    eventLogEl.appendChild(el);
    eventLogEl.scrollTop = eventLogEl.scrollHeight;
}

function appendAssistantDelta(delta) {
    if (!currentAssistantEl) {
        currentAssistantEl = appendMessage("assistant", "");
    }
    currentAssistantEl.textContent += delta;
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function sendMessage(message) {
    currentAbortController = new AbortController();
    currentAssistantEl = null;

    appendMessage("user", message);
    appendEvent("Starting request...");

    const response = await fetch(`${API_BASE}/chat/stream`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            message,
            thread_id: currentThreadId,
            max_turns: 30,
        }),
        signal: currentAbortController.signal,
    });

    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }

    if (!response.body) {
        throw new Error("Response body is empty.");
    }

    const stream = response.body.pipeThrough(new TextDecoderStream());
    const reader = stream.getReader();

    let buffer = "";

    while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += value;

        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";

        for (const part of parts) {
            handleSSEChunk(part);
        }
    }

    if (buffer.trim()) {
        handleSSEChunk(buffer);
    }
}

function handleSSEChunk(chunk) {
    const lines = chunk.split("\n");
    let eventName = "message";
    let dataText = "";

    for (const line of lines) {
        if (line.startsWith("event:")) {
            eventName = line.slice("event:".length).trim();
        } else if (line.startsWith("data:")) {
            dataText += line.slice("data:".length).trim();
        }
    }

    if (!dataText) return;

    let payload;
    try {
        payload = JSON.parse(dataText);
    } catch (err) {
        appendEvent(`Bad JSON payload:\n${dataText}`);
        return;
    }

    handleEvent(eventName, payload);
}

function handleEvent(eventName, payload) {
    switch (eventName) {
        case "commentary":
            appendEvent(`[commentary] ${payload.data ?? ""}`);
            break;

        case "reasoning_summary":
            appendEvent(`[reasoning] ${payload.data ?? ""}`);
            break;

        case "tool_start":
            appendEvent(
                `[tool start] ${payload.tool_name ?? "unknown"}\n` +
                `${payload.arguments_preview ?? ""}`
            );
            break;

        case "tool_result":
            appendEvent(
                `[tool result] ${payload.tool_name ?? "unknown"}\n` +
                `${payload.output_preview ?? payload.summary ?? ""}`
            );
            break;

        case "text_delta":
            appendAssistantDelta(payload.data ?? "");
            break;

        case "done":
            appendEvent("[done]");
            currentAbortController = null;
            break;

        case "error":
            appendEvent(`[error] ${payload.message ?? "Unknown error"}`);
            currentAbortController = null;
            break;

        default:
            appendEvent(`[${eventName}] ${JSON.stringify(payload)}`);
            break;
    }
}

formEl.addEventListener("submit", async (e) => {
    e.preventDefault();

    const message = inputEl.value.trim();
    if (!message) return;

    inputEl.value = "";

    try {
        await sendMessage(message);
    } catch (err) {
        if (err.name === "AbortError") {
            appendEvent("[aborted]");
        } else {
            appendEvent(`[request error] ${err.message}`);
        }
    }
});

stopBtn.addEventListener("click", () => {
    if (currentAbortController) {
        currentAbortController.abort();
        currentAbortController = null;
    }
});