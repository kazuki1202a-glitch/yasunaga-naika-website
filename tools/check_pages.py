# -*- coding: utf-8 -*-
"""1ファイル・レスポンシブ版15ページの自動チェック。

2026-09-14、スマホ用(*.html)とPC用(*_pc.html)の2ファイル体制を1ファイルに統合した。
旧 tools/check_pc_pages.py（2ファイル体制用）の後継。

チェック内容:
 1. style.final.css / style.pc.css / script.js の ?v=N が全15ページで揃っているか
    → 上げ忘れてブラウザが古いCSSをキャッシュしたまま
      「直したはずなのに直らない」という事故が実際に起きたため必須
 2. 統合済みの目印（style.pc.css・pc-nav・pc-contact・pcStatus）が全ページに揃っているか
 3. *_pc.html への参照が残っていないか（統合の取りこぼし検出。リンク切れになる）
 4. サイト内リンクの飛び先ファイル・ページ内アンカーが実在するか
 5. （--render）スマホ幅／PC幅の描画: 横スクロール・はみ出し・JSエラー・
    PCヘッダーの診療ステータス更新・ハンバーガー／PCナビの出し分け

使い方:
    python tools\\check_pages.py            # 1〜4（ブラウザ不要）
    python tools\\check_pages.py --render   # 5 も実行（playwright が必要）

    ブラウザ描画チェックを使う場合: pip install playwright && python -m playwright install chromium
"""
import io, os, re, sys, glob, urllib.parse
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)

PAGES = ["index", "当院について", "院長紹介", "診療内容", "一般内科", "消化器内科",
         "生活習慣病", "感染症外来", "ワクチン", "超音波検査", "特定健診",
         "市の健診", "施設基準", "自費診療料金", "プライバシーポリシー"]
ASSETS = ["style.final.css", "style.pc.css", "script.js"]
MOBILE_WIDTHS = [375, 390, 430]
PC_WIDTHS = [1024, 1440, 1920]

failures = []


def note(ok, msg):
    print(("  OK   " if ok else "  NG   ") + msg)
    if not ok:
        failures.append(msg)


def read(p):
    with io.open(p, "r", encoding="utf-8") as f:
        return f.read()


def page_path(n):
    return os.path.join(BASE, n + ".html")


# ---- 1. バージョン番号 -----------------------------------------------------
def check_versions():
    print("\n[1] CSS/JS のバージョン番号が全ページで揃っているか")
    note(all(os.path.exists(page_path(n)) for n in PAGES),
         "15ページすべて存在する")
    for asset in ASSETS:
        seen = defaultdict(list)
        pat = re.compile(re.escape(asset) + r'\?v=(\d+)')
        for n in PAGES:
            m = pat.findall(read(page_path(n)))
            if len(m) != 1:
                note(False, "%s: %s の読み込みが %d 箇所（1箇所であるべき）" % (n, asset, len(m)))
                continue
            seen[m[0]].append(n)
        note(len(seen) == 1, "%-16s v=%s" % (asset, dict((v, len(p)) for v, p in seen.items())))
        if len(seen) > 1:
            for v, ps in seen.items():
                print("         v=%s: %s" % (v, ", ".join(ps)))


# ---- 2. 統合済みの目印 -----------------------------------------------------
def check_merged():
    print("\n[2] 各ページが1ファイルでPCレイアウトに対応しているか")
    marks = {"style.pc.css の読み込み": 'href="style.pc.css',
             "PCグローバルナビ": 'class="pc-nav pc-only"',
             "PC電話・診療ステータス": 'class="pc-contact pc-only"',
             "ヘッダーのステータス表示枠": 'id="pcStatus"'}
    for label, needle in marks.items():
        miss = [n for n in PAGES if needle not in read(page_path(n))]
        note(not miss, "%s がある" % label + (" / 欠けているページ: %s" % miss if miss else ""))
    # index 以外は <main class="pc-main"> で本文を囲む（index はトップ専用構成のため対象外）
    miss = [n for n in PAGES if n != "index" and 'class="pc-main"' not in read(page_path(n))]
    note(not miss, "本文が <main class=\"pc-main\"> で囲まれている（index を除く）"
         + (" / 欠け: %s" % miss if miss else ""))


# ---- 3. 旧2ファイル体制の残骸 ----------------------------------------------
def check_no_pc_files():
    print("\n[3] 旧 *_pc.html の残骸が無いか")
    left = [os.path.basename(f) for f in glob.glob(os.path.join(BASE, "*_pc.html"))]
    note(not left, "*_pc.html ファイルは残っていない" + (" / 残存: %s" % left if left else ""))
    refs = []
    for pat in ("*.html", "*.css", "*.js", "*.xml", "*.txt"):
        for f in glob.glob(os.path.join(BASE, pat)):
            body = read(f)
            if f.endswith(".css"):
                body = re.sub(r'/\*.*?\*/', '', body, flags=re.S)   # 経緯を書いたコメントは対象外
            if "_pc.html" in body:
                refs.append(os.path.basename(f))
    note(not refs, "_pc.html へのリンク・参照も残っていない" + (" / 残存: %s" % refs if refs else ""))


