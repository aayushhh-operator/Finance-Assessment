# Zorvyn Frontend

Static SPA for the finance backend in `backend/app`.

## Configure

Edit `window.__FINANCE_APP_CONFIG__` in `index.html`:

- `apiBaseUrl`: backend origin, for example `http://127.0.0.1:8000`
- `apiV1Prefix`: API prefix, default `/api`

## Run

Because this app uses ES modules, serve the folder with any static server.

PowerShell example:

```powershell
Set-Location D:\Zorvyn\frontend
python -m http.server 4173
```

Then open [http://127.0.0.1:4173](http://127.0.0.1:4173).

If the frontend is served from a different origin than the backend, the backend or a proxy must allow CORS for `/api`.
