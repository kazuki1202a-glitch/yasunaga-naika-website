# -*- coding: utf-8 -*-
"""本番ページ（*.html）から PC専用ページ（*_pc.html）を生成する。

【重要】本番ファイルは読み込むだけで、絶対に書き換えない。
       書き込むのは《ページ名》_pc.html だけ。

なぜスクリプトにしているか:
  本番ページの文章を直したあと _pc.html に反映し忘れると、
  スマホとPCで違う医療情報が表示されることになる。
  本番から機械的に作り直せるようにして、その事故を防いでいる。
  （※ index_pc.html だけは構成が大きく違うため手作り。ここでは扱わない）

使い方:
    python tools\\build_pc_pages.py            # 現在のバージョン番号のまま作り直す
    python tools\\build_pc_pages.py --bump     # style.pc.css のバージョンを1つ上げて作り直す

style.pc.css を変更したときは必ず --bump を付けること。
（上げ忘れてブラウザが古いCSSをキャッシュしたまま
  「直したはずなのに直らない」という事故が実際に起きている）
"""
import io, os, re, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)

PAGES = [
    "当院について", "院長紹介", "診療内容", "一般内科", "消化器内科",
    "生活習慣病", "感染症外来", "ワクチン", "超音波検査", "特定健診",
    "市の健診", "施設基準", "自費診療料金", "プライバシーポリシー",
]

BRAND_ANCHOR_OLD = ('<a href="index.html" style="display: flex; align-items: center; gap: 12px; '
                    'text-decoration: none; color: inherit; flex-grow: 1;">')
BRAND_ANCHOR_NEW = ('<a class="pc-brand-link" href="index.html" style="display: flex; align-items: center; '
                    'gap: 12px; text-decoration: none; color: inherit; flex-grow: 1;">')

PC_HEADER = '''                <nav class="pc-nav pc-only" aria-label="メインメニュー">
                    <a href="index.html">トップ</a>
                    <a href="当院について.html">当院について</a>
                    <a href="院長紹介.html">院長紹介</a>
                    <a href="診療内容.html">診療案内</a>
                    <a href="index.html#contact-area">アクセス</a>
                </nav>
                <div class="pc-contact pc-only">
                    <span class="pc-status" id="pcStatus">診療時間をご確認ください</span>
                    <a class="pc-tel" href="tel:092-874-3433">092-874-3433</a>
                    <span class="pc-tel-note">受付 午前 9:00〜11:30 ／ 午後 14:00〜16:30</span>
                </div>
                <!-- 診療ステータスの判定ロジックは script.js のものをそのまま使いたいので、
                     script.js が書き込む先の #clinic-status-summary を非表示で置いておく。
                     （下層ページには診療時間カードが無いため） -->
                <span id="clinic-status-summary" class="pc-status-source"></span>
'''

SYNC_SCRIPT = '''    <script>
    // PC版ヘッダーの診療ステータス表示。判定ロジックは script.js のものをそのまま流用し、
    // #clinic-status-summary の結果をヘッダーへ写すだけにして二重管理を避ける。
    (function () {
        var src = document.getElementById('clinic-status-summary');
        var dst = document.getElementById('pcStatus');
        if (!src || !dst) return;
        var sync = function () {
            var t = (src.textContent || '').trim();
            if (!t || t === '読み込み中...') return;
            dst.textContent = t;
            dst.classList.toggle('is-open', !src.classList.contains('closed'));
        };
        document.addEventListener('DOMContentLoaded', function () { setTimeout(sync, 0); });
        setInterval(sync, 10000);
    })();
    </script>
'''

# --- サイト内リンクを _pc.html 版に差し替える ---------------------------------
# PC試作版は _pc.html だけで回遊できないと、途中からスマホ版に落ちてしまう。
# 以前はこの差し替えを手作業でやっていたため、このスクリプトで作り直すと
# 元に戻ってしまう（＝スクリプトが本番と _pc.html のずれを再現できない）状態だった。
# 2026-09-14、下の一律ルールで既存14ページが1バイト違わず再現できることを確認して取り込んだ。
LINKABLE = PAGES + ["index"]
LINK_RE = re.compile(
    r'href="(' + "|".join(re.escape(n) for n in sorted(LINKABLE, key=len, reverse=True))
    + r')\.html(#[^"]*)?"')


def to_pc_links(html):
    return LINK_RE.sub(
        lambda m: 'href="%s_pc.html%s"' % (m.group(1), m.group(2) or ""), html)


# --- メインナビの現在地強調 ---------------------------------------------------
# 診療案内の子ページ8枚には自分自身へのナビ項目が無いので、親の「診療案内」を強調する。
PARENT = "診療内容.html"
NAV_ACTIVE = {
    "当院について": "当院について.html",
    "院長紹介": "院長紹介.html",
    "診療内容": PARENT,
    "一般内科": PARENT, "消化器内科": PARENT, "生活習慣病": PARENT,
    "感染症外来": PARENT, "ワクチン": PARENT, "超音波検査": PARENT, "市の健診": PARENT,
    "特定健診": PARENT,
    # 独立ページ3枚は強調しない
    "施設基準": None, "自費診療料金": None, "プライバシーポリシー": None,
}


def mark_pc_nav(header, name):
    """PC_HEADER の pc-nav 内で、そのページに対応する1本にだけ class="active" を付ける。
       （ハンバーガーメニュー側の印は本番HTMLに入っているのでそのまま流れてくる）"""
    target = NAV_ACTIVE[name]
    if target is None:
        return header
    old = '<a href="%s">' % target
    if header.count(old) != 1:
        raise BuildError("%s: pc-nav に %s が %d 本（1本であるべき）"
                         % (name, target, header.count(old)))
    return header.replace(old, '<a href="%s" class="active">' % target, 1)


