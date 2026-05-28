import re
import time
from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from config import Settings


@dataclass
class ScrapeResult:
    name: str
    price: float
    currency: str


SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": Settings.USER_AGENT,
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})


def _clean_price(raw: str) -> Optional[float]:
    cleaned = re.sub(r"[^\d.,]", "", raw).replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_currency(soup: BeautifulSoup) -> str:
    text = soup.get_text()
    for sym in ["€", "£", "¥", "$"]:
        if sym in text:
            return sym
    return "$"


def scrape_url(url: str, retries: int = 2) -> Optional[ScrapeResult]:
    """
    Scrape a product page for name and price using multiple strategies.

    ----------
    CSS SELECTOR REFERENCE  (using what you see in browser DevTools)
    ----------
    .class-name      -> selects all elements with class="class-name"
    #id-name         -> selects the element with id="id-name"
    tag              -> selects all <tag> elements
    div > p          -> <p> that is a direct child of <div>
    [attr="value"]   -> elements with attr="value"

    Common e-commerce price selectors you might find via Inspect:
      .a-price-whole        -> Amazon whole-price span
      .price                 -> generic price class
      .product-price         -> common product page class
      [data-testid="price"]  -> React/SPA test-id attribute
      span.woocommerce-Price-amount -> WooCommerce
      .price--main           -> Shopify-style
    ----------
    """
    last_exception: Optional[Exception] = None

    for attempt in range(1 + retries):
        try:
            resp = SESSION.get(
                url,
                timeout=Settings.REQUEST_TIMEOUT,
                allow_redirects=True,
            )
            resp.raise_for_status()

            soup = BeautifulSoup(resp.content, "lxml")
            currency = _extract_currency(soup)

            # ----------------------------------------------------------------
            # STRATEGY 1: Try common price selectors seen on many stores
            # ----------------------------------------------------------------
            price = _try_selectors(soup, [
                ".a-price-whole",              # Amazon: the dollar-amount span
                ".a-offscreen",                # Amazon: screen-reader price
                ".price",                      # Generic: class="price"
                ".product-price",              # Generic: class="product-price"
                ".price--main",                # Shopify: main price
                ".price__current",             # Magento / some Shopify
                ".woocommerce-Price-amount",   # WooCommerce: <span class="woocommerce-Price-amount">
                "[data-testid='price']",       # React stores with test ids
                ".offer-price",                # Some deal pages
                ".sale-price",                 # Sale price class
                ".current-price",              # Common generic
                "#priceblock_ourprice",        # Amazon legacy id
                "#priceblock_dealprice",       # Amazon deal price id
                ".product__price",             # Standard BEM naming
                ".price-value",                # Another common pattern
                ".c-product__price",           # Common component pattern
                '[itemprop="price"]',          # Schema.org microdata
                # ------------------------------------------------------------
                # How the selector above works:
                #   [itemprop="price"]  -> any element whose itemprop attribute
                #   equals "price". Many e-commerce sites embed schema.org
                #   microdata for SEO.
                # ------------------------------------------------------------
            ])
            if price is not None:
                break

            # ----------------------------------------------------------------
            # STRATEGY 2: Regex fallback — find any "$XX.XX" in the page
            # ----------------------------------------------------------------
            price = _regex_price_fallback(soup)
            if price is not None:
                break

            # ----------------------------------------------------------------
            # STRATEGY 3: Scan every element with price-like text
            # ----------------------------------------------------------------
            price = _text_scan_fallback(soup)

            if price is not None:
                break

            if attempt < retries:
                time.sleep(2 ** attempt)

        except requests.RequestException as e:
            last_exception = e
            if attempt < retries:
                time.sleep(2 ** attempt)

    if price is None:
        return None

    # ----------------------------------------------------------------
    # Extract product name — try common selectors, then <title>
    # ----------------------------------------------------------------
    name = _extract_name(soup)

    return ScrapeResult(name=name, price=price, currency=currency)


def _try_selectors(soup: BeautifulSoup, selectors: list[str]) -> Optional[float]:
    for selector in selectors:
        try:
            el = soup.select_one(selector)
            if el is None:
                continue
            text = el.get_text(strip=True)
            if not text:
                continue
            parsed = _clean_price(text)
            if parsed is not None and parsed > 0:
                return parsed
        except Exception:
            continue
    return None


def _regex_price_fallback(soup: BeautifulSoup) -> Optional[float]:
    """
    Search the entire HTML text for the FIRST occurrence of a price pattern
    like $12.99, €49.90, £5.00 etc.
    """
    page_text = soup.get_text(separator=" ", strip=True)
    pattern = r"[£€\$¥]\s?\d+(?:[.,]\d{1,2})?"
    match = re.search(pattern, page_text)
    if match:
        return _clean_price(match.group())
    return None


def _text_scan_fallback(soup: BeautifulSoup) -> Optional[float]:
    """
    Walk every tag and look for short text that looks like a price.
    """
    for tag in soup.find_all(["span", "div", "p", "ins", "strong"]):
        if not isinstance(tag, Tag):
            continue
        text = tag.get_text(strip=True)
        if not text or len(text) > 30:
            continue
        if re.match(r"^[£€\$¥]?\s?\d+[.,]\d{2}$", text):
            parsed = _clean_price(text)
            if parsed is not None and parsed > 0:
                return parsed
    return None


def _extract_name(soup: BeautifulSoup) -> str:
    """
    Try product-name selectors, then fall back to <title> tag.
    """
    name_selectors = [
        "#productTitle",           # Amazon product title id
        ".product-title",          # Generic product title class
        ".product__title",         # BEM variant
        ".name",                   # Generic name class
        ".product-name",           # Common class
        "h1",                      # First <h1> on the page
        '[data-testid="title"]',   # React SPA test-id
    ]
    for selector in name_selectors:
        try:
            el = soup.select_one(selector)
            if el is not None:
                text = el.get_text(strip=True)
                if text and len(text) > 5:
                    return text[:200]
        except Exception:
            continue

    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        title = title_tag.string.strip()
        pipe_idx = title.find("|")
        dash_idx = title.find(" - ")
        cut = min(pipe_idx if pipe_idx > 0 else 999,
                  dash_idx if dash_idx > 0 else 999)
        return title[:cut].strip()[:200]

    return "Unknown Product"
