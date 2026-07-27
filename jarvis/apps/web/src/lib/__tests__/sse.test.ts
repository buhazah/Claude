import { describe, expect, it } from "vitest";
import { SSEParser, readSSE } from "../sse";

describe("SSEParser", () => {
  it("parses a complete frame", () => {
    const frames = new SSEParser().push('event: token\ndata: {"text":"hi"}\n\n');
    expect(frames).toEqual([{ event: "token", data: { text: "hi" } }]);
  });

  it("parses several frames from one chunk", () => {
    const frames = new SSEParser().push(
      'event: a\ndata: {"n":1}\n\nevent: b\ndata: {"n":2}\n\n',
    );
    expect(frames.map((f) => f.event)).toEqual(["a", "b"]);
  });

  it("holds an incomplete frame until the rest arrives", () => {
    const parser = new SSEParser();
    expect(parser.push("event: token\ndata: {\"te")).toEqual([]);
    expect(parser.push('xt":"split"}\n\n')).toEqual([
      { event: "token", data: { text: "split" } },
    ]);
  });

  it("survives a chunk boundary mid-line", () => {
    const parser = new SSEParser();
    parser.push("even");
    parser.push("t: done\nda");
    expect(parser.push('ta: {"ok":true}\n\n')).toEqual([
      { event: "done", data: { ok: true } },
    ]);
  });

  it("ignores keep-alive comments", () => {
    const frames = new SSEParser().push(': keep-alive\n\nevent: t\ndata: {"a":1}\n\n');
    expect(frames).toEqual([{ event: "t", data: { a: 1 } }]);
  });

  it("skips blocks with no event name", () => {
    expect(new SSEParser().push('data: {"orphan":true}\n\n')).toEqual([]);
  });

  it("surfaces malformed payloads instead of throwing", () => {
    const frames = new SSEParser().push("event: token\ndata: {not json}\n\n");
    expect(frames[0]).toEqual({ event: "token", data: { raw: "{not json}" } });
  });

  it("handles an event with no data", () => {
    expect(new SSEParser().push("event: ready\n\n")).toEqual([
      { event: "ready", data: {} },
    ]);
  });

  it("flushes a frame that never got its blank line", () => {
    const parser = new SSEParser();
    expect(parser.push('event: done\ndata: {"end":1}')).toEqual([]);
    expect(parser.flush()).toEqual([{ event: "done", data: { end: 1 } }]);
  });

  it("flushes nothing when the buffer is empty", () => {
    expect(new SSEParser().flush()).toEqual([]);
  });
});

function bodyOf(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(stream);
}

describe("readSSE", () => {
  it("yields frames across arbitrary chunk boundaries", async () => {
    const response = bodyOf([
      'event: routing\ndata: {"chosen":"research"}\n\nevent: to',
      'ken\ndata: {"text":"a"}\n\nevent: done\ndata: {"tokens":2}\n\n',
    ]);

    const frames = [];
    for await (const frame of readSSE(response)) frames.push(frame);

    expect(frames.map((f) => f.event)).toEqual(["routing", "token", "done"]);
    expect(frames[0].data).toEqual({ chosen: "research" });
  });

  it("emits a trailing unterminated frame", async () => {
    const frames = [];
    for await (const frame of readSSE(bodyOf(['event: done\ndata: {"n":1}']))) {
      frames.push(frame);
    }
    expect(frames).toEqual([{ event: "done", data: { n: 1 } }]);
  });

  it("rejects a response with no body", async () => {
    const iterate = async () => {
      for await (const _ of readSSE(new Response(null))) void _;
    };
    await expect(iterate()).rejects.toThrow(/no body/);
  });
});
