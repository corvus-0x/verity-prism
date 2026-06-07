import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import Sources from "../pages/workspace/Sources";
import { ToastProvider } from "../hooks/useToast";

const renderSources = () =>
  render(
    <ToastProvider>
      <MemoryRouter initialEntries={["/workspaces/ws-1/sources"]}>
        <Routes>
          <Route path="/workspaces/:workspaceId/sources" element={<Sources />} />
        </Routes>
      </MemoryRouter>
    </ToastProvider>
  );

beforeEach(() => {
  server.use(
    http.get("/workspaces/ws-1/connectors", () =>
      HttpResponse.json([
        {
          id: "irs-teos",
          name: "IRS TEOS — 990 Filings",
          description: "Fetch 990s by name",
          verticals: ["general"],
        },
      ])
    ),
    http.get("/workspaces/ws-1/connector-runs", () => HttpResponse.json([]))
  );
});

test("operator searches by name and sees candidates with EIN", async () => {
  server.use(
    http.post("/workspaces/ws-1/connectors/irs-teos/search", () =>
      HttpResponse.json([
        {
          ref: "123456789",
          display_name: "Bright Future Ministries Inc",
          identifier: "12-3456789",
          location: "Marysville, OH",
        },
      ])
    )
  );

  renderSources();
  await screen.findByText("IRS TEOS — 990 Filings");

  fireEvent.change(
    screen.getByPlaceholderText(/search by organization name/i),
    { target: { value: "Bright Future" } }
  );
  fireEvent.click(screen.getByRole("button", { name: /search/i }));

  await waitFor(() => {
    expect(screen.getByText("Bright Future Ministries Inc")).toBeInTheDocument();
    expect(screen.getByText(/12-3456789/)).toBeInTheDocument();
  });
});

test("selecting a candidate lists filings with checkboxes", async () => {
  server.use(
    http.post("/workspaces/ws-1/connectors/irs-teos/search", () =>
      HttpResponse.json([
        {
          ref: "123456789",
          display_name: "Bright Future Ministries Inc",
          identifier: "12-3456789",
          location: "Marysville, OH",
        },
      ])
    ),
    http.post("/workspaces/ws-1/connectors/irs-teos/list", () =>
      HttpResponse.json([
        {
          item_ref: "123456789:2023:o",
          label: "Form 990",
          year: 2023,
          item_type: "990",
          filed_date: "2024-05-12",
        },
      ])
    )
  );

  renderSources();
  await screen.findByText("IRS TEOS — 990 Filings");
  fireEvent.change(
    screen.getByPlaceholderText(/search by organization name/i),
    { target: { value: "Bright Future" } }
  );
  fireEvent.click(screen.getByRole("button", { name: /search/i }));
  fireEvent.click(await screen.findByText("Bright Future Ministries Inc"));

  await waitFor(() =>
    expect(screen.getByText(/Form 990/)).toBeInTheDocument()
  );
  expect(screen.getByText(/2023/)).toBeInTheDocument();
});
