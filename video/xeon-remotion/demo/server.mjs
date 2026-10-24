import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const host = "127.0.0.1";
const port = Number(process.env.XEON_DEMO_PORT || "4173");
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error("XEON_DEMO_PORT debe ser un puerto válido.");
}
const apiPort = process.env.XEON_DEMO_API_PORT || "8001";
if (!/^\d{1,5}$/.test(apiPort) || Number(apiPort) < 1 || Number(apiPort) > 65535) {
  throw new Error("XEON_DEMO_API_PORT debe ser un puerto válido.");
}
const api = `http://127.0.0.1:${apiPort}`;
const root = new URL("./", import.meta.url);
const files = new Map([
  ["/", ["index.html", "text/html; charset=utf-8"]],
  ["/app.js", ["app.js", "text/javascript; charset=utf-8"]],
  ["/style.css", ["style.css", "text/css; charset=utf-8"]],
  ["/xeon-logo.png", ["../public/images/xeon-logo-oficial.png", "image/png"]],
]);
const routes = new Map([
  ["GET /health", true],
  ["GET /v1/stock", true],
  ["POST /v1/chat", true],
  ["POST /v1/quotes", true],
]);

createServer(async (request, response) => {
  const url = new URL(request.url ?? "/", `http://${host}:${port}`);
  const route = `${request.method} ${url.pathname}`;
  try {
    if (url.pathname.startsWith("/api/")) {
      const targetPath = url.pathname.slice(4);
      if (!routes.has(`${request.method} ${targetPath}`)) {
        response.writeHead(404).end("Ruta no disponible");
        return;
      }
      if (targetPath !== "/health") {
        const health = await fetch(`${api}/health`, { signal: AbortSignal.timeout(5_000) });
        const profile = await health.json();
        if (profile.provider !== "mock") {
          response.writeHead(409, { "content-type": "application/json; charset=utf-8" });
          response.end(JSON.stringify({ error: "La demo solo permite LLM_PROVIDER=mock; no se enviaron datos al proveedor configurado." }));
          return;
        }
      }
      const chunks = [];
      let bytes = 0;
      for await (const chunk of request) {
        bytes += chunk.length;
        if (bytes > 12_000) {
          response.writeHead(413).end("Solicitud demasiado grande");
          return;
        }
        chunks.push(chunk);
      }
      const upstream = await fetch(`${api}${targetPath}${url.search}`, {
        method: request.method,
        headers: request.method === "POST" ? { "content-type": "application/json" } : {},
        body: request.method === "POST" ? Buffer.concat(chunks) : undefined,
        signal: AbortSignal.timeout(15_000),
      });
      response.writeHead(upstream.status, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" });
      response.end(await upstream.text());
      return;
    }
    if (request.method !== "GET" || !files.has(url.pathname)) {
      response.writeHead(404).end("No encontrado");
      return;
    }
    const [file, type] = files.get(url.pathname);
    response.writeHead(200, { "content-type": type, "cache-control": "no-store" });
    response.end(await readFile(new URL(file, root)));
  } catch {
    response.writeHead(502, { "content-type": "application/json; charset=utf-8" });
    response.end(JSON.stringify({ error: "No se pudo conectar con XEON local. Comprueba que la API mock esté iniciada." }));
  }
}).listen(port, host, () => {
  process.stdout.write(`Demo XEON: http://${host}:${port}\n`);
  process.stdout.write(`API esperada: ${api} (LLM_PROVIDER=mock)\n`);
});
