# Lab 05 Multi-Agent Frontend

Static frontend for the Lab 05 backend in `../lab05-multi-agent`.

## Features

- task input for the supervisor
- configurable iteration limit
- workflow summary panel
- agent activity trace
- final output plus structured worker outputs

## Local Run

```bash
cd solutions/labs/lab05-multi-agent-frontend
python3 -m http.server 4173
```

By default `config.js` points to:

```text
http://127.0.0.1:8000
```

If you deploy the backend, update `config.js` with the new API base URL.
