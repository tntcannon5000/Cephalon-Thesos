import { expect, test } from "@playwright/test";

const INTRO_KEY = "thesos.intro-seen";

test.beforeEach(async ({ page }) => {
  await page.addInitScript((introKey) => {
    localStorage.setItem(introKey, "true");
    localStorage.removeItem("veris.sample-mode");
  }, INTRO_KEY);
});

test("completed first reply supplies the transmission topic", async ({ page }) => {
  const createdAt = "2026-08-15T18:00:00.000Z";
  const events = [
    { event_id: 1, run_id: "run-1", type: "run.accepted", created_at: createdAt, payload: {} },
    {
      event_id: 2,
      run_id: "run-1",
      type: "status.changed",
      created_at: createdAt,
      payload: { message: "Opening the Archives" },
    },
    { event_id: 3, run_id: "run-1", type: "answer.started", created_at: createdAt, payload: {} },
    {
      event_id: 4,
      run_id: "run-1",
      type: "answer.snapshot",
      created_at: createdAt,
      payload: { text: "Void Relics contain Prime rewards." },
    },
    {
      event_id: 5,
      run_id: "run-1",
      type: "conversation.titled",
      created_at: createdAt,
      payload: { title: "Void Relic Rewards" },
    },
    {
      event_id: 6,
      run_id: "run-1",
      type: "run.completed",
      created_at: createdAt,
      payload: { status: "completed" },
    },
  ];

  await page.route("**/api/v1/runs", (route) =>
    route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: "run-1",
        event_url: "/api/v1/runs/run-1/events",
        cancel_url: "/api/v1/runs/run-1",
      }),
    }),
  );
  await page.route("**/api/v1/runs/run-1/events", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      headers: { "Cache-Control": "no-cache" },
      body: events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join(""),
    }),
  );

  await page.goto("/");
  await page.getByRole("textbox", { name: "Message Thesos" }).fill("How do Void Relics work?");
  await page.getByRole("textbox", { name: "Message Thesos" }).press("Enter");

  await expect(page.getByRole("heading", { name: "Void Relic Rewards" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Void Relic Rewards/ })).toBeVisible();
  await expect(page.getByText("Void Relics contain Prime rewards.")).toBeVisible();
  await expect(page.getByText("Opening transmission")).toHaveCount(0);
});

test("a persisted conversation can submit a follow-up turn", async ({ page }) => {
  const legacyAssistantId = "2bdd7a99-69a2-4794-a945-b783b265e67a-veris";
  await page.addInitScript(
    ({ assistantId }) => {
      localStorage.setItem(
        "veris.conversations.v1",
        JSON.stringify([
          {
            id: "conversation-1",
            title: "Tenno-Made Cephalons",
            pinned: false,
            updatedAt: "2026-08-15T18:00:00.000Z",
            terminated: false,
            messages: [
              {
                id: "user-1",
                role: "user",
                content: "Have the Tenno made Cephalons before?",
                createdAt: "2026-08-15T17:59:00.000Z",
                state: "complete",
              },
              {
                id: assistantId,
                role: "assistant",
                content: "They are associated with Orokin technology.",
                createdAt: "2026-08-15T18:00:00.000Z",
                state: "complete",
              },
            ],
          },
        ]),
      );
    },
    { assistantId: legacyAssistantId },
  );

  let submittedHistory: Array<{ id: string; role: string; content: string }> = [];
  await page.route("**/api/v1/runs", async (route) => {
    const request = (await route.request().postDataJSON()) as {
      history: Array<{ id: string; role: string; content: string }>;
    };
    submittedHistory = request.history;
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: "run-follow-up",
        event_url: "/api/v1/runs/run-follow-up/events",
        cancel_url: "/api/v1/runs/run-follow-up",
      }),
    });
  });
  const createdAt = "2026-08-15T18:01:00.000Z";
  const events = [
    {
      event_id: 1,
      run_id: "run-follow-up",
      type: "status.changed",
      created_at: createdAt,
      payload: { kind: "thinking", label: "Thinking" },
    },
    {
      event_id: 2,
      run_id: "run-follow-up",
      type: "answer.started",
      created_at: createdAt,
      payload: {},
    },
    {
      event_id: 3,
      run_id: "run-follow-up",
      type: "answer.snapshot",
      created_at: createdAt,
      payload: { text: "Follow-ups work." },
    },
    {
      event_id: 4,
      run_id: "run-follow-up",
      type: "run.completed",
      created_at: createdAt,
      payload: { status: "completed" },
    },
  ];
  await page.route("**/api/v1/runs/run-follow-up/events", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join(""),
    }),
  );

  await page.goto("/");
  const composer = page.getByRole("textbox", { name: "Message Thesos" });
  await composer.fill("What should I call recent chats?");
  await composer.press("Enter");

  await expect(page.getByText("Follow-ups work.")).toBeVisible();
  await expect.poll(() => submittedHistory.length).toBe(2);
  expect(submittedHistory[1]?.id).toBe(legacyAssistantId);
});

