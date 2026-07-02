"""
config.py — the control panel for the entire pipeline.

Every list below is data, not logic. To change what the dashboard tracks,
edit this file only. refresh.py reads from here and never hardcodes a topic,
keyword, vendor, or feed.

The taxonomy (13 topics, 4 source types, 20 keywords, 14 vendors, 9 industries)
mirrors the Week 1 workbook (Week1_Market_Intelligence_Dataset.xlsx) and the
Week 3 account model (accounts.xlsx) exactly, so live data stays comparable
to the baselines.
"""

# ---------------------------------------------------------------------------
# 1. TOPICS — the 13 rows of the Week 1 Trend Heatmap.
#    "queries"     -> sent to Google News RSS (each query returns up to ~100
#                     articles). More queries = more sources per topic.
#    "match_terms" -> lowercase phrases used to assign articles from the
#                     curated industry feeds (Section 5) to this topic.
# ---------------------------------------------------------------------------
TOPICS = {
    "Market Sizing & Spend": {
        "queries": [
            "AI infrastructure spending forecast",
            "data center capex AI investment",
            "AI networking market size forecast",
            "enterprise AI infrastructure budget",
        ],
        "match_terms": ["market size", "capex", "spending forecast", "billion",
                        "infrastructure investment", "it spending"],
    },
    "AIOps / Autonomous Networks": {
        "queries": [
            "AIOps network operations",
            "autonomous network self-driving operations",
            "agentic AI network management",
        ],
        "match_terms": ["aiops", "autonomous network", "self-driving network",
                        "agentic", "network automation"],
    },
    "AI Back-End / GPU Fabric": {
        "queries": [
            "GPU cluster network fabric",
            "AI back-end network Ethernet fabric",
            "GPU interconnect data center networking",
        ],
        "match_terms": ["gpu fabric", "back-end network", "gpu cluster",
                        "ai fabric", "interconnect"],
    },
    "Adoption Barriers & Skills": {
        "queries": [
            "AI adoption barriers enterprise survey",
            "network engineer skills gap AI",
            "enterprise AI readiness challenges",
        ],
        "match_terms": ["skills gap", "adoption barrier", "talent shortage",
                        "ai readiness", "survey"],
    },
    "Private / Sovereign AI": {
        "queries": [
            "private AI enterprise infrastructure",
            "sovereign AI cloud data center",
            "on-premises AI deployment enterprise",
        ],
        "match_terms": ["private ai", "sovereign", "on-premises ai", "on-prem ai"],
    },
    "Power & Sustainability": {
        "queries": [
            "data center power consumption AI",
            "AI data center energy sustainability",
            "liquid cooling data center",
        ],
        "match_terms": ["power", "energy", "sustainability", "liquid cooling",
                        "megawatt", "gigawatt"],
    },
    "High-Speed Optics": {
        "queries": [
            "800G optics data center",
            "1.6T optical transceiver AI",
            "co-packaged optics networking",
        ],
        "match_terms": ["800g", "1.6t", "optics", "optical", "transceiver",
                        "co-packaged"],
    },
    "Ethernet vs NVLink (Scale-up)": {
        "queries": [
            "Ethernet scale-up AI networking NVLink",
            "Ultra Ethernet Consortium AI",
            "UALink NVLink scale-up fabric",
        ],
        "match_terms": ["nvlink", "ualink", "scale-up", "ultra ethernet",
                        "sonic ethernet"],
    },
    "Vendor Product Launch": {
        "queries": [
            "AI networking switch launch announcement",
            "networking vendor AI product release",
            "new data center switch AI announcement",
        ],
        "match_terms": ["launches", "unveils", "announces", "introduces",
                        "new switch", "new router", "new platform"],
    },
    "Network Security (Zero-Trust)": {
        "queries": [
            "zero trust network security AI",
            "AI infrastructure network security",
            "secure AI data center network",
        ],
        "match_terms": ["zero-trust", "zero trust", "security", "firewall",
                        "sase"],
    },
    "Network Observability": {
        "queries": [
            "network observability AI workloads",
            "AI network telemetry monitoring",
            "network visibility GPU cluster",
        ],
        "match_terms": ["observability", "telemetry", "monitoring",
                        "visibility"],
    },
    "NaaS / Cloud Connectivity": {
        "queries": [
            "network as a service enterprise cloud",
            "multicloud networking connectivity AI",
            "cloud WAN interconnect enterprise",
        ],
        "match_terms": ["naas", "network as a service", "multicloud",
                        "multi-cloud", "cloud wan", "interconnect"],
    },
    "Competitive / M&A": {
        "queries": [
            "networking vendor acquisition merger",
            "telecom networking company acquisition AI",
            "HPE Juniper Cisco competition AI networking",
        ],
        "match_terms": ["acquisition", "acquires", "merger", "m&a",
                        "consolidation"],
    },
}

