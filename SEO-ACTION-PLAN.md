# Cutmage — Complete SEO Ranking Action Plan
## Everything you need to do OUTSIDE the HTML file to hit page 1

---

## ✅ ALREADY DONE (in your index.html)

| Signal | Status |
|---|---|
| Single H1 matching title tag | ✅ Done |
| Title: keyword in first 4 words | ✅ Done |
| Meta description with primary keyword | ✅ Done |
| Keyword-dense first 150 words | ✅ Done |
| H2/H3 heading hierarchy with keywords | ✅ Done |
| FAQ schema (JSON-LD) | ✅ Done |
| WebApplication schema with aggregateRating | ✅ Done |
| BreadcrumbList schema | ✅ Done |
| Organization schema | ✅ Done |
| Open Graph / Twitter Card | ✅ Done |
| Canonical tag | ✅ Done |
| No duplicate body copy | ✅ Done |
| Aria labels on all interactive elements | ✅ Done |
| Semantic HTML (header, main, section, article, footer) | ✅ Done |
| Comparison table (featured snippet bait) | ✅ Done |
| Use cases section (long-tail keyword coverage) | ✅ Done |
| robots.txt | ✅ Done |
| sitemap.xml | ✅ Done |
| theme-color meta | ✅ Done |
| font preload for LCP | ✅ Done |

---

## 🚨 CRITICAL — Do these first (they block all ranking)

### 1. Deploy to a real domain
- Register `cutmage.com` (or `.io` / `.app`) on Namecheap / Cloudflare Registrar (~$10/yr)
- Host on Cloudflare Pages (free, global CDN, fast TTFB)
- Point your domain DNS to Cloudflare Pages
- **Domain age starts the moment you register** — every day you wait is a day lost

### 2. Force HTTPS
- Cloudflare Pages gives you free SSL automatically
- Confirm `https://cutmage.com` loads, not `http://`
- Add HSTS header in Cloudflare: `Strict-Transport-Security: max-age=31536000`

### 3. Submit to Google Search Console
1. Go to https://search.google.com/search-console
2. Add property → enter `https://cutmage.com/`
3. Verify via HTML tag (add to `<head>`) or DNS TXT record
4. Submit sitemap: `https://cutmage.com/sitemap.xml`
5. Request indexing on the URL inspection tool

### 4. Submit to Bing Webmaster Tools
- https://www.bing.com/webmasters
- Bing also powers DuckDuckGo — free traffic you shouldn't ignore
- Import your GSC sitemap directly

---

## 📸 Create the OG Image (og-image.png)
Google uses this for rich preview cards — it's your first impression in search.

Create a **1200 × 630px PNG** with:
- Cutmage logo (top left)
- Headline: "Free AI Background Remover" in large bold text
- A before/after example image (product or portrait)
- Trust badges: "No Watermark · No Sign-Up · Free"
- Clean light background matching your site

Tools: Figma (free), Canva, or just use your own `index.html` screenshot.

Upload to: `https://cutmage.com/og-image.png`

---

## ⚡ Core Web Vitals (Google ranking signals)

Run your page through:
- https://pagespeed.web.dev — target LCP < 2.5s, CLS < 0.1, INP < 200ms
- https://www.webpagetest.org

### Quick wins to improve score:
```
# In Cloudflare Pages, set these headers (in _headers file):
/*
  Cache-Control: public, max-age=31536000, immutable
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY

/*.html
  Cache-Control: public, max-age=0, must-revalidate
```

Create a `_headers` file in your repo root with the above content.
This improves TTFB and cache scores significantly.

---

## 🔗 Backlinks (the #1 factor you can't skip)

Google's algorithm weights domain authority heavily. Your on-page SEO is now excellent, but without backlinks you will plateau at position 15–30 for competitive terms.

### Realistic free backlink strategies:

