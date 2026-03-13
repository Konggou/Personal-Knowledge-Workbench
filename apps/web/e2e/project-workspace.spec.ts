import { expect, test, type Locator, type Page } from "@playwright/test";

const fixtureUrl = "http://127.0.0.1:3311/source-article";

function uniqueSuffix() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

async function createProject(page: Page, namePrefix: string) {
  const suffix = uniqueSuffix();

  await page.goto("/workspace");
  await page.getByPlaceholder("例如：Android 安装排障").fill(`${namePrefix} ${suffix}`);
  await page.getByPlaceholder("一句话说明这个项目会沉淀什么资料、处理什么问题。").fill(`E2E fixture project ${suffix}`);
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

test.describe("chat-first project flow", () => {
  test("creates a project, starts a session, adds a source, and answers in the same chat", async ({ page }) => {
    await createProject(page, "E2E Chat");
    await createSession(page);
    await addFixtureSourceInsideChat(page);

    await page.getByPlaceholder("继续在这个项目里提问…").fill("What does the source say about lighthouse orchard benchmark?");
    await page.getByRole("button", { name: "发送" }).click();

    await expect(page.locator("main")).toContainText("lighthouse orchard benchmark");
    await page.getByRole("button", { name: /1 个来源|2 个来源|3 个来源/ }).click();
    await expect(page.getByRole("button", { name: "Workbench Fixture Article" })).toBeVisible();
  });

  test("creates a summary card and a report card inside the same session", async ({ page }) => {
    await createProject(page, "E2E Result Cards");
    await createSession(page);
    await addFixtureSourceInsideChat(page);

    await page.getByPlaceholder("继续在这个项目里提问…").fill("Summarize the lighthouse orchard benchmark evidence.");
    await page.getByRole("button", { name: "发送" }).click();
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
    await expect(page.getByPlaceholder("继续在这个项目里提问…")).toBeVisible();
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
});
