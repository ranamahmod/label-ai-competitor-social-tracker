# label-ai-competitor-social-tracker

An AI agent that tracks 4–5 competitor Instagram/TikTok profiles, identifies content patterns, and outputs an HTML report plus a CSV of top posts. Built for marketing agencies.

## What It Does

Pass in a comma-separated list of Instagram or TikTok profile URLs. The agent scrapes publicly visible data from each profile, sends the results to Groq AI for competitive analysis, and outputs a dark-themed HTML report with per-competitor insights, a grouped bar chart of format mix, patterns competitors double down on, content gaps you can exploit, and a recommended strategy — plus a CSV of the top posts for further analysis.

## Who Buys This and at What Price

Social media managers, digital marketing agencies, and brand consultants who need to benchmark a client's competitors before building a content strategy. Deliverable-based pricing: $200–$600 per competitive analysis report, or included in a monthly social strategy retainer at $1,000–$2,500/month.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and fill in your GROQ_API_KEY
```

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Your Groq API key from [console.groq.com](https://console.groq.com) |

## Usage

```bash
python agent2_competitor_social_tracker.py --profiles "https://www.instagram.com/nike,https://www.instagram.com/adidas,https://www.tiktok.com/@gymshark"
```

Supports 1–5 profile URLs. Mix of Instagram and TikTok is supported.

## Output

Two timestamped files are saved in the current directory:

```
competitor_tracker_report_20260601_143022.html
competitor_top_posts_20260601_143022.csv
```

The HTML report includes:
- Per-competitor profile cards (followers, posting frequency, engagement estimate, key insight, top themes)
- Grouped bar chart of format mix across all competitors
- Patterns they double down on
- Content gaps you can exploit
- AI-recommended strategy

The CSV contains the top posts per profile with captions, format, and engagement estimates — ready for further analysis or client presentations.

## Notes

Instagram and TikTok both rate-limit and JS-render heavily. The agent uses publicly visible page data and meta tags. For best results, use direct profile URLs (e.g. `https://www.instagram.com/handle`). A polite 1.5-second delay is applied between requests.

---

Built by Rana Mahmod (Contact: mahmodrana24@gmail.com)
