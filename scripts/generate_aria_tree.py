"""Generate an Accessibility (ARIA) Tree from a webpage using pure Python (HTTPX + BeautifulSoup)."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import bs4
from bs4 import BeautifulSoup, Comment, NavigableString, Tag
import httpx


# W3C HTML-AAM mapping from HTML tag to ARIA landmark/role
TAG_TO_ROLE: Dict[str, str] = {
    "a": "link",
    "article": "article",
    "aside": "complementary",
    "button": "button",
    "details": "group",
    "dialog": "dialog",
    "figure": "figure",
    "footer": "contentinfo",
    "form": "form",
    "header": "banner",
    "main": "main",
    "nav": "navigation",
    "ol": "list",
    "ul": "list",
    "li": "listitem",
    "section": "region",
    "select": "combobox",
    "summary": "button",
    "table": "table",
    "tbody": "rowgroup",
    "thead": "rowgroup",
    "tfoot": "rowgroup",
    "tr": "row",
    "td": "cell",
    "th": "columnheader",
    "textarea": "textbox",
    "img": "image",
    "search": "search",
    "hr": "separator",
    "p": "paragraph",
    "blockquote": "blockquote",
}

INPUT_TYPE_TO_ROLE: Dict[str, str] = {
    "button": "button",
    "submit": "button",
    "reset": "button",
    "image": "button",
    "checkbox": "checkbox",
    "radio": "radio",
    "search": "searchbox",
    "text": "textbox",
    "email": "textbox",
    "tel": "textbox",
    "url": "textbox",
    "password": "textbox",
    "number": "spinbutton",
    "range": "slider",
}

IGNORE_TAGS = {"script", "style", "template", "svg", "path", "meta", "link", "head"}


class AccessibilityNode:
    def __init__(
        self,
        role: str,
        name: str = "",
        value: str = "",
        level: Optional[int] = None,
        href: Optional[str] = None,
        disabled: bool = False,
        checked: Optional[bool] = None,
        expanded: Optional[bool] = None,
    ):
        self.role = role
        self.name = name.strip()
        self.value = value.strip()
        self.level = level
        self.href = href
        self.disabled = disabled
        self.checked = checked
        self.expanded = expanded
        self.children: List[AccessibilityNode] = []

    def format_tree(self, depth: int = 0) -> List[str]:
        indent = "  " * depth
        attrs = []
        if self.name:
            clean_name = re.sub(r"\s+", " ", self.name)
            if len(clean_name) > 120:
                clean_name = clean_name[:117] + "..."
            attrs.append(f'"{clean_name}"')
        if self.level is not None:
            attrs.append(f"[level: {self.level}]")
        if self.value:
            attrs.append(f'[value: "{self.value}"]')
        if self.checked is not None:
            attrs.append(f"[checked: {self.checked}]")
        if self.expanded is not None:
            attrs.append(f"[expanded: {self.expanded}]")
        if self.disabled:
            attrs.append("[disabled]")
        if self.href:
            attrs.append(f"<{self.href}>")

        attr_str = (" " + " ".join(attrs)) if attrs else ""
        lines = [f"{indent}- {self.role}{attr_str}"]
        for child in self.children:
            lines.extend(child.format_tree(depth + 1))
        return lines


def is_hidden(tag: Tag) -> bool:
    if tag.has_attr("hidden"):
        return True
    if tag.get("aria-hidden") == "true":
        return True
    style = tag.get("style", "")
    # Check for direct inline hidden styles
    if "display:none" in style.replace(" ", "") or "visibility:hidden" in style.replace(" ", ""):
        return True
    return False


def get_accessible_name(tag: Tag) -> str:
    # 1. aria-label
    if tag.get("aria-label"):
        return tag["aria-label"]
    # 2. alt (for images)
    if tag.name == "img" and tag.has_attr("alt"):
        return tag["alt"]
    # 3. title
    if tag.get("title"):
        return tag["title"]
    # 4. placeholder
    if tag.get("placeholder"):
        return tag["placeholder"]
    # 5. value attribute for button inputs
    if tag.name == "input" and tag.get("type") in ("button", "submit", "reset") and tag.get("value"):
        return tag["value"]
    return ""


def determine_role(tag: Tag) -> Optional[str]:
    # Explicit role overrides tag default
    if tag.has_attr("role"):
        role = tag["role"].strip().lower()
        if role in ("presentation", "none"):
            return None
        return role

    tag_name = tag.name.lower()

    # Headings h1..h6
    if re.match(r"^h[1-6]$", tag_name):
        return "heading"

    # Inputs
    if tag_name == "input":
        inp_type = tag.get("type", "text").lower()
        return INPUT_TYPE_TO_ROLE.get(inp_type, "textbox")

    # Links must have href to have role='link'
    if tag_name == "a":
        return "link" if tag.has_attr("href") else None

    # Form role heuristics
    if tag_name == "form":
        action = tag.get("action", "")
        if "search" in action or tag.get("role") == "search":
            return "search"
        return "form"

    return TAG_TO_ROLE.get(tag_name, None)


def parse_dom_node(element: bs4.PageElement, base_url: str = "") -> List[AccessibilityNode]:
    if isinstance(element, Comment):
        return []

    if isinstance(element, NavigableString):
        text = str(element).strip()
        if not text:
            return []
        clean_text = re.sub(r"\s+", " ", text)
        return [AccessibilityNode(role="text", name=clean_text)]

    if not isinstance(element, Tag):
        return []

    tag_name = element.name.lower()
    if tag_name in IGNORE_TAGS:
        return []

    # If noscript, inspect children for non-JS environment
    if tag_name == "noscript":
        nodes = []
        for child in element.children:
            nodes.extend(parse_dom_node(child, base_url))
        if nodes:
            group = AccessibilityNode(role="region", name="No-Script Fallback Notice")
            group.children = nodes
            return [group]
        return []

    if is_hidden(element):
        return []

    role = determine_role(element)
    acc_name = get_accessible_name(element)
    value = element.get("value", "") if element.name in ("input", "textarea", "select") else ""

    level = None
    if re.match(r"^h[1-6]$", tag_name):
        level = int(tag_name[1])

    href = None
    if element.name == "a" and element.has_attr("href"):
        href = element["href"]
        if base_url and href and not href.startswith(("javascript:", "#")):
            href = urljoin(base_url, href)

    disabled = element.has_attr("disabled") or element.get("aria-disabled") == "true"
    checked = True if element.has_attr("checked") or element.get("aria-checked") == "true" else (
        False if element.get("aria-checked") == "false" else None
    )
    expanded = True if element.get("aria-expanded") == "true" else (
        False if element.get("aria-expanded") == "false" else None
    )

    child_nodes: List[AccessibilityNode] = []
    direct_texts: List[str] = []

    for child in element.children:
        if isinstance(child, NavigableString):
            txt = str(child).strip()
            if txt:
                direct_texts.append(txt)
        elif isinstance(child, Tag):
            child_nodes.extend(parse_dom_node(child, base_url))

    if not acc_name:
        all_text = " ".join(direct_texts).strip()
        if role in ("button", "link", "heading", "cell", "columnheader"):
            if all_text:
                acc_name = all_text
            elif child_nodes and all(c.role == "text" for c in child_nodes):
                acc_name = " ".join(c.name for c in child_nodes)
                child_nodes = []

    # Non-semantic wrappers (div, span)
    if not role:
        if acc_name:
            node = AccessibilityNode(role="generic", name=acc_name)
            node.children = child_nodes
            return [node]
        # Prune wrapper tag and hoist children
        return child_nodes

    node = AccessibilityNode(
        role=role,
        name=acc_name,
        value=value if isinstance(value, str) else "",
        level=level,
        href=href,
        disabled=disabled,
        checked=checked,
        expanded=expanded,
    )
    node.children = child_nodes
    return [node]


def build_aria_tree_from_html(html: str, base_url: str = "") -> AccessibilityNode:
    soup = BeautifulSoup(html, "html.parser")
    title_text = soup.title.string.strip() if (soup.title and soup.title.string) else "Webpage"
    root = AccessibilityNode(role="document", name=title_text)

    body = soup.find("body") or soup
    for child in body.children:
        root.children.extend(parse_dom_node(child, base_url))

    return root


def fetch_and_generate_aria_tree(url: str, output_path: Path) -> Path:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    print(f"Fetching {url}...")
    response = httpx.get(url, headers=headers, follow_redirects=True, timeout=15.0)
    response.raise_for_status()

    print(f"Parsing DOM & generating ARIA tree ({len(response.text)} bytes)...")
    tree = build_aria_tree_from_html(response.text, base_url=url)
    lines = tree.format_tree()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        f"# ARIA Accessibility Tree Snapshot",
        f"# URL: {url}",
        f"# Document Title: {tree.name}",
        f"# Total Accessibility Nodes in Tree: {len(lines)}",
        f"# Method: Pure Python Static HTML-AAM Parser (Option 2: HTTPX + BeautifulSoup)",
        "=" * 80,
        "",
    ]
    full_content = "\n".join(header + lines)
    output_path.write_text(full_content, encoding="utf-8")
    print(f"Saved ARIA tree to {output_path} ({len(lines)} nodes)")
    return output_path


if __name__ == "__main__":
    target_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.google.com/search?q=beautifulsoup"
    out_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("aria_tree_google_search.txt")
    fetch_and_generate_aria_tree(target_url, out_file)
