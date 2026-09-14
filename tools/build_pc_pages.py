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

    # 1) style.pc.css のリンク
    marker = '    <link rel="stylesheet" href="style.final.css?v=23">\n'
    link = ('    <!-- PC専用レイアウト。中身はすべて @media (min-width:1024px) で囲まれているため、'
            'スマホ幅では1行も効きません -->\n'
            '    <link rel="stylesheet" href="style.pc.css?v=%d">\n' % version)
    html = rep(marker, marker + link, "style.final.css のリンクが見つからない")

    # 2) ヘッダーのロゴリンク（本番は flex-grow:1 で横幅を食い尽くすためPCでは打ち消す）
    html = rep(BRAND_ANCHOR_OLD, BRAND_ANCHOR_NEW, "ヘッダーのブランドリンクが見つからない")

    # 3) PCナビ・電話・診療ステータス
    hb = '                <div class="menu-btn-container" id="menuBtn">'
    html = rep(hb, PC_HEADER + hb, "menu-btn-container が見つからない")

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
    tail = '    <script src="script.js?v=9"></script>\n'
    html = rep(tail, tail + SYNC_SCRIPT, "script.js の読み込みが見つからない")

    if problems:
        raise BuildError("%s: %s" % (name, " / ".join(problems)))
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
