import { execFileSync } from "node:child_process";
import { join } from "node:path";

import { expect, test, type Locator, type Page } from "@playwright/test";

const fixtureUrl = "http://127.0.0.1:3311/source-article";
const repoRoot = join(process.cwd(), "..", "..");
const apiPython = join(repoRoot, "apps", "api", ".venv", "Scripts", "python.exe");
const sendButtonName = "发送";
const sourceBubbleName = /来源/;
const composerPlaceholder = "继续在这个项目里提问……";

function uniqueSuffix() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

async function createProject(page: Page, namePrefix: string) {
  const suffix = uniqueSuffix();

  await page.goto("/workspace");
  await page.locator("main input").first().fill(`${namePrefix} ${suffix}`);
  await page.locator("main textarea").first().fill(`E2E fixture project ${suffix}`);
  await page.getByRole("button", { name: "创建项目" }).click();

  await expect(page).toHaveURL(/\/projects\/[^/?]+$/);
}

async function createSession(page: Page) {
  await page.getByRole("button", { name: "新建会话" }).last().click();
  await expect(page).toHaveURL(/sessionId=/);
}

function sourceCard(page: Page, title: string): Locator {
  return page.locator("article").filter({ hasText: title }).first();
}

async function addFixtureSourceInsideChat(page: Page) {
  await page.getByRole("button", { name: "增加资料" }).click();
  await page.getByRole("button", { name: "添加网页链接" }).click();
  await page.getByPlaceholder("https://example.com/article").fill(fixtureUrl);
  await page.getByRole("button", { name: "添加网页" }).click();
  await expect(page.locator("main")).toContainText(/已添加网页资料。|已保存到知识库，可继续追问新资料。|网页资料已在知识库中/);
}

function jsonResponse(payload: unknown) {
  return {
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(payload),
  };
}

function createStructuredDocx(outputPath: string) {
  const payload = Buffer.from(
    JSON.stringify({
      headings: ["研究内容", "优化建议"],
      paragraphs: [
        "该系统面向室内空气质量检测与智能控制。",
        "实施计划包括采集模块、控制模块、显示模块与告警模块。",
        "控制模块负责根据空气质量指标联动风扇转速。",
        "可以进一步优化多传感器融合并补充实验验证。",
      ],
      table_rows: [
        ["课题名称", "基于STM32的室内空气质量检测与智能控制系统设计"],
        ["项目名称", "室内空气质量检测与智能控制系统"],
      ],
    }),
    "utf8",
  ).toString("base64");

  const script = [
    "import base64, json, sys",
    "from docx import Document",
    "payload = json.loads(base64.b64decode(sys.argv[1]).decode('utf-8'))",
    "document = Document()",
    "for heading in payload['headings']:",
    "    document.add_heading(heading, level=1)",
    "for paragraph in payload['paragraphs']:",
    "    document.add_paragraph(paragraph)",
    "table = document.add_table(rows=len(payload['table_rows']), cols=2)",
    "for row_index, row in enumerate(payload['table_rows']):",
    "    table.cell(row_index, 0).text = row[0]",
    "    table.cell(row_index, 1).text = row[1]",
    "document.save(sys.argv[2])",
  ].join("\n");

  execFileSync(apiPython, ["-c", script, payload, outputPath], { stdio: "pipe" });
}

