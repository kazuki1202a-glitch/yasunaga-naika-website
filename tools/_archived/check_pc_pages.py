# -*- coding: utf-8 -*-
# ============================================================================
# 【役目を終えました｜2026-09-14 アーカイブ】実行しないでください。
#
# 2ファイル体制(*.html / *_pc.html)の前提で作られたチェックツールです。
# 2026-09-14 の1ファイル統合により *_pc.html が無くなったため動きません。
# 統合直前にこのツールの [2]（本番と _pc.html の内容ずれ）を通し、14ページすべてが
# 本番から1バイト違わず再生成できる＝内容のずれが無いことを確認したうえで統合しました。
# 当時どういう観点で守っていたかの記録として残しています。
# ============================================================================
"""PC版15ページの自動チェック。style.pc.css / *_pc.html を触ったら必ず通すこと。

チェック内容:
 1. style.pc.css?v=N のバージョン番号が全 _pc.html で一致しているか
    → 実際に「上げ忘れてブラウザが古いCSSをキャッシュしたまま、
       直したはずなのに直らない」という事故が起きたため必須
 2. 本番ページと _pc.html の本文が食い違っていないか（内容の二重管理事故の防止）
    → build_pc_pages.py で作り直した結果と現物が一致するかで判定する
 3. PC幅(1024/1440/1920)で横スクロール・要素のはみ出し・JSエラーが無いか
 4. .pc-main 直下に「枠付きの箱」が新しく増えていないか
    → style.pc.css の .pc-main > *:not(...) で左右paddingを0にしているため、
      箱が増えたら除外リストに足さないと文字が枠にぶつかる

使い方:
    python tools\\check_pc_pages.py          # 1・2・4 のみ（ブラウザ不要）
    python tools\\check_pc_pages.py --render # 3 も実行（playwright が必要）

    ブラウザ描画チェックを使う場合:  pip install playwright && python -m playwright install chromium
"""
import io, os, re, sys, glob
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)

PAGES = ["index", "当院について", "院長紹介", "診療内容", "一般内科", "消化器内科",
         "生活習慣病", "感染症外来", "ワクチン", "超音波検査", "特定健診",
         "市の健診", "施設基準", "自費診療料金", "プライバシーポリシー"]
WIDTHS = [1024, 1440, 1920]

failures = []


def note(ok, msg):
    print(("  OK   " if ok else "  NG   ") + msg)
    if not ok:
        failures.append(msg)


def read(p):
    with io.open(p, "r", encoding="utf-8") as f:
        return f.read()


# ---- 1. CSSバージョンの一致 ----------------------------------------------
def check_version():
    print("\n[1] style.pc.css のバージョン番号が全ページで揃っているか")
    files = sorted(glob.glob(os.path.join(BASE, "*_pc.html")))
    vers, bad = Counter(), []
    for f in files:
        m = re.findall(r'href="style\.pc\.css\?v=(\d+)"', read(f))
        if len(m) != 1:
            bad.append(os.path.basename(f))
        else:
            vers[m[0]] += 1
    note(len(files) == len(PAGES), "_pc.html は %d 個（期待 %d 個）" % (len(files), len(PAGES)))
    note(not bad, "全ファイルに style.pc.css のリンクが1つずつある" + (" / 例外: %s" % bad if bad else ""))
    note(len(vers) == 1, "バージョン番号の分布: %s" % dict(vers))


# ---- 2. 本番との内容ずれ --------------------------------------------------
def check_drift():
    print("\n[2] 本番ページと _pc.html の内容がずれていないか")
    sys.path.insert(0, HERE)
    import build_pc_pages as b
    drift = []
    for name in b.PAGES:
        dst = os.path.join(BASE, name + "_pc.html")
        if not os.path.exists(dst):
            drift.append(name + "（未生成）")
            continue
        # 現物と、いま本番から作り直した場合の中身を比較する
        expected = b.transform(read(os.path.join(BASE, name + ".html")), name)
        if read(dst).replace("\r\n", "\n") != expected.replace("\r\n", "\n"):
            drift.append(name)
    note(not drift, "本番から再生成した結果と一致" + ("しないページ: %s" % drift if drift else ""))
    if drift:
        print("       → python tools\\build_pc_pages.py で作り直してください")
    print("  --   index_pc.html だけは手作りのため、index.html を直したら手で反映すること")


