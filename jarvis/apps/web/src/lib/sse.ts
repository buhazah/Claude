/**
 * Server-sent event parsing.
 *
 * `EventSource` cannot issue a POST, and chat is a POST, so the client reads
 * the response body as a stream and frames it here. Kept pure and separate
 * from transport so the framing rules — which are fiddly and easy to get
 * subtly wrong across chunk boundaries — can be tested directly.
 */

export type SSEFrame = { event: string; data: unknown };

/**
 * Incremental SSE parser.
 *
 * Network chunks split anywhere, including mid-frame and mid-line, so parsing
 * must hold a buffer across pushes rather than treating each chunk as whole.
 */
export class SSEParser {
  private buffer = "";

  push(chunk: string): SSEFrame[] {
    this.buffer += chunk;
    const frames: SSEFrame[] = [];

    // A frame ends at a blank line. Anything after the last one is incomplete
    // and stays buffered for the next push.
    let boundary = this.buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const block = this.buffer.slice(0, boundary);
      this.buffer = this.buffer.slice(boundary + 2);
      const frame = parseBlock(block);
      if (frame) frames.push(frame);
      boundary = this.buffer.indexOf("\n\n");
    }
    return frames;
  }

  /** Flush a trailing frame that arrived without its terminating blank line. */
  flush(): SSEFrame[] {
    const rest = this.buffer.trim();
    this.buffer = "";
    if (!rest) return [];
    const frame = parseBlock(rest);
    return frame ? [frame] : [];
  }
}

function parseBlock(block: string): SSEFrame | null {
  let event: string | null = null;
  const dataLines: string[] = [];

  for (const line of block.split("\n")) {
    if (line.startsWith(":")) continue; // comment / keep-alive
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (event === null) return null;

  const raw = dataLines.join("\n");
  try {
    return { event, data: raw ? JSON.parse(raw) : {} };
  } catch {
    // A malformed payload must not kill the stream; surface it as text.
    return { event, data: { raw } };
  }
}

/** Read a `fetch` response body as a sequence of SSE frames. */
export async function* readSSE(response: Response): AsyncGenerator<SSEFrame> {
  if (!response.body) throw new Error("response has no body to stream");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SSEParser();

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      for (const frame of parser.push(decoder.decode(value, { stream: true }))) {
        yield frame;
      }
    }
    for (const frame of parser.flush()) yield frame;
  } finally {
    reader.releaseLock();
  }
}
