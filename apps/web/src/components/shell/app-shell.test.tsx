import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./app-shell";

vi.mock("next/navigation", () => ({
  usePathname: () => "/workspace",
}));

describe("AppShell", () => {
  it("renders the top navigation labels", () => {
    render(
      <AppShell subtitle="subtitle" title="title">
        <div>content</div>
      </AppShell>,
    );

    expect(screen.getByText("工作台")).toBeInTheDocument();
    expect(screen.getByText("会话")).toBeInTheDocument();
    expect(screen.getByText("知识库")).toBeInTheDocument();
  });
});
