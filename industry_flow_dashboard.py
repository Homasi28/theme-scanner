"""Generate a self-contained interactive industry-leadership dashboard."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


TIMEFRAMES = {
    "1w": "is_top_1w",
    "1m": "is_top_1m",
    "3m": "is_top_3m",
    "6m": "is_top_6m",
}

# Related industries roll up so a Semis kickoff is not missed when
# leadership spreads across peripherals / equipment names.
THEME_CLUSTERS = {
    "Semis complex": frozenset({
        "Semiconductors",
        "Computer Peripherals",
        "Computer Processing Hardware",
        "Electronic Production Equipment",
        "Electronic Equipment/Instruments",
        "Electronics/Appliances",
    }),
}

RISING_MIN_COUNT = 2
RISING_MIN_DELTA = 1

# Named narrative themes defined by an explicit ticker list, e.g. "AI Memory".
# These are tracked alongside TradingView's industry labels, never merged into
# them: a basket is a hand-curated view, an industry is exchange taxonomy.
# Edit theme_baskets.json to add, remove, or re-scope a basket.
BASKETS_FILE = Path(__file__).with_name("theme_baskets.json")


def load_theme_baskets(path: Path = BASKETS_FILE) -> dict[str, frozenset[str]]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(name): frozenset(str(ticker).strip().upper() for ticker in tickers if str(ticker).strip())
        for name, tickers in raw.items()
    }


THEME_BASKETS = load_theme_baskets()

# Livingston's voice in Edwin Lefèvre, Reminiscences of a Stock Operator (1923).
# Public domain in the USA. Short lines only — not passages from later books.
LIVERMORE_QUOTES = [
    "There is nothing new in Wall Street. There can't be because speculation is as old as the hills. Whatever happens in the stock market today has happened before and will happen again.",
    "A battle goes on in the stock market and the tape is your telescope. You can depend upon it seven out of ten cases.",
    "I didn't ask the tape why when I was fourteen, and I don't ask it today, at forty. Your business with the tape is now — not tomorrow. The reason can wait.",
    "I kept my business to myself. It was a one-man business. That is why I have always played a lone hand.",
    "I was playing a system and not a favorite stock or backing opinions.",
    "There is the plain fool, who does the wrong thing at all times everywhere, but there is the Wall Street fool, who thinks he must trade all the time.",
    "No man can always have adequate reasons for buying or selling stocks daily — or sufficient knowledge to make his play an intelligent play.",
    "Whenever I read the tape by the light of experience I made money, but when I made a plain fool play I had to lose.",
    "The desire for constant action irrespective of underlying conditions is responsible for many losses in Wall Street even among the professionals, who feel that they must take home some money every day, as though they were working for regular wages.",
    "I always made money when I was sure I was right before I began. What beat me was not having brains enough to stick to my own game — to play the market only when I was satisfied that precedents favored my play.",
    "There is a time for all things, but I didn't know it. And that is precisely what beats so many men in Wall Street.",
    "I never lose my temper over the stock market. I never argue with the tape. Getting sore at the market doesn't get you anywhere.",
    "There wasn't anything wrong with me; only with my play.",
    "It takes a man a long time to learn all the lessons of all his mistakes.",
    "There is only one side to the stock market; and it is not the bull side or the bear side, but the right side.",
    "A man must believe in himself and his judgment if he expects to make a living at this game. That is why I don't believe in tips.",
    "Nobody can make big money on what someone else tells him to do.",
    "If I buy stocks on Smith's tip I must sell those same stocks on Smith's tip. I am depending on him.",
    "The game taught me the game. And it didn't spare the rod while teaching.",
    "Reading the tape like an expert did not save me.",
    "In A. R. Fullerton's office the tape always talked ancient history to me, as far as my system of trading went, and I didn't realise it.",
    "It was not that I was playing it legitimately that made me lose, but that I was playing it ignorantly.",
    "Of course I let the craving for excitement get the better of my judgment.",
    "I was accustomed to regarding the tape as the best little friend I had, because I bet according to what it told me. But this time the tape double-crossed me.",
    "It took me five years to learn to play the game intelligently enough to make big money when I was right.",
    "I thought I was beating the game when in reality I was only beating the shop.",
    "The market does not beat them. They beat themselves, because though they have brains they cannot sit tight.",
    "Old Turkey was dead right in doing and saving what he did. He had not only the courage of his convictions but the intelligent patience to sit tight.",
    "Disregarding the big swing and trying to jump in and out was fatal to me. Nobody can catch all the fluctuations.",
    "In a bull market your game is to buy and hold until you believe that the bull market is near its end.",
    "To do this you must study the general conditions and not tips or special factors affecting individual stocks. Then get out of all your stocks; get out for keeps!",
    "The big money was not in the individual fluctuations but in the main movements — not in reading the tape but in sizing up the entire market and its trend.",
    "When old Mr. Partridge kept on telling the other customers, \"Well, you know this is a bull market!\" he really meant to tell them that the big money was not in the individual fluctuations but in the main movements.",
    "It never was my thinking that made the big money for me. It always was my sitting. My sitting tight!",
    "It is no trick at all to be right on the market. You always find lots of early bulls in bull markets and early bears in bear markets.",
    "Men who can both be right and sit tight are uncommon. I found it one of the hardest things to learn.",
    "It is literally true that millions come easier to a trader after he knows how to trade than hundreds did in the days of his ignorance.",
    "A man may see straight and clearly and yet become impatient or doubtful when the market takes its time about doing as he figured it must do.",
    "They say you never grow poor taking profits. No, you don't. But neither do you grow rich taking a four-point profit in a bull market.",
    "Of all speculative blunders there are few greater than trying to average a losing game.",
    "Always sell what shows you a loss and keep what shows you a profit.",
    "The cotton showed me a loss and I kept it. The wheat showed me a profit and I sold it out.",
    "The speculator's chief enemies are always boring from within.",
    "It is inseparable from human nature to hope and to fear.",
    "When the market goes against you, you hope that every day will be the last day — and you lose more than you should had you not listened to hope.",
    "When the market goes your way you become fearful that the next day will take away your profit, and you get out — too soon.",
    "Fear keeps you from making as much money as you ought to. The successful trader has to fight these two deep-seated instincts.",
    "Instead of hoping he must fear; instead of fearing he must hope. He must fear that his loss may develop into a much bigger loss, and hope that his profit may become a big profit.",
    "The speculator's deadly enemies are ignorance, greed, fear and hope. All the statute books in the world and all the rules of all the Exchanges on earth cannot eliminate these from the human animal.",
    "If a stock doesn't act right don't touch it; because, being unable to tell precisely what is wrong, you cannot tell which way it is going. No diagnosis, no prognosis. No prognosis, no profit.",
    "It is enough for the experienced trader to perceive that something is wrong. He must not expect the tape to become a lecturer. His job is to listen for it to say \"Get out!\"",
    "Prices, like everything else, move along the line of least resistance. They will go up if there is less resistance to an advance than to a decline; and vice versa.",
    "The trend is evident to a man who has an open mind and reasonably clear sight, for it is never wise for a speculator to fit his facts to his theories.",
    "The speculator is not an investor. His object is not to secure a steady return on his money at a good rate of interest, but to profit by either a rise or a fall in the price of whatever he may be speculating in.",
    "A man cannot be convinced against his own convictions, but he can be talked into a state of uncertainty and indecision, which is even worse, for that means that he cannot trade with confidence and comfort.",
    "The professional concerns himself with doing the right thing rather than with making money, knowing that the profit takes care of itself if the other things are attended to.",
    "A trader gets to play the game as the professional billiard player does — he looks far ahead instead of considering the particular shot before him.",
    "I have always found it profitable to study my mistakes.",
    "It was all very well not to lose your bear position in a bear market, but at all times the tape should be read to determine the propitiousness of the time for operating.",
    "Observation, experience, memory and mathematics — these are what the successful trader must depend on.",
    "He must not only observe accurately but remember at all times what he has observed.",
    "He cannot bet on the unreasonable or on the unexpected, however strong his personal convictions may be.",
    "The principles of successful stock speculation are based on the supposition that people will continue in the future to make the mistakes that they have made in the past.",
    "The public is so often whipsawed that one marvels at their persistence in not learning their lesson.",
    "The average man doesn't wish to be told that it is a bull or a bear market. What he desires is to be told specifically which particular stock to buy or sell.",
    "He wants to get something for nothing. He does not wish to work. He doesn't even wish to have to think.",
    "I never hesitate to tell a man that I am bullish or bearish. But I do not tell people to buy or sell any particular stock.",
    "In a bear market all stocks go down and in a bull market they go up.",
    "To buy on a rising market is the most comfortable way of buying stocks. The point is not to buy as cheap as possible or go short at top prices, but to buy or sell at the right time.",
    "When I am bearish and I sell a stock, each sale must be at a lower level than the previous sale. When I am buying, the reverse is true. I must buy on a rising scale.",
    "I don't buy long stock on a scale down. I buy on a scale up.",
    "Remember that stocks are never too high for you to begin buying or too low to begin selling.",
    "After the initial transaction, don't make a second unless the first shows you a profit. Wait and watch.",
    "Never try to sell at the top. It isn't wise. Sell after a reaction if there is no rally.",
    "Give up trying to catch the last eighth — or the first. These two are the most expensive eighths in the world.",
    "The man who is right always has two forces working in his favor — basic conditions and the men who are wrong.",
    "In a bull market bear factors are ignored. That is human nature.",
    "A man may possess an original mind and a lifelong habit of independent thinking and withal be vulnerable to attacks by a persuasive personality.",
    "The training of a stock trader is like a medical education. He learns the theory and then proceeds to devote his life to the practice.",
    "He must not permit himself set opinions. He must have an open mind and flexibility.",
    "It is not wise to disregard the message of the tape, no matter what your opinion of crop conditions or of the probable demand may be.",
    "The weaknesses to which a speculator is prone are almost numberless.",
    "I have been in the speculative game ever since I was fourteen. It is all I have ever done.",
    "A man may beat a stock or a group at a certain time, but no man living can beat the stock market!",
]


RECORD_COLUMNS = [
    "name",
    "industry",
    "exchange",
    "Perf.1M",
    "Perf.3M",
    "Perf.6M",
    "Perf.W",
    "average_dollar_volume_30d",
    "dollar_volume_30d",
    "atr_extension_from_50d",
    "is_top_1w",
    "is_top_1m",
    "is_top_3m",
    "is_top_6m",
    "earnings_soon",
    "earnings_date",
    "tradingview_url",
]


def _records_from_frame(frame: pd.DataFrame) -> list[dict]:
    columns = [column for column in RECORD_COLUMNS if column in frame.columns]
    if "name" not in columns:
        return []
    return json.loads(frame.loc[:, columns].to_json(orient="records"))


# Member rows use short keys because this list is the bulk of the embedded
# payload: n=name, i=industry, e=exchange, then the four performance windows.
MEMBER_KEYS = {"name": "n", "industry": "i", "exchange": "e", "Perf.W": "1w", "Perf.1M": "1m", "Perf.3M": "3m", "Perf.6M": "6m"}


def _performance_records(*paths: Path) -> dict[str, dict[str, list[dict]]]:
    """Performance CSVs -> {scope: {window: [rows ranked best first]}}.

    Takes both the TradingView-derived file and, when a local run managed to
    fetch it, Finviz's own group table. They share a schema and differ only in
    the `scope` column, so the dashboard can toggle between taxonomies.
    """
    frames = [pd.read_csv(path) for path in paths if path.exists()]
    frames = [frame for frame in frames if not frame.empty and "scope" in frame.columns]
    if not frames:
        return {}
    combined = pd.concat(frames, ignore_index=True)
    out: dict[str, dict[str, list[dict]]] = {}
    for (scope, window), group in combined.groupby(["scope", "window"]):
        ranked = group.sort_values("median_pct", ascending=False)
        rows = []
        for row in ranked.itertuples():
            record = {
                "industry": str(row.industry),
                "median": float(row.median_pct),
                "mean": float(row.mean_pct),
            }
            members = getattr(row, "members", None)
            if members is not None and not pd.isna(members):
                record["members"] = int(members)
            slug = getattr(row, "slug", None)
            if slug is not None and not pd.isna(slug) and str(slug):
                record["slug"] = str(slug)
            rows.append(record)
        out.setdefault(str(scope), {})[str(window)] = rows
    return out


def _finviz_member_records(path: Path) -> dict[str, list[dict]]:
    """finviz_group_members CSV -> {industry: [names ranked by the week]}."""
    if not path.exists():
        return {}
    frame = pd.read_csv(path)
    if frame.empty or "industry" not in frame.columns:
        return {}
    windows = [column for column in ("1w", "1m", "3m", "6m") if column in frame.columns]
    slim = frame.loc[:, ["industry", "rank", "ticker", *windows]].sort_values(["industry", "rank"])
    out: dict[str, list[dict]] = {}
    for industry, group in slim.groupby("industry"):
        records = []
        for row in group.to_dict(orient="records"):
            record = {"t": str(row["ticker"])}
            for window in windows:
                value = row[window]
                record[window] = None if pd.isna(value) else float(value)
            records.append(record)
        out[str(industry)] = records
    return out


def _member_records(path: Path) -> list[dict]:
    """Eligible-universe rows, slimmed down, for the industry drill-down."""
    if not path.exists():
        return []
    frame = pd.read_csv(path)
    if frame.empty or "name" not in frame.columns:
        return []
    columns = [column for column in MEMBER_KEYS if column in frame.columns]
    slim = frame.loc[:, columns].rename(columns=MEMBER_KEYS)
    return json.loads(slim.to_json(orient="records"))


def _cluster_counts(groups: dict[str, int], members: frozenset[str]) -> int:
    return sum(int(groups.get(name, 0) or 0) for name in members)


def _signal_for_rise(prior: int, current: int) -> str | None:
    delta = current - prior
    if delta < RISING_MIN_DELTA or current < RISING_MIN_COUNT:
        return None
    # Fresh breadth: new or thin theme expanding into real participation.
    if prior == 0 or (prior <= 1 and current >= 3):
        return "KICKOFF"
    return "RISING"


def detect_rising_themes(
    current_groups: dict[str, dict[str, int]] | None,
    prior_groups: dict[str, dict[str, int]] | None,
    *,
    primary_frame: str = "1m",
    current_baskets: dict[str, dict[str, int]] | None = None,
    prior_baskets: dict[str, dict[str, int]] | None = None,
) -> list[dict]:
    """Flag industries, clusters, and ticker baskets whose count is expanding."""
    current_groups = current_groups or {}
    prior_groups = prior_groups or {}
    current_baskets = current_baskets or {}
    prior_baskets = prior_baskets or {}
    frames = [primary_frame] + [frame for frame in TIMEFRAMES if frame != primary_frame]
    rising: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for frame in frames:
        now = current_groups.get(frame) or {}
        then = prior_groups.get(frame) or {}
        industries = set(now) | set(then)
        for industry in industries:
            current = int(now.get(industry, 0) or 0)
            prior = int(then.get(industry, 0) or 0)
            signal = _signal_for_rise(prior, current)
            if not signal:
                continue
            key = (frame, industry)
            if key in seen:
                continue
            seen.add(key)
            rising.append({
                "frame": frame,
                "industry": industry,
                "kind": "industry",
                "prior_count": prior,
                "current_count": current,
                "delta": current - prior,
                "signal": signal,
            })
        for cluster_name, members in THEME_CLUSTERS.items():
            current = _cluster_counts(now, members)
            prior = _cluster_counts(then, members)
            signal = _signal_for_rise(prior, current)
            if not signal:
                continue
            key = (frame, cluster_name)
            if key in seen:
                continue
            seen.add(key)
            rising.append({
                "frame": frame,
                "industry": cluster_name,
                "kind": "cluster",
                "prior_count": prior,
                "current_count": current,
                "delta": current - prior,
                "signal": signal,
                "members": sorted(members),
            })
        now_baskets = current_baskets.get(frame) or {}
        then_baskets = prior_baskets.get(frame) or {}
        for basket in set(now_baskets) | set(then_baskets):
            current = int(now_baskets.get(basket, 0) or 0)
            prior = int(then_baskets.get(basket, 0) or 0)
            signal = _signal_for_rise(prior, current)
            if not signal:
                continue
            key = (frame, basket)
            if key in seen:
                continue
            seen.add(key)
            rising.append({
                "frame": frame,
                "industry": basket,
                "kind": "basket",
                "prior_count": prior,
                "current_count": current,
                "delta": current - prior,
                "signal": signal,
            })

    rising.sort(
        key=lambda row: (
            0 if row["frame"] == primary_frame else 1,
            0 if row["signal"] == "KICKOFF" else 1,
            -int(row["delta"]),
            -int(row["current_count"]),
            str(row["industry"]),
        )
    )
    return rising


def rising_industry_names(rising: list[dict], *, frame: str | None = "1m") -> set[str]:
    """Industries to highlight on desk lists for a rising / kickoff theme."""
    names: set[str] = set()
    for row in rising:
        if frame is not None and row.get("frame") != frame:
            continue
        kind = row.get("kind")
        if kind == "basket":
            # Baskets are ticker lists, not industries; matched separately.
            continue
        if kind == "cluster":
            names.update(row.get("members") or [])
        else:
            names.add(str(row["industry"]))
    return names


def rising_basket_symbols(rising: list[dict], *, frame: str | None = "1m") -> set[str]:
    """Tickers belonging to a rising basket, for highlighting desk rows."""
    symbols: set[str] = set()
    for row in rising:
        if frame is not None and row.get("frame") != frame:
            continue
        if row.get("kind") != "basket":
            continue
        symbols.update(THEME_BASKETS.get(str(row["industry"]), frozenset()))
    return symbols


def annotate_rising_themes(snapshots: list[dict]) -> list[dict]:
    for index, snapshot in enumerate(snapshots):
        prior = snapshots[index - 1] if index else None
        rising = detect_rising_themes(
            snapshot.get("groups"),
            prior.get("groups") if prior else None,
            current_baskets=snapshot.get("baskets"),
            prior_baskets=prior.get("baskets") if prior else None,
        )
        snapshot["rising_themes"] = rising
        snapshot["rising_industries"] = sorted(rising_industry_names(rising, frame="1m"))
        snapshot["rising_basket_symbols"] = sorted(rising_basket_symbols(rising, frame="1m"))
    return snapshots


def write_rising_theme_csvs(output_dir: Path, snapshots: list[dict]) -> list[Path]:
    """Persist rising-theme flags beside the daily scan outputs."""
    written: list[Path] = []
    export_dir = output_dir / "EXPORT"
    export_dir.mkdir(parents=True, exist_ok=True)
    for snapshot in snapshots:
        rising = snapshot.get("rising_themes") or []
        stamp = snapshot["date"]
        path = output_dir / f"rising_themes_{stamp}.csv"
        rows = []
        for item in rising:
            rows.append({
                "date": stamp,
                "frame": item.get("frame"),
                "kind": item.get("kind"),
                "industry": item.get("industry"),
                "signal": item.get("signal"),
                "prior_count": item.get("prior_count"),
                "current_count": item.get("current_count"),
                "delta": item.get("delta"),
                "members": "|".join(item.get("members") or []),
            })
        frame = pd.DataFrame(rows, columns=[
            "date", "frame", "kind", "industry", "signal",
            "prior_count", "current_count", "delta", "members",
        ])
        frame.to_csv(path, index=False)
        written.append(path)

        rising_set = set(snapshot.get("rising_industries") or [])
        rising_tickers = set(snapshot.get("rising_basket_symbols") or [])
        symbols = sorted({
            name
            for row in (snapshot.get("liquid") or [])
            for name in [str(row.get("name") or "").strip()]
            if name and (
                str(row.get("industry") or "").strip() in rising_set
                or name.upper() in rising_tickers
            )
        })
        symbol_path = export_dir / f"rising_theme_symbols_{stamp}.csv"
        pd.DataFrame({"symbol": symbols}).to_csv(symbol_path, index=False)
        written.append(symbol_path)

        basket_rows = [
            {"date": stamp, "frame": frame, "basket": basket, "leaders": count}
            for frame, counts in (snapshot.get("baskets") or {}).items()
            for basket, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ]
        basket_path = output_dir / f"theme_baskets_{stamp}.csv"
        pd.DataFrame(basket_rows, columns=["date", "frame", "basket", "leaders"]).to_csv(basket_path, index=False)
        written.append(basket_path)
    return written


def collect_industry_history(output_dir: Path) -> list[dict]:
    """Summarise every dated momentum-leader snapshot by industry and timeframe."""
    snapshots = []
    for path in sorted(output_dir.glob("momentum_leaders_*.csv")):
        match = re.search(r"(\d{4}-\d{2}-\d{2})\.csv$", path.name)
        if not match:
            continue
        frame = pd.read_csv(path)
        if "industry" not in frame.columns:
            continue
        groups = {}
        baskets = {}
        for label, flag in TIMEFRAMES.items():
            if flag not in frame.columns:
                continue
            window = frame.loc[frame[flag].fillna(False).astype(bool)]
            counts = window["industry"].fillna("Unclassified").value_counts().to_dict()
            groups[label] = {str(industry): int(count) for industry, count in counts.items()}
            symbols = {str(name).strip().upper() for name in window["name"].dropna()}
            baskets[label] = {
                basket: len(symbols & tickers)
                for basket, tickers in THEME_BASKETS.items()
                if symbols & tickers
            }
        stamp = match.group(1)
        # `groups`, `baskets` and `liquid` all come from the full momentum-leader
        # file, so nothing narrower can distort theme leadership.
        snapshots.append({
            "date": stamp,
            "groups": groups,
            "baskets": baskets,
            "liquid": _records_from_frame(frame),
            "performance": _performance_records(
                output_dir / f"industry_performance_{stamp}.csv",
                output_dir / f"finviz_groups_{stamp}.csv",
            ),
            "members": _member_records(output_dir / f"filtered_universe_{stamp}.csv"),
            "finviz_members": _finviz_member_records(output_dir / f"finviz_group_members_{stamp}.csv"),
        })
    return annotate_rising_themes(snapshots)


def write_dashboard(output_dir: Path) -> Path:
    """Write an offline-friendly interactive dashboard with embedded history."""
    history = collect_industry_history(output_dir)
    write_rising_theme_csvs(output_dir, history)
    dashboard = Path("industry_flow_dashboard.html")
    pages_entrypoint = Path("index.html")
    # `liquid` is the full leader list. The CSV exports above need it, the page
    # does not, and it is the single largest thing in the payload.
    browser_history = [
        {key: value for key, value in snapshot.items() if key != "liquid"}
        for snapshot in history
    ]
    payload = json.dumps(browser_history, separators=(",", ":"))
    quotes_payload = json.dumps(LIVERMORE_QUOTES, ensure_ascii=False, separators=(",", ":"))
    template = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>THM &lt;GO&gt; | Theme Scanner</title>
  <meta name="description" content="Track which industries are gaining leadership among the market’s most liquid momentum stocks.">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="https://homasi28.github.io/theme-scanner/">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Theme Scanner">
  <meta property="og:title" content="THM <GO> | Theme Scanner">
  <meta property="og:description" content="Track which industries are gaining leadership among the market’s most liquid momentum stocks.">
  <meta property="og:url" content="https://homasi28.github.io/theme-scanner/">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="THM <GO> | Theme Scanner">
  <meta name="twitter:description" content="Track which industries are gaining leadership among the market’s most liquid momentum stocks.">
  <link rel="preload" href="assets/fonts/ibm-plex-mono-latin-400.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="tokens.css">
  <style>
html { color-scheme: dark; }
html, body { overflow-x: clip; overflow-anchor: none; }
* { box-sizing: border-box; }
html { background: var(--color-paper); }
body {
  margin: 0;
  background: var(--color-paper);
  color: var(--color-ink-2);
  font-family: var(--font-body);
  font-weight: 400;
  font-size: var(--text-base);
  line-height: 1.35;
  -webkit-text-size-adjust: 100%;
  text-size-adjust: 100%;
  overscroll-behavior-y: contain;
}
main { min-height: 100dvh; }
img, svg, table { max-width: 100%; }
h1, h2, h3 {
  font-family: var(--font-display);
  font-style: normal;
  font-weight: 400;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-accent);
  overflow-wrap: anywhere;
  min-width: 0;
  line-height: 1;
  scroll-margin-top: calc(var(--banner-height) + var(--mobile-nav-keys, 0px) + var(--space-xs));
}
#qotd { scroll-margin-top: calc(var(--banner-height) + var(--mobile-nav-keys, 0px)); }
a { color: inherit; }
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
.skip-link {
  position: absolute;
  left: var(--space-sm);
  top: var(--space-sm);
  z-index: var(--z-sticky-nav);
  padding: var(--space-xs) var(--space-sm);
  background: var(--color-accent);
  color: var(--color-accent-ink);
  font-family: var(--font-display);
  text-decoration: none;
  transform: translateY(-200%);
  white-space: nowrap;
}
.skip-link:focus-visible { transform: none; outline: 2px solid var(--color-focus); outline-offset: var(--space-3xs); }

.chamfer {
  clip-path: polygon(8px 0, 100% 0, 100% calc(100% - 8px), calc(100% - 8px) 100%, 0 100%, 0 8px);
}

.nav-edge {
  position: sticky;
  top: 0;
  z-index: var(--z-sticky-nav);
  display: flex;
  justify-content: space-between;
  align-items: stretch;
  gap: var(--space-sm);
  min-height: var(--banner-height);
  padding: 0 var(--page-gutter);
  padding-left: max(var(--page-gutter), env(safe-area-inset-left));
  padding-right: max(var(--page-gutter), env(safe-area-inset-right));
  background: var(--grey-800);
  color: var(--grey-100);
  border-bottom: var(--rule) solid var(--grey-100);
}
.wordmark,
.bbg-product {
  font-family: var(--font-display);
  font-style: normal;
  font-weight: 400;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--grey-100);
  text-decoration: none;
  line-height: 1;
  white-space: nowrap;
}
.wordmark { font-size: var(--text-md); color: var(--cyan-300); }
.bbg-brand {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}
.bbg-product {
  font-size: var(--text-xs);
  color: var(--grey-500);
}
.bbg-keys {
  display: flex;
  flex: 1;
  min-width: 0;
  align-items: center;
  gap: var(--space-8);
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
}
.bbg-keys a {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: 0 var(--space-8);
  min-height: 45px;
  font-family: var(--font-display);
  font-size: var(--text-xs);
  font-weight: 400;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  text-decoration: none;
  color: var(--grey-100);
  white-space: nowrap;
  flex: 0 0 auto;
  border-top: var(--rule) solid var(--grey-100);
  border-bottom: var(--rule) solid var(--grey-100);
}
.bbg-keys kbd {
  font-family: var(--font-mono);
  font-size: 0.625rem;
  font-weight: 400;
  padding: 0 0.2rem;
  border: var(--rule) solid var(--cyan-300);
  color: var(--cyan-300);
}
.nav-edge__controls {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  min-width: 0;
}
.bbg-clock {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 400;
  color: var(--grey-400);
  white-space: nowrap;
}
select,
.btn,
select,
.btn {
  min-height: 45px;
  padding: 0 var(--space-16);
  white-space: nowrap;
}
select { width: 9.5rem; max-width: 100%; min-width: 0; background: var(--grey-800); }
.btn { cursor: pointer; clip-path: polygon(8px 0, 100% 0, 100% calc(100% - 8px), calc(100% - 8px) 100%, 0 100%, 0 8px); }
.btn--primary {
  background: var(--grey-100);
  color: var(--grey-800);
  border-color: var(--grey-100);
}
.btn--ghost {
  background: transparent;
  color: var(--grey-100);
  border-color: var(--grey-100);
}
@media (hover: hover) and (pointer: fine) {
  select:hover, .btn:hover { border-color: var(--cyan-300); color: var(--cyan-300); }
  .btn--primary:hover { background: var(--grey-200); color: var(--grey-800); border-color: var(--grey-200); }
  .ticker-link:hover { color: var(--cyan-300); text-decoration: underline; text-underline-offset: var(--space-3xs); }
  .bbg-keys a:hover { color: var(--cyan-300); border-color: var(--cyan-300); }
}
select:focus-visible,
.btn:focus-visible,
.ticker-link:focus-visible,
.wordmark:focus-visible,
.bbg-keys a:focus-visible {
  outline: 2px solid var(--color-ink);
  outline-offset: 1px;
}
select:active, .btn:active { transform: translateY(1px); }
.btn:disabled, select:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.btn[data-state="loading"] { cursor: wait; opacity: 0.7; }
.btn[data-state="error"] { border-color: var(--color-danger); color: var(--color-danger); }
.btn[data-state="success"] { border-color: var(--color-up); }

main {
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 0 var(--page-gutter) var(--space-lg);
}
.lede {
  display: flex;
  justify-content: space-between;
  gap: var(--space-sm);
  max-width: none;
  margin: 0 calc(var(--page-gutter) * -1) var(--space-sm);
  padding: var(--space-2xs) var(--page-gutter);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-accent);
  background: var(--color-paper-2);
  border-bottom: var(--rule) solid var(--color-rule);
}
.desk-block {
  margin-top: var(--space-md);
  border: var(--rule) solid var(--grey-100);
  padding: var(--space-xs);
  background: var(--grey-800);
  clip-path: polygon(8px 0, 100% 0, 100% calc(100% - 8px), calc(100% - 8px) 100%, 0 100%, 0 8px);
}
.desk-block--graphite {
  margin-inline: 0;
  padding: var(--space-xs);
  background: var(--grey-700);
  color: var(--color-ink);
  border-color: var(--cyan-300);
}
.desk-block--graphite h1,
.desk-block--graphite h2,
.desk-block--graphite h3 { color: var(--color-accent); }
.desk-block--graphite .btn--ghost {
  background: transparent;
  color: var(--color-accent);
  border-color: var(--color-accent);
}
.section-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--space-2xs);
  align-items: center;
  margin: 0 0 var(--space-xs);
  padding: var(--space-2xs) var(--space-xs);
  background: var(--color-paper-3);
  border-bottom: var(--rule) solid var(--color-rule);
}
.section-heading h1,
.section-heading h2 {
  margin: 0;
  font-size: var(--text-display);
  font-style: normal;
}
.section-heading .btn { justify-self: start; }
.rules {
  border: var(--rule) solid var(--grey-100);
  padding: var(--space-xs);
  margin-top: var(--space-sm);
  clip-path: polygon(8px 0, 100% 0, 100% calc(100% - 8px), calc(100% - 8px) 100%, 0 100%, 0 8px);
}
.qotd {
  margin: 0 0 var(--space-sm);
  padding-bottom: var(--space-sm);
  border-bottom: var(--rule) solid var(--color-rule);
}
.qotd__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-xs);
  margin: 0 0 var(--space-xs);
  padding: var(--space-2xs) var(--space-xs);
  background: var(--color-paper-3);
}
.qotd__head h2 {
  flex: 1 1 10rem;
  min-width: 0;
  margin: 0;
  font-size: var(--text-sm);
  font-style: normal;
}
.qotd__quote {
  margin: 0;
  padding: var(--space-xs);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-style: normal;
  font-weight: 400;
  line-height: 1.45;
  color: var(--grey-100);
  overflow-wrap: anywhere;
}
.qotd__meta {
  margin: var(--space-2xs) 0 0;
  padding: 0 var(--space-xs);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-muted);
}
.scope-toggle { display: flex; gap: var(--space-2xs); }
.scope-toggle .btn.is-active {
  border-color: var(--color-frame-1m);
  color: var(--color-frame-1m);
}
.perf-row { cursor: pointer; }
.perf-row:hover .industry, .perf-row:focus-visible .industry { text-decoration: underline; }
.perf-row[aria-selected="true"] { background: color-mix(in oklch, var(--color-frame-1m) 10%, transparent); }
.bar--down { opacity: 0.75; }
.industry-detail {
  margin-top: var(--space-sm);
  border: var(--rule) solid var(--grey-100);
  padding: var(--space-xs);
}
.industry-detail__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: var(--space-xs);
  margin-bottom: var(--space-2xs);
}
.industry-detail h3 { margin: 0; font-size: var(--text-sm); }
.window-sections {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--space-sm);
  align-items: start;
}
.panel,
.panel h2,
.panel[data-frame="1w"] h2 { color: var(--color-frame-1w); }
.panel[data-frame="1m"] h2 { color: var(--color-frame-1m); }
.panel[data-frame="3m"] h2 { color: var(--color-frame-3m); }
.panel[data-frame="6m"] h2 { color: var(--color-frame-6m); }
.desk-block--graphite .panel,
.bars { display: grid; gap: var(--space-2xs); padding: var(--space-xs); }
.bar-row {
  display: grid;
  grid-template-columns: minmax(0, 8rem) minmax(0, 1fr) 2.5rem;
  gap: var(--space-xs);
  align-items: center;
}
.industry {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  line-height: 1.3;
  overflow-wrap: anywhere;
}
.rising-alert {
  margin: 0 0 var(--space-md);
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--color-frame-1m);
  background: color-mix(in oklch, var(--color-frame-1m) 12%, var(--color-paper));
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  line-height: 1.45;
  color: var(--color-ink-2);
}
.rising-alert[hidden] { display: none; }
.rising-alert__label {
  display: inline-block;
  margin-right: 0.55rem;
  padding: 0.1rem 0.4rem;
  border: 1px solid var(--color-frame-1m);
  color: var(--color-frame-1m);
  font-family: var(--font-display);
  font-size: var(--text-xs);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.rising-alert strong {
  color: var(--color-frame-1m);
  font-family: var(--font-display);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.industry--rising::after {
  content: " ▲";
  color: var(--color-frame-1m);
  font-size: 0.85em;
}
.track {
  height: 0.75rem;
  position: relative;
  background: var(--color-paper-3);
}
.desk-block--graphite .track { background: var(--color-paper-3); }
.bar {
  height: 0.25rem;
  position: absolute;
  left: 0;
}
.bar.current { top: 0.0625rem; }
.bar.previous { bottom: 0.0625rem; background: var(--color-prior); }
.value {
  color: var(--color-ink);
  text-align: right;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-size: var(--text-xs);
}
.desk-block--graphite .value { color: var(--color-graphite-ink); }
svg {
  width: 100%;
  height: var(--chart-height);
  display: block;
  overflow: visible;
  padding: 0 var(--space-xs) var(--space-xs);
}
.table-wrap { overflow-x: auto; max-width: 100%; -webkit-overflow-scrolling: touch; }
.scrollable-table { max-height: 16rem; overflow-y: auto; }
table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}
.scrollable-table th {
  position: sticky;
  top: 0;
  background: var(--color-paper-3);
  z-index: var(--z-raised);
}
.desk-block--graphite .scrollable-table th { background: var(--color-paper-3); }
th, td {
  padding: var(--space-3xs) var(--space-2xs);
  border-bottom: var(--rule) solid var(--color-rule);
  text-align: right;
  font-size: var(--text-xs);
}
.desk-block--graphite th,
.desk-block--graphite td { border-bottom-color: var(--color-graphite-rule); }
th:first-child, th:nth-child(2), td:first-child, td:nth-child(2) { text-align: left; }
th {
  color: var(--color-accent);
  font-family: var(--font-display);
  font-size: 0.625rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  background: var(--color-paper-3);
}
.desk-block--graphite th { color: var(--color-accent); }
.ticker-link {
  font-family: var(--font-outlier);
  font-weight: 600;
  color: var(--color-ink);
  text-decoration: none;
}
.desk-block--graphite .ticker-link { color: var(--color-graphite-ink); }
tbody tr:nth-child(even) { background: color-mix(in oklch, var(--color-paper-2) 70%, transparent); }
.tick-up { color: var(--color-up); }
.tick-down { color: var(--color-down); }
.empty {
  color: var(--color-muted);
  padding: var(--space-sm) var(--space-xs);
  text-align: left;
  font-family: var(--font-mono);
}
.desk-block--graphite .empty { color: var(--color-graphite-muted); }
.snapshot-date {
  font-family: var(--font-outlier);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--color-accent-ink);
}
.dashboard-title { margin: 0; }
.foot-line {
  border-top: var(--rule) solid var(--grey-100);
  padding: var(--space-xs) var(--page-gutter);
  max-width: none;
  margin: 0;
  background: var(--grey-800);
}
.foot-line p {
  margin: 0;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

@media (min-width: 40rem) {
  .section-heading { grid-template-columns: minmax(0, 1fr) auto; }
  .section-heading .btn { justify-self: end; }
  .bar-row { grid-template-columns: minmax(0, 11rem) minmax(0, 1fr) 2.5rem; }
}
@media (min-width: 60rem) {
  .window-sections { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (min-width: 90rem) {
  .window-sections { grid-template-columns: repeat(4, minmax(0, 1fr)); }
}
@media (max-width: 72rem) {
  .bbg-product { display: none; }
}
@media (max-width: 60rem) {
  .bbg-clock { display: none; }
}
@media (max-width: 47.99rem) {
  :root {
    --page-gutter: var(--space-8);
    --chart-height: 11rem;
    --banner-height: 3.25rem;
    --control-height: 2.75rem;
    --mobile-nav-keys: 2.5rem;
  }
  body {
    padding-bottom: env(safe-area-inset-bottom);
    font-size: var(--text-sm);
  }
  .nav-edge {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    grid-template-areas:
      "brand controls"
      "keys keys";
    align-items: center;
    gap: 0;
    min-height: 0;
    padding: 0;
    padding-top: env(safe-area-inset-top);
  }
  .bbg-brand {
    grid-area: brand;
    min-height: var(--banner-height);
    padding-left: max(var(--page-gutter), env(safe-area-inset-left));
  }
  .nav-edge__controls {
    grid-area: controls;
    gap: var(--space-4);
    flex-shrink: 0;
    padding-right: max(var(--page-gutter), env(safe-area-inset-right));
  }
  .bbg-keys {
    grid-area: keys;
    flex: 0 0 auto;
    width: 100%;
    height: var(--mobile-nav-keys);
    gap: 0;
    border-top: var(--rule) solid var(--grey-700);
    padding: 0 max(var(--page-gutter), env(safe-area-inset-left)) 0 max(var(--page-gutter), env(safe-area-inset-right));
    scrollbar-width: none;
    overscroll-behavior-x: contain;
  }
  .bbg-keys::-webkit-scrollbar { display: none; }
  .bbg-keys a {
    min-height: var(--mobile-nav-keys);
    height: var(--mobile-nav-keys);
    padding: 0 var(--space-12);
    border-top: 0;
    border-bottom: 0;
    font-size: 0.625rem;
    touch-action: manipulation;
  }
  .bbg-keys kbd { display: none; }
  select,
  .btn {
    min-height: var(--control-height);
    padding: 0 var(--space-8);
    font-size: 0.625rem;
    touch-action: manipulation;
  }
  select { width: auto; min-width: 6.5rem; }
  .lede {
    margin-left: 0;
    margin-right: 0;
    padding-left: max(var(--page-gutter), env(safe-area-inset-left));
    padding-right: max(var(--page-gutter), env(safe-area-inset-right));
  }
  .desk-block,
  .rules,
  .foot-line {
    padding-left: max(var(--page-gutter), env(safe-area-inset-left));
    padding-right: max(var(--page-gutter), env(safe-area-inset-right));
  }
  .section-heading { gap: var(--space-8); }
  .section-heading .btn { width: 100%; justify-self: stretch; }
  .bar-row {
    grid-template-columns: minmax(0, 1fr) 2rem;
    gap: var(--space-4) var(--space-8);
  }
  .bar-row .industry { grid-column: 1 / -1; }
  .bar-row .track { grid-column: 1; }
  .bar-row .value { grid-column: 2; grid-row: 2; }
  .scrollable-table { max-height: 22rem; overscroll-behavior: contain; }
  th, td { padding: var(--space-2xs) var(--space-3xs); }
  .foot-line p { white-space: normal; }
  .ticker-link { touch-action: manipulation; }
}
@media (max-width: 22.5rem) {
  .bbg-keys a { padding: 0 var(--space-8); }
  select { min-width: 5.5rem; }
  .btn--primary { padding: 0 var(--space-8); }
}
@media (pointer: coarse) {
  .ticker-link { padding: var(--space-2xs) 0; display: inline-block; }
}
@media (prefers-reduced-motion: reduce) {
  select, .btn, .ticker-link, .skip-link {
    transition: none;
  }
  select:active, .btn:active { transform: none; }
}
  </style>
</head>
<body>
<a class="skip-link" href="#thematic-title">Skip to desk</a>
<main>
  <header class="nav-edge topbar">
    <div class="bbg-brand">
      <a class="wordmark" href="#thematic-title">THM</a>
      <span class="bbg-product">Theme Scanner</span>
    </div>
    <nav class="bbg-keys" aria-label="Terminal panels">
      <a href="#thematic-title"><kbd>F1</kbd> Themes</a>
      <a href="#baskets-title"><kbd>F2</kbd> Baskets</a>
      <a href="#qotd"><kbd>F3</kbd> Quote</a>
    </nav>
    <div class="nav-edge__controls">
      <span id="bbg-clock" class="bbg-clock" aria-live="off"></span>
      <label class="visually-hidden" for="date">Snapshot date</label>
      <select id="date" aria-label="Snapshot date"></select>
      <button id="download-image" class="btn btn--primary" type="button">Snap &lt;GO&gt;</button>
    </div>
  </header>
  <p class="lede">Post-close desk · track industry themes · open charts <span id="bbg-session">US equity session</span></p>
  <section class="desk-block" aria-labelledby="thematic-title">
    <div class="section-heading">
      <h1 id="thematic-title" class="dashboard-title">Thematic Leadership</h1>
      <div class="scope-toggle" role="group" aria-label="Universe scope">
        <button id="scope-finviz" class="btn btn--ghost" type="button" aria-pressed="false">Finviz groups</button>
        <button id="scope-all" class="btn btn--ghost is-active" type="button" aria-pressed="true">All stocks</button>
        <button id="scope-liquid" class="btn btn--ghost" type="button" aria-pressed="false">Liquid only</button>
      </div>
    </div>
    <p class="lede" id="scope-note"></p>
    <div id="rising-theme-alert" class="rising-alert" hidden role="status" aria-live="polite"></div>
    <div id="leadership-sections" class="window-sections"></div>
    <div id="industry-detail" class="industry-detail" hidden aria-live="polite"></div>
  </section>
  <section class="desk-block desk-block--graphite" aria-labelledby="baskets-title">
    <div class="section-heading">
      <h2 id="baskets-title">Theme Baskets</h2>
      <button id="download-baskets" class="btn btn--ghost" type="button">Export Baskets</button>
    </div>
    <p class="lede">Named themes defined by a curated ticker list, counted the same way as industries. Edit <code>theme_baskets.json</code> to change one.</p>
    <div id="basket-sections" class="window-sections"></div>
  </section>
  <section id="qotd" class="rules" aria-label="Quote of the day">
    <div class="qotd">
      <div class="qotd__head">
        <h2 id="qotd-title">Quote of the day</h2>
        <button id="qotd-next" class="btn btn--ghost" type="button">Next quote</button>
      </div>
      <blockquote id="qotd-text" class="qotd__quote" aria-live="polite"></blockquote>
      <p id="qotd-meta" class="qotd__meta">Jesse Livermore</p>
    </div>
  </section>
</main>
<footer class="foot-line">
  <p>THM · Theme Scanner · not financial advice · kelex</p>
</footer>
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
<script>
const history = __DATA__;
const QUOTES = __QUOTES__;
(function initQuoteOfDay() {
  const text = document.getElementById('qotd-text');
  const meta = document.getElementById('qotd-meta');
  const button = document.getElementById('qotd-next');
  if (!text || !Array.isArray(QUOTES) || !QUOTES.length) return;
  const storageKey = 'thm-qotd';
  function nyDate() {
    return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  }
  function hash(value) {
    let h = 2166136261;
    for (let i = 0; i < value.length; i++) {
      h ^= value.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }
  function readSaved() {
    try { return JSON.parse(localStorage.getItem(storageKey) || 'null'); } catch { return null; }
  }
  function save(index) {
    try { localStorage.setItem(storageKey, JSON.stringify({ date: nyDate(), index })); } catch { /* private mode */ }
  }
  function show(index) {
    text.textContent = QUOTES[index];
    text.dataset.index = String(index);
    if (meta) meta.textContent = (index + 1) + ' / ' + QUOTES.length + ' · Jesse Livermore · Reminiscences, 1923';
  }
  const today = nyDate();
  const saved = readSaved();
  let index = hash('thm|' + today) % QUOTES.length;
  if (saved && saved.date === today && Number.isInteger(saved.index) && saved.index >= 0 && saved.index < QUOTES.length) index = saved.index;
  show(index);
  if (!button) return;
  button.addEventListener('click', () => {
    const current = Number(text.dataset.index);
    let next = current;
    if (QUOTES.length > 1) {
      while (next === current) next = Math.floor(Math.random() * QUOTES.length);
    }
    show(next);
    save(next);
  });
})();
const dateSelect = document.getElementById('date');
const leadershipSections = document.getElementById('leadership-sections');
const risingThemeAlert = document.getElementById('rising-theme-alert');
const basketSections = document.getElementById('basket-sections');
const downloadButton = document.getElementById('download-image');
const downloadBasketsButton = document.getElementById('download-baskets');
const flowMeta = { '1w': { label:'1 week', color:'var(--color-frame-1w)' }, '1m': { label:'1 month', color:'var(--color-frame-1m)' }, '3m': { label:'3 months', color:'var(--color-frame-3m)' }, '6m': { label:'6 months', color:'var(--color-frame-6m)' } };
const rankColors = ['var(--color-rank-1)', 'var(--color-rank-2)', 'var(--color-rank-3)', 'var(--color-rank-4)', 'var(--color-rank-5)'];
const NOTE_KEY = 'thm-note:';

function risingThemes(snapshot) { return snapshot?.rising_themes || []; }
function basketCounts(snapshot, frame) { return snapshot?.baskets?.[frame] || {}; }
function renderRisingAlert(snapshot) {
  if (!risingThemeAlert) return;
  const primary = risingThemes(snapshot).filter(row => row.frame === '1m');
  if (!primary.length) {
    risingThemeAlert.hidden = true;
    risingThemeAlert.innerHTML = '';
    return;
  }
  const parts = primary.slice(0, 6).map(row => {
    const arrow = `${row.prior_count}→${row.current_count}`;
    return `<strong>${escapeHTML(row.signal)}</strong> ${escapeHTML(row.industry)} (${arrow}, +${row.delta})`;
  });
  risingThemeAlert.hidden = false;
  risingThemeAlert.innerHTML = `<span class="rising-alert__label">Do not miss</span>${parts.join(' · ')}.`;
}
function escapeHTML(value) { return String(value ?? '—').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char])); }
function updateDates() {
  dateSelect.innerHTML = history.map((d,i) => `<option value="${i}">${d.date}</option>`).join('');
  dateSelect.value = Math.max(0, history.length - 1);
}
function tickClock() {
  const clock = document.getElementById('bbg-clock');
  if (!clock) return;
  clock.textContent = new Date().toLocaleString('en-US', {
    timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
  }) + ' NY';
}
function currentSnapshot() { return history[Number(dateSelect.value)] || null; }
const SCOPES = {
  finviz: { label: 'Finviz groups', note: "Finviz's own industry taxonomy, ranked by their published group performance. It keeps groups like Semiconductor Equipment & Materials intact, which TradingView splits apart. Select a group to open its constituents on Finviz." },
  all: { label: 'All stocks', note: 'Every scanned stock grouped by TradingView industry, ranked by median member performance. Select an industry to see the eligible names inside it.' },
  liquid: { label: 'Liquid only', note: 'Only names passing the liquidity and ADR filters, grouped by TradingView industry. Select an industry to see the names inside it.' },
};
// Prefer Finviz's taxonomy when a local run managed to fetch it.
let perfScope = (history.at?.(-1)?.performance?.finviz) ? 'finviz' : 'all';
let openIndustry = null;
function perfRows(snapshot, frame) { return snapshot?.performance?.[perfScope]?.[frame] || []; }
function formatSigned(value) { const n = Number(value); return Number.isFinite(n) ? `${n >= 0 ? '+' : ''}${n.toFixed(1)}%` : '—'; }
function renderPerformanceBars(current, frame, container) {
  if (!container) return;
  const rows = perfRows(current, frame).slice(0, 10);
  if (!rows.length) { container.innerHTML = '<p class="empty">No industry performance for this snapshot. Re-run the scanner.</p>'; return; }
  const max = Math.max(1, ...rows.map(row => Math.abs(Number(row.median) || 0)));
  container.innerHTML = rows.map((row, index) => {
    const color = rankColors[index % rankColors.length];
    const value = Number(row.median) || 0;
    const up = value >= 0;
    const selected = openIndustry && openIndustry.industry === row.industry && openIndustry.frame === frame;
    const title = row.members === undefined
      ? `${row.industry} · ${value.toFixed(2)}% (Finviz)`
      : `${row.industry} · ${row.members} members · median ${value.toFixed(2)}% · mean ${Number(row.mean).toFixed(2)}%`;
    return `<div class="bar-row perf-row" role="button" tabindex="0" aria-selected="${selected ? 'true' : 'false'}" data-industry="${escapeHTML(row.industry)}" data-frame="${escapeHTML(frame)}" title="${escapeHTML(title)}"><div class="industry" style="color:${color}">${escapeHTML(row.industry)}</div><div class="track"><div class="bar current ${up ? '' : 'bar--down'}" style="width:${Math.abs(value) / max * 100}%;background:${color}"></div></div><div class="value ${up ? 'tick-up' : 'tick-down'}">${formatSigned(value)}</div></div>`;
  }).join('');
}
function memberChartUrl(row) {
  const name = String(row.n || '').trim();
  const venue = String(row.e || 'NASDAQ').trim().toUpperCase() || 'NASDAQ';
  return `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(venue + ':' + name)}&interval=D`;
}
function renderIndustryDetail() {
  const panel = document.getElementById('industry-detail');
  if (!panel) return;
  if (!openIndustry) { panel.hidden = true; panel.innerHTML = ''; return; }
  const snapshot = currentSnapshot();
  const { industry, frame } = openIndustry;
  if (perfScope === 'finviz') {
    // Finviz groups carry their own membership and their own numbers, already
    // ranked by the week when scraped.
    const row = perfRows(snapshot, frame).find(r => r.industry === industry);
    const names = (snapshot?.finviz_members || {})[industry] || [];
    const body = names.length
      ? `<div class="table-wrap scrollable-table"><table><thead><tr><th>Symbol</th><th>1 week</th><th>1 month</th><th>3 months</th><th>6 months</th></tr></thead><tbody>${names.map(m => `<tr><td class="col-ticker"><a class="ticker-link" href="https://finviz.com/quote.ashx?t=${encodeURIComponent(m.t)}" target="_blank" rel="noopener noreferrer">${escapeHTML(m.t)}</a></td><td class="${Number(m['1w']) >= 0 ? 'tick-up' : 'tick-down'}">${formatSigned(m['1w'])}</td><td class="${Number(m['1m']) >= 0 ? 'tick-up' : 'tick-down'}">${formatSigned(m['1m'])}</td><td class="${Number(m['3m']) >= 0 ? 'tick-up' : 'tick-down'}">${formatSigned(m['3m'])}</td><td class="${Number(m['6m']) >= 0 ? 'tick-up' : 'tick-down'}">${formatSigned(m['6m'])}</td></tr>`).join('')}</tbody></table></div>`
      : '<p class="empty">No member list for this group in this snapshot. Run fetch_finviz_groups.py.</p>';
    panel.hidden = false;
    panel.innerHTML = `<div class="industry-detail__head"><h3>${escapeHTML(industry)} · ${formatSigned(row?.median)} over ${escapeHTML(flowMeta[frame]?.label || frame)} · ${names.length} name${names.length === 1 ? '' : 's'}, best week first</h3><button id="close-industry" class="btn btn--ghost" type="button">Close</button></div>${body}`;
    return;
  }
  const members = (snapshot?.members || [])
    .filter(row => String(row.i || '').trim() === industry)
    .sort((a, b) => (Number(b[frame]) || -Infinity) - (Number(a[frame]) || -Infinity));
  const label = flowMeta[frame]?.label || frame;
  const body = members.length
    ? `<div class="table-wrap scrollable-table"><table><thead><tr><th>Symbol</th><th>1 week</th><th>1 month</th><th>3 months</th><th>6 months</th></tr></thead><tbody>${members.map(row => `<tr><td class="col-ticker"><a class="ticker-link" href="${escapeHTML(memberChartUrl(row))}" target="_blank" rel="noopener noreferrer">${escapeHTML(row.n)}</a></td><td class="${Number(row['1w']) >= 0 ? 'tick-up' : 'tick-down'}">${formatSigned(row['1w'])}</td><td class="${Number(row['1m']) >= 0 ? 'tick-up' : 'tick-down'}">${formatSigned(row['1m'])}</td><td class="${Number(row['3m']) >= 0 ? 'tick-up' : 'tick-down'}">${formatSigned(row['3m'])}</td><td class="${Number(row['6m']) >= 0 ? 'tick-up' : 'tick-down'}">${formatSigned(row['6m'])}</td></tr>`).join('')}</tbody></table></div>`
    : '<p class="empty">No eligible names in this industry for this snapshot. The ranking above can include stocks that fail the liquidity filters.</p>';
  panel.hidden = false;
  panel.innerHTML = `<div class="industry-detail__head"><h3>${escapeHTML(industry)} · ${members.length} eligible name${members.length === 1 ? '' : 's'} · sorted by ${escapeHTML(label)}</h3><button id="close-industry" class="btn btn--ghost" type="button">Close</button></div>${body}`;
}
function setScope(scope) {
  perfScope = scope;
  openIndustry = null;
  Object.keys(SCOPES).forEach(key => {
    const button = document.getElementById(`scope-${key}`);
    if (!button) return;
    const available = Boolean(currentSnapshot()?.performance?.[key]);
    const active = key === scope;
    button.hidden = !available;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-pressed', active ? 'true' : 'false');
  });
  const note = document.getElementById('scope-note');
  if (note) note.textContent = SCOPES[scope]?.note || '';
  render();
}
function renderBasketBars(current, previous, frame, container) {
  if (!container) return;
  const now = basketCounts(current, frame), then = basketCounts(previous, frame);
  const rising = new Set(risingThemes(current).filter(row => row.frame === frame && row.kind === 'basket').map(row => row.industry));
  const names = [...new Set([...Object.keys(now), ...Object.keys(then)])]
    .sort((a, b) => (now[b]||0) - (now[a]||0) || (then[b]||0) - (then[a]||0) || a.localeCompare(b))
    .slice(0, 8);
  if (!names.length) { container.innerHTML = '<p class="empty">No basket members lead this window.</p>'; return; }
  const max = Math.max(1, ...names.flatMap(n => [now[n]||0, then[n]||0]));
  container.innerHTML = names.map((name, index) => {
    const color = rankColors[index % rankColors.length];
    const risingClass = rising.has(name) ? ' industry--rising' : '';
    const delta = (now[name]||0) - (then[name]||0);
    const title = rising.has(name) ? `${name} · rising ${delta >= 0 ? '+' : ''}${delta}` : name;
    return `<div class="bar-row"><div class="industry${risingClass}" style="color:${color}" title="${escapeHTML(title)}">${escapeHTML(name)}</div><div class="track"><div class="bar current" style="width:${(now[name]||0)/max*100}%;background:${color}" title="Selected: ${now[name]||0}"></div><div class="bar previous" style="width:${(then[name]||0)/max*100}%" title="Prior: ${then[name]||0}"></div></div><div class="value">${now[name]||0}</div></div>`;
  }).join('');
}
function render() {
  const current = currentSnapshot(), index = Number(dateSelect.value), previous = history[index-1];
  renderRisingAlert(current);
  leadershipSections.innerHTML = Object.entries(flowMeta).map(([frame, meta]) => `<section class="panel" data-frame="${frame}"><h2>${meta.label} performance</h2><div id="bars-${frame}" class="bars"></div></section>`).join('');
  if (basketSections) basketSections.innerHTML = Object.entries(flowMeta).map(([frame, meta]) => `<section class="panel" data-frame="${frame}"><h2>${meta.label} baskets</h2><div id="baskets-${frame}" class="bars"></div></section>`).join('');
  Object.keys(flowMeta).forEach(frame => renderPerformanceBars(current, frame, document.getElementById(`bars-${frame}`)));
  Object.keys(flowMeta).forEach(frame => renderBasketBars(current, previous, frame, document.getElementById(`baskets-${frame}`)));
  renderIndustryDetail();
}
function downloadBasketCounts() {
  const snapshot = currentSnapshot();
  if (!snapshot) return;
  const rows = [['frame', 'basket', 'leaders']];
  Object.keys(flowMeta).forEach(frame => {
    Object.entries(basketCounts(snapshot, frame))
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .forEach(([basket, count]) => rows.push([frame, basket, String(count)]));
  });
  const csv = rows.map(row => row.map(cell => `"${String(cell).replaceAll('"', '""')}"`).join(',')).join('\n') + '\n';
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const link = document.createElement('a'); link.download = `theme_baskets_${snapshot.date}.csv`; link.href = URL.createObjectURL(blob); link.click(); URL.revokeObjectURL(link.href);
}
async function downloadPageImage() {
  if (typeof html2canvas !== 'function') { window.alert('The image exporter could not load. Check your connection and try again.'); return; }
  downloadButton.disabled = true; downloadButton.dataset.state = 'loading'; downloadButton.textContent = 'Creating image…';
  try {
    const canvas = await html2canvas(document.querySelector('main'), { backgroundColor: getComputedStyle(document.body).backgroundColor, scale:2, useCORS:true, windowWidth:document.documentElement.scrollWidth, windowHeight:document.documentElement.scrollHeight, onclone: clonedDocument => { const bar = clonedDocument.querySelector('.topbar'); bar.innerHTML = `<div class="bbg-brand"><a class="wordmark">THM</a><span class="bbg-product">Theme Scanner</span></div><span class="snapshot-date">${currentSnapshot().date}</span>`; } });
    const link = document.createElement('a'); link.download = `industry-themes-${currentSnapshot().date}.png`; link.href = canvas.toDataURL('image/png'); link.click();
  } finally { downloadButton.disabled = false; downloadButton.dataset.state = ''; downloadButton.textContent = 'Snap <GO>'; }
}
function toggleIndustry(industry, frame) {
  openIndustry = (openIndustry && openIndustry.industry === industry && openIndustry.frame === frame)
    ? null
    : { industry, frame };
  Object.keys(flowMeta).forEach(key => renderPerformanceBars(currentSnapshot(), key, document.getElementById(`bars-${key}`)));
  renderIndustryDetail();
  if (openIndustry) document.getElementById('industry-detail')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
document.addEventListener('keydown', event => {
  if (event.key !== 'Enter' && event.key !== ' ') return;
  const row = event.target.closest?.('.perf-row');
  if (!row) return;
  event.preventDefault();
  toggleIndustry(row.dataset.industry, row.dataset.frame);
});
document.addEventListener('click', event => {
  const scopeButton = event.target.closest('.scope-toggle .btn');
  if (scopeButton) { setScope(scopeButton.id.replace('scope-', '')); return; }
  if (event.target.closest('#close-industry')) { openIndustry = null; Object.keys(flowMeta).forEach(key => renderPerformanceBars(currentSnapshot(), key, document.getElementById(`bars-${key}`))); renderIndustryDetail(); return; }
  const perfRow = event.target.closest('.perf-row');
  if (perfRow) { toggleIndustry(perfRow.dataset.industry, perfRow.dataset.frame); return; }
  const nav = event.target.closest('.bbg-keys a[href^="#"], a.wordmark[href^="#"]');
  if (nav) {
    const href = nav.getAttribute('href');
    const target = href ? document.querySelector(href) : null;
    if (target) {
      event.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      if (history.replaceState) history.replaceState(null, '', href);
    }
    return;
  }
  const link = event.target.closest('a.ticker-link');
  if (!link) return;
  const href = link.getAttribute('href');
  if (!href || href.startsWith('#')) return;
  event.preventDefault();
  window.open(href, '_blank', 'noopener,noreferrer');
});
document.addEventListener('keydown', event => {
  const map = { F1: '#thematic-title', F2: '#baskets-title', F3: '#qotd' };
  const href = map[event.key];
  if (!href) return;
  event.preventDefault();
  document.querySelector(href)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
});
// The bars size themselves with CSS percentages, so a resize needs no redraw.
if (!history.length) { document.querySelector('main').innerHTML = '<p class="empty">Run the scanner once to create a momentum-leader snapshot.</p>'; } else { updateDates(); tickClock(); setInterval(tickClock, 1000); dateSelect.addEventListener('change', () => setScope(currentSnapshot()?.performance?.[perfScope] ? perfScope : 'all')); downloadButton.addEventListener('click', downloadPageImage); if (downloadBasketsButton) downloadBasketsButton.addEventListener('click', downloadBasketCounts); setScope(perfScope); }
</script>
</body>
</html>'''
    rendered = template.replace("__DATA__", payload).replace("__QUOTES__", quotes_payload)
    dashboard.write_text(rendered, encoding="utf-8")
    pages_entrypoint.write_text(rendered, encoding="utf-8")
    return dashboard
