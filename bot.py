import httpx
import re
import fnmatch
from urllib.parse import urljoin, urlparse
from pathlib import Path
from bs4 import BeautifulSoup

TIMEOUT = 15
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/*,*/*;q=0.8",
}

IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml", "image/bmp", "image/avif"}
EXT_MAP = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
    "image/webp": ".webp", "image/svg+xml": ".svg", "image/bmp": ".bmp",
    "image/avif": ".avif",
}

BG_IMAGE_RE = re.compile(r"""background(?:-image)?\s*:\s*[^;]*url\(\s*['"]?([^'")]+)['"]?\s*\)""", re.IGNORECASE)
SRC_PATTERN = "*images.adsttc.com/media/images*large_jpg*"


def matches(url: str, pattern: str | tuple[str, ...]) -> bool:
    if isinstance(pattern, tuple):
        return any(matches(url, p) for p in pattern)
    return fnmatch.fnmatch(url, pattern) or fnmatch.fnmatch(urlparse(url).path, pattern)


def extract_bg_urls(text: str, base_url: str) -> list[str]:
    return [urljoin(base_url, m) for m in BG_IMAGE_RE.findall(text)]


def build_link_pattern(site_url: str) -> str:
    path = urlparse(site_url).path.rstrip("/")
    return f"*{path}/*"


def project_name_from_url(site_url: str) -> str:
    path = urlparse(site_url).path.rstrip("/")
    slug = path.split("/")[-1]
    return slug.replace("-", " ").title()


def find_target_links(client: httpx.Client, site_url: str, link_pattern: str | tuple[str, ...]) -> list[str]:
    resp = client.get(site_url, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    urls: list[str] = []
    seen = set()
    for tag in soup.find_all("a", href=True):
        full = urljoin(site_url, tag["href"])
        if full not in seen and matches(full, link_pattern):
            seen.add(full)
            urls.append(full)
    return urls


def find_image_on_page(client: httpx.Client, page_url: str, src_pattern: str) -> str | None:
    resp = client.get(page_url, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    candidates: list[str] = []
    for tag in soup.find_all("img", src=True):
        candidates.append(urljoin(page_url, tag["src"]))
    for tag in soup.find_all("source", srcset=True):
        for part in tag["srcset"].split(","):
            src = part.strip().split()[0]
            if src:
                candidates.append(urljoin(page_url, src))
    for tag in soup.find_all(attrs={"data-src": True}):
        candidates.append(urljoin(page_url, tag["data-src"]))
    for tag in soup.find_all("meta", attrs={"property": "og:image"}):
        if tag.get("content"):
            candidates.append(urljoin(page_url, tag["content"]))
    for tag in soup.find_all(style=True):
        candidates.extend(extract_bg_urls(tag["style"], page_url))
    for style_tag in soup.find_all("style"):
        if style_tag.string:
            candidates.extend(extract_bg_urls(style_tag.string, page_url))

    for url in candidates:
        if matches(url, src_pattern):
            return url
    return None


def download_image(client: httpx.Client, url: str, dest: Path) -> bool:
    try:
        resp = client.get(url, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError:
        return False

    ct = resp.headers.get("content-type", "").split(";")[0].strip().lower()
    if ct not in IMAGE_CONTENT_TYPES:
        return False

    ext = EXT_MAP.get(ct, ".jpg")
    final = dest.with_suffix(ext)
    final.write_bytes(resp.content)
    return True


def scrape_project(site_url: str, save_dir: Path, on_progress=None):
    """
    Main scraping function.
    on_progress(stage, current, total, message) is called for UI updates.
    Returns (saved_count, total_count, project_name).
    """
    link_pattern = build_link_pattern(site_url)
    project_name = project_name_from_url(site_url)
    project_dir = save_dir / project_name
    project_dir.mkdir(parents=True, exist_ok=True)

    def notify(stage, current, total, msg):
        if on_progress:
            on_progress(stage, current, total, msg)

    with httpx.Client(timeout=TIMEOUT, headers=HEADERS, http2=True) as client:
        notify("scan", 0, 0, f"Scanning {site_url} ...")
        targets = find_target_links(client, site_url, link_pattern)

        if not targets:
            notify("error", 0, 0, "No image pages found on this project.")
            return 0, 0, project_name

        total = len(targets)
        notify("found", 0, total, f"Found {total} image page(s)")

        saved = 0
        for i, target_url in enumerate(targets, start=1):
            notify("download", i, total, f"[{i}/{total}] Downloading ...")
            try:
                img_url = find_image_on_page(client, target_url, SRC_PATTERN)
            except httpx.HTTPError:
                notify("download", i, total, f"[{i}/{total}] Page load failed")
                continue

            if not img_url:
                notify("download", i, total, f"[{i}/{total}] No matching image")
                continue

            dest = project_dir / str(i)
            if download_image(client, img_url, dest):
                saved += 1
                notify("download", i, total, f"[{i}/{total}] Saved {i}.jpg")
            else:
                notify("download", i, total, f"[{i}/{total}] Download failed")

    return saved, total, project_name
