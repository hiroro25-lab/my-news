#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
パーソナライズドニュースリーダー
GitHub Actions 自動実行版（PDF OCR対応）
"""

import feedparser
import re
import os
import json
import base64
import io
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

# =============================================
# 設定
# =============================================
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
PDF_FOLDER = Path("maritime_pdf")  # リポジトリ内のフォルダ

RSS_SOURCES = {
    "経済・ビジネス": [
    {"name": "東洋経済オンライン",    "url": "https://toyokeizai.net/list/feed/rss"},
    {"name": "ビジネスインサイダー",   "url": "https://www.businessinsider.jp/feed/index.xml"},
    {"name": "日経新聞",             "url": "https://www.nikkei.com/rss/index.rss"},
    {"name": "ロイター経済",          "url": "https://feeds.reuters.com/reuters/JPBusinessNews"},
    {"name": "朝日新聞 経済",         "url": "https://www.asahi.com/rss/asahi/business.rdf"},
],
    "テクノロジー・IT": [
        {"name": "ITmedia NEWS",   "url": "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml"},
        {"name": "Gigazine",       "url": "https://gigazine.net/news/rss_2.0/"},
        {"name": "TechCrunch JP",  "url": "https://jp.techcrunch.com/feed/"},
    ],
    "政治・社会（国内）": [
        {"name": "NHK 主要",   "url": "https://www3.nhk.or.jp/rss/news/cat0.xml"},
        {"name": "朝日新聞",   "url": "https://www.asahi.com/rss/asahi/newsheadlines.rdf"},
    ],
    "国際ニュース": [
        {"name": "NHK 国際",       "url": "https://www3.nhk.or.jp/rss/news/cat6.xml"},
        {"name": "BBC Japan",      "url": "https://feeds.bbci.co.uk/japanese/rss.xml"},
        {"name": "Reuters Japan",  "url": "https://feeds.reuters.com/reuters/JPTopNews"},
    ],
    "物流": [
        {"name": "LNEWS",             "url": "https://lnews.jp/feed",                             "filter": False},
        {"name": "LOGISTICS TODAY", "url": "https://www.logi-today.com/feed", "filter": False},
        {"name": "物流ウィークリー",    "url": "https://www.weekly-net.co.jp/feed",                 "filter": False},
        {"name": "カーゴニュース",      "url": "https://www.cargonews.co.jp/feed",                  "filter": False},
        {"name": "NHK",               "url": "https://www3.nhk.or.jp/rss/news/cat0.xml",          "filter": True},
        {"name": "ITmedia",           "url": "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml", "filter": True},
        {"name": "東洋経済",           "url": "https://toyokeizai.net/list/feed/rss",              "filter": True},
        {"name": "日経新聞",           "url": "https://www.nikkei.com/rss/index.rss",              "filter": True},
        {"name": "ビジネスインサイダー", "url": "https://www.businessinsider.jp/feed/index.xml",    "filter": True},
    ],
}

LOGISTICS_KEYWORDS = [
    "物流", "配送", "輸送", "宅配", "ロジスティクス", "倉庫", "運送",
    "トラック", "ドライバー", "サプライチェーン", "港湾", "航空貨物",
    "2024年問題", "荷物", "配達", "ヤマト", "佐川", "日本郵便",
    "フォワーダー", "通関", "コンテナ", "船舶", "フェリー", "鉄道貨物",
    "ラストワンマイル", "ドローン配送", "自動配送", "置き配", "再配達",
    "3PL", "4PL", "WMS", "TMS", "配車", "運賃", "荷役",
    "港運", "船社", "海運", "岸壁", "埠頭", "ターミナル",
]

MAX_ARTICLES_PER_SOURCE = 8

# =============================================
# RSS取得
# =============================================
def clean_html(text):
    return re.sub(r"<[^>]+>", "", text or "")[:220]

def parse_date(entry):
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6]).strftime("%Y/%m/%d %H:%M")
        except:
            pass
    return entry.get("published", "")

def fetch_rss_news():
    all_news = {}
    for genre, sources in RSS_SOURCES.items():
        articles = []
        seen_titles = set()
        for source in sources:
            do_filter = source.get("filter", False)
            try:
                print(f"  取得中: {source['name']} ...", end="", flush=True)
                feed = feedparser.parse(source["url"])
                count = 0
                for entry in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
                    title    = entry.get("title", "タイトルなし")
                    link     = entry.get("link", "#")
                    summary  = clean_html(entry.get("summary", entry.get("description", "")))
                    pub_date = parse_date(entry)
                    if title in seen_titles:
                        continue
                    if do_filter:
                        if not any(kw in title + summary for kw in LOGISTICS_KEYWORDS):
                            continue
                    seen_titles.add(title)
                    articles.append({"title": title, "link": link, "summary": summary,
                                     "pub_date": pub_date, "source": source["name"]})
                    count += 1
                print(f" {count}件")
            except Exception as e:
                print(f" エラー: {e}")
        all_news[genre] = articles
    return all_news

# =============================================
# マリタイムPDF → Claude OCR
# =============================================
def pdf_to_images_base64(pdf_path):
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(str(pdf_path), dpi=72, first_page=1, last_page=4)
        result = []
        for img in images:
            w, h = img.size
            img = img.resize((w//2, h//2))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=70)
            b64 = base64.b64encode(buf.getvalue()).decode()
            result.append(b64)
        return result
    except ImportError:
        print("  pdf2imageが必要です")
        return []
    except Exception as e:
        print(f"  PDF変換エラー: {e}")
        return []

def extract_articles_with_claude(pdf_path):
    if not ANTHROPIC_API_KEY:
        print("  APIキーが設定されていません（スキップ）")
        return []

    print(f"  PDFを画像に変換中...", end="", flush=True)
    images_b64 = pdf_to_images_base64(pdf_path)
    if not images_b64:
        return []
    print(f" {len(images_b64)}ページ完了")

    fname = pdf_path.stem
    pub_date = ""
    date_match = re.match(r'(\d{4})(\d{2})(\d{2})', fname)
    if date_match:
        pub_date = f"{date_match.group(1)}/{date_match.group(2)}/{date_match.group(3)}"

    print(f"  Claude APIで記事抽出中...", end="", flush=True)

    content = []
    for b64 in images_b64:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}
        })
    content.append({
        "type": "text",
        "text": """このPDFはマリタイムデーリーニュースという海運・港湾・物流専門の日刊紙です。