# ---- 4. リンク切れ ---------------------------------------------------------
HREF_RE = re.compile(r'href="([^"]+)"')
ID_RE = re.compile(r'\bid="([^"]+)"')
NAME_RE = re.compile(r'\bname="([^"]+)"')


def check_links():
    print("\n[4] サイト内リンクの飛び先が実在するか")
    ids = {n: set(ID_RE.findall(read(page_path(n)))) | set(NAME_RE.findall(read(page_path(n))))
           for n in PAGES}
    broken = []
    for n in PAGES:
        for raw in HREF_RE.findall(read(page_path(n))):
            if raw.startswith(("tel:", "mailto:", "http://", "https://", "javascript:")):
                continue
            raw = raw.split("?")[0]                      # CSS/JS の ?v=N を落とす
            if raw.endswith((".css", ".js")) or not raw:
                continue
            tgt, _, frag = raw.partition("#")
            if tgt and not os.path.exists(os.path.join(BASE, urllib.parse.unquote(tgt))):
                broken.append("%s → %s（ファイルが無い）" % (n, raw))
                continue
            if frag:
                dest = (tgt[:-5] if tgt.endswith(".html") else n) if tgt else n
                if dest in ids and frag not in ids[dest]:
                    broken.append("%s → %s（アンカーが無い）" % (n, raw))
    note(not broken, "リンク切れなし" if not broken else "リンク切れ %d 件" % len(broken))
    for b in broken[:20]:
        print("         " + b)


# ---- 5. 描画チェック -------------------------------------------------------
CHECK_JS = """() => {
  const w = document.documentElement.clientWidth;
  const r = {hscroll: document.documentElement.scrollWidth > w + 1, overflow: [],
             status: null, hamburger: false, pcnav: false};
  const st = document.getElementById('pcStatus');
  if (st) r.status = st.textContent.trim();
  const hb = document.getElementById('menuBtn'), nv = document.querySelector('.pc-nav');
  if (hb) r.hamburger = getComputedStyle(hb).display !== 'none';
  if (nv) r.pcnav = getComputedStyle(nv).display !== 'none';
  document.querySelectorAll('body *').forEach(el => {
    const b = el.getBoundingClientRect();
    if (b.width === 0 && b.height === 0) return;
    // 閉じているハンバーガーメニューは画面外に待機させる設計なので対象外
    if (el.closest('#navDrawer, #navOverlay') && !document.body.classList.contains('nav-open')) return;
    // 横スクロールさせる前提の区画（施設ギャラリー・料金表など）の中身も対象外。
    // ページ全体が横に伸びているかは r.hscroll で別に見ている。
    for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
      const ov = getComputedStyle(a).overflowX;
      if (ov === 'auto' || ov === 'scroll' || ov === 'hidden') return;
    }
    if (b.right > w + 1 || b.left < -1)
      r.overflow.push(el.tagName.toLowerCase() + '.' + String(el.className).slice(0, 40));
  });
  r.overflow = r.overflow.slice(0, 5);
  return r;
}"""


def check_render():
    print("\n[5] 描画チェック（スマホ幅／PC幅）")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        note(False, "playwright が入っていないため描画チェックを実行できません")
        return
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        for w in MOBILE_WIDTHS + PC_WIDTHS:
            is_pc = w >= 1024
            page = br.new_page(viewport={"width": w, "height": 1000})
            errs = []
            page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errs.append(str(e)))
            bad = []
            for n in PAGES:
                errs[:] = []
                page.goto("file:///" + page_path(n).replace("\\", "/"))
                page.wait_for_timeout(400)
                r = page.evaluate(CHECK_JS)
                if r["hscroll"] or r["overflow"]:
                    bad.append("%s: %s" % (n, r["overflow"] or "横スクロール"))
                if errs:
                    bad.append("%s: JSエラー %s" % (n, errs[0][:60]))
                if is_pc:
                    if not r["status"] or r["status"] == "診療時間をご確認ください":
                        bad.append("%s: ヘッダーの診療ステータスが更新されない" % n)
                    if not r["pcnav"]:
                        bad.append("%s: PCナビが出ていない" % n)
                    if r["hamburger"]:
                        bad.append("%s: PC幅なのにハンバーガーが出ている" % n)
                else:
                    if not r["hamburger"]:
                        bad.append("%s: スマホ幅なのにハンバーガーが出ていない" % n)
                    if r["pcnav"]:
                        bad.append("%s: スマホ幅なのにPCナビが出ている" % n)
            note(not bad, "%dpx 幅: 崩れ・エラーなし" % w + ("" if not bad else " / " + "; ".join(bad[:4])))
            page.close()
        br.close()


if __name__ == "__main__":
    check_versions()
    check_merged()
    check_no_pc_files()
    check_links()
    if "--render" in sys.argv:
        check_render()
    else:
        print("\n[5] 描画チェックは省略（--render を付けると実行）")
    print("\n==== 結果: %s ====" % ("すべてOK" if not failures else "NG %d件" % len(failures)))
    sys.exit(1 if failures else 0)