test("stopping before an answer cancels the run and leaves an editable stopped turn", async ({
  page,
}) => {
  const createdAt = "2026-08-16T10:00:00.000Z";
  let cancellationRequests = 0;
  await page.route("**/api/v1/runs", (route) =>
    route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: "run-stop-empty",
        event_url: "/api/v1/runs/run-stop-empty/events",
        cancel_url: "/api/v1/runs/run-stop-empty",
      }),
    }),
  );
  await page.route("**/api/v1/runs/run-stop-empty/events", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: `data: ${JSON.stringify({
        event_id: 1,
        run_id: "run-stop-empty",
        type: "status.changed",
        created_at: createdAt,
        payload: { kind: "thinking", label: "Thinking" },
      })}\n\n`,
    }),
  );
  await page.route("**/api/v1/runs/run-stop-empty", (route) => {
    cancellationRequests += 1;
    return route.fulfill({ status: 204, body: "" });
  });

  await page.goto("/");
  const composer = page.getByRole("textbox", { name: "Message Thesos" });
  await composer.fill("Explain damage attenuation");
  await composer.press("Enter");
  await expect(page.getByRole("status", { name: "Thinking" })).toBeVisible();
  await page.getByRole("button", { name: "Stop response" }).click();

  await expect(page.getByRole("status", { name: "Stopped" })).toBeVisible();
  await expect.poll(() => cancellationRequests).toBe(1);
  await expect(composer).toBeEnabled();
  await page.getByRole("button", { name: "Edit this message" }).click();
  await expect(page.getByText("Editing this turn will remove everything after it")).toBeVisible();
});

test("stopping during an answer finalizes the visible partial response", async ({ page }) => {
  const createdAt = "2026-08-16T10:00:00.000Z";
  let cancelled = false;
  await page.route("**/api/v1/runs", (route) =>
    route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: "run-stop-partial",
        event_url: "/api/v1/runs/run-stop-partial/events",
        cancel_url: "/api/v1/runs/run-stop-partial",
      }),
    }),
  );
  const events = [
    {
      event_id: 1,
      run_id: "run-stop-partial",
      type: "answer.started",
      created_at: createdAt,
      payload: {},
    },
    {
      event_id: 2,
      run_id: "run-stop-partial",
      type: "answer.snapshot",
      created_at: createdAt,
      payload: { text: "Damage attenuation changes incoming damage" },
    },
  ];
  await page.route("**/api/v1/runs/run-stop-partial/events", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join(""),
    }),
  );
  await page.route("**/api/v1/runs/run-stop-partial", (route) => {
    cancelled = true;
    return route.fulfill({ status: 204, body: "" });
  });

  await page.goto("/");
  const composer = page.getByRole("textbox", { name: "Message Thesos" });
  await composer.fill("Explain damage attenuation");
  await composer.press("Enter");
  const response = page.getByLabel("Damage attenuation changes incoming damage");
  await expect(response).toBeVisible();
  await page.getByRole("button", { name: "Stop response" }).click();

  await expect.poll(() => cancelled).toBe(true);
  await expect(response.locator(".streamed-word")).toHaveCount(5);
  await expect(response.locator("xpath=following-sibling::*[contains(@class, 'response-caret')]")).toHaveCount(0);
  await expect(page.getByRole("status", { name: "Stopped" })).toHaveCount(0);
  await expect(response.locator("xpath=ancestor::article")).toHaveClass(/complete/);
});