各ページから記事のタイトルとサブタイトル、本文の要約（2〜3文）を抽出してください。

必ず以下のJSON形式だけで返してください。他のテキストは不要です：
[
  {
    "title": "記事タイトル",
    "sub": "サブタイトル（なければ空文字）",
    "summary": "本文の要約2〜3文"
  }
]"""
    })

    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 3000,
        "messages": [{"role": "user", "content": content}]
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as res:
            result = json.loads(res.read())
        raw = result["content"][0]["text"]
        raw = re.sub(r"```json|```", "", raw).strip()
        articles_data = json.loads(raw)
        articles = []
        for art in articles_data:
            articles.append({
                "title":    art.get("title", ""),
                "sub":      art.get("sub", ""),
                "summary":  art.get("summary", ""),
                "pub_date": pub_date,
                "source":   "マリタイムデーリーニュース",
                "link":     "#"
            })
        print(f" {len(articles)}件")
        return articles
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f" HTTPエラー {e.code}: {body[:300]}")
        return []
    except Exception as e:
        print(f" エラー: {e}")
        return []

def fetch_maritime_news():
    print(f"  [マリタイム] PDFを検索中...", end="", flush=True)
    if not PDF_FOLDER.exists():
        print(f" フォルダなし → スキップ")
        return []
    pdfs = sorted(PDF_FOLDER.glob("*.pdf"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not pdfs:
        print(f" PDFなし → スキップ")
        return []
    print(f" {pdfs[0].name} を発見")
    return extract_articles_with_claude(pdfs[0])

# =============================================
# HTML生成
# =============================================
def generate_html(all_news, maritime_articles):
    genre_meta = {
        "経済・ビジネス":            ("#1a3a5c", "#e8f0fe", "📈"),
        "テクノロジー・IT":          ("#0d3b2e", "#e6f4ea", "💻"),
        "政治・社会（国内）":        ("#3b1a1a", "#fce8e6", "🏛"),
        "国際ニュース":              ("#2c1a4a", "#f3e8fd", "🌍"),
        "物流":                      ("#1a3030", "#e6f4f1", "🚚"),
        "マリタイムデーリーニュース": ("#1a2a4a", "#e8eef8", "🚢"),
    }

    if maritime_articles:
        all_news["マリタイムデーリーニュース"] = maritime_articles
now = datetime.now(timezone(timedelta(hours=9))).strftime("%Y年%m月%d日 %H:%M")
    tabs_html = ""
    panels_html = ""

    for i, (genre, articles) in enumerate(all_news.items()):
        color, bg, icon = genre_meta.get(genre, ("#333", "#f5f5f5", "📰"))
        tab_id = f"tab{i}"
        active = "active" if i == 0 else ""
        tabs_html += f'<button class="tab-btn {active}" data-tab="{tab_id}" style="--accent:{color}">{icon} {genre} <span class="badge">{len(articles)}</span></button>\n'

        cards_html = ""
        if articles:
            for art in articles:
                sub_html = f'<p class="card-sub">{art.get("sub","")}</p>' if art.get("sub") else ""
                link_attr = f'href="{art["link"]}" target="_blank"' if art.get("link","#") != "#" else 'href="#"'
                cards_html += f"""
                <article class="card">
                    <div class="card-meta">
                        <span class="source-tag" style="background:{color}">{art['source']}</span>
                        <span class="pub-date">{art['pub_date']}</span>
                    </div>
                    <h3 class="card-title"><a {link_attr}>{art['title']}</a></h3>
                    {sub_html}
                    <p class="card-summary">{art['summary']}</p>
                </article>"""
        else:
            cards_html = '<p class="no-news">記事を取得できませんでした。</p>'

        panels_html += f"""
        <div id="{tab_id}" class="tab-panel {active}" style="--panel-bg:{bg};--panel-accent:{color}">
            <div class="panel-header">
                <span class="panel-icon">{icon}</span>
                <h2>{genre}</h2>
                <span class="article-count">{len(articles)}件の記事</span>
            </div>
            <div class="cards-grid">{cards_html}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>マイニュース</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+JP:wght@400;700&family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">