# ---- 3・4. ブラウザ描画チェック -------------------------------------------
CHECK_JS = """
() => {
  const w = document.documentElement.clientWidth;
  const r = {hscroll: document.documentElement.scrollWidth > w + 1, overflow: [], boxed: [], status: null};
  const st = document.getElementById('pcStatus');
  if (st) r.status = st.textContent.trim();
  document.querySelectorAll('body *').forEach(el => {
    const b = el.getBoundingClientRect();
    if (b.width === 0 && b.height === 0) return;
    if (b.right > w + 1 || b.left < -1)
      r.overflow.push(el.tagName.toLowerCase() + '.' + String(el.className).slice(0, 40));
  });
  document.querySelectorAll('.pc-main > *').forEach(el => {
    const c = getComputedStyle(el);
    const isBox = (c.backgroundColor !== 'rgba(0, 0, 0, 0)' && c.backgroundColor !== 'transparent')
                  || c.borderLeftWidth !== '0px' || c.borderTopWidth !== '0px';
    if (isBox) r.boxed.push(String(el.className).slice(0, 40));
  });
  r.overflow = r.overflow.slice(0, 5);
  return r;
}
"""

# style.pc.css の .pc-main > *:not(...) で既に除外済みのクラス
KNOWN_BOXED = {"about-intro-card"}


def check_render():
    print("\n[3] PC幅での描画チェック（横はみ出し・JSエラー・ステータス表示）")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        note(False, "playwright が入っていないため描画チェックを実行できません")
        return
    new_boxes = set()
    with sync_playwright() as p:
        br = p.chromium.launch()
        for w in WIDTHS:
            page = br.new_page(viewport={"width": w, "height": 1000})
            errs = []
            page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errs.append(str(e)))
            bad = []
            for n in PAGES:
                errs[:] = []
                page.goto("file:///" + os.path.join(BASE, n + "_pc.html").replace("\\", "/"))
                page.wait_for_timeout(300)
                r = page.evaluate(CHECK_JS)
                if r["hscroll"] or r["overflow"]:
                    bad.append("%s: %s" % (n, r["overflow"] or "横スクロール"))
                if errs:
                    bad.append("%s: JSエラー %s" % (n, errs[0][:60]))
                if not r["status"] or r["status"] == "診療時間をご確認ください":
                    bad.append("%s: ヘッダーの診療ステータスが更新されていない" % n)
                for c in r["boxed"]:
                    for cls in c.split():
                        if cls not in KNOWN_BOXED and not cls.startswith("pc-"):
                            new_boxes.add(cls)
                page.close() if False else None
            note(not bad, "%dpx 幅: 崩れ・エラーなし" % w + ("" if not bad else " / " + "; ".join(bad[:4])))
            page.close()
        br.close()

    print("\n[4] .pc-main 直下に未知の「枠付きの箱」が増えていないか")
    note(not new_boxes,
         "既知の箱のみ" if not new_boxes else
         "未知の箱: %s → style.pc.css の .pc-main > *:not(...) に追加が必要" % sorted(new_boxes))


if __name__ == "__main__":
    check_version()
    check_drift()
    if "--render" in sys.argv:
        check_render()
    else:
        print("\n[3][4] 描画チェックは省略（--render を付けると実行）")
    print("\n==== 結果: %s ====" % ("すべてOK" if not failures else "NG %d件" % len(failures)))
    sys.exit(1 if failures else 0)
