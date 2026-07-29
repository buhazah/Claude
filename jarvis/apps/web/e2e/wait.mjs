/**
 * Block until both servers answer.
 *
 * CI starts them in the background, and a suite that races them fails in a way
 * that reads as a product bug rather than a timing one.
 */

import { waitForServer } from "./browser.mjs";

const API = process.env.API_URL ?? "http://localhost:8000";
const WEB = process.env.WEB_URL ?? "http://localhost:3000";

await waitForServer(`${API}/health`, { label: "api" });
await waitForServer(WEB, { label: "web" });
console.log("both servers are up");
