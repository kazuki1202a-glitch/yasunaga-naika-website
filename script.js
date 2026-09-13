document.addEventListener('DOMContentLoaded', () => {
    // Menu drawer
    const menuBtn = document.getElementById('menuBtn');
    const navDrawer = document.getElementById('navDrawer');
    const navOverlay = document.getElementById('navOverlay');
    const navDrawerClose = document.getElementById('navDrawerClose');

    const openMenu = () => {
        navDrawer.classList.add('open');
        navOverlay.classList.add('open');
        document.body.classList.add('nav-open');
    };
    const closeMenu = () => {
        navDrawer.classList.remove('open');
        navOverlay.classList.remove('open');
        document.body.classList.remove('nav-open');
    };

    if (menuBtn && navDrawer && navOverlay) {
        menuBtn.addEventListener('click', openMenu);
        navOverlay.addEventListener('click', closeMenu);
        if (navDrawerClose) navDrawerClose.addEventListener('click', closeMenu);
    }

    // Clinic Status and Today Highlight Logic
    const isJapaneseHoliday = (date) => {
        const y = date.getFullYear();
        const m = date.getMonth() + 1;
        const d = date.getDate();
        const ymd = `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
        
        // 2026年の祝日データ
        const holidays2026 = [
            "2026-01-01", "2026-01-12", "2026-02-11", "2026-02-23",
            "2026-03-20", "2026-04-29", "2026-05-03", "2026-05-04",
            "2026-05-05", "2026-05-06", "2026-07-20", "2026-08-11",
            "2026-09-21", "2026-09-22", "2026-09-23", "2026-10-12",
            "2026-11-03", "2026-11-23"
        ];
        return holidays2026.includes(ymd);
    };

    const updateClinicStatus = () => {
        const now = new Date();
        const day = now.getDay();
        const hour = now.getHours();
        const min = now.getMinutes();
        const currentTime = hour * 100 + min;

        const summaryContainer = document.getElementById('clinic-status-summary');
        
        // Highlight today in table
        document.querySelectorAll(`[data-day]`).forEach(el => el.classList.remove('today-highlight'));
        document.querySelectorAll(`[data-day="${day}"]`).forEach(el => el.classList.add('today-highlight'));

        let statusText = '';
        let isOpenNow = false;

        if (day === 0 || isJapaneseHoliday(now)) { // Sunday or Holiday
            statusText = '本日は休診日です';
        } else {
            const isThuSat = (day === 4 || day === 6); // Thu, Sat: morning only

            if (currentTime >= 900 && currentTime <= 1130) {
                statusText = '診療受付中です';
                isOpenNow = true;
            } else if (currentTime >= 1131 && currentTime <= 1230) {
                statusText = '午前の診療受付は終了いたしました';
            } else if (!isThuSat && currentTime >= 1400 && currentTime <= 1630) {
                statusText = '診療受付中です';
                isOpenNow = true;
            } else if (!isThuSat && currentTime >= 1631 && currentTime <= 1730) {
                statusText = '午後の診療受付は終了いたしました';
            } else {
                statusText = '只今の時間は、診療時間外です';
            }
        }

        if (summaryContainer) {
            summaryContainer.textContent = statusText;
            summaryContainer.classList.toggle('closed', !isOpenNow);
        }

        // Hide the fixed call bar outside reception hours, since calling then wouldn't reach anyone
        const callBar = document.querySelector('.fixed-call-bar');
        if (callBar) {
            callBar.classList.toggle('hidden', !isOpenNow);
        }
    };

    updateClinicStatus();
    setInterval(updateClinicStatus, 60000);

    // Greeting Toggle Logic
    const toggleBtn = document.getElementById('toggle-greeting');
    const fullGreeting = document.getElementById('full-greeting');

    if (toggleBtn && fullGreeting) {
        // Launch promotion: show the full greeting by default for 30 days after the site goes live
        const launchDate = new Date(2026, 8, 10); // 2026-09-10
        const promoEnd = new Date(launchDate);
        promoEnd.setDate(promoEnd.getDate() + 30);

        if (new Date() < promoEnd) {
            fullGreeting.classList.add('show');
            toggleBtn.style.display = 'none';
        }

        toggleBtn.addEventListener('click', () => {
            fullGreeting.classList.toggle('show');
            if (fullGreeting.classList.contains('show')) {
                toggleBtn.textContent = '閉じる';
            } else {
                toggleBtn.textContent = '全文を表示する';
            }
        });
    }

    // Scroll reveal animation
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('reveal');
            }
        });
    }, { threshold: 0.1 });

    document.querySelectorAll('.feature-item, .greeting-card').forEach(el => {
        el.classList.add('reveal-target');
        observer.observe(el);
    });

    // Tap feedback for buttons (iOS Safari does not trigger :active on tap alone)
    const PRESS_MS = 160;
    const press = (el) => el.classList.add('is-pressed');
    const release = (el) => el.classList.remove('is-pressed');

    // Don't leave a button stuck in its pressed color after a back/forward (bfcache) restore
    window.addEventListener('pageshow', () => {
        document.querySelectorAll('.is-pressed').forEach(release);
    });

    document.querySelectorAll('.btn-3d, .btn-premium-gold, .fixed-call-bar a').forEach(btn => {
        const href = btn.getAttribute('href');
        const isSameTabLink = btn.tagName === 'A' && !!href && btn.target !== '_blank' &&
            !href.startsWith('#') && !/^(tel:|mailto:|javascript:)/i.test(href);

        btn.addEventListener('touchstart', () => press(btn), { passive: true });
        btn.addEventListener('touchcancel', () => release(btn));
        btn.addEventListener('mousedown', () => press(btn));
        btn.addEventListener('mouseleave', () => release(btn));

        if (isSameTabLink) {
            // Keep the pressed color until navigation actually happens (no flicker on touchend)
            btn.addEventListener('click', (e) => {
                if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
                if (typeof e.button === 'number' && e.button > 0) return;
                e.preventDefault();
                press(btn);
                setTimeout(() => { window.location.href = href; }, PRESS_MS);
            });
        } else {
            // Non-navigating buttons (hash links, tel:, external tabs): show the color briefly, then release
            btn.addEventListener('touchend', () => setTimeout(() => release(btn), PRESS_MS));
            btn.addEventListener('mouseup', () => setTimeout(() => release(btn), PRESS_MS));
        }
    });

    // Scroll-to-top link (placed above the "トップページに戻る" button on each page)
    document.querySelectorAll('.scroll-top-link').forEach(el => {
        el.addEventListener('click', (e) => {
            e.preventDefault();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    });
});
