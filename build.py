#!/usr/bin/env python3
"""
AIPrOoHub blog engine.

Usage:
    python3 build.py                                   # build from content/articles/
    python3 build.py --source-dir /path/to/articles/   # ingest articles from another folder
                                                       # e.g. ~/workspace/gumroad-store/real-estate-prompts/traffic/week-1/articles/

Workflow for a new article:
    1. Write a markdown file in content/articles/ (see existing files for frontmatter format).
    2. Run: python3 build.py
    3. Deploy the website/ folder to Cloudflare Pages as-is (pure static output).

What it does:
    - Converts each .md article to blog/<slug>.html using the site template.
    - Regenerates blog/index.html (newest first).
    - Regenerates sitemap.xml (static pages + all articles).
    - Files WITH frontmatter use it; files WITHOUT get title from first H1,
      slug from filename, date from file mtime.
"""

import argparse
import html
import json
import os
import re
import sys
from datetime import datetime

SITE_URL = "https://aiproohub.com"
ROOT = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(ROOT, "content", "articles")
BLOG_DIR = os.path.join(ROOT, "blog")

# ---------------------------------------------------------------- markdown

def md_to_html(md):
    """Small stdlib-only markdown converter: headings, bold, italic, links,
    images, lists, blockquotes, code, paragraphs, hr."""
    lines = md.split("\n")
    out = []
    in_ul = in_ol = in_quote = in_code = False
    code_buf = []

    def close_lists():
        nonlocal in_ul, in_ol, in_quote
        if in_ul:
            out.append("</ul>"); in_ul = False
        if in_ol:
            out.append("</ol>"); in_ol = False
        if in_quote:
            out.append("</blockquote>"); in_quote = False

    def inline(t):
        t = html.escape(t)
        t = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1" loading="lazy">', t)
        t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
        t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", t)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        return t

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                out.append("<pre><code>" + html.escape("\n".join(code_buf)) + "</code></pre>")
                code_buf = []
                in_code = False
            else:
                close_lists(); in_code = True
            continue
        if in_code:
            code_buf.append(line)
            continue
        if not stripped:
            close_lists()
            continue
        if re.match(r"^#{1,4}\s", stripped):
            close_lists()
            level = len(stripped) - len(stripped.lstrip("#"))
            out.append(f"<h{level}>{inline(stripped[level:].strip())}</h{level}>")
            continue
        if stripped in ("---", "***", "___"):
            close_lists(); out.append("<hr>"); continue
        if stripped.startswith("> "):
            if not in_quote:
                close_lists(); out.append("<blockquote>"); in_quote = True
            out.append(f"<p>{inline(stripped[2:])}</p>")
            continue
        m = re.match(r"^(\d+)\.\s+(.*)", stripped)
        if m:
            if not in_ol:
                close_lists(); out.append("<ol>"); in_ol = True
            out.append(f"<li>{inline(m.group(2))}</li>")
            continue
        if re.match(r"^[-*]\s+", stripped):
            if not in_ul:
                close_lists(); out.append("<ul>"); in_ul = True
            out.append(f"<li>{inline(stripped[2:])}</li>")
            continue
        close_lists()
        out.append(f"<p>{inline(stripped)}</p>")

    close_lists()
    return "\n".join(out)

# ---------------------------------------------------------------- articles

