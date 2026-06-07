# Nuxt Minimal Starter

Look at the [Nuxt documentation](https://nuxt.com/docs/getting-started/introduction) to learn more.

## Setup

Make sure to install dependencies:

```bash
# npm
npm install

# pnpm
pnpm install

# yarn
yarn install

# bun
bun install
```

## Development Server

Start the development server on `http://localhost:3000`:

```bash
# npm
npm run dev

# pnpm
pnpm dev

# yarn
yarn dev

# bun
bun run dev
```

## Backend Integration

This frontend reads live backend data when available.

- Default backend base URL: `http://localhost:9000`
- Configure with env vars:
  - `NUXT_PUBLIC_API_BASE` (backend base URL)
  - `NUXT_PUBLIC_COOKIES_FILE` (optional backend `cookies_file` query value)

Live-backed areas in current frontend:

- Login/logout (`/api/v1/auth/*`)
- Source sync and data snapshot (`/api/v1/sync/all`, `/api/v1/bb/*`, `/api/v1/tis/*`)
- Profile prefill from TIS info (`/api/v1/tis/info`) after CAS login

For the latest backend contract, see `docs/frontend-backend-api.md`.

## Production

Build the application for production:

```bash
# npm
npm run build

# pnpm
pnpm build

# yarn
yarn build

# bun
bun run build
```

Locally preview production build:

```bash
# npm
npm run preview

# pnpm
pnpm preview

# yarn
yarn preview

# bun
bun run preview
```

Check out the [deployment documentation](https://nuxt.com/docs/getting-started/deployment) for more information.
