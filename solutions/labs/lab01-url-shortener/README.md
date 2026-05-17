# Lab 01 URL Shortener

Functional local solution for Module 1 Lab 01.

This version is optimized for easy local execution:
- Python standard library only
- SQLite for storage
- single-page browser UI
- JSON API for shortening
- redirect support for short codes

## Features

- `POST /api/shorten` accepts `{"url": "https://..."}` and returns a short code
- `GET /{short_code}` redirects to the original URL
- SQLite storage
- 6-character alphanumeric short codes
- duplicate URLs return the existing code
- browser UI with copy button, loading state, and error handling

## Run It Locally

Follow these steps:

### 1. Open a terminal

Use the terminal inside your editor or a normal system terminal.

### 2. Go to the project folder

```bash
cd solutions/labs/lab01-url-shortener
```

### 3. Start the app

```bash
python3 app.py
```

You should see:

```text
URL shortener running at http://127.0.0.1:8000
```

Leave that terminal window open while the app is running.

### 4. Open the app in your browser

Copy this URL into your browser:

```text
http://127.0.0.1:8000
```

### 5. Test it in the page

In the browser:

1. paste a long URL like `https://example.com/very/long/url`
2. click `Create Short URL`
3. copy the generated result
4. open the short URL to confirm it redirects

### 6. Stop the app when you are done

Go back to the terminal where `python3 app.py` is running and press `Ctrl+C`.

## Test

```bash
cd solutions/labs/lab01-url-shortener
python3 -m unittest test_app.py
```

## API Example

```bash
curl -X POST http://127.0.0.1:8000/api/shorten \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'
```

Example response:

```json
{
  "short_code": "a1b2c3",
  "short_url": "http://127.0.0.1:8000/a1b2c3"
}
```

## Notes

The official lab suggests FastAPI plus Next.js. This solution keeps the same product behavior but uses only built-in Python modules so it runs locally without installing extra packages.

## Demo Recording

A local demo recording of the project is included here:

- [demo/lab01-demo.mov](./demo/lab01-demo.mov)
