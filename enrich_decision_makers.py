#!/usr/bin/env python3

import argparse
import csv
import html
import re
import subprocess
import sys
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import quote_plus, unquote, urljoin, urlparse, urlunparse


URL_RE = re.compile(r"https?://[^\"\s,]+")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
NAME_WORD = r"[A-Z][A-Za-z\u00C0-\u024F'\u2019`.-]+"
NAME_RE = re.compile(
    rf"{NAME_WORD}(?:\s+[A-Z]\.)?(?:\s+{NAME_WORD}){{1,3}}"
)

TITLE_SCORES = OrderedDict(
    [
        ("Founder & Managing Partner", 100),
        ("Co-Founder & Managing Partner", 99),
        ("Founding Partner", 98),
        ("Founder", 97),
        ("Managing Partner", 96),
        ("Co-Founder", 95),
        ("Chief Executive Officer", 94),
        ("Chief Executive", 93),
        ("CEO", 93),
        ("President", 92),
        ("Chairman", 90),
        ("Managing Director", 88),
        ("Senior Managing Director", 87),
        ("Senior Partner", 86),
        ("Partner", 84),
        ("Principal", 83),
        ("Founder & President", 82),
        ("Senior Adviser", 80),
        ("Senior Advisor", 80),
        ("Executive Director", 78),
        ("Director", 70),
    ]
)
TITLE_PATTERN = re.compile(
    "|".join(re.escape(title) for title in sorted(TITLE_SCORES, key=len, reverse=True))
)
NEGATIVE_TITLE_WORDS = {
    "marketing",
    "compliance",
    "operations",
    "office",
    "assistant",
    "research",
    "analyst",
    "associate",
    "administration",
    "finance",
    "controller",
}
NON_OFFICIAL_DOMAINS = {
    "linkedin.com",
    "pitchbook.com",
    "zoominfo.com",
    "privateequityinternational.com",
    "en.wikipedia.org",
    "wikipedia.org",
    "github.com",
    "smartcrowdfunding.us",
    "crunchbase.com",
    "rocketreach.co",
    "signalhire.com",
    "apollo.io",
    "firstpartycapital.com",
}
TEAM_HINTS = (
    "team",
    "about",
    "leadership",
    "people",
    "partners",
    "meet",
    "staff",
    "company",
    "management",
    "contact",
)
BAD_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".xml",
)
BUSINESS_WORDS = {
    "capital",
    "partners",
    "partner",
    "advisors",
    "advisor",
    "group",
    "management",
    "securities",
    "investments",
    "investment",
    "markets",
    "holdings",
    "financial",
    "finance",
    "consulting",
    "consultants",
    "llc",
    "ltd",
    "inc",
    "corp",
    "company",
}
GENERIC_NAME_WORDS = {
    "contact",
    "search",
    "menu",
    "home",
    "about",
    "team",
    "our",
    "us",
}


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def strip_www(netloc: str) -> str:
    return netloc.lower().split(":", 1)[0].removeprefix("www.")


def is_non_official_domain(netloc: str) -> bool:
    host = strip_www(netloc)
    return any(host == item or host.endswith(f".{item}") for item in NON_OFFICIAL_DOMAINS)


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    path = parsed.path or "/"
    if path != "/":
        path = re.sub(r"/+", "/", path)
    clean = parsed._replace(params="", fragment="", path=path)
    value = urlunparse(clean)
    return value[:-1] if value.endswith("/") and path == "/" else value


def home_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme or 'https'}://{parsed.netloc}/"


def decode_cfemail(encoded: str) -> Optional[str]:
    try:
        key = int(encoded[:2], 16)
        chars = [chr(int(encoded[i : i + 2], 16) ^ key) for i in range(2, len(encoded), 2)]
        return "".join(chars)
    except Exception:
        return None


def looks_like_name(value: str) -> bool:
    if not value or len(value) > 80:
        return False
    if any(ch.isdigit() for ch in value):
        return False
    if value.isupper():
        return False
    words = value.split()
    if not 2 <= len(words) <= 4:
        return False
    if sum(1 for w in words if w[:1].isupper()) < 2:
        return False
    if any(word.lower().strip(".,&") in BUSINESS_WORDS for word in words):
        return False
    if any(word.lower().strip(".,&") in GENERIC_NAME_WORDS for word in words):
        return False
    return bool(NAME_RE.fullmatch(value))


