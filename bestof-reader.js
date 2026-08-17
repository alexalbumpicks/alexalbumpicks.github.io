// Best of Year, read-only. This is the published script; best-of-year.js is the editor's and
// is not deployed. The two share bestof-data.js and best-of-year.css, nothing else.
//
// What is deliberately absent, and why it is absent rather than merely hidden:
//
//   localStorage      The editor keeps a saved copy of every entry so hand edits survive a
//                     reload. A reader has nothing to save. Reading a visitor's storage would
//                     also mean a stale blob could shadow the file they just downloaded, so
//                     this file never touches it - what ships in bestof-data.js is what shows.
//   the heal layer    STORAGE_SCHEMA_VERSION and the RERANKED_YEARS / RETIRED_KEYS / backfill
//                     machinery exist only to reconcile a saved copy against the baked data.
//                     With no saved copy there is nothing to reconcile.
//   persist()         The editor assigns yearRank to any year that has never been ranked and
//                     writes it back. Here the printed number is the album's position in the
//                     sorted list, so nothing needs to be assigned and ENTRIES is never mutated.
//   the modal,        Add / edit / delete / reorder / export. The editor page hid these behind
//   export, ranking   an `is-local` CSS class, which stops them being clicked but still ships
//                     every line of the code that performs them. Leaving them out of the file
//                     is the difference between a control being invisible and being absent.
//
// Kept in full: the year nav, the cards, the tag chips, and the mini player.

