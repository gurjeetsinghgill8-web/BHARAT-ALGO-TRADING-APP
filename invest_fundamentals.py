"""
invest_fundamentals.py — BHARAT ALGOVERSE v3.1 | Fundamental Reason Engine
============================================================================
LEGO 6: Why is this sector running right now?

Rule-based mapping — no external API needed.
Covers government policy, macro factors, sector tailwinds.
Returns 4-5 bullet points per sector explaining the rally.

Updated: 2026 India context
"""

from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")


# ════════════════════════════════════════════════════════════
# SECTOR FUNDAMENTAL DATABASE
# ════════════════════════════════════════════════════════════

SECTOR_FUNDAMENTALS = {
    "Nifty Auto": {
        "short": "Auto sector chal raha hai — demand + EV cycle",
        "reasons": [
            "🚗 India's auto sales at multi-year highs — PV, 2W, CV all segments growing",
            "⚡ EV transition accelerating — Tata, M&M, TVS getting premium valuations for EV pipeline",
            "🌾 Rural demand recovery — good monsoon → 2-wheeler/tractor cycle turning up",
            "🏦 Low interest rates + easy vehicle financing driving retail demand",
            "🌏 Export momentum — India becoming auto export hub for small cars & EV components",
        ],
        "risk": "Semiconductor shortage, commodity cost spike, or monsoon failure can reverse trend.",
    },
    "Nifty Bank": {
        "short": "Banks strong — credit growth + clean balance sheets",
        "reasons": [
            "📈 Credit growth running at 14-16% YoY — highest in a decade",
            "🧹 NPA (bad loan) cycle complete — all large banks report clean books",
            "💰 RBI rate normalization helps NIMs (Net Interest Margins) stay elevated",
            "🏗️ Corporate capex revival → large project financing — PSU & private banks both winning",
            "📊 FII inflows into banking sector — weight in indices attracting passive funds",
        ],
        "risk": "RBI tightening cycle, global banking stress, or NPAs rising in retail segment.",
    },
    "Nifty PSU Bank": {
        "short": "PSU Banks — government backing + valuations cheap",
        "reasons": [
            "🏛️ Government capex ₹11+ lakh crore — PSU banks are biggest lenders to infra projects",
            "📉 All PSU banks done NPA cleanup — operating leverage playing out in profits",
            "💸 Dividend yield attractive — government as promoter ensures dividends",
            "📊 Still trading at 0.8-1.2x book — significant discount to private banks",
            "🔄 Credit growth in MSME & agri — PSU banks dominant in these segments",
        ],
        "risk": "Election-time directed lending returning, or government pressuring rates below market.",
    },
    "Nifty IT": {
        "short": "IT recovery — US spending + AI deals",
        "reasons": [
            "🤖 AI/GenAI implementation deals — Indian IT cos getting large transformation contracts",
            "🇺🇸 US tech spend recovery — BFSI, retail, healthcare verticals all re-opening budgets",
            "💱 Rupee weakness vs USD — IT earns in USD, reports in INR → automatic margin boost",
            "📦 Deal TCV at record highs — multi-year contracts giving earnings visibility",
            "🌐 Europe recovery + BFSI segment revival adding to diversification",
        ],
        "risk": "US recession, visa restrictions, strong rupee, or AI replacing lower-end IT jobs.",
    },
    "Nifty Pharma": {
        "short": "Pharma — US FDA approvals + domestic growth",
        "reasons": [
            "🇺🇸 US FDA import alerts resolved for major players — export volumes recovering",
            "💊 Chronic disease burden rising — diabetes, cardiac, oncology segments growing 18%+",
            "🧬 API (Active Pharma Ingredient) — India becoming China+1 for global pharma supply",
            "🏥 Healthcare infrastructure expansion — hospitals + insurance penetration rising",
            "📋 USFDA inspections clearing backlog — companies getting more product approvals",
        ],
        "risk": "US price erosion in generics, FDA import alerts returning, or competition from China.",
    },
    "Nifty FMCG": {
        "short": "FMCG — rural recovery + premiumization",
        "reasons": [
            "🌾 Rural income revival — good rabi crop + MSP increases boosting FMCG consumption",
            "🛍️ Premiumization trend — urban consumers upgrading from economy to premium SKUs",
            "📉 Raw material costs cooling — palm oil, crude derivatives dropping → margin expansion",
            "🏪 Kirana modernization + quick commerce growth — distribution reach expanding",
            "💰 Volume growth returning after 6-8 quarters of value-led growth",
        ],
        "risk": "Monsoon failure, rural distress, competitive pressure from regional brands.",
    },
    "Nifty Metal": {
        "short": "Metal sector — China + India infra cycle",
        "reasons": [
            "🇨🇳 China stimulus revival — metal demand from China's construction/infra pickup",
            "🏗️ India PLI + infra spend creating captive domestic demand for steel, aluminium",
            "📈 Global commodity supercycle — supply not keeping up with EV/green energy demand",
            "⚡ EV & renewable energy need — copper, lithium, nickel, aluminium all in structural demand",
            "🔄 Inventory restocking cycle — global manufacturers rebuilding depleted inventories",
        ],
        "risk": "China slowdown, US recession reducing metals demand, or supply glut from new mines.",
    },
    "Nifty Realty": {
        "short": "Real estate bull run — affordability + RERA trust",
        "reasons": [
            "🏘️ Housing demand at 10-year high — millennials entering home-buying age in India",
            "📋 RERA building trust — buyers more confident after regulatory protection",
            "💰 Home loan rates still historically affordable — EMIs manageable",
            "🏙️ Tier-2 city expansion — builders expanding beyond Mumbai/NCR/Bengaluru",
            "🔄 Inventory overhang cleared — fresh launches getting pre-sold immediately",
        ],
        "risk": "Interest rate spike, regulatory tightening, or economic slowdown reducing demand.",
    },
    "Nifty Energy": {
        "short": "Energy sector — green transition + government policy",
        "reasons": [
            "☀️ Renewable energy push — India's 500 GW target by 2030 driving massive capex",
            "⚡ NTPC, Adani Green, JSW Energy — massive capacity addition plans getting funded",
            "🛢️ Oil & Gas reform — ONGC/Oil India getting exploration blocks + pricing freedom",
            "🔋 Energy storage demand — battery, pumped hydro storage — new opportunity opening",
            "🏛️ Government coal PLI + renewable tariff clarity → investment certainty",
        ],
        "risk": "Global oil price crash, delayed renewable auctions, or policy reversal.",
    },
    "Nifty Infra": {
        "short": "Infra boom — government capex super cycle",
        "reasons": [
            "🏗️ ₹11 lakh crore government capex — roads, railways, ports, airports all booming",
            "🚄 PM Gati Shakti + NIP ₹100 lakh crore multi-year pipeline — visibility for 5 years",
            "🔌 Power infra — transmission lines, substations — Rs 3 lakh crore opportunity",
            "🌊 Jal Jeevan Mission, Smart Cities — creating urban infra demand",
            "📦 Logistics & warehousing boom — industrial corridors driving real estate + infra",
        ],
        "risk": "Fiscal constraints forcing capex cuts, election changes in spending priorities.",
    },
    "Nifty Media": {
        "short": "Media — OTT + digital ad recovery",
        "reasons": [
            "📱 OTT subscriber growth — ZEE, SunTV, Network18 all expanding digital presence",
            "📺 IPL & cricket rights creating advertising demand surge for broadcasters",
            "💻 Digital advertising recovery — as economy strengthens, ad budgets opening up",
            "🎬 Content boom — Indian content going global (Netflix, Amazon co-productions)",
            "📡 Sports streaming rights consolidation — creating moats for incumbents",
        ],
        "risk": "Content cost inflation, competition from global OTT, or advertising slowdown.",
    },
    "Nifty Finance": {
        "short": "NBFCs + financial services — credit boom",
        "reasons": [
            "📊 Bajaj Finance, Muthoot, Chola — consumer credit growing at 20%+ YoY",
            "💳 Credit card, personal loan boom — India's credit penetration still very low",
            "🏠 Housing finance revival — affordable housing demand still unmet in Tier 2/3",
            "🏆 Mutual fund AUM growing — wealth management fee income rising structurally",
            "📈 Insurance penetration still low — massive growth runway ahead",
        ],
        "risk": "NPA spike in retail/MSME segment, or RBI tightening NBFC lending norms.",
    },
    "Nifty Midcap 100": {
        "short": "Midcap outperformance — domestic growth stories",
        "reasons": [
            "🏭 Manufacturing PLI beneficiaries — many midcap cos in electronics, pharma, chemicals",
            "📈 Earnings growth > Nifty — midcaps growing faster than large caps currently",
            "🌊 Domestic consumption theme — midcaps more India-focused, less global risk",
            "💰 SIP inflows — ₹20,000 crore/month into mutual funds, many mid-cap funds active",
            "🔄 Market leadership rotation — after large cap run, mid/small caps getting attention",
        ],
        "risk": "Liquidity risk in market downturn, valuations stretched in some names.",
    },
    "Nifty Smallcap": {
        "short": "Small cap surge — emerging stories + speculative",
        "reasons": [
            "🚀 Domestic themes — defence, railways, EVs have many small cap plays",
            "💹 Re-rating cycle — small cos delivering above-expectation earnings",
            "🏗️ Government contract beneficiaries — many small cos winning govt tenders",
            "📊 Low institutional ownership — retail discovery still ongoing",
            "🔄 Economic cycle upturn — small cos get disproportionate benefit in upcycles",
        ],
        "risk": "Most vulnerable in market correction. High volatility. Illiquid in panic.",
    },
    "Nifty Commodities": {
        "short": "Commodity cycle — global demand revival",
        "reasons": [
            "🌍 Global commodity supercycle — underinvestment in supply + rising demand",
            "⚡ Green energy materials — copper, aluminium, lithium in structural demand",
            "🇨🇳 China re-stimulation — largest commodity consumer restarting economy",
            "🛢️ Oil supply discipline by OPEC+ — prices staying elevated",
            "📦 Global logistics normalizing — supply chains rebuilding inventories",
        ],
        "risk": "China slowdown, US recession, or commodity supply surge from new projects.",
    },
}

