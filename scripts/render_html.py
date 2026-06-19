"""Render static HTML from normalized JSON."""
from __future__ import annotations

import re
from copy import deepcopy
from html import escape
from pathlib import Path

from bs4 import BeautifulSoup

from images import cleanup_orphan_images
from template_utils import (
    DETAIL_TEMPLATES_DIR,
    LISTING_TEMPLATES_DIR,
    apply_status_visibility,
    ensure_detail_templates,
    ensure_listing_templates,
)
from util import (
    ROOT,
    adjust_root_paths,
    apply_bindings,
    clean_text,
    format_deadline,
    set_page_title,
    status_class,
    twitter_handle,
)

FOOTER_MINIMAL = """
  <div class="section-footer">
    <div class="container-default w-container">
      <div class="flex-footer-32px">
        <h2 class="heading-section white">superteamDAO</h2>
        <div class="flex-legal-8px">
          <a href="{prefix}docs/tnc.html" class="links-footer">Terms and Privacy</a>
          <div class="text-bodysmaller">superteam © 2022</div>
        </div>
      </div>
    </div>
  </div>
"""

NAV = """
  <div data-animation="over-right" data-collapse="medium" data-duration="400" data-easing="ease" data-easing2="ease" data-doc-height="1" role="banner" class="navbar-default w-nav">
    <div class="container-navbar w-container">
      <a href="{prefix}index.html" class="navbar-home w-nav-brand"><img alt="Superteam Logo" loading="lazy" src="{prefix}images/Logo.svg"></a>
      <nav role="navigation" class="navbar-menu w-nav-menu">
        <a href="{prefix}about.html" class="navbar-links w-nav-link">about</a>
        <a href="{prefix}earn.html" class="navbar-links w-nav-link">earn</a>
        <a href="{prefix}grow.html" class="navbar-links w-nav-link">grow</a>
        <a href="{prefix}showcase.html" class="navbar-links w-nav-link">showcase</a>
        <a href="{prefix}connect.html" class="navbar-links w-nav-link">connect</a>
      </nav>
      <div class="navbar-menubutton w-nav-button">
        <div class="icon-menu open w-embed"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewbox="0 0 24 24"><path d="M18 7H6a1 1 0 0 0 0 2h12a1 1 0 1 0 0-2Zm0 4H6a1 1 0 1 0 0 2h12a1 1 0 1 0 0-2Zm0 4H6a1 1 0 1 0 0 2h12a1 1 0 1 0 0-2Z"></path></svg></div>
      </div>
    </div>
  </div>
"""

HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <meta content="width=device-width, initial-scale=1" name="viewport">
  <link href="{prefix}css/normalize.css" rel="stylesheet" type="text/css">
  <link href="{prefix}css/webflow.css" rel="stylesheet" type="text/css">
  <link href="{prefix}css/akshays-design-for-superteam-fun.webflow.css" rel="stylesheet" type="text/css">
  <script type="text/javascript">!function(o,c){{var n=c.documentElement,t=" w-mod-";n.className+=t+"js",("ontouchstart"in o||o.DocumentTouch&&c instanceof DocumentTouch)&&(n.className+=t+"touch")}}(window,document);</script>
  <link href="{prefix}images/favicon.png" rel="shortcut icon" type="image/x-icon">
  <style>h1, h2, h3, h4 {{ font-variation-settings: "wdth" 110; }}</style>
</head>
<body class="{body_class}">
"""

SCRIPTS = """
  <script src="https://d3e54v103j8qbb.cloudfront.net/js/jquery-3.5.1.min.dc5e7f18c8.js?site=65b670ec21078c5d27e36100" type="text/javascript" integrity="sha256-9/aliU8dGd2tb6OSsuzixeV4y/faTqgFtohetphbbj0=" crossorigin="anonymous"></script>
  <script src="{prefix}js/webflow.js" type="text/javascript"></script>
