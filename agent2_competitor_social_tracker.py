"""
Agent 2: Competitor Social Media Tracker
Scrapes 4-5 Instagram/TikTok public profile URLs, identifies content patterns,
and outputs an HTML report with Chart.js charts plus a CSV of top posts.

Usage:
    python agent2_competitor_social_tracker.py --profiles "url1,url2,url3"
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama3-70b-8192"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.google.com/",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Competitor Social Media Tracker — powered by Groq AI"
    )
    parser.add_argument(
        "--profiles",
        required=True,
        help="Comma-separated list of Instagram or TikTok profile URLs",
    )
    return parser.parse_args()


def detect_platform(url: str) -> str:
    if "instagram.com" in url:
        return "instagram"
    if "tiktok.com" in url:
        return "tiktok"
    return "unknown"


def extract_handle(url: str) -> str:
    parsed = urlparse(url.rstrip("/"))
    parts = [p for p in parsed.path.split("/") if p]
    return parts[0].lstrip("@") if parts else url


def scrape_instagram_profile(url: str, handle: str) -> dict:
    """Scrape publicly visible data from an Instagram profile page."""
    result = {
        "platform": "instagram",
        "handle": handle,
        "url": url,
        "bio": "",
        "followers": "N/A",
        "posts_count": "N/A",
        "posts": [],
        "raw_text": "",
        "status": "partial",
    }
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "lxml")

        # Pull meta description which often has follower/post counts
        meta_desc = soup.find("meta", {"name": "description"})
        if meta_desc:
            content = meta_desc.get("content", "")
            result["bio"] = content[:300]
            # Extract follower counts
            followers_match = re.search(r"([\d,.]+[KkMm]?)\s*Followers", content, re.I)
            if followers_match:
                result["followers"] = followers_match.group(1)
            posts_match = re.search(r"([\d,.]+)\s*Posts", content, re.I)
            if posts_match:
                result["posts_count"] = posts_match.group(1)

        # Strip scripts and get visible text
        for tag in soup(["script", "style"]):
            tag.decompose()
        result["raw_text"] = soup.get_text(separator="\n", strip=True)[:4000]

        # Try to pull image alt texts as post captions
        imgs = soup.find_all("img", alt=True)
        for img in imgs[:15]:
            alt = img.get("alt", "").strip()
            if len(alt) > 20:
                result["posts"].append({
                    "caption": alt[:300],
                    "format": "image",
                    "engagement": "N/A",
                    "url": url,
                })

        result["status"] = "scraped"
        print(f"  [+] Instagram @{handle}: {len(result['posts'])} post previews found.")
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        print(f"  [!] Error scraping Instagram @{handle}: {e}")
    return result


def scrape_tiktok_profile(url: str, handle: str) -> dict:
    """Scrape publicly visible data from a TikTok profile page."""
    result = {
        "platform": "tiktok",
        "handle": handle,
        "url": url,
        "bio": "",
        "followers": "N/A",
        "posts_count": "N/A",
        "posts": [],
        "raw_text": "",
        "status": "partial",
    }
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "lxml")

        meta_desc = soup.find("meta", {"name": "description"})
        if meta_desc:
            result["bio"] = meta_desc.get("content", "")[:300]

        # TikTok embeds initial data in __NEXT_DATA__ or window.__INIT_PROPS__
        scripts = soup.find_all("script", string=re.compile(r"__NEXT_DATA__|followerCount", re.I))
        for script in scripts:
            text = script.string or ""
            follower_match = re.search(r'"followerCount"\s*:\s*(\d+)', text)
            if follower_match:
                result["followers"] = str(int(follower_match.group(1)))

            # Extract video descriptions
            desc_matches = re.findall(r'"desc"\s*:\s*"([^"]{20,})"', text)
            for desc in desc_matches[:10]:
                result["posts"].append({
                    "caption": desc[:300],
                    "format": "video",
                    "engagement": "N/A",
                    "url": url,
                })

        for tag in soup(["script", "style"]):
            tag.decompose()
        result["raw_text"] = soup.get_text(separator="\n", strip=True)[:4000]
        result["status"] = "scraped"
        print(f"  [+] TikTok @{handle}: {len(result['posts'])} post previews found.")
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        print(f"  [!] Error scraping TikTok @{handle}: {e}")
    return result


def scrape_profiles(urls: list) -> list:
    profiles = []
    for url in urls:
        url = url.strip()
        if not url:
            continue
        platform = detect_platform(url)
        handle = extract_handle(url)
        print(f"[*] Scraping {platform} profile: @{handle}")
        if platform == "instagram":
            data = scrape_instagram_profile(url, handle)
        elif platform == "tiktok":
            data = scrape_tiktok_profile(url, handle)
        else:
            data = {
                "platform": "unknown",
                "handle": handle,
                "url": url,
                "bio": "",
                "followers": "N/A",
                "posts_count": "N/A",
                "posts": [],
                "raw_text": "",
                "status": "unsupported_platform",
            }
            print(f"  [!] Unsupported platform for URL: {url}")
        profiles.append(data)
        time.sleep(1.5)  # polite delay
    return profiles


def analyze_with_groq(profiles: list) -> dict:
    """Send all profile data to Groq for competitive analysis."""
    if not GROQ_API_KEY:
        print("[!] GROQ_API_KEY not set. Skipping AI analysis.")
        return {
            "competitors": [
                {
                    "handle": p["handle"],
                    "platform": p["platform"],
                    "posting_frequency": "Unknown",
                    "format_mix": {"video": 50, "image": 30, "carousel": 20},
                    "top_themes": ["N/A — set GROQ_API_KEY"],
                    "engagement_estimate": "N/A",
                    "key_insight": "Set GROQ_API_KEY in .env to enable AI analysis.",
                }
                for p in profiles
            ],
            "patterns_they_double_down_on": ["AI analysis requires GROQ_API_KEY"],
            "content_gaps_you_can_exploit": ["AI analysis requires GROQ_API_KEY"],
            "recommended_strategy": "Add your GROQ_API_KEY to the .env file and re-run this agent.",
        }

    client = Groq(api_key=GROQ_API_KEY)

    summary_blocks = []
    for p in profiles:
        posts_sample = "\n".join([f"  - {post['caption']}" for post in p.get("posts", [])[:5]])
        summary_blocks.append(
            f"Profile: @{p['handle']} ({p['platform']})\n"
            f"Followers: {p.get('followers', 'N/A')}\n"
            f"Bio: {p.get('bio', 'N/A')[:200]}\n"
            f"Sample posts:\n{posts_sample or '  (no posts extracted)'}"
        )

    context = "\n\n---\n\n".join(summary_blocks)

    prompt = f"""You are a competitive social media intelligence analyst.

