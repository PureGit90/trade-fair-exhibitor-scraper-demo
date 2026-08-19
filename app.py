import io
import os
import random
import re

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Trade Fair Exhibitor Extractor", page_icon="🗂️", layout="wide")

REQUIRED_FIELDS = ["Company name", "Country", "Official website", "Corporate email address"]

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

# ---------------------------------------------------------------------------
# Region / sector reference data -- used both to identify plausible trade
# fairs and to generate realistic (fictional) exhibitor directories for
# combinations that don't have a captured sample file.
# ---------------------------------------------------------------------------
REGIONS = [
    "Germany", "Vietnam", "Italy", "China", "United States",
    "United Kingdom", "Netherlands", "India", "Brazil", "UAE",
]
SECTORS = [
    "Manufacturing", "Textiles", "Furniture", "Electronics",
    "Food & Beverage", "Building Materials", "Packaging", "Automotive Parts",
]

REGION_CITY = {
    "Germany": "Hannover", "Vietnam": "Ho Chi Minh City", "Italy": "Milan",
    "China": "Shanghai", "United States": "Chicago", "United Kingdom": "Birmingham",
    "Netherlands": "Utrecht", "India": "Mumbai", "Brazil": "Sao Paulo", "UAE": "Dubai",
}
COUNTRY_SUFFIX = {
    "Germany": "GmbH", "Vietnam": "Co., Ltd", "Italy": "S.p.A", "China": "Co., Ltd",
    "United States": "Inc.", "United Kingdom": "Ltd", "Netherlands": "B.V.",
    "India": "Pvt. Ltd", "Brazil": "Ltda", "UAE": "LLC",
}
COUNTRY_TLD = {
    "Germany": "de", "Vietnam": "vn", "Italy": "it", "China": "cn",
    "United States": "com", "United Kingdom": "co.uk", "Netherlands": "nl",
    "India": "in", "Brazil": "com.br", "UAE": "ae",
}
NEIGHBOR_COUNTRIES = {
    "Germany": ["Germany", "Germany", "Austria", "Switzerland"],
    "Vietnam": ["Vietnam", "Vietnam", "Thailand", "Cambodia"],
    "Italy": ["Italy", "Italy", "France", "Spain"],
    "China": ["China", "China", "Taiwan", "Hong Kong"],
    "United States": ["United States", "United States", "Canada", "Mexico"],
}

SECTOR_WORDS = {
    "Manufacturing": ["Precision", "Machinery", "Engineering", "Industrial Systems", "Metalworks"],
    "Textiles": ["Textiles", "Garments", "Apparel", "Fabrics", "Weaving Mills"],
    "Furniture": ["Furniture", "Interiors", "Woodcraft", "Design Studio", "Living"],
    "Electronics": ["Electronics", "Circuits", "Components", "Technologies", "Semiconductors"],
    "Food & Beverage": ["Foods", "Beverages", "Provisions", "Agro Foods", "Ingredients"],
    "Building Materials": ["Building Materials", "Construction Supply", "Concrete Systems", "Roofing"],
    "Packaging": ["Packaging", "Cartons", "Containers", "Wrapping Systems"],
    "Automotive Parts": ["Auto Parts", "Drivetrain", "Components", "Automotive Systems"],
}
DEFAULT_SECTOR_WORDS = ["Trading", "Industries", "Group", "Solutions", "Enterprises"]
ADJECTIVES = [
    "Global", "United", "Nordic", "Alpine", "Pacific", "Continental", "Rapid",
    "Superior", "Prime", "Meridian", "Golden", "Silver", "Apex", "Vertex",
    "Summit", "Crown", "Bright", "Steady", "Clearline", "Ironbridge",
]
EMAIL_LOCALS = ["info", "sales", "export", "contact"]