function esc(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

const ENTRIES = BEST_OF_ENTRIES;

// Seeds the order of a year that was never ranked by hand. No text - the tier badges were
// dropped from the cards long ago; this only breaks ties on rating.
const tierWeight = {
  essential: 3,
  pioneer: 2,
  postinfluence: 1,
  influence: 0
};

function albumArt(entry) {
  if (entry.art) {
    return `<img src="${esc(entry.art)}" alt="${esc(entry.title)} album art" loading="lazy">`;
  }
  return `
    <div class="year-art-fallback" style="background:${esc(entry.artBg || '#181818')};color:${esc(entry.artColor || '#999')}">
      <div>${esc(entry.title)}<br><span style="opacity:.65">${esc(entry.artist)}</span></div>
    </div>
  `;
}

// --- language ---------------------------------------------------------------------------------
// Carried in the URL, not in localStorage. Storage was left out of this file on purpose (see the
// header) and a language preference is not a good enough reason to let it back in: a stored
// preference is invisible, survives past the moment it was wanted, and cannot be linked to. In
// the query string the choice is inspectable, shareable, and gone the moment the visitor leaves.
// The cost is that every internal link has to carry it, which is what withLang below is for.
const LANGS = ['en', 'zh'];
const DEFAULT_LANG = 'en';

// Only the page's own furniture. Album titles, artist names and genre tags are left exactly as
// they are in the data: they are proper nouns and terms of art, and 'Singer-songwriter' or
// 'trip-hop' translated into Chinese reads worse than the English, not better.
const STRINGS = {
  en: {
    label: 'EN',
    htmlLang: 'en',
    kicker: "Alex's Album Picks",
    docTitle: year => `Alex's Album Picks — Best Albums of ${year}`,
    yearTitle: year => `Best Albums of ${year}`,
    navLabel: 'Browse years',
    langLabel: 'Language',
    sidebarLabel: 'How this ranking works',
    note: 'Albums are ordered by hand, best first. Years I have not gone through yet fall back to rating order.',
    noteProvisional: 'This year has not been gone through yet. The list is held back until it is.',
    provisionalTitle: 'Still being filled in',
    provisionalHeading: year => `${year} is still being filled in`,
    provisionalBody: 'I have not finished going through this year, so the ranking is not up yet. Check back.',
    emptyHeading: year => `No albums for ${year}`,
    emptyBody: 'Nothing ranked for this year yet.',
    listen: 'Listen',
    hidePlayer: 'Hide player',
    close: 'Close'
  },
  zh: {
    label: '中文',
    htmlLang: 'zh-Hans',
    kicker: 'Alex 的专辑精选',
    docTitle: year => `Alex 的专辑精选 — ${year} 年度最佳专辑`,
    yearTitle: year => `${year} 年度最佳专辑`,
    navLabel: '浏览年份',
    langLabel: '语言',
    sidebarLabel: '关于这个榜单',
    note: '专辑由我手动排序，最好的排在前面。还没有整理过的年份暂时按评分排列。',
    noteProvisional: '这一年我还没有整理，榜单暂时不放出来。',
    provisionalTitle: '还在整理中',
    provisionalHeading: year => `${year} 年还在整理中`,
    provisionalBody: '这一年我还没有听完，榜单还没做好。过段时间再来看看。',
    emptyHeading: year => `${year} 年暂无专辑`,
    emptyBody: '这一年还没有排过任何专辑。',
    listen: '试听',
    hidePlayer: '收起播放器',
    close: '关闭'
  }
};

// The default language is left out of the URL, so the plain address stays plain and only the
// non-default choice has to be spelled out.
function withLang(query) {
  return activeLang === DEFAULT_LANG ? query : `${query}&lang=${activeLang}`;
}

// A bare query string keeps the visitor on this page whatever it is named or wherever it is
// mounted. The editor hard-codes its own filename here; the reader has no reason to.
function yearLink(year) {
  return withLang(`?year=${encodeURIComponent(year)}`);
}

// Switching language must not also throw away which year you were reading.
function langLink(lang) {
  const base = `?year=${encodeURIComponent(activeYear)}`;
  return lang === DEFAULT_LANG ? base : `${base}&lang=${lang}`;
}

// Years that are still being filled in: dimmed in the nav, and their list withheld in favour of
// a note. Kept as a predicate rather than a list of years because the pre-1967 stretch is a
// contiguous range: adding 1958 to the data should not also require editing this file.
// Nothing is deleted or hidden from the data - bestof-data.js still carries every album for these
// years and the editor still shows them. This only decides what the published page puts on screen,
// so finishing a year is a one-line change here, not a data migration.
function isProvisional(year) {
  return year === 2025 || year < 1967;
}

function compareDefaultYearOrder(a, b) {
  const ratingDiff = (b.entry.rating || 0) - (a.entry.rating || 0);
  if (ratingDiff !== 0) return ratingDiff;

  const tierDiff = (tierWeight[b.entry.tier] || 0) - (tierWeight[a.entry.tier] || 0);
  if (tierDiff !== 0) return tierDiff;

  return a.idx - b.idx;
}

function allAlbums() {
  return ENTRIES
    .map((entry, idx) => ({ entry, idx }))
    .filter(({ entry }) => entry.type === 'album' && Number.isFinite(entry.year));
}

// Same comparator as the editor, minus the write-back. The editor stamps yearRank onto an
// unranked year and saves it; here the rank shown is just the index in this sorted array, so
// the sort is pure and ENTRIES comes out exactly as bestof-data.js left it.
function sortedYearAlbums(year) {
  return allAlbums()
    .filter(({ entry }) => entry.year === year)
    .sort((a, b) => {
      if (Number.isFinite(a.entry.yearRank) || Number.isFinite(b.entry.yearRank)) {
        if (!Number.isFinite(a.entry.yearRank)) return 1;
        if (!Number.isFinite(b.entry.yearRank)) return -1;
        if (a.entry.yearRank !== b.entry.yearRank) return a.entry.yearRank - b.entry.yearRank;
      }
      return compareDefaultYearOrder(a, b);
    });
}

// --- page state -------------------------------------------------------------------------------
// Everything above this line is pure: given the data it computes the same answer every time and
// reads nothing from the environment. Everything below depends on the URL. Keeping the boundary
// in one place is what lets t_reader.js eval the sort on its own, with no window to stub, and
// compare it against the editor's.
const years = [...new Set(allAlbums().map(({ entry }) => entry.year))].sort((a, b) => b - a);
const params = new URLSearchParams(window.location.search);
const requestedYear = Number.parseInt(params.get('year'), 10);
// An unknown ?year= is honoured rather than corrected, so a shared link to a year that has
// since been emptied lands on the empty state instead of silently showing a different year.
const activeYear = Number.isFinite(requestedYear) ? requestedYear : (years[0] || new Date().getFullYear());
// An unrecognised ?lang= falls back rather than blanking the page, on the same principle: a bad
// parameter should degrade to the default, not to an error.
const requestedLang = params.get('lang');
const activeLang = LANGS.includes(requestedLang) ? requestedLang : DEFAULT_LANG;
const S = STRINGS[activeLang];

let activePlayerIndex = null;

// The bits of chrome that live in index.html rather than being generated here. Setting them from
// JS means index.html carries one language's wording as its shipped state and this rewrites it;
// the alternative, duplicating every string into data attributes, puts the same text in two files
// and lets them drift.
function renderChrome() {
  document.documentElement.lang = S.htmlLang;
  document.title = S.docTitle(activeYear);
  document.getElementById('hero-kicker').textContent = S.kicker;
  document.getElementById('sidebar-label').textContent = S.sidebarLabel;
  document.getElementById('year-nav').setAttribute('aria-label', S.navLabel);
  document.getElementById('mini-player-close').setAttribute('title', S.close);

  // Real links, like the year pills - so a language is a place you can be sent to, and the
  // browser Back button undoes the switch. The inactive one is what you can click.
  const nav = document.getElementById('lang-nav');
  nav.setAttribute('aria-label', S.langLabel);
  nav.innerHTML = LANGS
    .map(lang => {
      const cls = `lang-pill${lang === activeLang ? ' is-active' : ''}`;
      const current = lang === activeLang ? ' aria-current="true"' : '';
      return `<a class="${cls}" href="${langLink(lang)}" lang="${STRINGS[lang].htmlLang}"${current}>${STRINGS[lang].label}</a>`;
    })
    .join('');
}

function renderYearNav() {
  const navYears = years.includes(activeYear)
    ? years
    : [activeYear, ...years].sort((a, b) => b - a);
  document.getElementById('year-nav').innerHTML = navYears
    .map(year => {
      const cls = `year-pill${year === activeYear ? ' is-active' : ''}${isProvisional(year) ? ' is-provisional' : ''}`;
      // The title carries the reason in words. Dimming is only legible by comparison, so on
      // its own it says "different" without ever saying what is different about it.
      const why = isProvisional(year) ? ` title="${esc(S.provisionalTitle)}"` : '';
      return `<a class="${cls}" href="${yearLink(year)}"${why}>${year}</a>`;
    })
    .join('');
}

function renderList() {
  const list = document.getElementById('year-list');

  document.getElementById('year-title').textContent = S.yearTitle(activeYear);
  // The year blurb stays hidden here for the same reason as on the editor: the list is the
  // argument, and a paragraph above the number one only competes with it.
  document.getElementById('year-dek').hidden = true;
  // On a provisional year the note describes the state of the year rather than how the ranking
  // works, because there is no ranking on screen for the usual sentence to be about.
  document.getElementById('ranking-note').textContent = isProvisional(activeYear)
    ? S.noteProvisional
    : S.note;

  // A provisional year is withheld, not empty: the albums exist in the data and sort fine, but a
  // half-finished top ten read as a finished one no matter how dim the pill in the nav was, so
  // the list is not rendered at all. The check sits ahead of the empty-state so that a year which
  // is both provisional and empty says the more specific of the two things.
  if (isProvisional(activeYear)) {
    list.innerHTML = `
      <section class="year-empty">
        <h2>${esc(S.provisionalHeading(activeYear))}</h2>
        <p>${esc(S.provisionalBody)}</p>
      </section>
    `;
    return;
  }

  const yearAlbums = sortedYearAlbums(activeYear);

  if (!yearAlbums.length) {
    list.innerHTML = `
      <section class="year-empty">
        <h2>${esc(S.emptyHeading(activeYear))}</h2>
        <p>${esc(S.emptyBody)}</p>
      </section>
    `;
    return;
  }

  list.innerHTML = yearAlbums.map(({ entry }, i) => {
    const tags = (entry.tags || []).map(tag => `<span class="year-tag">${esc(tag)}</span>`).join('');
    const audio = entry.audio
      ? `<button class="year-action" type="button" data-listen="${i}" aria-expanded="${activePlayerIndex === i ? 'true' : 'false'}">${activePlayerIndex === i ? esc(S.hidePlayer) : esc(S.listen)}</button>`
      : '';
    // Only the albums that have one. `tagline` and `tier` were dropped from these cards because
    // 36 and 81 entries out of 985 carried them - a field that thin reads as an inconsistency
    // rather than a feature. `review` is thinner still today, but the difference is that these
    // were written for this page, by hand, one album at a time. An album with nothing to say
    // renders exactly as it did before, so the sparse case stays clean while the list fills in.
    //
    // The blurbs were written in Chinese and translated after, so `review` is the original and
    // `reviewEn` the translation. On an untranslated album the Chinese is shown in either
    // language rather than nothing: a blurb the reader may not be able to read still beats a
    // card that silently loses a paragraph when you switch language. `lang` on the element is
    // what tells the browser it is looking at the other language, which matters for font
    // selection and for a screen reader picking a voice.
    const reviewText = activeLang === 'en' ? (entry.reviewEn || entry.review) : entry.review;
    const reviewLang = activeLang === 'en' && !entry.reviewEn ? 'zh-Hans' : S.htmlLang;
    const review = reviewText
      ? `<p class="year-review" lang="${reviewLang}">${esc(reviewText)}</p>`
      : '';

    return `
      <article class="year-card" style="position:relative">
        <div class="year-rank">
          <div class="year-rank-num">${i + 1}</div>
        </div>
        <div class="year-art">${albumArt(entry)}</div>
        <div class="year-copy">
          <div class="year-title-row">
            <h2 class="year-album-title">${esc(entry.title)}</h2>
          </div>
          <div class="year-artist">${esc(entry.artist)}</div>
          ${tags ? `<div class="year-tags">${tags}</div>` : ''}
          ${review}
          ${audio ? `<div class="year-actions">${audio}</div>` : ''}
        </div>
      </article>
    `;
  }).join('');
}

function playYearAlbum(index) {
  const yearAlbums = sortedYearAlbums(activeYear);
  const item = yearAlbums[index];
  if (!item || !item.entry.audio) return;
  const entry = item.entry;
  const url = entry.audio;

  const player = document.getElementById('mini-player');
  const iframe = document.getElementById('mini-player-iframe');
  const audio = document.getElementById('mini-player-audio');
  const titleEl = document.getElementById('mini-player-title');

  if (activePlayerIndex === index && player.classList.contains('visible')) {
    closeMiniPlayer();
    return;
  }

  const sp = url.match(/open\.spotify\.com\/(track|album|playlist|episode)\/([A-Za-z0-9]+)/);
  const yt = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([A-Za-z0-9_-]+)/);
  const sc = url.includes('soundcloud.com');
  const af = /\.(mp3|ogg|wav|m4a|aac|flac)(\?|$)/i.test(url);

  let iframeSrc = '';
  let iframeH = 80;
  let useAudio = false;

  if (sp) {
    iframeSrc = `https://open.spotify.com/embed/${sp[1]}/${sp[2]}?utm_source=generator&autoplay=1&theme=0`;
  } else if (yt) {
    window.open(url, '_blank');
    return;
  } else if (sc) {
    iframeSrc = `https://w.soundcloud.com/player/?url=${encodeURIComponent(url)}&auto_play=true&color=%23ff5500&hide_related=true&show_comments=false&show_teaser=false`;
    iframeH = 120;
  } else if (af) {
    useAudio = true;
  } else {
    window.open(url, '_blank');
    return;
  }

  activePlayerIndex = index;
  titleEl.textContent = `${entry.artist}  —  ${entry.title}`;

  player.style.display = 'block';
  void player.offsetWidth;
  player.classList.add('visible');

  if (useAudio) {
    iframe.style.display = 'none';
    iframe.src = '';
    audio.style.display = 'block';
    audio.src = url;
    audio.play().catch(() => {});
  } else {
    audio.style.display = 'none';
    audio.pause();
    audio.src = '';
    // Replacing the element rather than reassigning .src keeps a dead entry out of history,
    // so the browser Back button does not walk backwards through every preview played.
    const curIframe = document.getElementById('mini-player-iframe');
    const fresh = document.createElement('iframe');
    fresh.id = 'mini-player-iframe';
    fresh.height = String(iframeH);
    fresh.setAttribute('allow', 'autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture');
    fresh.setAttribute('allowtransparency', 'true');
    fresh.style.cssText = 'width:100%;display:block;border:none';
    fresh.src = iframeSrc;
    curIframe.replaceWith(fresh);
  }

  renderList();
}

function closeMiniPlayer() {
  const player = document.getElementById('mini-player');
  const iframe = document.getElementById('mini-player-iframe');
  const audio = document.getElementById('mini-player-audio');
  player.classList.remove('visible');
  setTimeout(() => {
    player.style.display = 'none';
    iframe.src = '';
    audio.pause();
    audio.src = '';
    activePlayerIndex = null;
    renderList();
  }, 240);
}

// One listener on the list, not one per card: renderList replaces the whole innerHTML on every
// play and close, so anything bound to an individual button would be discarded with it.
document.getElementById('year-list').addEventListener('click', event => {
  const listenBtn = event.target.closest('[data-listen]');
  if (!listenBtn) return;
  playYearAlbum(Number.parseInt(listenBtn.dataset.listen, 10));
});

document.getElementById('mini-player-close').addEventListener('click', closeMiniPlayer);

renderChrome();
renderYearNav();
renderList();
