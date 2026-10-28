"""Optional local Edge/Playwright audit. Screenshots may contain licensed data; keep private.

Run the dashboard first, then `uv run --with playwright python -m scripts.audit_ui`.
Requires installed Microsoft Edge. No observations, formulas or source integrations are changed.
"""

import argparse
import json
from pathlib import Path

from src.settings import settings

ROOT = Path(__file__).resolve().parents[1]

# Check actual painted foregrounds, alpha compositing and inherited backgrounds.
# Disabled controls and non-text icon glyphs are exempt; canvas cells are tested by
# the theme-pair/Styler unit tests because their text is not represented in the DOM.
CONTRAST_AUDIT = r"""() => {
 const rgb = s => {const v=s.match(/[\d.]+/g);return v ? [Number(v[0]),Number(v[1]),Number(v[2]),v.length>3?Number(v[3]):1] : [0,0,0,0]};
 const over=(fg,bg)=>[0,1,2].map(i=>fg[i]*fg[3]+bg[i]*(1-fg[3]));
 const lum=c=>{const v=c.slice(0,3).map(x=>x/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4);return v[0]*.2126+v[1]*.7152+v[2]*.0722};
 const ratio=(a,b)=>(Math.max(lum(a),lum(b))+.05)/(Math.min(lum(a),lum(b))+.05);
 const bad=[],checked=[];
 const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
 while(walker.nextNode()){
  const node=walker.currentNode,e=node.parentElement,text=node.textContent.trim();
  if(!e||!text||e.closest('script,style,[aria-hidden="true"],[disabled],[aria-disabled="true"],[role="tooltip"]'))continue;
  const r=e.getBoundingClientRect(),s=getComputedStyle(e);
  if(r.width<1||r.height<1||r.bottom<0||r.top>innerHeight||r.right<0||r.left>innerWidth||s.visibility==='hidden'||s.display==='none')continue;
  if(/Material|icon/i.test(s.fontFamily)||['CANVAS','OPTION'].includes(e.tagName))continue;
  const parents=[];for(let p=e;p;p=p.parentElement)parents.unshift(p);
  let bg=[255,255,255],opacity=1;
  for(const p of parents){const ps=getComputedStyle(p);bg=over(rgb(ps.backgroundColor),bg);opacity*=Number(ps.opacity||1)}
  if(opacity===0)continue;
  const color=rgb(e.namespaceURI==='http://www.w3.org/2000/svg'?s.fill:s.color);color[3]*=opacity;
  const fg=over(color,bg),value=ratio(fg,bg);
  const large=parseFloat(s.fontSize)>=24||(parseFloat(s.fontSize)>=18.66&&parseInt(s.fontWeight)>=700);
  const item={text:text.slice(0,85),ratio:Number(value.toFixed(2)),foreground:fg.map(Math.round),background:bg.map(Math.round),tag:e.tagName};
  checked.push(item);
  if(value<(large?3:4.5)-.02)bad.push(item);
 }
 return {checked:checked.length,failures:bad};
}"""


def wait_for_app(page, title):
    page.get_by_role("heading", name=title, exact=True).wait_for(timeout=60000)
    page.wait_for_function(
        "document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state') === 'notRunning'",
        timeout=60000,
    )
    # Streamlit animates loading/stale captions. Audit the settled interface,
    # after our scoped opacity rule is applied, rather than a transition frame.
    page.wait_for_function(
        """()=>Array.from(document.querySelectorAll('[data-testid="stMain"] [data-testid="stCaptionContainer"]')).every(e=>getComputedStyle(e).opacity==='1')""",
        timeout=10000,
    )