# ---------------------------------------------------------------------------
# Layer 1: trade fair catalog -- a small set of real, well-known fairs per
# region/sector combo (names only, not exhibitor data) so common searches
# return a recognizable answer. Falls back to a templated generic fair name
# for any region/sector combo not covered here.
# ---------------------------------------------------------------------------
TRADE_FAIR_CATALOG = {
    ("Germany", "Manufacturing"): [
        {"name": "HANNOVER MESSE", "city": "Hannover", "month": "April", "source": "csv"},
        {"name": "AMB Stuttgart (Metalworking)", "city": "Stuttgart", "month": "September", "source": "generated"},
    ],
    ("Vietnam", "Textiles"): [
        {"name": "Saigontex", "city": "Ho Chi Minh City", "month": "April", "source": "generated"},
        {"name": "VIATT - Vietnam Int'l Textile & Apparel Trade Fair", "city": "Ho Chi Minh City", "month": "November", "source": "generated"},
    ],
    ("Italy", "Furniture"): [
        {"name": "Salone del Mobile.Milano", "city": "Milan", "month": "April", "source": "generated"},
    ],
    ("China", "Electronics"): [
        {"name": "electronica China", "city": "Shanghai", "month": "March", "source": "generated"},
        {"name": "Canton Fair (Electronics Sector)", "city": "Guangzhou", "month": "October", "source": "generated"},
    ],
}

FAIR_TEMPLATES = [
    "{region} International {sector} Expo",
    "{region} {sector} Trade Fair",
]


def identify_trade_fairs(region: str, sector: str) -> list:
    """Layer 1: return 2-3 plausible trade fairs for a region + sector.

    Uses a small catalog of known, named fairs for common combinations.
    Anything outside the catalog falls back to a templated generic fair name
    rather than inventing a specific fake event -- this mirrors what a human
    researcher would flag as 'needs manual confirmation of exact fair name'.
    """
    key = (region, sector)
    if key in TRADE_FAIR_CATALOG:
        return TRADE_FAIR_CATALOG[key]

    city = REGION_CITY.get(region, f"{region} (venue TBD)")
    fairs = []
    for i, template in enumerate(FAIR_TEMPLATES):
        fairs.append({
            "name": template.format(region=region, sector=sector),
            "city": city,
            "month": "TBD -- confirm exact date against organizer calendar",
            "source": "generated",
        })
    return fairs


# ---------------------------------------------------------------------------
# Layer 2: real file parsing -- the Hannover Messe entry loads an actual CSV
# (captured exhibitor directory export) via pandas, same as the client would
# hand off a scraped file for formatting.
# ---------------------------------------------------------------------------
def load_csv_exhibitors(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    for col in REQUIRED_FIELDS:
        if col not in df.columns:
            df[col] = ""
    df = df[REQUIRED_FIELDS].fillna("")
    return df


# ---------------------------------------------------------------------------
# Layer 3: templated exhibitor generation -- the mock mechanism that stands
# in for a live scrape/AI-extraction pass against an official exhibitor
# directory. Deterministic (seeded) so the same region/sector always returns
# the same sample set.
# ---------------------------------------------------------------------------
def _slug(text: str) -> str:
    text = text.lower().replace("&", "and")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def generate_exhibitors(fair_name: str, region: str, sector: str, n: int = 7) -> pd.DataFrame:
    rnd = random.Random(f"{fair_name}|{region}|{sector}")
    words = SECTOR_WORDS.get(sector, DEFAULT_SECTOR_WORDS)
    suffix = COUNTRY_SUFFIX.get(region, "Ltd")
    tld = COUNTRY_TLD.get(region, "com")
    country_pool = NEIGHBOR_COUNTRIES.get(region, [region])

    seen_names = set()
    rows = []
    attempts = 0
    while len(rows) < n and attempts < n * 6:
        attempts += 1
        adjective = rnd.choice(ADJECTIVES)
        word = rnd.choice(words)
        name = f"{adjective} {word} {suffix}"
        if name in seen_names:
            continue
        seen_names.add(name)

        slug = _slug(f"{adjective}-{word}")
        domain = f"{slug}.{tld}"
        website = f"https://www.{domain}"
        country = rnd.choice(country_pool)

        roll = rnd.random()
        if roll < 0.20:
            email = ""  # missing -- required field, don't guess it
        elif roll < 0.30:
            # domain mismatch case: an email that doesn't resolve back to the
            # listed official website -- unverifiable, not simply "missing"
            other_adj = rnd.choice(ADJECTIVES)
            other_word = rnd.choice(words)
            other_slug = _slug(f"{other_adj}-{other_word}")
            email = f"{rnd.choice(EMAIL_LOCALS)}@{other_slug}.com"
        else:
            email = f"{rnd.choice(EMAIL_LOCALS)}@{domain}"

        rows.append({
            "Company name": name,
            "Country": country,
            "Official website": website,
            "Corporate email address": email,
        })

    return pd.DataFrame(rows, columns=REQUIRED_FIELDS)


# ---------------------------------------------------------------------------
# Verification layer -- rule-based email QA, applied to every row regardless
# of which layer produced it. Flags rather than guesses.
# ---------------------------------------------------------------------------
def website_domain(url: str) -> str:
    d = url.lower().replace("https://", "").replace("http://", "").replace("www.", "")
    return d.split("/")[0]


def flag_row(row: pd.Series) -> str:
    email = str(row.get("Corporate email address", "")).strip()
    website = str(row.get("Official website", "")).strip()
    if not email:
        return "Missing -- no email found, needs manual sourcing"
    if not EMAIL_RE.match(email):
        return "Malformed -- does not look like a valid email address"
    email_domain = email.split("@", 1)[1].lower()
    site_domain = website_domain(website)
    if site_domain and email_domain not in site_domain and site_domain not in email_domain:
        return "Unverifiable -- email domain doesn't match official website, confirm manually"
    return "OK"


def build_dataset(region: str, sector: str) -> pd.DataFrame:
    fairs = identify_trade_fairs(region, sector)
    frames = []
    for fair in fairs:
        if fair["source"] == "csv":
            df = load_csv_exhibitors("sample_data/hannover_messe_exhibitors_sample.csv")
        else:
            df = generate_exhibitors(fair["name"], region, sector)
        df = df.copy()
        df.insert(0, "Trade fair", fair["name"])
        frames.append(df)
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["Trade fair"] + REQUIRED_FIELDS
    )
    combined["Email status"] = combined.apply(flag_row, axis=1)
    return combined, fairs


