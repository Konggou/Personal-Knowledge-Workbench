import { execFileSync } from "node:child_process";
import { join } from "node:path";

import { expect, test, type Locator, type Page } from "@playwright/test";

const fixtureUrl = "http://127.0.0.1:3311/source-article";
const repoRoot = join(process.cwd(), "..", "..");
const apiPython = join(repoRoot, "apps", "api", ".venv", "Scripts", "python.exe");
const sendButtonName = /发送/;
const sourceBubbleName = /1 个来源|2 个来源|3 个来源/;

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
  await expect(page.locator("main")).toContainText("已添加网页资料");
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

    await page.getByPlaceholder("继续在这个项目里提问……").fill("What does the source say about lighthouse orchard benchmark?");
    await page.getByRole("button", { name: sendButtonName }).click();

    await expect(page.locator("main")).toContainText("lighthouse orchard benchmark");
    await page.getByRole("button", { name: sourceBubbleName }).click();
    await expect(page.getByRole("button", { name: "Workbench Fixture Article" }).first()).toBeVisible();
  });

  test("creates a summary card and a report card inside the same session", async ({ page }) => {
    await createProject(page, "E2E Result Cards");
    await createSession(page);
    await addFixtureSourceInsideChat(page);

    await page.getByPlaceholder("继续在这个项目里提问……").fill("Summarize the lighthouse orchard benchmark evidence.");
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
    await expect(page.getByPlaceholder("继续在这个项目里提问……")).toBeVisible();
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

  test("imports a docx source and keeps the same session context", async ({ page }, testInfo) => {
    const docxPath = testInfo.outputPath("structured-e2e.docx");
    createStructuredDocx(docxPath);

    await createProject(page, "E2E Structured DOCX");
    await createSession(page);

    await page.locator('input[type="file"]').setInputFiles(docxPath);
    await expect(page.locator("main")).toContainText("structured-e2e.docx");
    await expect(page.locator("main")).toContainText("已添加文件资料");
    await expect(page.getByPlaceholder("继续在这个项目里提问……")).toBeVisible();
    await expect(page.getByRole("button", { name: "增加资料" })).toBeVisible();
    await expect(page).toHaveURL(/sessionId=/);
  });

  test("keeps deep research inside the same session flow", async ({ page }) => {
    await createProject(page, "E2E Deep Research");
    await createSession(page);
    await addFixtureSourceInsideChat(page);

    await page.getByRole("button", { name: "深度调研" }).click();
    await page.getByPlaceholder("继续在这个项目里提问……").fill("请结合资料深度调研 lighthouse orchard benchmark。");
    await page.getByRole("button", { name: sendButtonName }).click();

    await expect(page.locator("main")).toContainText(/深度调研|调研结论/);
    await expect(page).toHaveURL(/sessionId=/);
  });
});