def audit_page(page, title, output, viewport):
    wait_for_app(page, title)
    errors = page.locator('[data-testid="stException"]').all_text_contents()
    assert not errors, (title, errors)
    # Plotly renders lazily below the viewport. Expose every chart before auditing
    # its actual canvas/SVG styles instead of treating an offscreen placeholder as verified.
    chart_elements = page.locator('[data-testid="stPlotlyChart"]')
    for index in range(chart_elements.count()):
        details = chart_elements.nth(index).locator("xpath=ancestor::details[1]")
        if details.count() and details.get_attribute("open") is None:
            details.locator("summary").click()
        chart_elements.nth(index).scroll_into_view_if_needed()
        page.wait_for_function(
            """i=>Boolean(document.querySelectorAll('[data-testid="stPlotlyChart"]')[i]?.querySelector('.js-plotly-plot')?._fullLayout)""",
            arg=index,
            timeout=30000,
        )
    page.locator('[data-testid="stMain"]').evaluate("e=>e.scrollTo(0,0)")
    page.wait_for_timeout(100)
    overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth + 2")
    top = page.evaluate(CONTRAST_AUDIT)
    charts = page.locator(".js-plotly-plot").evaluate_all("""es=>es.map(e=>({
      font:e._fullLayout?.font?.color, legend:e._fullLayout?.legend?.font?.color,
      hover:e._fullLayout?.hoverlabel?.font?.color, background:e._fullLayout?.hoverlabel?.bgcolor,
      axes:Object.entries(e._fullLayout||{}).filter(([k])=>/^[xy]axis[0-9]*$/.test(k)).map(([,v])=>v.tickfont?.color)
    }))""")
    page.locator('[data-testid="stMain"]').evaluate("e=>e.scrollTo(0,e.scrollHeight)")
    page.wait_for_timeout(120)
    bottom = page.evaluate(CONTRAST_AUDIT)
    page.screenshot(
        path=str(
            output
            / (title.lower().replace(" ", "_").replace("&", "and") + f"-{viewport}-bottom.png")
        ),
        full_page=True,
    )
    page.locator('[data-testid="stMain"]').evaluate("e=>e.scrollTo(0,0)")
    filename = title.lower().replace(" ", "_").replace("&", "and") + f"-{viewport}.png"
    page.screenshot(path=str(output / filename), full_page=True)
    return {
        "page": title,
        "viewport": viewport,
        "horizontal_overflow": overflow,
        "text_nodes_checked": top["checked"] + bottom["checked"],
        "contrast_failures": top["failures"] + bottom["failures"],
        "screenshot": filename,
        "rendered_chart_styles": charts,
    }


def run(base_url, output):
    from playwright.sync_api import sync_playwright

    groups = json.loads((ROOT / "config/pages.json").read_text())
    titles = (
        ["Executive Overview"]
        + [title for pages in groups.values() for title in pages]
        + ["Data Sources & System Status", "Workbook Administration"]
    )
    results = []
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        for label, width in [("desktop", 1440), ("narrow", 390)]:
            context = browser.new_context(
                viewport={"width": width, "height": 1000}, device_scale_factor=1
            )
            page = context.new_page()
            page.goto(base_url.rstrip("/") + "/", wait_until="domcontentloaded")
            wait_for_app(page, "Executive Overview")
            for title in titles:
                if title != "Executive Overview":
                    expand = page.locator('[data-testid="stExpandSidebarButton"]')
                    if label == "narrow" and expand.is_visible():
                        expand.click()
                        page.wait_for_timeout(250)
                    page.get_by_role("link", name=title, exact=True).click()
                    wait_for_app(page, title)
                    collapse = page.locator('[data-testid="stSidebarCollapseButton"]')
                    if label == "narrow" and collapse.is_visible():
                        collapse.click()
                        page.wait_for_timeout(250)
                result = audit_page(page, title, output, label)
                results.append(result)
                print(
                    f"{label}: {title}: {len(result['contrast_failures'])} contrast findings; overflow={result['horizontal_overflow']}",
                    flush=True,
                )
                # Persist after every page so interrupted audits retain their evidence.
                (output / "report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
            context.close()
        browser.close()
    failures = sum(len(r["contrast_failures"]) for r in results)
    overflows = sum(r["horizontal_overflow"] for r in results)
    print(
        f"Audited {len(results)} page/viewport combinations; {failures} contrast findings; {overflows} overflows"
    )
    return 1 if failures or overflows else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8501")
    parser.add_argument(
        "--output", type=Path, default=Path(settings.excel_artifact_dir) / "ui_audit"
    )
    args = parser.parse_args()
    raise SystemExit(run(args.base_url, args.output))
