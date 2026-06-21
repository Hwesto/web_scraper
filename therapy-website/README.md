# Counsellor one-page website (Kent · town + online)

A fast, accessible, SEO-optimised **single-page website** for a self-employed
counsellor in Kent. Built as plain HTML/CSS/JS — no build step, no framework,
no dependencies. Drop the folder on any host and it works.

The sample content uses a fictional counsellor (**"Sarah Bennett", Maidstone**)
so the site looks real and demoable out of the box. Replace the placeholders
(see [Customise](#customise-in-10-minutes)) with the real practitioner's details.

```
therapy-website/
├── index.html     # the page (content + SEO meta + structured data)
├── styles.css     # calming sage/teal + warm sand theme, fully responsive
├── script.js      # mobile nav, footer year, contact-form handling
├── robots.txt     # search-engine crawl rules
├── sitemap.xml    # one-URL sitemap for Google Search Console
└── README.md      # this file
```

---

## What a top UK independent therapist site does well (the analysis)

I reviewed the leading therapist web-design studios and a set of top
counsellor sites (see [Sources](#sources)). The patterns that consistently
convert visitors into enquiries — all built into this template:

| Ingredient | Why it matters | Where it is here |
|---|---|---|
| **Reassuring hero** that names the client's struggle + offers hope | Visitor decides in seconds whether they're "in the right place" | `.hero` headline + lede |
| **Warm, human photo** over a clinical stock image | Therapy is a relationship; people hire a person, not a logo | `.hero-photo` (add real photo) |
| **A clear, low-commitment CTA** ("free 15-min call") repeated down the page | Removes the fear of a big first step; the #1 conversion driver | "Book a free consultation" buttons |
| **Plain-language "How I can help"** with named issues | Matches how people search ("anxiety counselling") and reassures | `#help` service cards |
| **"How it works" steps** | Demystifies the process for nervous first-timers | `#process` |
| **Transparent fees** | Builds trust; reduces time-wasting enquiries | `#fees` |
| **Trust signals** — BACP registration, qualifications, supervision, insurance | Credibility + safety | About + footer |
| **Curated testimonials** | Social proof | `.quotes` |
| **FAQ** | Answers objections *and* wins Google "rich results" / long-tail searches | `#faq` |
| **Crisis/safeguarding notice** | Ethical best practice for therapy sites | `.crisis` band |
| **Calming palette, generous whitespace, big readable type** | Signals safety; aids accessibility | `styles.css` |

Things the best sites *avoid*, also reflected here: image carousels, autoplay,
clutter, jargon, and burying the phone number.

---

## SEO strategy (town + online)

The brief was **good local SEO in Kent**, anchored to one town while also
promoting online sessions. Here's what's built in and what you must do after
launch.

### Already in the code
- **Keyword-rich `<title>` and meta description** targeting `counsellor [town]`,
  `counselling Kent`, and `online counselling`.
- **One clear `<h1>`** and a logical single-H1 heading hierarchy.
- **`LocalBusiness` / `ProfessionalService` structured data** (JSON-LD) with
  `address`, `geo`, `areaServed` (Maidstone + nearby Kent towns + Kent),
  `openingHours`, `telephone`, and BACP membership — this is the biggest lever
  for **"near me"** and **map** results.
- **`FAQPage` structured data** — eligible for expanded FAQ rich results.
- **Consistent NAP** (Name, Address, Phone) in the schema, contact section and
  footer — local ranking depends on this matching everywhere.
- **Open Graph / Twitter tags** for clean social sharing.
- **Semantic HTML, alt text, fast load (no frameworks), mobile-first** — all
  Core Web Vitals / page-experience ranking factors.
- **`robots.txt` + `sitemap.xml`**.
- **Online-session copy** woven through (areaServed includes Kent + UK) so you
  rank beyond the home town without diluting the local anchor.

### Do this after launch (off-page — where local rankings are really won)
1. **Google Business Profile** — create/claim it, exact same NAP, choose
   category "Counselor", add photos, collect Google reviews. This alone drives
   most "counsellor near me" visibility.
2. **Bing Places** — same again.
3. **Directory listings** (also feed the `sameAs` array in the schema):
   - [BACP "Find a Therapist"](https://www.bacp.co.uk/) — essential for credibility
   - [Counselling Directory](https://www.counselling-directory.org.uk/)
   - [Psychology Today UK](https://www.psychologytoday.com/gb)
4. **Get reviews** on Google and the directories — volume + recency matter.
5. **Consider a small blog** later (e.g. "Signs of burnout", "What happens in
   your first counselling session") to capture informational searches — the one
   page can grow into a small site without re-theming.
6. **Submit `sitemap.xml`** in Google Search Console once the domain is live.

---

## Customise in 10 minutes

Everything client-specific is plain text. Search-and-replace these across
`index.html` (and the URLs in `robots.txt` / `sitemap.xml`):

| Placeholder | Replace with |
|---|---|
| `Sarah Bennett` | Counsellor's name |
| `Maidstone` | Their town (and update the nearby-towns list in `areaServed` + footer) |
| `https://www.example-counselling.co.uk/` | Real domain (every occurrence, incl. canonical, OG, schema, sitemap, robots) |
| `01622 000000` / `+44-1622-000000` / `+441622000000` | Phone (display, schema, and `tel:` link) |
| `hello@example-counselling.co.uk` | Email (and the `mailto:` link) |
| `£55` / 50-minute session | Real fee |
| Address + `geo` lat/long + postcode in the JSON-LD | Real practice address / coordinates ([find lat-long](https://www.latlong.net/)) |
| Qualifications list (`.credentials`) | Real diplomas / memberships |
| Testimonials (`.quotes`) | Real, permissioned client feedback |
| Hero photo box (`.hero-photo`) | Replace the placeholder block with `<img src="assets/sarah.jpg" alt="Sarah Bennett, counsellor in Maidstone">` |
| `SB` brand initials (header + favicon) | Their initials |

> Keep the **crisis/safeguarding band** — it's ethical best practice for therapy
> sites and reassures clients.

### Make the contact form actually send
The form is wired for a no-JS-required hosted service. Easiest options:
- **Netlify** — add `netlify` attribute to the `<form>` and deploy to Netlify.
- **[Formspree](https://formspree.io/)** — set `action="https://formspree.io/f/yourID"` and `method="post"`.
Then remove/adjust the local-only fallback note in `script.js`.

---

## Run / preview locally

No build step. Just open the file, or serve it:

```bash
cd therapy-website
python3 -m http.server 8000
# visit http://localhost:8000
```

## Deploy

Upload the folder to any static host — **Netlify, Cloudflare Pages, GitHub
Pages, Vercel**, or traditional cPanel hosting. Point the custom domain at it
and enable HTTPS (required; also a ranking signal).

---

## Accessibility & performance notes
- Skip link, visible focus styles, `aria` on the nav toggle, semantic landmarks.
- `prefers-reduced-motion` respected.
- Colour contrast meets WCAG AA for body text.
- No render-blocking JS (`defer`), no framework, one webfont — fast Core Web Vitals.
- Works fully with JavaScript disabled.

## Sources
- [Strong Roots — Ten great therapist website examples](https://strongrootswebdesign.com/the-top-ten-therapist-website-examples/)
- [Your Therapy Website (UK)](https://www.yourtherapywebsite.co.uk/)
- [YouCan Consulting — therapist websites (UK)](https://www.youcanconsulting.co.uk/)
- [Counselling Directory — Kent](https://www.counselling-directory.org.uk/county/kent)
- [BACP — Find a Therapist directory](https://www.bacp.co.uk/about-therapy/using-our-therapist-directory/)
- [iCanotes — SEO for Therapists 2026 guide](https://www.icanotes.com/2026/02/17/seo-for-therapists/)