# ---------------------------------------------------------------------------
# Optional AI-assisted step: a short QA summary of the flagged rows.
# Rule-based mock by default; swaps to a real Claude call when an API key is
# supplied in the sidebar.
# ---------------------------------------------------------------------------
def _mock_qa_notes(stats: dict) -> str:
    return (
        f"**QA summary (rule-based -- no Anthropic API key set)**\n\n"
        f"Extracted {stats['total']} exhibitor records across {stats['fair_count']} trade fair(s). "
        f"{stats['ok']} corporate emails matched their listed official website domain and are "
        f"ready to upload as-is. {stats['missing']} record(s) had no email published in the source "
        f"directory and are left blank rather than guessed. {stats['unverifiable']} record(s) list "
        f"an email address whose domain doesn't match the official website on file, which usually "
        f"means a personal/generic address was published instead of the corporate one, or the "
        f"company uses a separate domain for email -- both need a quick manual check before outreach.\n\n"
        f"Recommended next step: hand the flagged rows to a 2-minute manual pass (company website "
        f"contact page is usually enough) before this batch goes into the Drive folder."
    )


def generate_qa_notes(stats: dict, api_key: str) -> str:
    if not api_key:
        return _mock_qa_notes(stats)
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            "Write a short QA summary (100-150 words) for a non-technical operations manager "
            "describing the results of an automated trade fair exhibitor extraction pass. Be "
            "direct and specific, end with one recommended next step. Findings:\n"
            f"- {stats['total']} exhibitor records extracted across {stats['fair_count']} trade fair(s)\n"
            f"- {stats['ok']} records have a corporate email that matches the official website domain\n"
            f"- {stats['missing']} records have no email published in the source directory\n"
            f"- {stats['unverifiable']} records have an email whose domain doesn't match the "
            "official website and need manual confirmation"
        )
        message = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception as exc:  # pragma: no cover - network/env dependent
        return _mock_qa_notes(stats) + f"\n\n_(Claude API call failed: {exc})_"


# ---------------------------------------------------------------------------
# Excel export -- exactly the fields the client asked for on the main sheet,
# with a second sheet for anything flagged so nothing is silently dropped.
# ---------------------------------------------------------------------------
def build_excel(combined: pd.DataFrame) -> bytes:
    clean = combined.copy()
    clean.loc[clean["Email status"] != "OK", "Corporate email address"] = ""
    clean_export = clean[["Trade fair"] + REQUIRED_FIELDS]

    flagged = combined[combined["Email status"] != "OK"][
        ["Trade fair", "Company name", "Country", "Official website", "Corporate email address", "Email status"]
    ].rename(columns={"Email status": "Reason flagged"})

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        clean_export.to_excel(writer, sheet_name="Exhibitors", index=False)
        flagged.to_excel(writer, sheet_name="Flagged for review", index=False)
    return buffer.getvalue()