<style>
  :root{{--bg:#f7f4ef;--surface:#fff;--text:#1a1a1a;--text-muted:#666;--border:#e0dbd4;--shadow:0 2px 12px rgba(0,0,0,0.08);}}
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{font-family:'Noto Sans JP',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;}}
  header{{background:#1a1a2e;color:white;padding:20px 32px;display:flex;align-items:center;justify-content:space-between;box-shadow:0 2px 16px rgba(0,0,0,0.3);}}
  header h1{{font-family:'Noto Serif JP',serif;font-size:1.6rem;letter-spacing:0.05em;}}
  .update-time{{font-size:0.8rem;color:#aaa;}}
  .tab-nav{{display:flex;gap:4px;padding:16px 24px 0;background:#1a1a2e;overflow-x:auto;}}
  .tab-btn{{padding:10px 18px;border:none;border-radius:8px 8px 0 0;background:rgba(255,255,255,0.1);color:#ccc;font-family:'Noto Sans JP',sans-serif;font-size:0.85rem;cursor:pointer;white-space:nowrap;transition:all 0.2s;display:flex;align-items:center;gap:6px;}}
  .tab-btn:hover{{background:rgba(255,255,255,0.2);color:white;}}
  .tab-btn.active{{background:var(--bg);color:var(--accent);font-weight:700;}}
  .badge{{background:rgba(255,255,255,0.25);border-radius:12px;padding:1px 7px;font-size:0.75rem;}}
  .tab-btn.active .badge{{background:rgba(0,0,0,0.1);}}
  .main{{padding:0 24px 40px;}}
  .tab-panel{{display:none;}}
  .tab-panel.active{{display:block;}}
  .panel-header{{display:flex;align-items:center;gap:12px;padding:24px 0 16px;border-bottom:2px solid var(--panel-accent);margin-bottom:20px;}}
  .panel-icon{{font-size:1.8rem;}}
  .panel-header h2{{font-family:'Noto Serif JP',serif;font-size:1.4rem;color:var(--panel-accent);}}
  .article-count{{margin-left:auto;font-size:0.8rem;color:var(--text-muted);background:var(--panel-bg);border:1px solid var(--border);border-radius:20px;padding:3px 12px;}}
  .cards-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px;}}
  .card{{background:var(--surface);border-radius:10px;padding:18px;box-shadow:var(--shadow);border-top:3px solid var(--panel-accent);transition:transform 0.2s,box-shadow 0.2s;}}
  .card:hover{{transform:translateY(-3px);box-shadow:0 6px 20px rgba(0,0,0,0.12);}}
  .card-meta{{display:flex;align-items:center;gap:8px;margin-bottom:10px;flex-wrap:wrap;}}
  .source-tag{{color:white;font-size:0.7rem;padding:2px 8px;border-radius:4px;font-weight:700;}}
  .pub-date{{font-size:0.75rem;color:var(--text-muted);}}
  .card-title{{font-family:'Noto Serif JP',serif;font-size:0.95rem;line-height:1.6;margin-bottom:4px;}}
  .card-title a{{color:var(--text);text-decoration:none;}}
  .card-title a:hover{{color:var(--panel-accent);text-decoration:underline;}}
  .card-sub{{font-size:0.82rem;color:var(--panel-accent);margin-bottom:6px;font-weight:500;}}
  .card-summary{{font-size:0.8rem;color:var(--text-muted);line-height:1.6;}}
  .no-news{{color:var(--text-muted);font-style:italic;padding:20px;}}
  @media(max-width:600px){{
    header{{padding:14px 16px;}}
    header h1{{font-size:1.2rem;}}
    .tab-nav{{padding:10px 8px 0;}}
    .tab-btn{{padding:8px 12px;font-size:0.78rem;}}
    .main{{padding:0 12px 32px;}}
    .cards-grid{{grid-template-columns:1fr;}}
  }}
</style>
</head>
<body>
<header>
  <h1>📰 マイニュース</h1>
  <span class="update-time">更新: {now} (JST)</span>
</header>
<nav class="tab-nav">{tabs_html}</nav>
<main class="main">{panels_html}</main>
<script>
  document.querySelectorAll('.tab-btn').forEach(btn=>{{
    btn.addEventListener('click',()=>{{
      document.querySelectorAll('.tab-btn,.tab-panel').forEach(el=>el.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(btn.dataset.tab).classList.add('active');
    }});
  }});
</script>
</body>
</html>"""

# =============================================
# メイン
# =============================================
if __name__ == "__main__":
    print("=" * 50)
    print("  マイニュースリーダー 起動中")
    print("=" * 50)
    print("\n📡 RSSフィードを取得中...\n")
    all_news = fetch_rss_news()
    print("\n🚢 マリタイムPDFを処理中...")
    maritime = fetch_maritime_news()
    total = sum(len(v) for v in all_news.values()) + len(maritime)
    print(f"\n✅ 合計 {total} 件の記事を取得しました")
    print("\n📄 HTMLを生成中...")
    html = generate_html(all_news, maritime)
    output_path = Path("index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ 完成！ → {output_path}")
    print("=" * 50)
