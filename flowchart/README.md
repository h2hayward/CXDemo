# Shareable research flowchart

This diagram is built with [React Flow](https://reactflow.dev/) and exports as a PNG. The five connected nodes describe the tested workflow. The daily scheduling section is explicitly marked as a next step.

```bash
cd flowchart
npm ci
npm run dev
```

Use **Download PNG** to save the complete diagram, including the real sample and scheduling note. The browser does not call the research providers or need API keys.

To rebuild the committed image:

```bash
npm run export
```

The export script runs the built page in an isolated headless browser and uses its download button. It uses Chrome on macOS when available, accepts `CHROME_EXECUTABLE`, or uses Playwright Chromium (`npx playwright install chromium`). The output is `docs/SDR-research-workflow.png` in the repository root.

Edit the five steps and sample text in `src/main.jsx`; presentation is in `src/style.css`.