</body>
</html>
"""


def load_template(name: str) -> str:
    return (DETAIL_TEMPLATES_DIR / name).read_text(encoding="utf-8")


def load_listing_template(rel_path: str) -> str:
    return (LISTING_TEMPLATES_DIR / rel_path).read_text(encoding="utf-8")


def write_html(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def render_from_template(
    template_name: str,
    out_path: Path,
    bindings: list[dict],
    title: str,
    depth: int = 1,
    status: str = "open",
) -> None:
    soup = BeautifulSoup(load_template(template_name), "html.parser")
    apply_bindings(soup, bindings)
    apply_status_visibility(soup, status)
    set_page_title(soup, title)
    html = adjust_root_paths(str(soup), depth)
    write_html(out_path, html)


def simple_page(prefix: str, body_class: str, title: str, hero_title: str, hero_sub: str, content_html: str) -> str:
    return (
        HEAD.format(title=escape(title), prefix=prefix, body_class=body_class)
        + NAV.format(prefix=prefix)
        + f"""
  <div class="section-hero squirclelightpurple">
    <div class="container-hero w-container">
      <div class="flex-hero-32px">
        <h1 class="heading-hero yellow">{escape(hero_title)}</h1>
        <h4 class="heading-hero constrain-30">{escape(hero_sub)}</h4>
      </div>
    </div>
  </div>
  <div class="section-default">
    <div class="container-default w-container">
      {content_html}
    </div>
  </div>
