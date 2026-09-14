# -*- coding: utf-8 -*-
"""現在地のナビ強調・パンくず・CSSバージョン番号を機械的に検証する。

    python tools\\check_nav_breadcrumb.py

チェック内容:
  1. CSSのバージョン番号（?v=N）が全ファイルで揃っているか
     ※過去に上げ忘れ・不揃いでキャッシュ事故が起きているため必ず機械で見る
  2. メインナビの強調が「各ページちょうど1本」付いているか、対象が正しいか
  3. パンくずが該当16ファイルにだけ有るか、リンク先が実在するファイルか
"""
import io, os, re, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)

CHILDREN = ["一般内科", "消化器内科", "生活習慣病", "感染症外来",
            "ワクチン", "超音波検査", "特定健診", "市の健診"]
STANDALONE = ["施設基準", "自費診療料金", "プライバシーポリシー"]
PARENTS = ["index", "当院について", "院長紹介", "診療内容"]
ALL = PARENTS + CHILDREN + STANDALONE

NAV_TARGET = {"index": "index", "当院について": "当院について",
              "院長紹介": "院長紹介", "診療内容": "診療内容"}
for c in CHILDREN:
    NAV_TARGET[c] = "診療内容"
for s in STANDALONE:
    NAV_TARGET[s] = None

errors, checks = [], [0]


def ok(cond, msg):
    checks[0] += 1
    if not cond:
        errors.append(msg)


def read(p):
    with io.open(p, "r", encoding="utf-8") as f:
        return f.read()


def main():
    files = sorted(glob.glob(os.path.join(BASE, "*.html")))
    ok(len(files) == 30, "HTMLが30枚でない: %d枚" % len(files))

    # ---- 1. CSSバージョン番号 -------------------------------------------------
    finals, pcs = {}, {}
    for p in files:
        t, n = read(p), os.path.basename(p)
        m = re.search(r'href="style\.final\.css\?v=(\d+)"', t)
        ok(m is not None, "%s: style.final.css のリンクが無い" % n)
        if m:
            finals.setdefault(m.group(1), []).append(n)
        m2 = re.search(r'href="style\.pc\.css\?v=(\d+)"', t)
        if n.endswith("_pc.html"):
            ok(m2 is not None, "%s: style.pc.css のリンクが無い" % n)
            if m2:
                pcs.setdefault(m2.group(1), []).append(n)
        else:
            ok(m2 is None, "%s: 本番ページに style.pc.css が入っている" % n)

    ok(len(finals) == 1,
       "style.final.css のバージョンが不揃い: %s"
       % {k: len(v) for k, v in finals.items()})
    ok(len(pcs) == 1,
       "style.pc.css のバージョンが不揃い: %s" % {k: len(v) for k, v in pcs.items()})
    ok(sum(len(v) for v in finals.values()) == 30, "style.final.css が30枚に無い")
    ok(sum(len(v) for v in pcs.values()) == 15, "style.pc.css が15枚に無い")
    print("style.final.css: v=%s (%d枚)" % (list(finals)[0], sum(len(v) for v in finals.values())))
    print("style.pc.css   : v=%s (%d枚)" % (list(pcs)[0], sum(len(v) for v in pcs.values())))

    # ---- 2. ナビの現在地強調 ---------------------------------------------------
    for name in ALL:
        for suffix in ("", "_pc"):
            n = name + suffix + ".html"
            t = read(os.path.join(BASE, n))
            target = NAV_TARGET[name]
            want = None if target is None else target + suffix + ".html"

            drawer = re.findall(r'<a href="([^"]+)" class="nav-drawer-link active">', t)
            ok(drawer == ([] if want is None else [want]),
               "%s: ドロワーの強調が想定と違う 期待=%s 実際=%s" % (n, want, drawer))

            if suffix == "_pc":
                m = re.search(r'<nav class="pc-nav.*?</nav>', t, re.S)
                ok(m is not None, "%s: pc-nav が無い" % n)
                pcnav = re.findall(r'<a href="([^"]+)" class="active">', m.group(0)) if m else []
                ok(pcnav == ([] if want is None else [want]),
                   "%s: pc-nav の強調が想定と違う 期待=%s 実際=%s" % (n, want, pcnav))
            else:
                ok("pc-nav" not in t, "%s: 本番ページに pc-nav が入っている" % n)

    # ---- 3. パンくず -----------------------------------------------------------
    for name in ALL:
        for suffix in ("", "_pc"):
            n = name + suffix + ".html"
            t = read(os.path.join(BASE, n))
            crumbs = re.findall(r'<nav class="breadcrumb"[^>]*>(.*?)</nav>', t, re.S)
            if name not in CHILDREN:
                ok(not crumbs, "%s: パンくずが付いてはいけないページに付いている" % n)
                continue
            ok(len(crumbs) == 1, "%s: パンくずが %d 個（1個であるべき）" % (n, len(crumbs)))
            if len(crumbs) != 1:
                continue
            body = crumbs[0]
            ok('aria-label="パンくずリスト"' in t, "%s: nav に aria-label が無い" % n)
            links = re.findall(r'<a href="([^"]+)">([^<]+)</a>', body)
            ok([l[1] for l in links] == ["ホーム", "診療案内"],
               "%s: パンくずの項目名が想定と違う: %s" % (n, [l[1] for l in links]))
            ok([l[0] for l in links] == ["index%s.html" % suffix, "診療内容%s.html" % suffix],
               "%s: パンくずのリンク先が想定と違う: %s" % (n, [l[0] for l in links]))
            for href, _ in links:
                ok(os.path.exists(os.path.join(BASE, href.split("#")[0])),
                   "%s: パンくずのリンク先が存在しない: %s" % (n, href))
            cur = re.findall(r'<span aria-current="page">([^<]+)</span>', body)
            ok(cur == [name], "%s: 現在ページ名が想定と違う: %s" % (n, cur))
            ok("<a" not in body.split("aria-current")[-1],
               "%s: 現在ページがリンクになっている" % n)

    print("\n検査項目 %d 件" % checks[0])
    if errors:
        print("NG %d 件:" % len(errors))
        for e in errors:
            print("  - " + e)
        return 1
    print("すべて OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
