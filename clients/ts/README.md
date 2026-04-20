# Drift TypeScript Client

Auto-generated from the OpenAPI spec at `/api/openapi.json`.

## Generate

```bash
npm install
npm run generate
```

## Usage

```typescript
import { DriftClient } from './src';

const client = new DriftClient({
  baseUrl: 'http://localhost:8000',
  token: 'your-access-token',
});

const me = await client.auth.me();
```

## Regenerate after API changes

```bash
npx openapi-typescript http://localhost:8000/api/openapi.json -o src/schema.d.ts
```
