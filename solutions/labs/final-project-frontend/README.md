# Final Project Frontend

Static frontend for the final project backend in `../final-project`.

## Features

- code input with file loading
- review mode and language selectors
- workflow summary and activity trace
- retrieved guidance panel
- structured review results
- bundled evaluation trigger for demo coverage

## Local Run

```bash
cd solutions/labs/final-project-frontend
python3 -m http.server 4173
```

By default `config.js` points to:

```text
http://127.0.0.1:8000
```

If you deploy the backend, update `config.js` with the new API base URL.