DEFAULT_FUNDAMENTALS = {
    "short": "Sector showing momentum vs Nifty",
    "reasons": [
        "📊 RS-55 above 1.0 — sector outperforming Nifty benchmark",
        "📈 Price action strong — sector making higher highs vs Nifty",
        "💹 Institutional interest — volume and participation rising",
        "🔄 Earnings momentum — sector companies reporting better results",
    ],
    "risk": "Monitor RS weekly — exit when RS drops below 0.95.",
}


# ════════════════════════════════════════════════════════════
# PUBLIC API
# ════════════════════════════════════════════════════════════

def get_sector_thesis(sector_name: str, rs_value: float = 0) -> dict:
    """
    Returns fundamental thesis for a sector.
    {short, reasons: [str], risk: str}
    """
    fund = SECTOR_FUNDAMENTALS.get(sector_name, DEFAULT_FUNDAMENTALS)
    result = dict(fund)
    result["sector"] = sector_name
    result["rs_55"]  = round(rs_value, 3)
    result["rs_pct"] = f"{(rs_value - 1) * 100:+.1f}% vs Nifty" if rs_value else ""
    return result


def format_thesis_text(sector_name: str, rs_value: float = 0) -> str:
    """Formats sector thesis as readable Telegram/dashboard text."""
    thesis = get_sector_thesis(sector_name, rs_value)
    lines  = [
        f"📌 **WHY {sector_name.upper()} IS LEADING?**",
        f"RS-55: {thesis['rs_55']:.3f} ({thesis['rs_pct']})",
        f"_{thesis['short']}_",
        "",
        "**Key Drivers:**",
    ]
    for reason in thesis["reasons"]:
        lines.append(f"  {reason}")
    lines += [
        "",
        f"⚠️ **Risk:** {thesis['risk']}",
    ]
    return "\n".join(lines)


def format_all_top_sector_theses(top_sectors: list[dict]) -> str:
    """Format thesis for all top sectors in one block."""
    if not top_sectors:
        return "Koi strong sector nahi mila abhi. Market defensive mode mein hai."

    blocks = []
    for s in top_sectors:
        blocks.append(format_thesis_text(s["sector"], s.get("rs", 0)))
        blocks.append("─" * 40)

    return "\n".join(blocks)
