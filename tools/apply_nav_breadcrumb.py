# -*- coding: utf-8 -*-
"""本番ページ（*.html）に「現在地のナビ強調」と「パンくずリスト」を入れる。

これは1回きりの変換ではなく、何度実行しても同じ結果になる（冪等）ように書いてある。
本番ページの文章を直したあとでも、もう一度流せば印が付け直される。

  python tools\\apply_nav_breadcrumb.py           # 本番15ページ + index_pc.html を更新
  python tools\\apply_nav_breadcrumb.py --check   # 書き換えずに、付いているかどうかだけ確認

※ 《ページ名》_pc.html（index_pc.html を除く14枚）は本番から
   tools\\build_pc_pages.py で作り直すので、ここでは触らない。
   index_pc.html だけは手作りのため、ここでナビの印を付ける。
"""
import io, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)

# メインナビ5項目のうち、そのページで強調する項目の href。
# 診療案内の子ページ8枚は、自分自身へのナビ項目が無いので親の「診療内容.html」を強調する。
PARENT = "診療内容.html"
CHILDREN = ["一般内科", "消化器内科", "生活習慣病", "感染症外来",
            "ワクチン", "超音波検査", "特定健診", "市の健診"]

ACTIVE_HREF = {
    "index": "index.html",
    "当院について": "当院について.html",
    "院長紹介": "院長紹介.html",
    "診療内容": PARENT,
}
for _c in CHILDREN:
    ACTIVE_HREF[_c] = PARENT

# 独立ページ3枚はナビ強調・パンくずとも対象外（値 None ＝ 印を付けない）
for _n in ["施設基準", "自費診療料金", "プライバシーポリシー"]:
    ACTIVE_HREF[_n] = None

PAGES = sorted(ACTIVE_HREF)

BREADCRUMB = u'''
        <!-- パンくずリスト -->
        <nav class="breadcrumb" aria-label="パンくずリスト">
            <ol>
                <li><a href="index.html">ホーム</a></li>
                <li><a href="診療内容.html">診療案内</a></li>
                <li><span aria-current="page">%s</span></li>
            </ol>
        </nav>
'''

# ページバナー画像のブロック。全8ページで同じ形をしている。
BANNER_RE = re.compile(
    r'(<div style="padding: 15px 15px 0;">\s*<img [^>]*>\s*</div>\n)')

DRAWER_RE = re.compile(
    r'(<a href="([^"]+)" class="nav-drawer-link)( active)?(">)')
PCNAV_RE = re.compile(
    r'(<a href="([^"]+)")( class="active")?(>(?:トップ|当院について|院長紹介|診療案内|アクセス)</a>)')


def read(p):
    with io.open(p, "r", encoding="utf-8") as f:
        return f.read()


def write(p, t):
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(t)


def set_drawer_active(html, target, suffix=""):
    """ハンバーガーメニュー内の該当リンクにだけ class="nav-drawer-link active" を付ける。
       既に付いている印はいったん全部外してから付け直す（冪等にするため）。"""
    want = None if target is None else (
        target.replace(".html", suffix + ".html") if suffix else target)
    n = [0]

    def sub(m):
        href = m.group(2)
        if want is not None and href == want:
            n[0] += 1
            return m.group(1) + " active" + m.group(4)
        return m.group(1) + m.group(4)

    out = DRAWER_RE.sub(sub, html)
    if want is not None and n[0] != 1:
        raise SystemExit(u"ドロワーの強調対象が %d 件（1件であるべき）: %s" % (n[0], want))
    return out


def set_pcnav_active(html, target, suffix=""):
    """PC版ヘッダーの pc-nav 内の該当リンクにだけ class="active" を付ける。"""
    if "pc-nav" not in html:
        return html
    want = None if target is None else (
        target.replace(".html", suffix + ".html") if suffix else target)
    start = html.index('<nav class="pc-nav')
    end = html.index("</nav>", start) + len("</nav>")
    block, n = html[start:end], [0]

    def sub(m):
        if want is not None and m.group(2) == want:
            n[0] += 1
            return m.group(1) + ' class="active"' + m.group(4)
        return m.group(1) + m.group(4)

    block = PCNAV_RE.sub(sub, block)
    if want is not None and n[0] != 1:
        raise SystemExit(u"pc-nav の強調対象が %d 件（1件であるべき）: %s" % (n[0], want))
    return html[:start] + block + html[end:]


def set_breadcrumb(html, name):
    """診療案内の子ページ8枚にだけ、バナー画像の直下へパンくずを置く。
       既にあれば内容を入れ替える（重複して増えないようにする）。"""
    html = re.sub(r'\n?        <!-- パンくずリスト -->\n'
                  r'        <nav class="breadcrumb".*?</nav>\n',
                  "", html, flags=re.S)
    if name not in CHILDREN:
        return html
    m = BANNER_RE.search(html)
    if not m:
        raise SystemExit(u"%s: ページバナーのブロックが見つからない" % name)
    ins = BREADCRUMB % name
    return html[:m.end()] + ins + html[m.end():]


def main():
    check = "--check" in sys.argv
    bad = 0
    for name in PAGES:
        p = os.path.join(BASE, name + ".html")
        src = read(p)
        out = set_breadcrumb(set_drawer_active(src, ACTIVE_HREF[name]), name)
        changed = out != src
        if check:
            print(u"%-6s %s.html" % ("差分あり" if changed else "OK", name))
            bad += 1 if changed else 0
        else:
            if changed:
                write(p, out)
            print(u"%-4s %s.html" % ("更新" if changed else "変更なし", name))

    # index_pc.html は手作りなので、ここでナビの印を付ける（_pc リンクなので suffix 指定）
    p = os.path.join(BASE, "index_pc.html")
    src = read(p)
    out = set_pcnav_active(set_drawer_active(src, "index.html", "_pc"),
                           "index.html", "_pc")
    changed = out != src
    if check:
        print(u"%-6s index_pc.html" % ("差分あり" if changed else "OK"))
        bad += 1 if changed else 0
    else:
        if changed:
            write(p, out)
        print(u"%-4s index_pc.html" % ("更新" if changed else "変更なし"))

    if check and bad:
        print(u"\n未適用のページが %d 件あります" % bad)
        return 1
    print(u"\n完了")
    return 0


if __name__ == "__main__":
    sys.exit(main())