def parse_article(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    meta = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip().strip('"').strip("'")
            body = parts[2].strip()

    fname = os.path.splitext(os.path.basename(path))[0]
    if "slug" not in meta:
        meta["slug"] = re.sub(r"[^a-z0-9]+", "-", fname.lower()).strip("-")
    if "title" not in meta:
        m = re.search(r"^#\s+(.+)$", body, re.M)
        meta["title"] = m.group(1).strip() if m else fname.replace("-", " ").title()
        if m:
            body = re.sub(r"^#\s+.+$\n?", "", body, count=1, flags=re.M).strip()
    if "date" not in meta:
        meta["date"] = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")
    meta.setdefault("description", meta["title"])
    meta.setdefault("keywords", "")
    return meta, body

# ---------------------------------------------------------------- templates

NAV = """<a class="skip-link" href="#main">Skip to content</a>
<header class="site"><nav class="nav container">
<a class="brand" href="/">AI<span>PrOo</span>Hub</a>
<ul class="nav-links">
<li><a href="/">Home</a></li>
<li><a href="/products/ai-prompts-real-estate-agents.html">Products</a></li>
<li><a href="/blog/">Blog</a></li>
<li><a href="/about.html">About</a></li>
<li><a href="/contact.html">Contact</a></li>
</ul>
<div class="nav-actions">
<button class="icon-btn" id="search-toggle" aria-label="Search the site" title="Search (Ctrl+K)">🔍</button>
<button class="icon-btn" id="theme-toggle" aria-label="Toggle dark mode" title="Dark mode">🌙</button>
<button class="icon-btn hamburger" id="menu-toggle" aria-label="Open menu" aria-expanded="false">☰</button>
</div>
</nav></header>"""

FOOTER = """<footer class="site"><div class="container footer-grid">
<div><a class="brand" href="/">AI<span>PrOo</span>Hub</a><br><small>AI tools, made simple.</small></div>
<div><ul><li><a href="/products/ai-prompts-real-estate-agents.html">AI Prompt Pack for Real Estate Agents</a></li><li><a href="/blog/">Blog</a></li><li><a href="/about.html">About</a></li></ul></div>
<div><ul><li><a href="/contact.html">Contact</a></li><li><a href="https://wa.me/923418289801" target="_blank" rel="noopener">WhatsApp orders</a></li></ul></div>
</div><div class="container mt"><small>&copy; 2026 AIPrOoHub. All rights reserved.</small></div></footer>
<div id="scroll-progress"></div>
<button id="back-to-top" aria-label="Back to top" title="Back to top">↑</button>
<a class="wa-float" href="https://wa.me/923418289801?utm_source=aiproohub.com&utm_medium=site&utm_campaign=float_button" target="_blank" rel="noopener" aria-label="Chat on WhatsApp" title="Chat on WhatsApp">💬</a>
<div id="search-overlay" role="dialog" aria-label="Site search">
<div class="search-box">
<input type="search" id="search-input" placeholder="Search guides, prompts, topics…" aria-label="Search the site" autocomplete="off">
<div id="search-results"><p class="search-hint">Type to search 30 guides and the prompt pack. Tip: press Ctrl+K anywhere.</p></div>
</div>
</div>
<script src="/assets/site.js" defer></script>
<!-- Cookie consent banner -->
<div id="cookie-banner" style="display:none;position:fixed;bottom:0;left:0;right:0;z-index:9999;background:#FDF8F0;border-top:2px solid #E8930C;padding:14px 20px;box-shadow:0 -2px 12px rgba(74,44,20,.12);">
<div style="max-width:960px;margin:0 auto;display:flex;gap:16px;align-items:center;justify-content:space-between;flex-wrap:wrap;">
<p style="margin:0;color:#4A2C14;font-size:14px;">We use cookies to understand site traffic (Google Analytics). No ads, no selling data.</p>
<div style="display:flex;gap:10px;align-items:center;">
<button id="cookie-accept" style="background:#E8930C;color:#fff;border:none;border-radius:8px;padding:9px 22px;font-weight:700;cursor:pointer;font-size:14px;">Accept</button>
<button id="cookie-decline" style="background:none;border:none;color:#4A2C14;cursor:pointer;font-size:14px;text-decoration:underline;">Decline</button>
</div></div></div>
<script>
(function(){var k='aiproohub-cookie-consent';
function apply(v){if(typeof gtag==='function'){gtag('consent','update',{'analytics_storage':v,'ad_storage':'denied'});}}
try{var s=localStorage.getItem(k);
if(s==='granted'){apply('granted');}
else if(s!=='denied'){document.getElementById('cookie-banner').style.display='block';}
}catch(e){document.getElementById('cookie-banner').style.display='block';}
document.getElementById('cookie-accept').onclick=function(){try{localStorage.setItem(k,'granted');}catch(e){}apply('granted');document.getElementById('cookie-banner').style.display='none';};
document.getElementById('cookie-decline').onclick=function(){try{localStorage.setItem(k,'denied');}catch(e){}apply('denied');document.getElementById('cookie-banner').style.display='none';};
})();
</script>"""

def head_tags(title, description, url, og_type="website", keywords="", og_image=""):
    kw = f'\n<meta name="keywords" content="{html.escape(keywords)}">' if keywords else ""
    og_img = ""
    if og_image:
        og_img = f'''\n<meta property="og:image" content="{og_image}">\n<meta name="twitter:image" content="{og_image}">'''
    return f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' https://www.googletagmanager.com https://static.cloudflareinsights.com; style-src 'self' 'unsafe-inline'; img-src 'self' https://www.googletagmanager.com; connect-src 'self' https://www.googletagmanager.com https://www.google-analytics.com https://region1.google-analytics.com https://static.cloudflareinsights.com https://cloudflareinsights.com; font-src 'self'; base-uri 'self'; form-action 'self' mailto:; object-src 'none'">
<title>{html.escape(title)} | AIPrOoHub</title>
<meta name="description" content="{html.escape(description)}">{kw}
<link rel="canonical" href="{url}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="AIPrOoHub">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:url" content="{url}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{html.escape(title)}">
<meta name="twitter:description" content="{html.escape(description)}">{og_img}
<link rel="stylesheet" href="/assets/styles.css">
<!-- Google Analytics 4 (consent mode: granted by default, denied on opt-out) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-ZR9HHKT39H"></script>
<script>
window.dataLayer = window.dataLayer || [];
function gtag(){{dataLayer.push(arguments);}}
gtag('consent','default',{{'analytics_storage':'granted','ad_storage':'denied'}});
gtag('js', new Date());
gtag('config','G-ZR9HHKT39H');
</script>
<!-- Cloudflare Web Analytics -->
<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{{"token": "3ff05c218f3f40b69dbfe81d62c30feb"}}'></script>
<!-- End Cloudflare Web Analytics -->"""

def article_page(meta, body_html):
    url = f"{SITE_URL}/blog/{meta['slug']}.html"
    try:
        date_str = datetime.strptime(meta["date"], "%Y-%m-%d").strftime("%B %d, %Y")
    except ValueError:
        date_str = meta["date"]
    updated = meta.get("updated", meta["date"])
    try:
        updated_str = datetime.strptime(updated, "%Y-%m-%d").strftime("%B %d, %Y")
    except ValueError:
        updated_str = updated
    updated_line = f' &nbsp;·&nbsp; Updated {updated_str}' if updated != meta["date"] else ''
    jsonld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": meta["title"],
        "description": meta["description"],
        "datePublished": meta["date"],
        "dateModified": updated,
        "author": {"@type": "Organization", "name": "AIPrOoHub"},
    }
    import json
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head_tags(meta["title"], meta["description"], url, "article", meta["keywords"], f"{SITE_URL}/assets/blog/{meta['slug']}.webp")}
<script type="application/ld+json">{json.dumps(jsonld)}</script>
</head>
<body>
{NAV}
<main class="container narrow" id="main"><section class="block">
<p class="article-meta"><a href="/blog/">&larr; All articles</a> &nbsp;·&nbsp; Published {date_str}{updated_line}</p>
<h1>{html.escape(meta["title"])}</h1>
<div class="article-body">
{body_html}
</div>
<div class="cta-box">
<h3>Write listings, ads &amp; emails in minutes</h3>
<p>The <strong>AI Prompt Pack for Real Estate Agents</strong> gives you 202 copy-paste prompts built exclusively for real estate, $39, yours forever.</p>
<p class="mt"><a class="btn" href="/products/ai-prompts-real-estate-agents.html">See what's inside</a></p>
</div>
</section></main>
{FOOTER}
</body>
</html>
"""

def blog_index(articles):
    cards = "\n".join(
        f"""<a class="post-card card" href="/blog/{a['slug']}.html">
<span class="kicker">AI for Real Estate</span>
<h2>{html.escape(a['title'])}</h2>
<p class="excerpt">{html.escape(a['description'])}</p>
<p class="article-meta">{a['date']}</p>
</a>""" for a in articles
    )
    url = f"{SITE_URL}/blog/"
    blog_schema = json.dumps({"@context":"https://schema.org","@type":"Blog","name":"AIPrOoHub Blog",
        "url":url,"description":"Practical guides on using AI for real estate marketing.",
        "publisher":{"@type":"Organization","name":"AIPrOoHub","url":SITE_URL}})
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head_tags("Blog | AI tips for real estate agents", "Practical guides on using AI for real estate marketing: listing copy, ads, social media, and client emails.", url, og_image=f"{SITE_URL}/assets/og-cover.jpg")}
<script type="application/ld+json">{blog_schema}</script>
</head>
<body>
{NAV}
<main class="container" id="main"><section class="block">
<span class="badge">The Blog</span>
<h1>AI tips for real estate agents</h1>
<p class="lead" style="color:var(--ink-soft)">Practical, no-fluff guides on using AI to market more homes in less time.</p>
<div class="blog-grid mt">
{cards}
</div>
</section></main>
{FOOTER}
</body>
</html>
"""

def sitemap(urls):
    entries = "\n".join(
        f"  <url><loc>{u}</loc><changefreq>weekly</changefreq></url>" for u in urls
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{entries}
</urlset>
"""