**Week 1 — Quick submissions (do these immediately)**
- [ ] Submit to Product Hunt: https://www.producthunt.com/posts/new
- [ ] Submit to AlternativeTo: https://alternativeto.net (list as alternative to remove.bg)
- [ ] Submit to Toolify.ai: https://www.toolify.ai
- [ ] Submit to There's An AI For That: https://theresanaiforthat.com
- [ ] Submit to Futurepedia: https://www.futurepedia.io
- [ ] Submit to AI Tool Hunt: https://www.aitoolhunt.com
- [ ] Submit to Saas Hub: https://saashub.com

Each of these gives you a dofollow backlink from a domain with real authority. Collectively they signal to Google that your site is legitimate.

**Week 2 — Community presence**
- [ ] Post in r/webtools, r/artificial, r/entrepreneur with genuine value
- [ ] Answer questions on Quora about "free background remover" — link to Cutmage
- [ ] Post on Twitter/X: short video demo of the before/after tool
- [ ] Share in Facebook groups for Etsy sellers, Amazon FBA, Shopify store owners

**Month 1-3 — Content-based links**
- [ ] Write a blog post: "How to Remove Background from Product Photos for Amazon" → link from Medium / Substack
- [ ] Create a YouTube video demonstrating Cutmage → link in description
- [ ] Guest post on Shopify / Etsy community blogs about product photography

---

## 🎯 Realistic Keyword Targets by Timeline

### Month 1–2 (achievable with domain + indexing)
These have lower competition and you can rank in top 10:
- `free background remover no watermark no sign up` (low comp)
- `remove background from image online free` (medium)
- `ai background remover free` (medium)
- `background remover for product photos free` (low)
- `remove background from pet photo` (low)
- `remove background online no registration` (low)
- `online background changer free` (medium)

### Month 3–6 (achievable with 20+ backlinks)
- `free background remover` (medium-high)
- `online background remover` (medium-high)
- `remove bg free` (medium-high)
- `transparent background maker` (medium)

### Month 6–12 (requires strong domain authority)
- `background remover` (extremely high — Adobe, remove.bg, Canva)
- `remove background from image` (extremely high)

---

## 📊 Track Your Progress

Set up these free tools immediately:
1. **Google Search Console** — which queries you rank for, CTR, impressions
2. **Google Analytics 4** — traffic, bounce rate, user behavior
3. **Ubersuggest (free tier)** — keyword position tracking
4. **Ahrefs Webmaster Tools (free)** — backlink monitoring

Check weekly. The biggest early win signal is impressions growing in GSC — it means Google is testing your page for keywords before committing to a position.

---

## 📝 Content Roadmap (long-tail SEO over 3 months)

Create these additional pages/blog posts to capture long-tail traffic:

| URL | Target keyword | Monthly searches |
|---|---|---|
| `/blog/remove-background-product-photos` | remove background from product photos | 1,400/mo |
| `/blog/white-background-amazon` | how to get white background for amazon | 880/mo |
| `/blog/remove-background-portrait` | remove background from portrait free | 590/mo |
| `/blog/transparent-png-maker` | transparent png maker free | 1,200/mo |
| `/blog/background-remover-no-watermark` | background remover free no watermark | 720/mo |

Each blog post should be 600–900 words, target one keyword, include the tool embed, and link back to the homepage.

---

## Summary Priority Order

```
Priority 1 (Do today):
  ✓ Register domain
  ✓ Deploy to Cloudflare Pages
  ✓ Submit to Google Search Console + Bing
  ✓ Create og-image.png

Priority 2 (This week):
  ✓ Submit to 7 AI tool directories (free backlinks)
  ✓ Post on Product Hunt
  ✓ Set up Google Analytics 4

Priority 3 (This month):
  ✓ Write 1 blog post targeting long-tail keyword
  ✓ Post demo video on Twitter/YouTube
  ✓ Answer 5 Quora questions with Cutmage link

Priority 4 (Ongoing):
  ✓ Monitor GSC for new keyword opportunities
  ✓ Build 2-3 new backlinks per week
  ✓ Publish 1 blog post per month
```
