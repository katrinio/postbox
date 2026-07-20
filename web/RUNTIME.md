# Frontend Production Runtime Contract

## What Gets Built

```bash
npm run build  →  vinext build  →  dist/
```

Output: Fully self-contained frontend artifact ready for production.

```
dist/
├── server/           Build-time compilation of React Server Components
│   ├── index.js      (15 KB, bundled HTTP server handler)
│   ├── wrangler.json (Cloudflare Workers configuration)
│   └── assets/       (shared assets)
└── client/           Browser-side assets
    ├── assets/       (JavaScript, CSS, fonts, pre-gzip)
    └── .vite/        (asset manifest)
```

**Key fact:** `dist/server/index.js` is a Cloudflare Worker module — completely standalone, no source dependencies.

## What Gets Copied to Production

```dockerfile
COPY web/package.json ./web/
COPY web/package-lock.json ./web/
COPY web/dist ./web/
COPY web/node_modules ./web/
```

**Required for runtime (`npm start`):**

| File/Dir | Size | Purpose | Required? |
|----------|------|---------|-----------|
| `package.json` | 2 KB | Dependency manifest for npm | ✅ Yes |
| `package-lock.json` | 500 KB | Lock file for reproducible installs | ✅ Yes (recommended) |
| `node_modules/` | 752 MB | Contains vinext CLI + dependencies | ✅ Yes |
| `dist/server/` | 1.3 MB | Compiled server (request handler) | ✅ Yes |
| `dist/client/` | 564 KB | Browser assets (CSS, JS, fonts) | ✅ Yes |
| `dist/.openai/` | ~5 KB | Cloudflare config | ✅ Yes |

**NOT copied (not needed in production):**

| File/Dir | Why |
|----------|-----|
| `app/` | Source code, not needed after build |
| `build/` | Vite plugins, build-time only |
| `vite.config.ts` | Build configuration, not runtime |
| `next.config.ts` | Next.js configuration, not runtime |
| `tsconfig.json` | TypeScript config, not runtime |
| `tests/` | Testing files, not runtime |
| `.wrangler/` | Wrangler cache, regenerated at runtime |
| `.vinext/` | Vite cache, regenerated at runtime |

## How Production Runs

```bash
npm start
  ↓
vinext start  (reads: dist/, node_modules/vinext)
  ↓
HTTP server on port 3000
  ↓
Serves: static assets + RSC requests
```

## Architecture: Vinext + RSC

- **Vinext**: Next.js fork designed for Cloudflare Workers
- **dist/server/index.js**: Cloudflare Worker module (exports `fetch()`)
- **Vinext CLI (`npm start`)**: Adapts Worker module to Node.js HTTP server
- **Why node_modules needed**: Vinext is a CLI tool, not a library; the server code can't run without the CLI wrapper

**Implication:** 752 MB of node_modules is the cost of this architecture. Alternative approaches exist but are out of scope.

## Reproducibility

**Build is deterministic:**
- `package-lock.json` pins exact dependency versions
- `npm ci` (vs `npm install`) uses lock file
- Vite + vinext produce consistent output

**To reproduce the exact build:**
```bash
npm ci                 # Install locked dependencies
npm run build          # Exact same dist/ every time
```

## Validation

Production checks confirm:
```
✓ package.json present
✓ vinext CLI available
✓ vinext installed in node_modules
✓ dist/server/ present
✓ dist/server/index.js bundled
✓ dist/client/ assets present
```

## Testing Production Artifact

To validate before deployment:

```bash
# Build
npm run build

# Test with standalone venv (no source)
mkdir -p /tmp/test && cd /tmp/test
cp -r /path/to/postbox/web/{package.json,package-lock.json,dist,node_modules} .

# Run
npm start

# Verify: HTTP server running on 3000
curl http://localhost:3000/
```

If this works in isolation (without source files), the artifact is valid for production.

## See Also

- `vite.config.ts` — Vite build configuration
- `package.json` — Dependency and script definitions
- `app/` — React components (source, not runtime)
- `Dockerfile` — How frontend is built and packaged in production