def normalize_name(value: str) -> str:
    value = normalize_space(value)
    words = value.split()
    if len(words) % 2 == 0 and words[: len(words) // 2] == words[len(words) // 2 :]:
        value = " ".join(words[: len(words) // 2])
    return value


def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z]+", " ", value.lower()).strip()


def known_title(value: str) -> Optional[str]:
    normalized = normalize_title(value)
    for title in TITLE_SCORES:
        if normalize_title(title) == normalized:
            return title
    return None


def title_score(title: str) -> int:
    lower = title.lower()
    if any(word in lower for word in NEGATIVE_TITLE_WORDS):
        return -1
    matched = known_title(title)
    return TITLE_SCORES.get(matched, -1) if matched else -1


def clean_email(email: str) -> str:
    return email.strip(" .,;:()[]<>{}").lower()


def merge_unique(values: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    result: List[str] = []
    for value in values:
        if not value:
            continue
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def format_url_list(values: Sequence[str]) -> str:
    return "; ".join(values)


class PageParser(HTMLParser):
    BLOCK_TAGS = {
        "p",
        "div",
        "section",
        "article",
        "header",
        "footer",
        "aside",
        "main",
        "li",
        "ul",
        "ol",
        "br",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "tr",
        "table",
        "td",
        "th",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: List[Tuple[str, str]] = []
        self.text_parts: List[str] = []
        self._ignore_depth = 0
        self._current_link_href: Optional[str] = None
        self._current_link_text: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._ignore_depth += 1
            return
        if self._ignore_depth:
            return
        attr_map = dict(attrs)
        if tag == "a":
            self._current_link_href = attr_map.get("href")
            self._current_link_text = []
        if tag == "br" or tag in self.BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            if self._ignore_depth:
                self._ignore_depth -= 1
            return
        if self._ignore_depth:
            return
        if tag == "a":
            if self._current_link_href:
                text = normalize_space("".join(self._current_link_text))
                self.links.append((self._current_link_href, text))
            self._current_link_href = None
            self._current_link_text = []
        if tag in self.BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignore_depth:
            return
        if data:
            self.text_parts.append(data)
            if self._current_link_href is not None:
                self._current_link_text.append(data)

    def text(self) -> str:
        text = html.unescape("".join(self.text_parts))
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r" *\n+ *", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


@dataclass
class Contact:
    name: str
    title: str
    score: int
    source_urls: Set[str] = field(default_factory=set)
    linkedin_urls: Set[str] = field(default_factory=set)
    emails: Set[str] = field(default_factory=set)

    def render(self) -> str:
        email = sorted(self.emails)[0] if self.emails else ""
        linkedin = sorted(self.linkedin_urls)[0] if self.linkedin_urls else ""
        return " | ".join(part for part in [self.name, self.title, email, linkedin] if part)


class Researcher:
    def __init__(self, pause_seconds: float = 0.25) -> None:
        self.fetch_cache: Dict[str, Optional[str]] = {}
        self.search_cache: Dict[str, Optional[str]] = {}
        self.pause_seconds = pause_seconds

    def fetch(self, url: str) -> Optional[str]:
        url = canonicalize_url(url)
        if url in self.fetch_cache:
            return self.fetch_cache[url]
        cmd = [
            "curl",
            "-L",
            "--compressed",
            "--max-time",
            "20",
            "-A",
            "Mozilla/5.0",
            "-sS",
            url,
        ]
        try:
            raw_output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
            output = raw_output.decode("utf-8", errors="ignore")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            output = None
        self.fetch_cache[url] = output
        if self.pause_seconds:
            time.sleep(self.pause_seconds)
        return output

    def yahoo_search_linkedin(self, name: str, firm: str) -> Optional[str]:
        key = f"{name}||{firm}"
        if key in self.search_cache:
            return self.search_cache[key]
        result = None
        queries = [
            f'"{name}" "{firm}" site:linkedin.com/in',
            f'"{name}" "{firm}" LinkedIn',
        ]
        for query in queries:
            url = f"https://search.yahoo.com/search?p={quote_plus(query)}"
            html_body = self.fetch(url)
            if not html_body:
                continue
            matches = re.findall(r"https?://r\.search\.yahoo\.com/[^\"'\s<>]+", html_body)
            for raw_url in matches:
                decoded = extract_yahoo_redirect(raw_url)
                if decoded and is_linkedin_profile(decoded):
                    result = decoded
                    break
            if not result:
                direct = re.findall(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:in|pub)/[^\"'\s<>?]+", html_body, flags=re.I)
                if direct:
                    result = clean_linkedin_url(direct[0])
            if result:
                break
        self.search_cache[key] = result
        return result


def extract_yahoo_redirect(value: str) -> Optional[str]:
    match = re.search(r"/RU=([^/]+)/RK=", value)
    if not match:
        return None
    decoded = unquote(match.group(1))
    return clean_linkedin_url(decoded) if is_linkedin_profile(decoded) else None


def is_linkedin_profile(url: str) -> bool:
    parsed = urlparse(url)
    host = strip_www(parsed.netloc)
    if host not in {"linkedin.com", "uk.linkedin.com", "www.linkedin.com", "ca.linkedin.com", "nl.linkedin.com"} and not host.endswith(".linkedin.com"):
        return False
    return parsed.path.startswith("/in/") or parsed.path.startswith("/pub/")


def clean_linkedin_url(url: str) -> str:
    parsed = urlparse(url)
    cleaned = parsed._replace(query="", fragment="")
    return urlunparse(cleaned).rstrip("/")


def extract_urls_from_row(row: Dict[str, str]) -> List[str]:
    urls: List[str] = []
    for value in row.values():
        if not isinstance(value, str):
            continue
        for match in URL_RE.findall(value):
            urls.append(match.rstrip('].,}"'))
    return merge_unique(canonicalize_url(url) for url in urls)


def official_urls(urls: Sequence[str]) -> List[str]:
    preferred: List[str] = []
    fallback: List[str] = []
    for url in urls:
        parsed = urlparse(url)
        netloc = parsed.netloc
        if not netloc or is_non_official_domain(netloc):
            continue
        path = parsed.path.lower().strip("/")
        if not path or any(hint in path for hint in TEAM_HINTS):
            preferred.append(url)
        elif not any(token in path for token in ["news", "article", "insight", "press", "blog", "service"]):
            fallback.append(url)
    return merge_unique(preferred + fallback)


def linkedin_company_urls(urls: Sequence[str]) -> List[str]:
    results = []
    for url in urls:
        parsed = urlparse(url)
        host = strip_www(parsed.netloc)
        if host.endswith("linkedin.com") and parsed.path.startswith("/company/"):
            results.append(url)
    return merge_unique(results)


def candidate_seed_pages(official: Sequence[str]) -> List[str]:
    if not official:
        return []
    seeds = list(official)
    primary = official[0]
    base = home_url(primary)
    existing_paths = {urlparse(url).path.lower() for url in official}
    for suffix in ["about/", "team/", "our-team/", "leadership/", "contact/"]:
        path = f"/{suffix}"
        if path not in existing_paths:
            seeds.append(urljoin(base, suffix))
    return merge_unique(canonicalize_url(url) for url in seeds)


def email_matches_domain(email: str, domain: str) -> bool:
    host = email.split("@", 1)[-1].lower()
    return host == domain or host.endswith(f".{domain}")


def extract_page_artifacts(page_url: str, raw_html: str, domain: str) -> Tuple[str, List[Tuple[str, str]], Set[str], Set[str]]:
    parser = PageParser()
    parser.feed(raw_html)
    text = parser.text()
    links = []
    for href, link_text in parser.links:
        normalized = normalize_link(page_url, href)
        if normalized:
            links.append((normalized, link_text))

    emails = {
        clean_email(match)
        for match in EMAIL_RE.findall(raw_html)
        if email_matches_domain(clean_email(match), domain)
    }
    for encoded in re.findall(r'data-cfemail="([0-9a-fA-F]+)"', raw_html):
        decoded = decode_cfemail(encoded)
        if decoded and email_matches_domain(clean_email(decoded), domain):
            emails.add(clean_email(decoded))
    for href, _ in links:
        if href.startswith("mailto:"):
            email = clean_email(href.removeprefix("mailto:"))
            if email_matches_domain(email, domain):
                emails.add(email)

    linkedin_urls = set(
        clean_linkedin_url(url)
        for url in re.findall(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:in|pub)/[^\"'\s<>?#]+", raw_html, flags=re.I)
        if is_linkedin_profile(url)
    )
    return text, links, emails, linkedin_urls


def normalize_link(page_url: str, href: str) -> Optional[str]:
    href = (href or "").strip()
    if not href or href.startswith("javascript:") or href.startswith("tel:"):
        return None
    if href.startswith("mailto:"):
        return href
    absolute = urljoin(page_url, href)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return None
    if any(parsed.path.lower().endswith(ext) for ext in BAD_EXTENSIONS):
        return None
    return canonicalize_url(absolute)


def extract_contacts_from_text(text: str, source_url: str) -> List[Contact]:
    contacts: List[Contact] = []
    seen: Set[Tuple[str, str]] = set()
    lines = [normalize_space(line) for line in re.split(r"\n+", text) if normalize_space(line)]
    single_line_patterns = [
        re.compile(rf"^(?P<name>{NAME_RE.pattern})\s+(?P<title>{TITLE_PATTERN.pattern})$", flags=re.U),
        re.compile(rf"^(?P<title>{TITLE_PATTERN.pattern})\s+(?P<name>{NAME_RE.pattern})$", flags=re.U),
    ]

    for index, line in enumerate(lines):
        for pattern in single_line_patterns:
            match = pattern.match(line)
            if not match:
                continue
            name = normalize_name(match.group("name"))
            title = known_title(match.group("title")) or normalize_space(match.group("title"))
            if not looks_like_name(name):
                continue
            score = title_score(title)
            if score < 0:
                continue
            key = (name.lower(), title.lower())
            if key not in seen:
                seen.add(key)
                contact = Contact(name=name, title=title, score=score)
                contact.source_urls.add(source_url)
                contacts.append(contact)

        if index + 1 >= len(lines):
            continue
        next_line = lines[index + 1]
        matched_title = known_title(next_line)
        if looks_like_name(line) and matched_title:
            name = normalize_name(line)
            title = matched_title
        else:
            continue
        key = (name.lower(), title.lower())
        if key in seen:
            continue
        seen.add(key)
        contact = Contact(name=name, title=title, score=title_score(title))
        contact.source_urls.add(source_url)
        contacts.append(contact)
    return contacts


def choose_follow_links(page_url: str, links: Sequence[Tuple[str, str]], domain: str) -> List[str]:
    scored: List[Tuple[int, str]] = []
    current_path = urlparse(page_url).path.lower()
    on_team_page = any(hint in current_path for hint in TEAM_HINTS)
    for href, link_text in links:
        if href.startswith("mailto:"):
            continue
        parsed = urlparse(href)
        if strip_www(parsed.netloc) != domain:
            continue
        path = parsed.path.lower()
        if path in {"", "/"}:
            continue
        score = 0
        if any(hint in path for hint in TEAM_HINTS):
            score += 10
        if any(hint in link_text.lower() for hint in TEAM_HINTS):
            score += 8
        if on_team_page and re.search(r"/[a-z0-9-]+/[a-z0-9-]+/?$", path):
            score += 6
        slug = path.rstrip("/").split("/")[-1]
        if slug.count("-") in {1, 2} and not any(token in slug for token in ["page", "category", "tag", "service", "news", "article"]):
            score += 4
        if score > 0:
            scored.append((score, href))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return merge_unique(url for _, url in scored[:8])


def assign_emails(contacts: List[Contact], emails: Iterable[str]) -> Tuple[List[Contact], List[str]]:
    remaining = set(clean_email(email) for email in emails if email)
    if not remaining:
        return contacts, []
    for contact in contacts:
        normalized_name = contact.name.lower()
        parts = [part for part in re.split(r"\s+", normalized_name) if part and len(part) > 1]
        if len(parts) < 2:
            continue
        first = parts[0]
        last = parts[-1].strip(".'`")
        initial = first[0]
        matches = []
        for email in sorted(remaining):
            local = email.split("@", 1)[0]
            if last in local and (first in local or f"{initial}{last}" in local or f"{first}.{last}" in local):
                matches.append(email)
        for email in matches:
            contact.emails.add(email)
            remaining.discard(email)
    public = sorted(email for email in remaining if not any(token in email for token in ["noreply", "donotreply"]))
    return contacts, public


def dedupe_contacts(contacts: Iterable[Contact]) -> List[Contact]:
    merged: Dict[str, Contact] = {}
    for contact in contacts:
        key = contact.name.lower()
        existing = merged.get(key)
        if existing is None or contact.score > existing.score:
            chosen = Contact(name=contact.name, title=contact.title, score=contact.score)
            if existing:
                chosen.linkedin_urls |= existing.linkedin_urls
                chosen.emails |= existing.emails
                chosen.source_urls |= existing.source_urls
            chosen.linkedin_urls |= contact.linkedin_urls
            chosen.emails |= contact.emails
            chosen.source_urls |= contact.source_urls
            merged[key] = chosen
        else:
            existing.linkedin_urls |= contact.linkedin_urls
            existing.emails |= contact.emails
            existing.source_urls |= contact.source_urls
    results = list(merged.values())
    results.sort(key=lambda c: (-c.score, c.name))
    return results


def research_row(researcher: Researcher, row: Dict[str, str]) -> Dict[str, str]:
    title = row.get("title", "")
    urls = extract_urls_from_row(row)
    official = official_urls(urls)
    company_linkedin = linkedin_company_urls(urls)
    if not official:
        official = search_official_site(researcher, title)

    contacts: List[Contact] = []
    page_emails: Set[str] = set()
    page_linkedin_urls: Set[str] = set()
    source_urls: Set[str] = set()
    visited: Set[str] = set()
    queued = candidate_seed_pages(official)

    primary_domain = strip_www(urlparse(official[0]).netloc) if official else ""

    while queued and len(visited) < 10:
        page_url = queued.pop(0)
        if page_url in visited:
            continue
        visited.add(page_url)
        html_body = researcher.fetch(page_url)
        if not html_body or len(html_body) < 200:
            continue
        text, links, emails, linkedin_urls = extract_page_artifacts(page_url, html_body, primary_domain)
        source_urls.add(page_url)
        page_emails |= emails
        page_linkedin_urls |= linkedin_urls
        contacts.extend(extract_contacts_from_text(text, page_url))
        if primary_domain:
            for link in choose_follow_links(page_url, links, primary_domain):
                if link not in visited and link not in queued:
                    queued.append(link)

    contacts = dedupe_contacts(contacts)
    contacts, public_contact_emails = assign_emails(contacts, page_emails)

    unused_linkedin = set(page_linkedin_urls)
    for contact in contacts[:3]:
        if not contact.linkedin_urls:
            discovered = researcher.yahoo_search_linkedin(contact.name, title)
            if discovered:
                contact.linkedin_urls.add(discovered)
        for linkedin in list(unused_linkedin):
            slug = urlparse(linkedin).path.lower()
            name_parts = [part.lower().strip(".'`") for part in contact.name.split() if len(part) > 1]
            if all(part in slug for part in name_parts[-2:]):
                contact.linkedin_urls.add(linkedin)
                unused_linkedin.discard(linkedin)

    top_contacts = contacts[:3]
    decision_maker_emails = merge_unique(email for contact in top_contacts for email in sorted(contact.emails))
    decision_maker_linkedin_urls = merge_unique(
        url for contact in top_contacts for url in sorted(contact.linkedin_urls)
    )

    if decision_maker_emails or decision_maker_linkedin_urls:
        status = "decision_maker_contact_found"
    elif public_contact_emails:
        status = "generic_email_only"
    elif top_contacts:
        status = "names_only"
    else:
        status = "no_public_contact_found"

    notes: List[str] = []
    if top_contacts and not decision_maker_emails:
        notes.append("identified senior names but no verified personal email on public pages")
    if top_contacts and not decision_maker_linkedin_urls:
        notes.append("identified senior names but no verified LinkedIn profile URL")
    if public_contact_emails and not decision_maker_emails:
        notes.append("public site exposes only firm-level contact email")
    if not official:
        notes.append("no official website URL found in source data or public search")

    return {
        "official_website": official[0] if official else "",
        "company_linkedin_url": company_linkedin[0] if company_linkedin else "",
        "decision_maker_contacts": " ; ".join(contact.render() for contact in top_contacts),
        "decision_maker_names": "; ".join(contact.name for contact in top_contacts),
        "decision_maker_titles": "; ".join(contact.title for contact in top_contacts),
        "decision_maker_emails": format_url_list(decision_maker_emails),
        "decision_maker_linkedin_urls": format_url_list(decision_maker_linkedin_urls),
        "public_contact_emails": format_url_list(public_contact_emails),
        "contact_source_urls": format_url_list(sorted(source_urls)[:8]),
        "contact_research_status": status,
        "contact_research_notes": "; ".join(notes),
    }


def search_official_site(researcher: Researcher, firm_name: str) -> List[str]:
    query = quote_plus(f'"{firm_name}" official website')
    url = f"https://search.yahoo.com/search?p={query}"
    html_body = researcher.fetch(url)
    if not html_body:
        return []
    candidates = []
    for raw_url in re.findall(r"https?://r\.search\.yahoo\.com/[^\"'\s<>]+", html_body):
        match = re.search(r"/RU=([^/]+)/RK=", raw_url)
        if not match:
            continue
        decoded = unquote(match.group(1))
        parsed = urlparse(decoded)
        if not parsed.netloc or is_non_official_domain(parsed.netloc):
            continue
        candidates.append(canonicalize_url(decoded))
    return merge_unique(candidates[:3])


def summarize(rows: Sequence[Dict[str, str]]) -> str:
    total = len(rows)
    contact_found = sum(1 for row in rows if row["contact_research_status"] == "decision_maker_contact_found")
    generic_only = sum(1 for row in rows if row["contact_research_status"] == "generic_email_only")
    names_only = sum(1 for row in rows if row["contact_research_status"] == "names_only")
    none_found = sum(1 for row in rows if row["contact_research_status"] == "no_public_contact_found")
    linkedin_count = sum(1 for row in rows if row["decision_maker_linkedin_urls"])
    email_count = sum(1 for row in rows if row["decision_maker_emails"])
    return "\n".join(
        [
            f"Total firms: {total}",
            f"Decision maker contact found: {contact_found}",
            f"Generic email only: {generic_only}",
            f"Names only: {names_only}",
            f"No public contact found: {none_found}",
            f"Rows with decision maker LinkedIn URLs: {linkedin_count}",
            f"Rows with decision maker emails: {email_count}",
        ]
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Enrich firm CSV with public decision maker contacts.")
    parser.add_argument("input_csv", help="Path to the source CSV")
    parser.add_argument("--output", help="Path to the enriched CSV output")
    parser.add_argument("--summary", help="Path to a plain-text summary output")
    parser.add_argument("--limit", type=int, help="Only process the first N rows")
    args = parser.parse_args(argv)

    input_path = Path(args.input_csv)
    output_path = Path(args.output) if args.output else input_path.with_name(f"{input_path.stem}_decision_makers.csv")
    summary_path = Path(args.summary) if args.summary else input_path.with_name(f"{input_path.stem}_decision_makers_summary.txt")

    with input_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        original_rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    if args.limit is not None:
        original_rows = original_rows[: args.limit]

    researcher = Researcher()
    enriched_rows: List[Dict[str, str]] = []
    extra_fields = [
        "official_website",
        "company_linkedin_url",
        "decision_maker_contacts",
        "decision_maker_names",
        "decision_maker_titles",
        "decision_maker_emails",
        "decision_maker_linkedin_urls",
        "public_contact_emails",
        "contact_source_urls",
        "contact_research_status",
        "contact_research_notes",
    ]

    for index, row in enumerate(original_rows, start=1):
        if index % 10 == 0:
            print(f"Processed {index}/{len(original_rows)} rows", file=sys.stderr)
        enriched = dict(row)
        enriched.update(research_row(researcher, row))
        enriched_rows.append(enriched)

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames + extra_fields)
        writer.writeheader()
        writer.writerows(enriched_rows)

    summary_text = summarize(enriched_rows)
    summary_path.write_text(summary_text + "\n", encoding="utf-8")
    print(summary_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