Analyze these competitor social media profiles and return ONLY valid JSON (no markdown):

{context[:5000]}

Return this exact JSON structure:
{{
  "competitors": [
    {{
      "handle": "@handle",
      "platform": "instagram or tiktok",
      "posting_frequency": "e.g. daily, 3x/week",
      "format_mix": {{"video": 60, "image": 25, "carousel": 15}},
      "top_themes": ["theme1", "theme2", "theme3"],
      "engagement_estimate": "e.g. high, medium, low",
      "key_insight": "1-2 sentence insight about this specific competitor"
    }}
  ],
  "patterns_they_double_down_on": ["pattern1", "pattern2", "pattern3"],
  "content_gaps_you_can_exploit": ["gap1", "gap2", "gap3"],
  "recommended_strategy": "2-3 sentence strategic recommendation based on competitive analysis"
}}

Provide one entry per competitor. Make format_mix values sum to 100 per competitor."""

    print("[*] Sending competitive data to Groq for AI analysis...")
    try:
        chat = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=2000,
        )
        raw = chat.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        result = json.loads(raw)
        print("[+] Groq analysis complete.")
        return result
    except Exception as e:
        print(f"[!] Groq error: {e}")
        return {
            "competitors": [
                {
                    "handle": p["handle"],
                    "platform": p["platform"],
                    "posting_frequency": "N/A",
                    "format_mix": {"video": 50, "image": 30, "carousel": 20},
                    "top_themes": [str(e)],
                    "engagement_estimate": "N/A",
                    "key_insight": "Analysis failed.",
                }
                for p in profiles
            ],
            "patterns_they_double_down_on": [str(e)],
            "content_gaps_you_can_exploit": [],
            "recommended_strategy": str(e),
        }


def export_csv(profiles: list, analysis: dict, filename: str):
    """Export top posts to CSV."""
    rows = []
    for profile_data, ai_data in zip(profiles, analysis.get("competitors", [])):
        for post in profile_data.get("posts", [])[:5]:
            rows.append({
                "handle": profile_data["handle"],
                "platform": profile_data["platform"],
                "caption": post.get("caption", ""),
                "format": post.get("format", ""),
                "engagement_estimate": ai_data.get("engagement_estimate", "N/A"),
                "key_insight": ai_data.get("key_insight", ""),
            })

    if not rows:
        rows.append({"handle": "N/A", "platform": "N/A", "caption": "No posts extracted", "format": "", "engagement_estimate": "", "key_insight": ""})

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["handle", "platform", "caption", "format", "engagement_estimate", "key_insight"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"[+] CSV exported: {filename}")


def build_html_report(profiles: list, analysis: dict) -> str:
    timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    competitors = analysis.get("competitors", [])
    patterns = analysis.get("patterns_they_double_down_on", [])
    gaps = analysis.get("content_gaps_you_can_exploit", [])
    strategy = analysis.get("recommended_strategy", "")

    # Build competitor cards
    comp_cards_html = ""
    chart_datasets = []
    chart_labels = ["Video", "Image", "Carousel"]
    chart_colors = ["#6c63ff", "#ff6584", "#43e97b", "#f59e0b", "#06b6d4"]

    for i, (profile, ai) in enumerate(zip(profiles, competitors)):
        handle = profile.get("handle", "unknown")
        platform = profile.get("platform", "")
        followers = profile.get("followers", "N/A")
        themes = ai.get("top_themes", [])
        fmt = ai.get("format_mix", {"video": 50, "image": 30, "carousel": 20})
        insight = ai.get("key_insight", "")
        freq = ai.get("posting_frequency", "N/A")
        engagement = ai.get("engagement_estimate", "N/A")
        platform_icon = "📸" if platform == "instagram" else "🎵" if platform == "tiktok" else "🌐"

        themes_pills = "".join(f'<span class="pill">{t}</span>' for t in themes)

        comp_cards_html += f"""
        <div class="comp-card">
          <div class="comp-header">
            <div>
              <div class="comp-handle">{platform_icon} @{handle}</div>
              <div class="comp-platform">{platform.capitalize()}</div>
            </div>
            <div class="comp-stats">
              <div class="stat-box"><div class="stat-val">{followers}</div><div class="stat-label">Followers</div></div>
              <div class="stat-box"><div class="stat-val">{freq}</div><div class="stat-label">Frequency</div></div>
              <div class="stat-box"><div class="stat-val">{engagement}</div><div class="stat-label">Engagement</div></div>
            </div>
          </div>
          <p class="comp-insight">"{insight}"</p>
          <div class="themes-row">{themes_pills}</div>
        </div>"""

        chart_datasets.append({
            "label": f"@{handle}",
            "data": [fmt.get("video", 0), fmt.get("image", 0), fmt.get("carousel", 0)],
            "backgroundColor": chart_colors[i % len(chart_colors)],
        })

    patterns_html = "".join(f"<li>{p}</li>" for p in patterns)
    gaps_html = "".join(f"<li>{g}</li>" for g in gaps)

    chart_json = json.dumps({
        "labels": chart_labels,
        "datasets": chart_datasets
    })

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Competitor Social Tracker Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f1117; --card: #1a1d27; --accent: #6c63ff;
    --accent2: #ff6584; --accent3: #43e97b; --text: #e2e8f0;
    --muted: #94a3b8; --border: #2d3148;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; }}
  .header {{ background: linear-gradient(135deg, #1a1d27 0%, #0d2d1a 100%); border-bottom: 2px solid var(--accent3); padding: 36px 48px; }}
  .header h1 {{ font-size: 2rem; font-weight: 700; color: #fff; }}
  .header .subtitle {{ color: var(--muted); margin-top: 8px; }}
  .header .ts {{ color: var(--muted); font-size: 0.85rem; margin-top: 12px; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 40px 24px; }}
  .section-title {{ font-size: 1.1rem; font-weight: 600; color: var(--accent); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 20px; }}
  .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 28px; margin-bottom: 24px; }}
  .comp-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 24px; margin-bottom: 20px; }}
  .comp-header {{ display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px; margin-bottom: 16px; }}
  .comp-handle {{ font-size: 1.2rem; font-weight: 700; color: #fff; }}
  .comp-platform {{ color: var(--muted); font-size: 0.85rem; margin-top: 4px; }}
  .comp-stats {{ display: flex; gap: 16px; }}
  .stat-box {{ text-align: center; background: #12151f; padding: 10px 16px; border-radius: 8px; border: 1px solid var(--border); min-width: 80px; }}
  .stat-val {{ font-size: 1rem; font-weight: 700; color: var(--accent3); }}
  .stat-label {{ font-size: 0.72rem; color: var(--muted); margin-top: 4px; text-transform: uppercase; }}
  .comp-insight {{ color: var(--muted); font-style: italic; font-size: 0.9rem; line-height: 1.6; margin-bottom: 14px; }}
  .themes-row {{ display: flex; flex-wrap: wrap; gap: 8px; }}
  .pill {{ background: #1e1b4b; border: 1px solid var(--accent); color: #c4b5fd; padding: 5px 12px; border-radius: 20px; font-size: 0.8rem; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }}
  @media (max-width: 768px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}
  .chart-wrap {{ position: relative; height: 300px; }}
  ul.insight-list {{ list-style: none; padding: 0; }}
  ul.insight-list li {{ padding: 10px 0; border-bottom: 1px solid var(--border); color: var(--text); font-size: 0.92rem; line-height: 1.5; }}
  ul.insight-list li::before {{ content: "→ "; color: var(--accent3); font-weight: 700; }}
  ul.insight-list li:last-child {{ border-bottom: none; }}
  .strategy-text {{ color: var(--text); line-height: 1.7; font-size: 0.95rem; }}
  .footer {{ text-align: center; padding: 32px; color: var(--muted); font-size: 0.82rem; border-top: 1px solid var(--border); margin-top: 20px; }}
</style>
</head>
<body>
<div class="header">
  <h1>Competitor Social Media Tracker</h1>
  <div class="subtitle">AI-powered competitive intelligence across {len(profiles)} profiles</div>
  <div class="ts">Generated: {timestamp}</div>
</div>

<div class="container">

  <!-- Competitor Cards -->
  <div class="section-title">Competitor Profiles</div>
  {comp_cards_html}

  <!-- Charts + Strategy -->
  <div class="grid-2">
    <div class="card">
      <div class="section-title">Format Mix by Competitor</div>
      <div class="chart-wrap"><canvas id="fmtChart"></canvas></div>
    </div>
    <div style="display:flex; flex-direction:column; gap:24px;">
      <div class="card" style="flex:1;">
        <div class="section-title">Patterns They Double Down On</div>
        <ul class="insight-list">{patterns_html}</ul>
      </div>
      <div class="card" style="flex:1;">
        <div class="section-title">Content Gaps You Can Exploit</div>
        <ul class="insight-list">{gaps_html}</ul>
      </div>
    </div>
  </div>

  <!-- Strategy -->
  <div class="card">
    <div class="section-title">Recommended Strategy</div>
    <p class="strategy-text">{strategy}</p>
  </div>

</div>

<div class="footer">
  Generated by The Label AI Studios PH — Competitor Social Tracker &nbsp;|&nbsp; Powered by Groq AI + llama3-70b-8192
</div>

<script>
const chartData = {chart_json};
new Chart(document.getElementById('fmtChart'), {{
  type: 'bar',
  data: chartData,
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      legend: {{ labels: {{ color: '#e2e8f0', font: {{ size: 12 }} }} }}
    }},
    scales: {{
      x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#2d3148' }} }},
      y: {{
        ticks: {{ color: '#94a3b8', callback: v => v + '%' }},
        grid: {{ color: '#2d3148' }},
        min: 0, max: 100
      }}
    }}
  }}
}});
</script>
</body>
</html>"""
    return html


def main():
    args = parse_args()
    urls = [u.strip() for u in args.profiles.split(",") if u.strip()]

    if not urls:
        print("[!] No valid URLs provided. Use --profiles 'url1,url2,...'")
        sys.exit(1)

    print(f"[*] Tracking {len(urls)} competitor profiles...")
    profiles = scrape_profiles(urls)
    analysis = analyze_with_groq(profiles)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_file = f"competitor_tracker_report_{timestamp_str}.html"
    csv_file = f"competitor_top_posts_{timestamp_str}.csv"

    html = build_html_report(profiles, analysis)
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)

    export_csv(profiles, analysis, csv_file)

    print(f"\n[✓] HTML report: {html_file}")
    print(f"[✓] CSV export:  {csv_file}")


if __name__ == "__main__":
    main()
