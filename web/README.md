# ReviewPulse website

Next.js 16 (App Router, Cache Components) + Tailwind CSS 4. Marketing pages are static; the
dashboard under `/app` runs in the browser and calls the FastAPI backend's `/v1` API, which
`next.config.ts` proxies so the session cookie stays same-origin.

```bash
npm install
BACKEND_URL=http://127.0.0.1:8000 npm run dev   # http://localhost:3000
npm run lint && npm run build                   # what CI runs
```

Brand copy and plan cards live in `src/lib/site.ts`; design tokens in `src/app/globals.css`.
