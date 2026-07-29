import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, streamChat } from "../api";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function sseResponse(text: string) {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(text));
        controller.close();
      },
    }),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("api", () => {
  it("fetches agents", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([{ id: "research" }])));
    await expect(api.agents()).resolves.toEqual([{ id: "research" }]);
  });

  it("raises ApiError carrying the status", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, 503)));
    await expect(api.agents()).rejects.toBeInstanceOf(ApiError);
    await expect(api.agents()).rejects.toMatchObject({ status: 503 });
  });

  it("url-encodes the memory query", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);
    await api.memories("pricing & margins");
    expect(fetchMock.mock.calls[0][0]).toContain("q=pricing%20%26%20margins");
  });

  it("posts the routing preview", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ candidates: [] }));
    vi.stubGlobal("fetch", fetchMock);
    await api.route("find leads");

    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ message: "find leads" });
  });
});

describe("streamChat", () => {
  it("yields typed events flattened from their frames", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        sseResponse(
          'event: routing\ndata: {"chosen":"copywriter","candidates":[]}\n\n' +
            'event: token\ndata: {"text":"Hello"}\n\n' +
            'event: done\ndata: {"run_id":"run_1","tokens":4,"cost_usd":0}\n\n',
        ),
      ),
    );

    const events = [];
    for await (const event of streamChat("write a headline")) events.push(event);

    expect(events.map((e) => e.type)).toEqual(["routing", "token", "done"]);
    expect(events[0]).toMatchObject({ chosen: "copywriter" });
    expect(events[1]).toMatchObject({ text: "Hello" });
    expect(events[2]).toMatchObject({ run_id: "run_1", tokens: 4 });
  });

  it("sends the pinned agent when one is given", async () => {
    const fetchMock = vi.fn().mockResolvedValue(sseResponse(""));
    vi.stubGlobal("fetch", fetchMock);

    for await (const _ of streamChat("hi", { agentId: "legal" })) void _;

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      message: "hi",
      agent_id: "legal",
      mode: null,
    });
  });

  it("throws ApiError when the request is rejected", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, 404)));
    const iterate = async () => {
      for await (const _ of streamChat("hi", { agentId: "ghost" })) void _;
    };
    await expect(iterate()).rejects.toBeInstanceOf(ApiError);
  });
});

describe("mode", () => {
  it("sends the mode so the kernel narrows, not the client", async () => {
    const fetchMock = vi.fn().mockResolvedValue(sseResponse(""));
    vi.stubGlobal("fetch", fetchMock);

    for await (const _ of streamChat("hi", { mode: "coding" })) void _;

    expect(JSON.parse(fetchMock.mock.calls[0][1].body).mode).toBe("coding");
  });

  it("previews routing inside the mode", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ candidates: [], mode: "coding" })));
    vi.stubGlobal("fetch", fetchMock);

    await api.route("refactor this", "coding");

    expect(fetchMock.mock.calls[0][0]).toContain("/v1/route?mode=coding");
  });

  it("omits the query string when no mode is given", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ candidates: [], mode: "personal" })));
    vi.stubGlobal("fetch", fetchMock);

    await api.route("anything");

    expect(fetchMock.mock.calls[0][0]).toMatch(/\/v1\/route$/);
  });
});
