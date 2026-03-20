import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SettingsPageClient } from "./settings-page-client";

const mocks = vi.hoisted(() => ({
  updateModelSettings: vi.fn(),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    updateModelSettings: mocks.updateModelSettings,
  };
});

const initialSettings = {
  llm: {
    base_url: "https://api.example.com",
    model: "example-chat",
    timeout_seconds: 45,
    has_api_key: true,
    api_key_preview: "exa*****key",
  },
  embedding: {
    model_name: "embedding-model",
    dimension: 384,
    allow_downloads: false,
  },
  reranker: {
    backend: "rule" as const,
    model_name: "reranker-model",
    remote_url: "",
    remote_timeout_seconds: 20,
    top_n: 8,
    allow_downloads: false,
  },
};

describe("SettingsPageClient", () => {
  it("renders all model sections and masked key state", () => {
    render(<SettingsPageClient initialSettings={initialSettings} />);

    expect(screen.getByRole("heading", { name: "大模型" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "向量模型" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "重排模型" })).toBeInTheDocument();
    expect(screen.getByText(/已配置：exa\*\*\*\*\*key/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText("留空表示不修改")).toHaveValue("");
  });

  it("submits updated settings and shows success feedback", async () => {
    mocks.updateModelSettings.mockResolvedValueOnce({
      ...initialSettings,
      llm: {
        ...initialSettings.llm,
        model: "next-chat",
      },
    });

    render(<SettingsPageClient initialSettings={initialSettings} />);

    const modelInputs = screen.getAllByDisplayValue("example-chat");
    fireEvent.change(modelInputs[0], { target: { value: "next-chat" } });
    fireEvent.click(screen.getByRole("button", { name: "保存设置" }));

    await waitFor(() => expect(mocks.updateModelSettings).toHaveBeenCalled());
    expect(mocks.updateModelSettings).toHaveBeenCalledWith(
      expect.objectContaining({
        llm: expect.objectContaining({
          model: "next-chat",
          clear_api_key: false,
        }),
      }),
    );
    expect(await screen.findByText("模型设置已保存，新请求会使用最新配置。")).toBeInTheDocument();
  });
});