test("branching creates a truncated conversation with independent IDs", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem(
      "thesos.conversations.v1",
      JSON.stringify([
        {
          id: "source-chat",
          title: "Damage attenuation",
          titleState: "generated",
          pinned: false,
          updatedAt: "2026-08-16T10:02:00.000Z",
          terminated: false,
          messages: [
            {
              id: "source-user-1",
              role: "user",
              content: "First question",
              createdAt: "2026-08-16T10:00:00.000Z",
              state: "complete",
            },
            {
              id: "source-assistant-1",
              role: "assistant",
              content: "First answer.",
              createdAt: "2026-08-16T10:00:01.000Z",
              state: "complete",
            },
            {
              id: "source-user-2",
              role: "user",
              content: "Later question",
              createdAt: "2026-08-16T10:01:00.000Z",
              state: "complete",
            },
            {
              id: "source-assistant-2",
              role: "assistant",
              content: "Later answer.",
              createdAt: "2026-08-16T10:01:01.000Z",
              state: "complete",
            },
          ],
        },
      ]),
    );
  });

  await page.goto("/");
  const firstResponse = page.locator(".message.assistant").first();
  await firstResponse.hover();
  await firstResponse.getByRole("button", { name: "Branch from this response" }).click();

  await expect(page.getByText("Later question")).toHaveCount(0);
  const stored = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("thesos.conversations.v1") ?? "[]") as Array<{
      id: string;
      messages: Array<{ id: string }>;
    }>,
  );
  expect(stored).toHaveLength(2);
  const branch = stored.find((conversation) => conversation.id !== "source-chat");
  expect(branch?.messages).toHaveLength(2);
  expect(branch?.messages.map((message) => message.id)).not.toEqual([
    "source-user-1",
    "source-assistant-1",
  ]);
});

test("transmissions can be pinned, unpinned, and deleted from their context menu", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const timestamp = "2026-08-15T18:00:00.000Z";
    localStorage.setItem(
      "thesos.conversations.v1",
      JSON.stringify([
        {
          id: "gyre-chat",
          title: "Gyre for Steel Path",
          pinned: false,
          updatedAt: timestamp,
          terminated: false,
          messages: [],
        },
        {
          id: "incarnon-chat",
          title: "Incarnon rotation",
          pinned: false,
          updatedAt: "2026-08-14T12:10:00.000Z",
          terminated: false,
          messages: [],
        },
        {
          id: "market-chat",
          title: "Arcane Energize prices",
          pinned: false,
          updatedAt: "2026-08-12T21:04:00.000Z",
          terminated: false,
          messages: [],
        },
      ]),
    );
  });
  await page.goto("/");
  const openMenu = page.getByRole("button", { name: "Open menu" });
  if (await openMenu.isVisible()) await openMenu.click();

  const gyre = page.getByRole("button", { name: /Gyre for Steel Path/ });
  await gyre.click({ button: "right" });
  await expect(page.getByRole("menuitem", { name: "Share" })).toBeDisabled();
  await page.getByRole("menuitem", { name: "Pin" }).click();

  const pinnedList = page.locator(".pinned-list");
  await expect(pinnedList.getByRole("button", { name: /Gyre for Steel Path/ })).toBeVisible();
  await pinnedList.getByRole("button", { name: /Gyre for Steel Path/ }).click({ button: "right" });
  await page.getByRole("menuitem", { name: "Unpin" }).click();
  await expect(pinnedList.getByRole("button", { name: /Gyre for Steel Path/ })).toHaveCount(0);

  const arcane = page.getByRole("button", { name: /Arcane Energize prices/ });
  await arcane.click({ button: "right" });
  await page.getByRole("menuitem", { name: "Delete" }).click();
  await expect(page.getByRole("button", { name: /Arcane Energize prices/ })).toHaveCount(0);
});

test("theme selection changes the interface and survives reload", async ({ page }) => {
  await page.goto("/");
  const openMenu = page.getByRole("button", { name: "Open menu" });
  if (await openMenu.isVisible()) await openMenu.click();

  await page.getByRole("button", { name: "Theme", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Interface theme" }).locator(".theme-option")).toHaveCount(9);
  await page.getByRole("button", { name: /Vallis Survey/ }).click();

  await expect(page.locator("html")).toHaveAttribute("data-theme", "vallis-survey");
  await expect(page.locator("html")).toHaveAttribute("data-color-scheme", "light");
  await expect(page.getByText("Sample data", { exact: true })).toHaveCount(0);

  await page.reload();

  await expect(page.locator("html")).toHaveAttribute("data-theme", "vallis-survey");
});