# ページ固有：読み物カラム(860px)から外して横に広げる区画に .pc-wide を付ける
WIDE = {
    "当院について": [
        ('<section id="equipment" class="about-photo-section"',
         '<section id="equipment" class="about-photo-section pc-wide"'),
        ('<section id="interior" class="about-photo-section"',
         '<section id="interior" class="about-photo-section pc-wide"'),
    ],
    "診療内容": [
        ('<section style="padding: 10px 20px 40px;">',
         '<section class="pc-wide pc-services" style="padding: 10px 20px 40px;">'),
    ],
}


class BuildError(Exception):
    pass


def current_version():
    """既存の _pc.html から style.pc.css のバージョン番号を読む（無ければ1）"""
    for f in sorted(glob.glob(os.path.join(BASE, "*_pc.html"))):
        m = re.search(r'href="style\.pc\.css\?v=(\d+)"', read(f))
        if m:
            return int(m.group(1))
    return 1


def read(p):
    with io.open(p, "r", encoding="utf-8") as f:
        return f.read()


def write(p, t):
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(t)


def transform(html, name, version=None):
    """本番ページのHTML文字列 → PC版HTML文字列。副作用なし（テストから使える）"""
    if version is None:
        version = current_version()
    problems = []

    def rep(old, new, what):
        if old not in html:
            problems.append(what)
            return html
        return html.replace(old, new, 1)

    def rep_re(pattern, make_new, what):
        """バージョン番号のようにキャッシュバスターで変動する部分は正規表現で拾う。
           （以前は ?v=23 等をベタ書きしていたため、バージョンを上げるたびにビルドが壊れていた）"""
        m = re.search(pattern, html)
        if not m:
            problems.append(what)
            return html
        return html[:m.end()] + make_new(m) + html[m.end():]

    # 1) style.pc.css のリンク（style.final.css のリンク行の直後に挿し込む）
    link = ('    <!-- PC専用レイアウト。中身はすべて @media (min-width:1024px) で囲まれているため、'
            'スマホ幅では1行も効きません -->\n'
            '    <link rel="stylesheet" href="style.pc.css?v=%d">\n' % version)
    html = rep_re(r'[ \t]*<link rel="stylesheet" href="style\.final\.css\?v=\d+">\n',
                  lambda m: link, "style.final.css のリンクが見つからない")

    # 2) ヘッダーのロゴリンク（本番は flex-grow:1 で横幅を食い尽くすためPCでは打ち消す）
    html = rep(BRAND_ANCHOR_OLD, BRAND_ANCHOR_NEW, "ヘッダーのブランドリンクが見つからない")

    # 3) PCナビ・電話・診療ステータス
    hb = '                <div class="menu-btn-container" id="menuBtn">'
    html = rep(hb, mark_pc_nav(PC_HEADER, name) + hb, "menu-btn-container が見つからない")

    # 4) ドロワー直後〜フッター直前を <main class="pc-main"> で囲む
    drawer_end = ('            <a href="index.html#contact-area" class="nav-drawer-link">'
                  'アクセス・お問い合わせ</a>\n        </nav>\n')
    html = rep(drawer_end, drawer_end + '\n        <main class="pc-main">\n',
               "ナビゲーションドロワーの終端が見つからない")

    footer = '        <footer class="footer">'
    if html.count(footer) != 1:
        problems.append("footer の開始タグが1個ではない (%d個)" % html.count(footer))
    html = html.replace(footer, '        </main>\n\n' + footer, 1)

    # 5) ページ固有の .pc-wide
    for old, new in WIDE.get(name, []):
        html = rep(old, new, ".pc-wide 対象が見つからない: %s" % old[:50])

    # 6) 診療ステータス同期スクリプト
    html = rep_re(r'[ \t]*<script src="script\.js\?v=\d+"></script>\n',
                  lambda m: SYNC_SCRIPT, "script.js の読み込みが見つからない")

    if problems:
        raise BuildError("%s: %s" % (name, " / ".join(problems)))

    # 7) 最後にサイト内リンクをまとめて _pc.html 版へ。
    #    （ヘッダー・ドロワー・本文のリンクを一度に扱えるので、ここでまとめてやる）
    html = to_pc_links(html)
    return html


def main():
    version = current_version() + (1 if "--bump" in sys.argv else 0)
    print("style.pc.css のバージョン: v=%d" % version)
    ok = True
    for name in PAGES:
        try:
            out = transform(read(os.path.join(BASE, name + ".html")), name, version)
        except BuildError as e:
            print("NG  %s" % e)
            ok = False
            continue
        write(os.path.join(BASE, name + "_pc.html"), out)
        print("OK  %s_pc.html" % name)

    # index_pc.html は手作りなので、バージョン番号だけ揃える
    p = os.path.join(BASE, "index_pc.html")
    t = read(p)
    t2 = re.sub(r'href="style\.pc\.css\?v=\d+"', 'href="style.pc.css?v=%d"' % version, t)
    if t2 == t and 'style.pc.css' not in t:
        print("NG  index_pc.html に style.pc.css のリンクが無い")
        ok = False
    else:
        write(p, t2)
        print("OK  index_pc.html (バージョンのみ更新。本文は手作りなので index.html の変更は手で反映すること)")

    print("\n%s" % ("全ページ生成完了" if ok else "失敗したページがあります"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
