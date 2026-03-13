import { createServer } from "node:http";

const host = "127.0.0.1";
const port = 3311;

const fixtureHtml = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Workbench Fixture Article</title>
  </head>
  <body>
    <main>
      <h1>Workbench Fixture Article</h1>
      <p>
        The lighthouse orchard benchmark proves the project prefers grounded answers over guesswork.
        It is the primary phrase used by the end-to-end test to verify retrieval.
      </p>
      <p>
        A second note says the copper-harbor dataset should stay attached to the same project snapshot.
        This gives the test another deterministic evidence line to inspect.
      </p>
      <p>
        A final note says roadmap comparison requires evidence first, then a structured conclusion.
      </p>
    </main>
  </body>
</html>`;

const server = createServer((request, response) => {
  if (request.url === "/health") {
    response.writeHead(200, { "Content-Type": "text/plain; charset=utf-8" });
    response.end("ok");
    return;
  }

  if (request.url === "/source-article") {
    response.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    response.end(fixtureHtml);
    return;
  }

  response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
  response.end("not found");
});

function shutdown() {
  server.close(() => {
    process.exit(0);
  });
}

server.listen(port, host, () => {
  process.stdout.write(`Fixture server listening at http://${host}:${port}\n`);
});

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