"""
        + FOOTER_MINIMAL.format(prefix=prefix)
        + SCRIPTS.format(prefix=prefix)
    )


def bounty_card_html(item: dict, prefix: str, closed: bool = False) -> str:
    f = item["fields"]
    st = status_class(f.get("status", ""))
    card_class = "closed" if closed or st != "open" else "open"
    badge = "Badge---Bounties---Dark.svg" if card_class == "closed" else "Badge---Bounties---Light.svg"
    href = f"{prefix}bounties/{item['slug']}.html"
    deadline = format_deadline(f.get("deadline"))
    date_text = f"<strong>{escape(deadline)}</strong>" if deadline else ""
    return f"""
          <div role="listitem" class="w-dyn-item">
            <div class="card-earnitem {card_class}">
              <div class="card-top"><img src="{prefix}images/{badge}" loading="lazy" alt="Bounties graphic" class="image-cardbadge">
                <div class="block-cardcontent-8px centered">
                  <div class="text-bodysmall">{escape(f.get('skillTag', ''))}</div>
                  <h3 class="card-text-title earncards">{escape(item['name'])}</h3>
                  <div class="text-bodylarge">{escape(f.get('type', ''))}</div>
                </div>
              </div>
              <div class="card-bottom">
                <div class="block-cardcontent-8px centered open">
                  <div class="text-currency">
                    <h1 class="text-currencymark emphasis-high nomargin">$</h1>
                    <h1 class="card-text-title earncards">{escape(f.get('prize', ''))}</h1>
                  </div>
                  <div class="text-bodyregular carddate">{date_text}</div>
                </div>
              </div>
              <a href="{href}" class="button-small button-lightprimary open w-button">get to work!</a>
              <a href="{href}" class="button-small button-lightsecondary w-button">sold!</a>
            </div>
          </div>"""


def mission_card_html(item: dict, prefix: str, closed: bool = False) -> str:
    f = item["fields"]
    st = status_class(f.get("status", ""))
    card_class = "closed" if closed or st != "open" else "open"
    badge = "Badge---Missions---Dark.svg" if card_class == "closed" else "Badge---Missions---Light.svg"
    href = f"{prefix}missions/{item['slug']}.html"
    return f"""
          <div role="listitem" class="w-dyn-item">
            <div class="card-earnitem {card_class}">
              <div class="card-top"><img src="{prefix}images/{badge}" loading="lazy" alt="Missions graphic" class="image-cardbadge">
                <div class="block-cardcontent-8px centered">
                  <div class="text-bodysmall">{escape(f.get('skillTag', ''))}</div>
                  <h3 class="card-text-title text-centered">{escape(item['name'])}</h3>
                  <div class="text-bodylarge">{escape(f.get('type', ''))}</div>
                </div>
              </div>
              <a href="{href}" class="button-small button-lightprimary open w-button">find a mission</a>
              <a href="{href}" class="button-small button-lightsecondary w-button">sold!</a>
            </div>
          </div>"""


def instagrant_card_html(item: dict, prefix: str) -> str:
    f = item["fields"]
    href = f"{prefix}instagrants/{item['slug']}.html"
    grant = clean_text(f.get("grantSize"))
    currency = clean_text(f.get("currency"))
    amount = f"{grant} {currency}".strip() if grant else "Instagrant"
    return f"""
          <div role="listitem" class="w-dyn-item">
            <div class="card-earnitem open">
              <div class="card-top"><img src="{prefix}images/Badge---Instagrants---Light.svg" loading="lazy" alt="Instagrants graphic" class="image-cardbadge">
                <div class="block-cardcontent-8px centered">
                  <div class="text-bodysmall">INSTAGRANT</div>
                  <h3 class="card-text-title text-centered">{escape(item['name'])}</h3>
                  <div class="text-bodylarge">{escape(amount)}</div>
                </div>
              </div>
              <a href="{href}" class="button-small button-lightprimary open w-button">apply now</a>
            </div>
          </div>"""


def project_card_html(item: dict, prefix: str, include_led_by: bool = True) -> str:
    f = item["fields"]
    thumb = f.get("thumbnail") or f.get("Thumbnail") or ""
    if thumb and not thumb.startswith("http"):
        thumb_src = f"{prefix}{thumb}"
    else:
        thumb_src = thumb or ""
    href = f"{prefix}projects/{item['slug']}.html"
    led_by_html = ""
    if include_led_by:
        lead_name = f.get("projectLead") or ""
        led_slug = item.get("refs", {}).get("ledBy")
        if led_slug:
            led_by_html = f'<div><div class="text-bodyregular inlinespace"><strong>Led by </strong></div><a href="{prefix}dao-members/{led_slug}.html" class="text-bodyregular text-emphasis">{escape(lead_name)}</a></div>'
        elif lead_name:
            led_by_html = f'<div><div class="text-bodyregular inlinespace"><strong>Led by </strong></div><span class="text-bodyregular text-emphasis">{escape(lead_name)}</span></div>'
    desc = f.get("description") or f.get("tagline") or ""
    return f"""
            <div role="listitem" class="w-dyn-item">
              <div class="card-project yellow">
                <div class="block-cardcontent-16px"><img alt="" loading="lazy" src="{escape(thumb_src)}" class="image-projectthumbnail">
                  <div class="block-cardcontent-8px">
                    <h3 class="card-text-title purple">{escape(item['name'])}</h3>
                    <div class="text-bodysmall">{escape(f.get('tagline', ''))}</div>
                    {led_by_html}
                    <div class="text-bodyregular">{escape(desc[:200])}</div>
                  </div>
                </div>
                <div class="block-buttonrow">
                  <a href="{href}" class="button-small button-lightsecondary w-inline-block">
                    <div class="text-buttonsmall">see project</div>
                  </a>
                </div>
              </div>
            </div>"""


def patch_dyn_list(html: str, list_index: int, cards_html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    lists = soup.select(".w-dyn-list")
    if list_index >= len(lists):
        return html
    dyn_list = lists[list_index]
    items_container = dyn_list.select_one(".w-dyn-items")
    if not items_container:
        return html
    parsed = BeautifulSoup(cards_html, "html.parser")
    items = parsed.select(".w-dyn-item")
    items_container.clear()
    for item in items:
        items_container.append(item)
    empty = dyn_list.select_one(".w-dyn-empty")
    if empty:
        empty.decompose()
    return str(soup)


def patch_file_dyn_lists(rel_path: str, patches: dict[int, str]) -> None:
    html = load_listing_template(rel_path)
    for idx in sorted(patches):
        html = patch_dyn_list(html, idx, patches[idx])
    out = ROOT / rel_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"  patched {rel_path}")


def render_dao_members(items: list[dict]) -> None:
    out_dir = ROOT / "dao-members"
    cards = []
    for m in items:
        tw = m["fields"].get("twitterLink", "")
        handle = twitter_handle(tw)
        label = f"@{handle}" if handle else m["name"]
        cards.append(f"""
            <div role="listitem" class="w-dyn-item">
              <div class="card-project yellow">
                <div class="block-cardcontent-16px">
                  <div class="block-cardcontent-8px">
                    <h3 class="card-text-title purple">{escape(m['name'])}</h3>
                    <div class="text-bodyregular"><a href="{escape(tw)}" target="_blank" rel="noopener noreferrer" class="text-emphasis">{escape(label)}</a></div>
                  </div>
                </div>
                <div class="block-buttonrow">
                  <a href="{m['slug']}.html" class="button-small button-lightsecondary w-inline-block">
                    <div class="text-buttonsmall">view profile</div>
                  </a>
                </div>
              </div>
            </div>""")
        content = f'<div class="text-bodylarge"><a href="{escape(tw)}" target="_blank" rel="noopener noreferrer" class="text-bodyregular text-emphasis">{escape(label)}</a></div>'
        write_html(out_dir / f"{m['slug']}.html", simple_page("../", "body-palepurple", f"{m['name']} | Superteam", m["name"], "DAO Member", content))

    index = simple_page("../", "body-palepurple", "DAO Members | Superteam", "DAO Members", "Core contributors in the Superteam cooperative", f'<div role="list" class="grid-gallerycards w-dyn-items">{"".join(cards)}</div>')
    write_html(out_dir / "index.html", index)


def render_master_skills(items: list[dict], bounties: list[dict]) -> None:
    out_dir = ROOT / "skills"
    bounty_by_skill: dict[str, list] = {}
    for b in bounties:
        for slug in b.get("refs", {}).get("skills", []):
            bounty_by_skill.setdefault(slug, []).append(b)

    cards = []
    for s in items:
        cards.append(f"""
            <div role="listitem" class="w-dyn-item">
              <div class="card-project yellow">
                <div class="block-cardcontent-8px">
                  <h3 class="card-text-title purple">{escape(s['name'])}</h3>
                </div>
                <div class="block-buttonrow">
                  <a href="{s['slug']}.html" class="button-small button-lightsecondary w-inline-block">
                    <div class="text-buttonsmall">view opportunities</div>
                  </a>
                </div>
              </div>
            </div>""")

        related = bounty_by_skill.get(s["slug"], [])[:8]
        bounty_cards = "".join(bounty_card_html(b, "../") for b in related)
        if related:
            content = f'<div class="w-layout-grid grid-gallerycards-bound">{bounty_cards}</div>'
        else:
            content = '<p class="text-bodylarge">No bounties tagged with this skill.</p>'

        page = (
            HEAD.format(title=escape(f"{s['name']} | Superteam"), prefix="../", body_class="body-palepurple")
            + NAV.format(prefix="../")
            + f"""
  <div class="section-hero squirclelightpurple">
    <div class="container-hero w-container">
      <div class="w-layout-grid grid-hero">
        <h1 class="heading-hero yellow">{escape(s['name'])}</h1>
        <div class="flex-h1button">
          <div class="flex-layout-32px text-dark emphasis-high">
            <h2 class="heading-hero">Bounties</h2>
            <div class="text-bodylarge">Open contests for work tagged with {escape(s['name'])}.</div>
          </div>
        </div>
      </div>
    </div>
  </div>
  <div class="section-filters"><div class="container-default w-container"><div class="flex-layout-48px">
    <h1 class="heading-section purple">Opportunities</h1>
    {content}
  </div></div></div>
