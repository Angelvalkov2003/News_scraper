"""
Fetch raw HTML of article pages from a list of URLs.
Saves one file per article to disk without any modification.
Uses requests only; no HTML cleaning or transformation.
"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import requests

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def url_to_filename(url: str) -> str:
    """Return a safe, unique filename for a URL (hash + .html)."""
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
    return f"{h}.html"


def url_to_slug_filename(url: str) -> str:
    """Return a readable filename from URL path (e.g. .../makale/slug-123 -> slug-123.html)."""
    path = url.strip().rstrip("/").split("/")[-1] or "page"
    return f"{path}.html" if path.endswith(".html") else f"{path}.html"


def load_urls_from_recent_posts(path: Path, website: str | None = None) -> list[tuple[str, str]]:
    """
    Load (url, website_name) from recent_posts_turkish_news_websites.json.
    If website is set, only include URLs from that entry.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    out: list[tuple[str, str]] = []
    for entry in data:
        if not entry.get("ok") or "results" not in entry:
            continue
        name = entry.get("website", "unknown")
        if website is not None and name != website:
            continue
        for item in entry.get("results", []):
            u = item.get("url")
            if u and isinstance(u, str):
                out.append((u.strip(), name))
    return out


def fetch_raw_html(url: str, session: requests.Session, timeout: int = 30) -> str | None:
    """
    GET url and return raw HTML as string. No transformation.
    Returns None on failure.
    """
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
        r.encoding = r.encoding or "utf-8"
        return r.text
    except requests.RequestException as e:
        print(f"Грешка: {e}", file=sys.stderr)
        return None


def fetch_and_save(
    url: str,
    path: Path,
    session: requests.Session,
    timeout: int = 30,
) -> bool:
    """
    GET url and save raw response body to path. No transformation.
    Returns True on success, False on failure.
    """
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
        return True
    except requests.RequestException as e:
        print(f"  FAIL {url}: {e}", file=sys.stderr)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch raw HTML for article URLs. Give a URL to print HTML to console; otherwise use JSON input and save to files."
    )
    parser.add_argument(
        "urls",
        nargs="*",
        type=str,
        help="Article URL(s). If one URL: print HTML to console. If multiple: save each to a file in --output-dir.",
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=Path("recent_posts_turkish_news_websites.json"),
        help="Path to recent_posts JSON (default: recent_posts_turkish_news_websites.json)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=Path("raw_html"),
        help="Directory to save HTML files (default: raw_html)",
    )
    parser.add_argument(
        "--website",
        "-w",
        type=str,
        default=None,
        help="Only fetch URLs from this website name (e.g. BirGunWebsite)",
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=None,
        help="Max number of URLs to fetch (default: all)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds to wait between requests (default: 1.0)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30)",
    )
    args = parser.parse_args()

    session = requests.Session()
    session.headers["User-Agent"] = DEFAULT_UA

    # Режим: подадени URL-и
    if args.urls:
        urls = [u.strip() for u in args.urls if u and u.strip()]
        if not urls:
            print("Моля, подайте поне един валиден URL.", file=sys.stderr)
            sys.exit(1)
        out_dir = args.output_dir.resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        if len(urls) == 1:
            url = urls[0]
            html = fetch_raw_html(url, session, timeout=args.timeout)
            if html is None:
                sys.exit(1)
            out_path = out_dir / url_to_slug_filename(url)
            out_path.write_text(html, encoding="utf-8")
            print(f"Записано: {out_path}")
        else:
            ok = 0
            for i, url in enumerate(urls):
                fname = url_to_slug_filename(url)
                path = out_dir / fname
                if fetch_and_save(url, path, session, timeout=args.timeout):
                    ok += 1
                    print(f"  [{i+1}/{len(urls)}] {path}")
                if i < len(urls) - 1 and args.delay > 0:
                    time.sleep(args.delay)
            print(f"Done: {ok}/{len(urls)} saved to {out_dir}")
        return

    # Режим: четене от JSON и запис във файлове
    if not args.input.exists():
        print(f"Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    urls_with_site = load_urls_from_recent_posts(args.input, website=args.website)
    if args.limit is not None:
        urls_with_site = urls_with_site[: args.limit]

    if not urls_with_site:
        print("No URLs to fetch.", file=sys.stderr)
        sys.exit(0)

    args.output_dir = args.output_dir.resolve()
    ok = 0
    for i, (url, website) in enumerate(urls_with_site):
        fname = url_to_filename(url)
        subdir = args.output_dir / website
        path = subdir / fname
        if path.exists():
            print(f"  [{i+1}/{len(urls_with_site)}] skip (exists) {url}")
            ok += 1
            continue
        if fetch_and_save(url, path, session, timeout=args.timeout):
            ok += 1
        if i < len(urls_with_site) - 1 and args.delay > 0:
            time.sleep(args.delay)

    print(f"Done: {ok}/{len(urls_with_site)} saved under {args.output_dir}")


if __name__ == "__main__":
    main()