test.describe("chat-first project flow", () => {
  test("creates a project, starts a session, adds a source, and answers in the same chat", async ({ page }) => {
    await createProject(page, "E2E Chat");
    await createSession(page);
    await addFixtureSourceInsideChat(page);

    await page.getByPlaceholder(composerPlaceholder).fill("What does the source say about lighthouse orchard benchmark?");
    await page.getByRole("button", { name: sendButtonName }).click();

    await expect(page.locator("main")).toContainText("lighthouse orchard benchmark");
    await page.getByRole("button", { name: sourceBubbleName }).click();
    await expect(page.getByRole("button", { name: "Workbench Fixture Article" }).first()).toBeVisible();
  });

  test("creates a summary card and a report card inside the same session", async ({ page }) => {
    await createProject(page, "E2E Result Cards");
    await createSession(page);
    await addFixtureSourceInsideChat(page);

    await page.getByPlaceholder(composerPlaceholder).fill("Summarize the lighthouse orchard benchmark evidence.");
    await page.getByRole("button", { name: sendButtonName }).click();
    await expect(page.locator("main")).toContainText("lighthouse orchard benchmark");

    const summaryResponsePromise = page.waitForResponse((response) =>
      response.request().method() === "POST" && response.url().includes("/summary"),
    );
    await page.getByRole("button", { name: "保存为摘要" }).click();
    const summaryResponse = await summaryResponsePromise;
    expect(summaryResponse.ok()).toBeTruthy();
    await expect(page.getByRole("heading", { name: /摘要：/ })).toBeVisible();

    const reportResponsePromise = page.waitForResponse((response) =>
      response.request().method() === "POST" && response.url().includes("/report"),
    );
    await page.getByRole("button", { name: "生成报告" }).click();
    const reportResponse = await reportResponsePromise;
    expect(reportResponse.ok()).toBeTruthy();
    await expect(page.getByRole("heading", { name: /报告：/ })).toBeVisible();
  });

  test("opens knowledge page, previews a source, and enters chat through a new session", async ({ page }) => {
    await createProject(page, "E2E Knowledge");
    const currentUrl = page.url();
    const match = currentUrl.match(/\/projects\/([^/?]+)/);
    const projectId = match?.[1];
    expect(projectId).toBeTruthy();

    await page.goto(`/knowledge?projectId=${projectId}`);
    await page.getByRole("button", { name: "添加网页链接" }).click();
    await page.getByPlaceholder("https://example.com/article").fill(fixtureUrl);
    await page.getByRole("button", { name: "保存" }).click();
    await expect(page.locator("main")).toContainText("Workbench Fixture Article");

    await page.getByRole("button", { name: "Workbench Fixture Article" }).first().click();
    await expect(page.locator("aside")).toContainText("来源预览");
    await page.getByRole("button", { name: "进入聊天" }).click();

    await expect(page).toHaveURL(new RegExp(`/projects/${projectId}\\?sessionId=`));
    await expect(page.getByPlaceholder(composerPlaceholder)).toBeVisible();
  });

  test("archives, restores, and deletes a source from the knowledge page", async ({ page }) => {
    await createProject(page, "E2E Knowledge Lifecycle");
    const currentUrl = page.url();
    const match = currentUrl.match(/\/projects\/([^/?]+)/);
    const projectId = match?.[1];
    expect(projectId).toBeTruthy();

    await page.goto(`/knowledge?projectId=${projectId}`);
    await page.getByRole("button", { name: "添加网页链接" }).click();
    await page.getByPlaceholder("https://example.com/article").fill(fixtureUrl);
    await page.getByRole("button", { name: "保存" }).click();

    const card = sourceCard(page, "Workbench Fixture Article");
    await expect(card).toBeVisible();

    await card.getByRole("button", { name: "归档" }).click();
    await expect(card).toBeHidden();

    await page.getByLabel("显示已归档资料").check();
    await page.getByRole("button", { name: "应用筛选" }).click();
    await expect(page).toHaveURL(new RegExp(`/knowledge\\?projectId=${projectId}&includeArchived=true`));

    const archivedCard = sourceCard(page, "Workbench Fixture Article");
    await expect(archivedCard).toBeVisible();
    await archivedCard.getByRole("button", { name: "恢复" }).click();
    await expect(archivedCard.getByRole("button", { name: "归档" })).toBeVisible();

    await archivedCard.getByRole("button", { name: "删除" }).click();
    await expect(archivedCard).toBeHidden();
  });

  test("imports a docx source and keeps structured follow-up in the same session", async ({ page }, testInfo) => {
    test.slow();
    const docxPath = testInfo.outputPath("structured-e2e.docx");
    createStructuredDocx(docxPath);

    await createProject(page, "E2E Structured DOCX");
    await createSession(page);

    await page.locator('input[type="file"]').setInputFiles(docxPath);
    await expect(page.locator("main")).toContainText("structured-e2e.docx");
    await expect(page.locator("main")).toContainText("已添加文件资料。");
    await expect(page.getByPlaceholder(composerPlaceholder)).toBeVisible();
    await expect(page.getByRole("button", { name: "增加资料" })).toBeVisible();
    await expect(page).toHaveURL(/sessionId=/);

    await page.getByPlaceholder(composerPlaceholder).fill("我的课题名称是什么？");
    await page.getByRole("button", { name: sendButtonName }).click();
    await expect(page.locator("main")).toContainText("STM32", { timeout: 45000 });

    await page.getByPlaceholder(composerPlaceholder).fill("现在你知道我的题目是什么了吗？");
    await page.getByRole("button", { name: sendButtonName }).click();
    await expect(page.locator("main")).toContainText(/STM32|室内空气质量检测/, { timeout: 45000 });
    await expect(page).toHaveURL(/sessionId=/);
  });

  test("keeps deep research inside the same session flow", async ({ page }) => {
    await createProject(page, "E2E Deep Research");
    await createSession(page);
    await addFixtureSourceInsideChat(page);

    await page.getByRole("button", { name: "深度调研" }).click();
    await page.getByPlaceholder(composerPlaceholder).fill("请结合资料深度调研 lighthouse orchard benchmark。");
    await page.getByRole("button", { name: sendButtonName }).click();

    await expect(page.locator("main")).toContainText(/深度调研|调研结论/);
    await expect(page).toHaveURL(/sessionId=/);
  });

  test("uses web supplementation, saves the external page, and continues the same session", async ({ page }) => {
    test.slow();
    await createProject(page, "E2E Web Supplement");
    await createSession(page);

    const sessionUrl = new URL(page.url());
    const projectId = sessionUrl.pathname.split("/").pop();
    const sessionId = sessionUrl.searchParams.get("sessionId");
    expect(projectId).toBeTruthy();
    expect(sessionId).toBeTruthy();
    if (!projectId || !sessionId) {
      throw new Error("Failed to resolve project/session from URL.");
    }

    const now = new Date().toISOString();
    let savedToKnowledge = false;
    let currentMessages: Array<Record<string, unknown>> = [];

    const buildUserMessage = (id: string, seqNo: number, content: string) => ({
      id,
      session_id: sessionId,
      project_id: projectId,
      seq_no: seqNo,
      role: "user",
      message_type: "user_prompt",
      title: null,
      content_md: content,
      source_mode: null,
      evidence_status: null,
      disclosure_note: null,
      status_label: null,
      supports_summary: false,
      supports_report: false,
      related_message_id: null,
      created_at: now,
      updated_at: now,
      deleted_at: null,
      sources: [],
    });

    const buildAssistantMessage = (
      id: string,
      seqNo: number,
      content: string,
      sources: Array<Record<string, unknown>>,
    ) => ({
      id,
      session_id: sessionId,
      project_id: projectId,
      seq_no: seqNo,
      role: "assistant",
      message_type: "assistant_answer",
      title: null,
      content_md: content,
      source_mode: "project_grounded",
      evidence_status: "grounded",
      disclosure_note: null,
      status_label: null,
      supports_summary: true,
      supports_report: true,
      related_message_id: null,
      created_at: now,
      updated_at: now,
      deleted_at: null,
      sources,
    });

    const externalSource = {
      id: "message-source-web-1",
      source_id: null,
      source_kind: "external_web",
      chunk_id: null,
      source_rank: 1,
      source_type: "web_page",
      source_title: "Workbench Fixture Article",
      canonical_uri: fixtureUrl,
      external_uri: fixtureUrl,
      location_label: "网页补充 #1",
      excerpt: "benchmark 结果显示 lighthouse orchard 在稳定性和误报率上表现更好。",
      relevance_score: 4.4,
    };

    const projectSource = {
      id: "message-source-project-1",
      source_id: "saved-web-source-1",
      source_kind: "project_source",
      chunk_id: null,
      source_rank: 1,
      source_type: "web_page",
      source_title: "Workbench Fixture Article",
      canonical_uri: fixtureUrl,
      external_uri: null,
      location_label: "网页 #1",
      excerpt: "benchmark 结果显示 lighthouse orchard 在稳定性和误报率上表现更好。",
      relevance_score: 4.6,
    };

    const buildSessionDetail = () => ({
      item: {
        id: sessionId,
        project_id: projectId,
        project_name: "E2E Web Supplement",
        title: "新会话",
        title_source: "pending",
        status: "active",
        latest_message_at: now,
        created_at: now,
        updated_at: now,
        deleted_at: null,
        message_count: currentMessages.length,
        messages: currentMessages,
      },
    });

    await page.route(new RegExp(`/api/v1/sessions/${sessionId}$`), async (route) => {
      await route.fulfill(jsonResponse(buildSessionDetail()));
    });

    await page.route(new RegExp(`/api/v1/projects/${projectId}/sources\\?include_archived=false$`), async (route) => {
      await route.fulfill(
        jsonResponse({
          items: savedToKnowledge
            ? [
                {
                  id: "saved-web-source-1",
                  project_id: projectId,
                  project_name: "E2E Web Supplement",
                  source_type: "web_page",
                  title: "Workbench Fixture Article",
                  canonical_uri: fixtureUrl,
                  original_filename: null,
                  mime_type: null,
                  ingestion_status: "ready",
                  quality_level: "normal",
                  refresh_strategy: "manual",
                  last_refreshed_at: null,
                  error_code: null,
                  error_message: null,
                  created_at: now,
                  updated_at: now,
                  archived_at: null,
                  deleted_at: null,
                  favicon_url: null,
                },
              ]
            : [],
        }),
      );
    });

    await page.route(new RegExp(`/api/v1/projects/${projectId}/sources/web$`), async (route) => {
      savedToKnowledge = true;
      await route.fulfill(
        jsonResponse({
          item: {
            id: "saved-web-source-1",
            project_id: projectId,
            project_name: "E2E Web Supplement",
            source_type: "web_page",
            title: "Workbench Fixture Article",
            canonical_uri: fixtureUrl,
            original_filename: null,
            mime_type: null,
            ingestion_status: "ready",
            quality_level: "normal",
            refresh_strategy: "manual",
            last_refreshed_at: null,
            error_code: null,
            error_message: null,
            created_at: now,
            updated_at: now,
            archived_at: null,
            deleted_at: null,
            favicon_url: null,
          },
        }),
      );
    });

    await page.route(new RegExp(`/api/v1/sessions/${sessionId}/messages/stream$`), async (route) => {
      const requestBody = JSON.parse(route.request().postData() ?? "{}") as { content?: string };
      const content = requestBody.content ?? "";
      if (content.includes("这个页面提到的 benchmark")) {
        currentMessages = [
          buildUserMessage("user-web-1", 1, `请联网补充并总结这个页面的 benchmark 结论：${fixtureUrl}`),
          buildAssistantMessage(
            "assistant-web-1",
            2,
            "这个 benchmark 页面提到 lighthouse orchard 在稳定性和误报率上表现更好。",
            [externalSource],
          ),
          buildUserMessage("user-web-2", 3, "这个页面提到的 benchmark 重点是什么？"),
          buildAssistantMessage(
            "assistant-web-2",
            4,
            "保存后继续追问时，可以直接基于项目资料回答：benchmark 的重点是稳定性更高、误报率更低。",
            [projectSource],
          ),
        ];
        await route.fulfill({
          status: 200,
          contentType: "text/event-stream",
          body: `event: done\ndata: ${JSON.stringify({ message: currentMessages[3] })}\n\n`,
        });
        return;
      }

      currentMessages = [
        buildUserMessage("user-web-1", 1, `请联网补充并总结这个页面的 benchmark 结论：${fixtureUrl}`),
        buildAssistantMessage(
          "assistant-web-1",
          2,
          "这个 benchmark 页面提到 lighthouse orchard 在稳定性和误报率上表现更好。",
          [externalSource],
        ),
      ];
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: `event: done\ndata: ${JSON.stringify({ message: currentMessages[1] })}\n\n`,
      });
    });

    await page.getByRole("button", { name: "联网补充" }).click();
    await page
      .getByPlaceholder(composerPlaceholder)
      .fill(`请联网补充并总结这个页面的 benchmark 结论：${fixtureUrl}`);
    await page.getByRole("button", { name: sendButtonName }).click();

    await expect(page.locator("main")).toContainText(/benchmark|误报率|稳定性|lighthouse orchard/i, { timeout: 45000 });
    await expect(page.getByRole("button", { name: /网页来源/ })).toBeVisible({ timeout: 45000 });
    await page.getByRole("button", { name: /网页来源/ }).click();
    await expect(page.locator("main")).toContainText("网页补充");
    await page.getByRole("button", { name: "保存到知识库" }).click();
    await expect(page.locator("main")).toContainText(/已保存到知识库，可继续追问新资料。|已添加网页资料。|网页资料已在知识库中/);

    await page.getByPlaceholder(composerPlaceholder).fill("这个页面提到的 benchmark 重点是什么？");
    await page.getByRole("button", { name: sendButtonName }).click();

    await expect(page.locator("main")).toContainText(/benchmark|误报率|稳定性/, { timeout: 45000 });
    await expect(page).toHaveURL(/sessionId=/);
  });
});
