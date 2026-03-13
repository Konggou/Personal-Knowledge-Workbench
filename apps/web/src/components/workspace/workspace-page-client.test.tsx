import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WorkspacePageClient } from "./workspace-page-client";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push,
  }),
}));

vi.mock("@/lib/api", () => ({
  createProject: vi.fn(async () => ({
    id: "project-1",
  })),
}));

describe("WorkspacePageClient", () => {
  it("navigates to the new project chat page after create", async () => {
    render(<WorkspacePageClient includeArchived={false} initialProjects={[]} initialQuery="" />);

    fireEvent.change(screen.getByPlaceholderText("例如：Android 安装排障"), { target: { value: "新项目" } });
    fireEvent.change(screen.getByPlaceholderText("一句话说明这个项目会沉淀什么资料、处理什么问题。"), {
      target: { value: "用于回归测试" },
    });
    fireEvent.click(screen.getByRole("button", { name: "创建项目" }));

    expect(await screen.findByRole("button", { name: "创建项目" })).toBeInTheDocument();
    expect(push).toHaveBeenCalledWith("/projects/project-1");
  });
});