# ---------------------------------------------------------------- build

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-dir", default=CONTENT_DIR,
                    help="Folder of .md articles (default: content/articles/)")
    args = ap.parse_args()

    src = os.path.abspath(os.path.expanduser(args.source_dir))
    if not os.path.isdir(src):
        sys.exit(f"Source dir not found: {src}")

    os.makedirs(BLOG_DIR, exist_ok=True)
    md_files = sorted(f for f in os.listdir(src) if f.endswith(".md"))
    if not md_files:
        print(f"No .md files in {src} — nothing to build.")
        return

    articles = []
    for fname in md_files:
        meta, body = parse_article(os.path.join(src, fname))
        articles.append((meta, body))
    articles.sort(key=lambda a: a[0]["date"], reverse=True)

    for meta, body in articles:
        page = article_page(meta, md_to_html(body))
        with open(os.path.join(BLOG_DIR, meta["slug"] + ".html"), "w", encoding="utf-8") as f:
            f.write(page)
        print(f"  built blog/{meta['slug']}.html")

    with open(os.path.join(BLOG_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(blog_index([m for m, _ in articles]))
    print("  built blog/index.html")

    urls = [
        f"{SITE_URL}/",
        f"{SITE_URL}/about.html",
        f"{SITE_URL}/contact.html",
        f"{SITE_URL}/products/ai-prompts-real-estate-agents.html",
        f"{SITE_URL}/blog/",
    ] + [f"{SITE_URL}/blog/{m['slug']}.html" for m, _ in articles]
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sitemap(urls))
    print(f"  built sitemap.xml ({len(urls)} urls)")

    # search index for client-side site search
    search_entries = [
        {"title": "AI Prompt Pack for Real Estate Agents", "desc": "202 copy-paste AI prompts for real estate, $39 one-time.", "keywords": "prompt pack product buy prompts", "url": "/products/ai-prompts-real-estate-agents.html"},
        {"title": "About AIPrOoHub", "desc": "Who we are and what we build.", "keywords": "about team", "url": "/about.html"},
        {"title": "Contact AIPrOoHub", "desc": "Get in touch with the AIPrOoHub team.", "keywords": "contact email support", "url": "/contact.html"},
    ] + [
        {"title": m["title"], "desc": m["description"][:140], "keywords": m.get("keywords", ""), "url": f"/blog/{m['slug']}.html"}
        for m, _ in articles
    ]
    with open(os.path.join(ROOT, "search-index.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(search_entries))
    print(f"  built search-index.json ({len(search_entries)} entries)")
    print(f"Done: {len(articles)} article(s).")

if __name__ == "__main__":
    main()