"""
            + FOOTER_MINIMAL.format(prefix="../")
            + SCRIPTS.format(prefix="../")
        )
        write_html(out_dir / f"{s['slug']}.html", page)

    write_html(out_dir / "index.html", simple_page("../", "body-palepurple", "Skills | Superteam", "Master Skills", "Browse opportunities by skill", f'<div role="list" class="grid-gallerycards w-dyn-items">{"".join(cards)}</div>'))


def render_missions(items: list[dict]) -> None:
    for item in items:
        f = item["fields"]
        bindings = [
            {"type": "text", "value": item["name"]},
            {"type": "text", "value": f.get("type", "")},
            {"type": "text", "value": f.get("availableTo", "")},
            {"type": "text", "value": f.get("missionBudget", "")},
            {"type": "text", "value": f.get("estimatedTime", "")},
            {"type": "text", "value": f.get("availableTo", "")},
            {"type": "text", "value": f.get("estimatedTime", "")},
            {"type": "html", "value": f.get("missionOverview", "")},
            {"type": "html", "value": f.get("scopeOfWork", "")},
            {"type": "html", "value": f.get("idealProfile", "")},
            {"type": "html", "value": f.get("notes", "")},
            {"type": "html", "value": f.get("screeningQuestions", "")},
            {"type": "html", "value": f.get("missionLogistics", "")},
            {"type": "text", "value": f.get("estimatedTime", "")},
        ]
        render_from_template(
            "detail_missions.html",
            ROOT / "missions" / f"{item['slug']}.html",
            bindings,
            f"{item['name']} | Superteam",
            status=f.get("status", ""),
        )


def render_instagrants(items: list[dict]) -> None:
    for item in items:
        f = item["fields"]
        bindings = [
            {"type": "text", "value": item["name"]},
            {"type": "text", "value": f"{f.get('grantSize', '')} {f.get('currency', '')}".strip()},
            {"type": "html", "value": f.get("grantOverview", "")},
            {"type": "html", "value": f.get("areasOfFocus", "")},
            {"type": "html", "value": f.get("howItWorks", "")},
            {"type": "html", "value": f.get("resources", "")},
            {"type": "html", "value": f.get("faqs", "")},
        ]
        render_from_template(
            "detail_instagrants.html",
            ROOT / "instagrants" / f"{item['slug']}.html",
            bindings,
            f"{item['name']} | Superteam",
            status=f.get("status", "Open"),
        )


def render_projects(items: list[dict]) -> None:
    for item in items:
        f = item["fields"]
        thumb = f.get("thumbnail", "")
        lead = f.get("projectLead", "")
        led_slug = item.get("refs", {}).get("ledBy")
        led_html = ""
        if led_slug:
            led_html = f'<p class="text-bodylarge"><strong>Led by </strong><a href="../dao-members/{led_slug}.html" class="text-emphasis">{escape(lead)}</a></p>'
        elif lead:
            led_html = f'<p class="text-bodylarge"><strong>Led by </strong><span class="text-emphasis">{escape(lead)}</span></p>'
        link = f.get("projectLink", "")
        link_html = f'<p class="text-bodylarge"><a href="{escape(link)}" class="button-big button-lightprimary w-button" target="_blank" rel="noopener">visit project</a></p>' if link else ""
        body = f.get("mainContent") or f.get("description") or ""
        content = f"""
      <div class="w-layout-grid grid-document">
        <div class="block-document">
          {f'<img src="../{thumb}" alt="" class="image-projectthumbnail" style="max-width:320px;margin-bottom:24px;">' if thumb and not thumb.startswith('http') else ''}
          <div class="text-bodysmall">{escape(f.get('tagline', ''))}</div>
          <h2 class="heading-subsection">{escape(item['name'])}</h2>
          {led_html}
          <div class="text-bodylarge w-richtext">{body}</div>
          {link_html}
        </div>
      </div>"""
        write_html(ROOT / "projects" / f"{item['slug']}.html", simple_page("../", "body-palepurple", f"{item['name']} | Superteam", item["name"], f.get("tagline", "Project"), content))


def render_bounties(items: list[dict]) -> None:
    for item in items:
        f = item["fields"]
        bindings = [
            {"type": "text", "value": item["name"]},
            {"type": "text", "value": f.get("type", "")},
            {"type": "text", "value": f.get("skillTag", "")},
            {"type": "html", "value": f.get("description", "")},
            {"type": "html", "value": f.get("mission", "")},
            {"type": "text", "value": format_deadline(f.get("deadline", ""))},
            {"type": "text", "value": format_deadline(f.get("deadline", ""))},
            {"type": "html", "value": f.get("notes", "")},
            {"type": "html", "value": f.get("rewards", "")},
            {"type": "html", "value": f.get("bugBounty", "")},
            {"type": "html", "value": f.get("evaluationCriteria", "")},
            {"type": "html", "value": f.get("resources", "")},
            {"type": "html", "value": f.get("terms", "")},
            {"type": "html", "value": f.get("notes", "")},
        ]
        render_from_template(
            "detail_bounties.html",
            ROOT / "bounties" / f"{item['slug']}.html",
            bindings,
            f"{item['name']} | Superteam",
            status=f.get("status", ""),
        )


def render_listings(data: dict[str, list[dict]]) -> None:
    bounties = data["bounties"]
    missions = data["missions"]
    instagrants = data["instagrants"]
    projects = data["projects"]

    open_bounties = [b for b in bounties if status_class(b["fields"].get("status")) == "open"]
    closed_bounties = [b for b in bounties if status_class(b["fields"].get("status")) != "open"]
    open_missions = [m for m in missions if status_class(m["fields"].get("status")) == "open"]
    closed_missions = [m for m in missions if status_class(m["fields"].get("status")) != "open"]

    patch_file_dyn_lists("earn/bounties.html", {
        0: "".join(bounty_card_html(b, "../") for b in open_bounties),
        1: "".join(bounty_card_html(b, "../", closed=True) for b in closed_bounties),
    })
    patch_file_dyn_lists("earn/missions.html", {
        0: "".join(mission_card_html(m, "../") for m in open_missions),
        1: "".join(mission_card_html(m, "../", closed=True) for m in closed_missions),
    })
    patch_file_dyn_lists("earn/instagrants.html", {
        0: "".join(instagrant_card_html(i, "../") for i in instagrants),
    })
    patch_file_dyn_lists("showcase.html", {
        0: "".join(project_card_html(p, "") for p in projects),
    })

    patch_file_dyn_lists("about.html", {
        0: "".join(project_card_html(p, "", include_led_by=False) for p in projects),
    })

    patch_file_dyn_lists("earn.html", {0: "".join(bounty_card_html(b, "") for b in open_bounties[:12])})
    patch_file_dyn_lists("index.html", {
        0: "".join(bounty_card_html(b, "") for b in open_bounties[:5]),
        1: "".join(mission_card_html(m, "") for m in open_missions[:5]),
    })


COLLECTION_DIRS = {
    "dao-members": "dao-members",
    "master-skills": "skills",
    "missions": "missions",
    "instagrants": "instagrants",
    "projects": "projects",
    "bounties": "bounties",
}


def cleanup_stale_pages(data: dict[str, list[dict]]) -> None:
    removed = 0
    for key, dir_name in COLLECTION_DIRS.items():
        out_dir = ROOT / dir_name
        if not out_dir.is_dir():
            continue
        valid = {item["slug"] for item in data.get(key, [])}
        valid.add("index")
        for html in out_dir.glob("*.html"):
            if html.stem not in valid:
                html.unlink()
                removed += 1
    if removed:
        print(f"  removed {removed} stale detail pages")


def render_all(data: dict[str, list[dict]]) -> None:
    print("Preparing templates...")
    ensure_listing_templates(ROOT)
    ensure_detail_templates(ROOT)
    print("Rendering detail pages...")
    cleanup_stale_pages(data)
    render_dao_members(data["dao-members"])
    render_master_skills(data["master-skills"], data["bounties"])
    render_missions(data["missions"])
    render_instagrants(data["instagrants"])
    render_projects(data["projects"])
    render_bounties(data["bounties"])
    print("Patching listing pages...")
    render_listings(data)
    cleanup_orphan_images(data)
    counts = {k: len(v) for k, v in data.items()}
    print(f"  generated pages: {sum(counts.values())} items across {len(counts)} collections")