# ---------------------------------------------------------------------------
# 2. SOURCE TYPES — the 4 columns of the Trend Heatmap.
#    An article is classified by the domain of its publisher. Anything not
#    matched below defaults to "Industry News".
# ---------------------------------------------------------------------------
SOURCE_TYPE_DOMAINS = {
    "Analyst Report": [
        "gartner.com", "idc.com", "forrester.com", "451research.com",
        "omdia.com", "delloro.com", "650group.com", "mckinsey.com",
        "spglobal.com", "isg-one.com",
    ],
    "Market Research": [
        "researchandmarkets.com", "marketsandmarkets.com",
        "grandviewresearch.com", "mordorintelligence.com",
        "globenewswire.com", "prnewswire.com", "businesswire.com",
        "statista.com",
    ],
    "Vendor (Primary)": [
        "cisco.com", "blogs.cisco.com", "nvidia.com", "juniper.net",
        "hpe.com", "arista.com", "lumen.com", "tatacommunications.com",
        "microsoft.com", "cloud.google.com", "aws.amazon.com", "nokia.com",
        "ciena.com", "broadcom.com", "marvell.com", "att.com",
        "verizon.com", "equinix.com", "nttdata.com", "orange-business.com",
    ],
    # "Industry News" is the default bucket — no list needed.
}
DEFAULT_SOURCE_TYPE = "Industry News"
SOURCE_TYPES = ["Analyst Report", "Industry News", "Market Research",
                "Vendor (Primary)"]

# ---------------------------------------------------------------------------
# 3. KEYWORDS — the 20 tracked terms from Week 1 (Keyword_Frequency sheet).
#    Each keyword maps to a list of case-insensitive aliases. An article
#    counts once per keyword if any alias appears in its title or snippet.
# ---------------------------------------------------------------------------
KEYWORDS = {
    "AI infrastructure":     {"category": "Market",       "aliases": ["ai infrastructure"]},
    "data center":           {"category": "Market",       "aliases": ["data center", "data centre", "datacenter"]},
    "hyperscaler":           {"category": "Market",       "aliases": ["hyperscaler", "hyperscale"]},
    "GPU":                   {"category": "Fabric",       "aliases": ["gpu"]},
    "Ethernet":              {"category": "Fabric",       "aliases": ["ethernet"]},
    "scale-up":              {"category": "Fabric",       "aliases": ["scale-up", "scale up fabric"]},
    "SONiC":                 {"category": "Fabric",       "aliases": ["sonic"]},
    "NVLink":                {"category": "Fabric",       "aliases": ["nvlink"]},
    "AIOps":                 {"category": "Operations",   "aliases": ["aiops"]},
    "agentic":               {"category": "Operations",   "aliases": ["agentic"]},
    "network observability": {"category": "Operations",   "aliases": ["observability"]},
    "800G":                  {"category": "Optics",       "aliases": ["800g", "800 gbe", "800gbe", "1.6t"]},
    "NaaS":                  {"category": "Connectivity", "aliases": ["naas", "network as a service"]},
    "PCF":                   {"category": "Connectivity", "aliases": ["programmable cloud fabric", "cloud fabric"]},
    "multi-cloud":           {"category": "Connectivity", "aliases": ["multi-cloud", "multicloud"]},
    "private AI":            {"category": "Strategy",     "aliases": ["private ai"]},
    "sovereign":             {"category": "Strategy",     "aliases": ["sovereign"]},
    "zero-trust":            {"category": "Security",     "aliases": ["zero-trust", "zero trust"]},
    "liquid cooling":        {"category": "Power",        "aliases": ["liquid cooling"]},
    "Mist":                  {"category": "Vendor",       "aliases": ["mist ai", "juniper mist"]},
}

# ---------------------------------------------------------------------------
# 4. VENDORS — the 14 competitors from Week 1 (Vendor_Mentions sheet).
#    "require_all": every alias group must appear (used for HPE/Juniper,
#    which only counts when the article mentions both names).
# ---------------------------------------------------------------------------
VENDORS = {
    "Cisco":               {"category": "Networking vendor",          "aliases": ["cisco"]},
    "Juniper":             {"category": "Networking vendor",          "aliases": ["juniper"]},
    "HPE/Juniper":         {"category": "Networking vendor",          "aliases": ["hpe"], "require_all": ["hpe", "juniper"]},
    "Arista":              {"category": "Networking vendor",          "aliases": ["arista"]},
    "NVIDIA":              {"category": "Silicon / fabric",           "aliases": ["nvidia"]},
    "Lumen":               {"category": "Telco / NSP",                "aliases": ["lumen"]},
    "AT&T":                {"category": "Telco / NSP",                "aliases": ["at&t"]},
    "Verizon":             {"category": "Telco / NSP",                "aliases": ["verizon"]},
    "NTT DATA":            {"category": "Telco / NSP",                "aliases": ["ntt"]},
    "Orange Business":     {"category": "Telco / NSP",                "aliases": ["orange business"]},
    "Equinix":             {"category": "Data center / interconnect", "aliases": ["equinix"]},
    "Tata Communications": {"category": "Telco / NSP (baseline)",     "aliases": ["tata communications"]},
    "Microsoft":           {"category": "Hyperscaler",                "aliases": ["microsoft", "azure"]},
    "Google":              {"category": "Hyperscaler",                "aliases": ["google cloud", "gcp"]},
}