def main():
    st.title("🗂️ Trade Fair Exhibitor Extractor")
    st.caption(
        "Give it a region and a sector. It identifies the relevant trade fairs, pulls exhibitor "
        "records with the four required fields (company name, country, official website, corporate "
        "email address), flags anything it can't verify instead of guessing, and produces the "
        "monthly Excel file ready to upload to Drive."
    )

    with st.sidebar:
        st.header("This month's criteria")
        region = st.selectbox("Region", REGIONS, index=0)
        sector = st.selectbox("Sector", SECTORS, index=0)
        st.divider()
        st.subheader("Optional: AI QA summary")
        api_key = st.text_input(
            "Anthropic API key (optional)",
            type="password",
            value=os.environ.get("ANTHROPIC_API_KEY", ""),
            help="Leave blank to use the built-in rule-based summary. No key required to run this demo.",
        )
        st.divider()
        st.caption(
            "This demo runs entirely on sample/generated data -- no live scraping target, no "
            "credentials required. Germany + Manufacturing loads a captured sample exhibitor "
            "directory (CSV) for HANNOVER MESSE via real pandas parsing; every other combination "
            "uses a deterministic templated generator so the full pipeline (identify -> extract -> "
            "verify -> export) is explorable for any region/sector pair."
        )

    combined, fairs = build_dataset(region, sector)

    stats = {
        "total": len(combined),
        "fair_count": len(fairs),
        "ok": int((combined["Email status"] == "OK").sum()),
        "missing": int(combined["Email status"].str.startswith("Missing").sum()),
        "unverifiable": int(
            (~combined["Email status"].isin(["OK"])
             & ~combined["Email status"].str.startswith("Missing")).sum()
        ),
    }

    st.subheader("Trade fairs identified this month")
    for fair in fairs:
        badge = "captured sample file" if fair["source"] == "csv" else "generated sample"
        st.markdown(f"- **{fair['name']}** -- {fair['city']}, {fair['month']}  \n  _source: {badge}_")

    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Exhibitors extracted", stats["total"])
    c2.metric("Trade fairs", stats["fair_count"])
    c3.metric("Emails verified", stats["ok"])
    c4.metric("Flagged for review", stats["missing"] + stats["unverifiable"])

    st.divider()
    with st.spinner("Preparing QA summary..."):
        notes = generate_qa_notes(stats, api_key)
    st.markdown(notes)

    st.divider()
    tab1, tab2 = st.tabs(["📋 Exhibitor Records", "🚩 Flagged for Review"])

    with tab1:
        st.write(
            "Exactly the fields requested: company name, country, official website, corporate "
            "email address (plus the source trade fair for traceability). Flagged emails are "
            "shown blank here -- see the Flagged tab for what was actually found and why it "
            "wasn't presented as verified."
        )
        display = combined.copy()
        display.loc[display["Email status"] != "OK", "Corporate email address"] = ""
        st.dataframe(
            display[["Trade fair"] + REQUIRED_FIELDS + ["Email status"]],
            use_container_width=True,
        )

    with tab2:
        flagged = combined[combined["Email status"] != "OK"]
        if len(flagged):
            st.write(
                "These records are held back from the clean export rather than guessed. Each "
                "one includes what was actually found (if anything) and why it needs a manual "
                "check before it goes to the client."
            )
            st.dataframe(
                flagged[["Trade fair", "Company name", "Official website", "Corporate email address", "Email status"]]
                .rename(columns={"Email status": "Reason flagged"}),
                use_container_width=True,
            )
        else:
            st.write("Nothing flagged in this batch.")

    st.divider()
    excel_bytes = build_excel(combined)
    st.download_button(
        "⬇️ Download this month's Excel file",
        data=excel_bytes,
        file_name=f"{_slug(region)}_{_slug(sector)}_exhibitors.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.caption(
        "Workbook has two sheets: **Exhibitors** (the four required fields, ready to upload as-is) "
        "and **Flagged for review** (anything held back, with the reason)."
    )

    st.divider()
    st.caption(
        "This is an MVP demo running against sample and templated data, not a live scrape -- "
        "there's no single 'official exhibitor directory' API to hit generically across regions "
        "and organizers. Production version points the same identify -> extract -> verify -> "
        "export pipeline at each month's real exhibitor directories (via Thunderbit/Browse AI/"
        "Octoparse or a direct scrape depending on the site), keeps the same verification and "
        "flagging logic, and adds a Google Drive API upload step so the finished file lands in "
        "the designated folder automatically instead of a manual download."
    )


if __name__ == "__main__":
    main()