# ---------------------------------------------------------------------------
# 5. CURATED INDUSTRY FEEDS — the outlets named in the internship brief.
#    These supplement Google News. A dead feed is logged and skipped;
#    it never breaks the run, because Google News alone can satisfy the
#    source-count thresholds.
# ---------------------------------------------------------------------------
CURATED_FEEDS = [
    ("Network World",        "https://www.networkworld.com/feed/"),
    ("SDxCentral",           "https://www.sdxcentral.com/feed/"),
    ("Light Reading",        "https://www.lightreading.com/rss.xml"),
    ("Data Center Dynamics", "https://www.datacenterdynamics.com/en/rss/"),
    ("The Register",         "https://www.theregister.com/networks/headlines.atom"),
    ("Fierce Network",       "https://www.fiercenetwork.com/rss/xml"),
    ("CIO.com",              "https://www.cio.com/feed/"),
]

# ---------------------------------------------------------------------------
# 6. INDUSTRIES — the 9 verticals from the Week 3 account model. Article
#    counts here power the Week 4 "industry momentum × account tier" join.
# ---------------------------------------------------------------------------
INDUSTRIES = {
    "Technology":                 ["software company", "saas", "tech giant", "semiconductor"],
    "Financial Services":         ["bank", "banking", "financial services", "insurance", "fintech", "capital markets"],
    "Healthcare":                 ["healthcare", "hospital", "pharma", "pharmaceutical", "medical", "life sciences"],
    "Manufacturing & Industrial": ["manufacturing", "manufacturer", "factory", "industrial", "automotive"],
    "Retail & Consumer":          ["retail", "retailer", "e-commerce", "ecommerce", "consumer goods"],
    "Energy & Utilities":         ["energy company", "utility", "utilities", "oil and gas", "power grid"],
    "Media & Entertainment":      ["media company", "streaming", "entertainment", "broadcaster"],
    "Logistics & Transportation": ["logistics", "supply chain", "shipping", "airline", "freight"],
    "Professional Services":      ["consulting", "consultancy", "professional services", "advisory"],
}

# ---------------------------------------------------------------------------
# 7. VALIDATION RULES — from the manager's feedback, verbatim.
#    First refresh: >= 15 distinct sources per topic.
#    Every later refresh: >= 12 distinct sources per topic.
#    If a topic is short, the window widens (35 -> 60 -> 90 days) and the
#    fetch retries before the run is declared a failure.
# ---------------------------------------------------------------------------
MIN_SOURCES_FIRST_REFRESH = 15
MIN_SOURCES_REPEAT_REFRESH = 12
LOOKBACK_WINDOWS_DAYS = [35, 60, 90]

# Politeness / reliability settings for outbound requests.
REQUEST_TIMEOUT_SECONDS = 20
SECONDS_BETWEEN_REQUESTS = 1.0
USER_AGENT = ("Mozilla/5.0 (compatible; ai-networks-intel-bot/1.0; "
              "+https://github.com; educational market-intelligence project)")

# ---------------------------------------------------------------------------
# 8. OUTPUT PATHS — everything the website reads lives under docs/data so
#    GitHub Pages can serve it. Do not move these without updating the
#    JavaScript fetch paths in docs/assets/.
# ---------------------------------------------------------------------------
DATA_DIR = "docs/data"
LATEST_JSON = f"{DATA_DIR}/latest.json"
HISTORY_JSON = f"{DATA_DIR}/history.json"
VALIDATION_JSON = f"{DATA_DIR}/validation_report.json"
ARCHIVE_DIR = f"{DATA_DIR}/archive"
LATEST_XLSX = f"{DATA_DIR}/latest_data.xlsx"   # auto-refreshed Tableau source
BASELINE_WEEK1 = f"{DATA_DIR}/baselines/week1_baseline.json"
BASELINE_WEEK3 = f"{DATA_DIR}/baselines/week3_accounts.json"
