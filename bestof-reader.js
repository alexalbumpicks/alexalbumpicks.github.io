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
    appleMusic: 'Apple Music',
    appleMusicTitle: entry => `Open ${entry} on Apple Music`,
    crossLinkTitle: (title, year) => `Go to ${title} (${year})`,
    close: 'Close',
    // The badge is the whole of what a reader sees. The `sensitive` field on the entry holds a
    // reason, and that reason is deliberately NOT rendered anywhere: a visitor who wants to know
    // what is in a record can find out the way anyone finds anything out, and a tooltip spelling
    // out the worst of it would be more specific than the badge it explains, which defeats the
    // point of a badge this vague.
    //
    // The reason is kept in the data because it does a second job that has nothing to do with the
    // reader — it keeps the author honest. A boolean can be set on a feeling and never questioned;
    // a sentence has to be defensible, and it has to describe something in the RECORD. That is
    // what keeps this off artists rather than on albums.
    sensitive: 'sensitive content'
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
    appleMusic: 'Apple Music',
    appleMusicTitle: entry => `在 Apple Music 上打开《${entry}》`,
    crossLinkTitle: (title, year) => `跳转到 ${year} 年的《${title}》`,
    close: '关闭',
    // Not a translation of the English - 慎入 is what a Chinese reader would actually be told, and
    // it carries the "approach at your own discretion" sense that `sensitive content` only implies.
    sensitive: '慎入'
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
// 2025 was the one carve-out and is now published: 38 albums ranked 1-38 by hand, all with art and
// a preview. What is left is the contiguous pre-1967 range, which is why the predicate is a
// comparison again rather than a comparison plus a special case.
function isProvisional(year) {
  return year < 1967;
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

// --- cross-links between blurbs ----------------------------------------------------------------
// When a blurb names another album that is in the file, the name becomes a link to that album's
// card. The pairs are curated in the data, in `reviewLinks`, rather than detected from the prose;
// the reasoning is written up in tmp/add_review_links.py, but the short of it is that the Chinese
// uses translated titles (《女英雄》 for Pure Heroine) so a title matcher finds none of them, and
// matching the other way round lights up Music, Star, Album, Post, Play and Grace as ordinary
// English words. Alex's text is never rewritten - this only decides where anchors go around it.

// A card's own id, and the fragment a link to it points at. Derived the same way as entryKey():
// NFKD, strip combining marks, then keep letters and digits of any script, so a CJK title folds
// to its own characters rather than to the empty string every other CJK title also folds to.
// Artist is in the key because year+title alone is not unique across the file in principle, and
// an id that collides silently sends the reader to the wrong record.
function albumSlug(entry) {
  const norm = value => String(value || '')
    .normalize('NFKD')
    // Latin combining marks only, then recompose - entryKey() does the same, and the two are
    // meant to stay in step. Stripping without recomposing loses a voiced kana: NFKD splits one
    // into its base plus U+3099, the dakuten. U+3099 is outside this range, but it is a mark
    // rather than a letter, so the /[^\p{L}\p{N}]/ below deletes it - and every voiced kana
    // folds together with its unvoiced base. Recomposing puts the dakuten back before anything
    // is stripped, so an acute accent still folds away while the kana survives intact.
    .replace(/[\u0300-\u036f]/g, '')
    .normalize('NFC')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]/gu, '');
  return `album-${entry.year}-${norm(entry.title)}-${norm(entry.artist)}`;
}

// year|title -> entry, for resolving a link's target. Built once; renderList runs on every play
// and close, and rebuilding a 1015-entry index inside the map callback would be 36 times per
// render for no reason.
const ALBUMS_BY_YEAR_TITLE = new Map();
ENTRIES.forEach(entry => {
  if (entry.type === 'album') ALBUMS_BY_YEAR_TITLE.set(`${entry.year}|${entry.title}`, entry);
});

// Escapes first, then splices anchors into the escaped string. Doing it the other way round -
// linking the raw text and escaping after - would escape the markup we just added, and linking
// the raw text and *not* escaping would put unescaped blurb text on the page.
//
// Every step here fails closed. A surface string that is missing, or that appears more than once,
// is skipped rather than guessed at: no link at all is a smaller error than a link on the wrong
// words in someone else's writing. Same for a target that is not in the file, and for a target in
// a provisional year, whose list is withheld - the link would land on a page with no card to
// scroll to.
function linkifyReview(text, entry) {
  const html = esc(text);
  const spans = [];

  (entry.reviewLinks || []).forEach(link => {
    const surface = activeLang === 'en' ? link.en : link.zh;
    if (!surface) return;
    const target = ALBUMS_BY_YEAR_TITLE.get(`${link.year}|${link.title}`);
    if (!target || isProvisional(target.year)) return;
    // An entry linking to itself would render a link that goes nowhere the reader is not already.
    if (target === entry) return;
    const needle = esc(surface);
    const at = html.indexOf(needle);
    if (at === -1) return;
    if (html.indexOf(needle, at + needle.length) !== -1) return;
    spans.push({ at, end: at + needle.length, target });
  });

  if (!spans.length) return html;

  // Collected as offsets and spliced in one pass, rather than replaced one at a time, because a
  // later replace() can otherwise match inside the markup an earlier one inserted.
  spans.sort((a, b) => a.at - b.at);
  const kept = [];
  spans.forEach(span => {
    // Overlapping surfaces would nest one anchor inside another. Keep the earlier, drop the rest.
    if (!kept.length || span.at >= kept[kept.length - 1].end) kept.push(span);
  });

  let out = '';
  let cursor = 0;
  kept.forEach(span => {
    // encodeURIComponent on the fragment only: the id attribute keeps the raw slug, which is
    // legal in HTML5 and is what getElementById is handed after decoding on the way back in.
    const href = `${yearLink(span.target.year)}#${encodeURIComponent(albumSlug(span.target))}`;
    out += html.slice(cursor, span.at)
      + `<a class="year-review-link" href="${esc(href)}"`
      + ` title="${esc(S.crossLinkTitle(span.target.title, span.target.year))}">`
      + html.slice(span.at, span.end)
      + '</a>';
    cursor = span.end;
  });
  return out + html.slice(cursor);
}


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

const decadeOf = year => Math.floor(year / 10) * 10;

// Two rows instead of one: pick a decade, then a year inside it. 71 pills wrapped to four rows
// and the whole block had to be read to find anything, because every pill looked like every
// other one and the only ordering cue was that they counted down. Eight decades fit one row, and
// the second row is never longer than ten.
//
// Every year is still rendered. The decades that are not open are hidden in CSS rather than left
// out of the HTML, which matters for three separate reasons: each year stays a real crawlable
// link, switching decades needs no re-render and cannot lose the active year, and the nav keeps
// working with JavaScript off — a stylesheet that never applies .is-open would leave all 71
// visible, which is the old behaviour rather than a broken one.
//
// The open decade is still not in the URL, but it no longer needs to be: it is derived from the
// active year, and a decade is now a link to a year rather than a control that only expands a row.
// Clicking one lands on the last year of that decade — the most recent, which is both the one most
// likely to be wanted and the one already sitting leftmost in the row that opens underneath.
//
// "Last" is read off the data, not computed as dec + 9: the 1950s stop at 1959 but the 1950s in
// this file are 1954, 1955, 1956 and 1959, and the current decade stops wherever the data does.
// So a decade with a gap at its end still points somewhere real.
function lastYearOf(dec, navYears) {
  return Math.max(...navYears.filter(year => decadeOf(year) === dec));
}

function renderYearNav() {
  const navYears = years.includes(activeYear)
    ? years
    : [activeYear, ...years].sort((a, b) => b - a);

  const decades = [...new Set(navYears.map(decadeOf))].sort((a, b) => b - a);
  const openDecade = decadeOf(activeYear);

  const decadeRow = decades
    .map(dec => {
      // A decade counts as provisional only when every year in it is: a decade with one finished
      // year in it is not a year I have not got to, and dimming it would say it was.
      const inDec = navYears.filter(year => decadeOf(year) === dec);
      const allProvisional = inDec.every(year => isProvisional(year));
      const cls = `decade-pill${dec === openDecade ? ' is-active' : ''}${allProvisional ? ' is-provisional' : ''}`;
      // aria-current, not aria-expanded: activating this goes somewhere rather than unfolding
      // something, and the row underneath opens because of where you now are, not because the
      // control was toggled. Saying "expanded" would promise a control that stays put.
      const current = dec === openDecade ? ' aria-current="true"' : '';
      return `<a class="${cls}" href="${yearLink(lastYearOf(dec, navYears))}" data-decade="${dec}"${current}>${dec}s</a>`;
    })
    .join('');

  const yearRows = decades
    .map(dec => {
      const pills = navYears
        .filter(year => decadeOf(year) === dec)
        .map(year => {
          const cls = `year-pill${year === activeYear ? ' is-active' : ''}${isProvisional(year) ? ' is-provisional' : ''}`;
          // The title carries the reason in words. Dimming is only legible by comparison, so on
          // its own it says "different" without ever saying what is different about it.
          const why = isProvisional(year) ? ` title="${esc(S.provisionalTitle)}"` : '';
          return `<a class="${cls}" href="${yearLink(year)}"${why}>${year}</a>`;
        })
        .join('');
      return `<div class="decade-years${dec === openDecade ? ' is-open' : ''}" data-decade-years="${dec}">${pills}</div>`;
    })
    .join('');

  document.getElementById('year-nav').innerHTML =
    `<div class="decade-row">${decadeRow}</div>${yearRows}`;
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
  // Drawn from the same sorted array the cards come from, so a dot's data-idx is the card's index
  // and the scroll sync can match them without a second lookup.
  renderYearMap(yearAlbums, activeYear);

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
    // The "Preview: <track>" caption used to live here, naming the song the button would play and
    // flipping to "Now playing" while it played. Removed as clutter: with the Apple Music link
    // added beside it the row had three things in it, and two of them were prose.
    //
    // The state half of it was already redundant — the button itself reads "Hide player" on the
    // one card that is sounding, so which card is playing was never only knowable from the
    // caption. What is genuinely lost is knowing *which track* before pressing, which is worth
    // less than a row you can read at a glance.
    //
    // `audioTrack` stays in the data. It cost a catalogue round-trip per album to resolve and
    // nothing to carry, and this is a presentation decision that may well go the other way once
    // the row is designed rather than accumulated.
    // The preview answers "what does this sound like"; this answers "where do I go to hear the
    // rest of it". They are different questions and the 30-second clip was only ever answering
    // the first one, so the card dead-ended right at the point the reader was most interested.
    //
    // Apple rather than Spotify because the data is already Apple's: every `audio` URL on this
    // page is an iTunes preview, so the album page is reachable by looking up the collection that
    // owns the preview — an identity match on a URL already stored, not a title search that has
    // to be trusted. The Spotify attempt went through MusicBrainz and returned nothing for even
    // the first album, which is the difference between deriving a link and guessing one.
    //
    // Five of the 23 have no link for the same reason they have no track name: the preview is not
    // in the catalogue, and neither is the album. Those cards keep the Listen button and lose
    // nothing else, rather than carrying a button that goes somewhere wrong.
    const appleMusic = entry.appleMusic
      ? `<a class="year-action year-action-secondary" href="${esc(entry.appleMusic)}" target="_blank" rel="noopener noreferrer" title="${esc(S.appleMusicTitle(entry.title))}">${esc(S.appleMusic)}</a>`
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
    // Not esc()'d again: linkifyReview escapes internally and returns HTML. Everything it emits
    // is either an escaped slice of the blurb or an anchor it assembled out of escaped parts, so
    // no blurb text reaches the page unescaped - escaping the result would show the tags.
    const review = reviewText
      ? `<p class="year-review" lang="${reviewLang}">${linkifyReview(reviewText, entry)}</p>`
      : '';

    // A lyric from the record, above the blurb. Not run through linkifyReview: the cross-link
    // matcher works on surfaces Alex chose inside his own prose, and a lyric is someone else's
    // words - a band name that happens to appear in one is a coincidence, not a reference.
    // Escaped, never translated. The words are the record's, so they are the same in both
    // languages, exactly like the album title above them.
    const lyric = entry.lyric && entry.lyric.text
      ? `<figure class="year-lyric-block">
          <blockquote class="year-lyric">${esc(entry.lyric.text)}</blockquote>
          ${entry.lyric.song ? `<figcaption class="year-lyric-song">&quot;${esc(entry.lyric.song)}&quot;</figcaption>` : ''}
        </figure>`
      : '';

    return `
      <article class="year-card" id="${esc(albumSlug(entry))}" style="position:relative">
        ${entry.sensitive ? `<div class="year-sensitive">${esc(S.sensitive)}</div>` : ''}
        <div class="year-rank">
          <div class="year-rank-num">${i + 1}</div>
        </div>
        <div class="year-art">${albumArt(entry)}</div>
        <div class="year-copy">
          <div class="year-title-row">
            <h2 class="year-album-title">${esc(entry.title)}</h2>
          </div>
          <div class="year-artist">${esc(entry.artist)}${entry.label ? `<span class="year-label"> · ${esc(entry.label)}</span>` : ''}</div>
          ${tags ? `<div class="year-tags">${tags}</div>` : ''}
          ${lyric}
          ${review}
          ${audio || appleMusic ? `<div class="year-actions">${audio}${appleMusic}</div>` : ''}
        </div>
      </article>
    `;
  }).join('');
}

// --- the map -----------------------------------------------------------------------------------
// A US outline in the sidebar with one dot per located band, and the dot for whichever album is
// currently at the top of the reading area lit up.
//
// City names are NOT drawn. At this scale Talking Heads and The Feelies land 4px apart and their
// labels overprint into an unreadable smear; the same is true of any two bands from one scene,
// which is exactly the pattern the map exists to show. So the labels come off and the caption
// under the map names only the current one - you get the place without the clutter, and the
// clutter would have been worst precisely where the map is most interesting.
//
// Everything is pre-projected in bestof-origins.js, so this draws circles at given coordinates and
// does no geography of its own.
let mapDots = [];

// The map is cumulative, not a snapshot of one year. On the 1985 page you see 1985's bands in red,
// every city that has already appeared since 1980 in grey, and nothing at all from 1986 onward - so
// scrolling forward builds the picture up rather than replacing it, and the grey is the memory of
// where the music has already been. Hiding the future rather than greying it is the point: a map
// showing Aberdeen in 1980 would give away that Nirvana is coming, and the argument is that these
// scenes did not know about each other yet.
//
// TWO MAPS, one visible at a time, swapped by the country of whichever band is being read. Both are
// built up front and toggled, rather than re-rendered on every scroll - a 12KB path string rebuilt
// sixty times a second is not free, and the swap has to be instant to read as one panel changing
// rather than two panels fighting.
const MAP_DEFS = {
  US: { viewBox: typeof US_MAP_VIEWBOX !== 'undefined' ? US_MAP_VIEWBOX : '', path: typeof US_MAP_PATH !== 'undefined' ? US_MAP_PATH : '' },
  GB: { viewBox: typeof UK_MAP_VIEWBOX !== 'undefined' ? UK_MAP_VIEWBOX : '', path: typeof UK_MAP_PATH !== 'undefined' ? UK_MAP_PATH : '' }
};

function renderYearMap(albums, year) {
  const card = document.getElementById('map-card');
  if (!card || typeof BAND_ORIGINS === 'undefined') return;

  const located = albums
    .map((item, i) => ({ i, entry: item.entry, origin: BAND_ORIGINS[item.entry.artist] }))
    .filter(x => x.origin);

  // Cities already seen in an earlier year, per country. Keyed by coordinate rather than by name so
  // two spellings of one place cannot draw two dots, and deduped against this year so a city that is
  // active now is not also drawn grey underneath it.
  const here = new Set(located.map(x => x.origin.country + ':' + x.origin.x + ',' + x.origin.y));
  const prior = new Map();
  ENTRIES.forEach(e => {
    if (e.type !== 'album' || !(e.year < year)) return;
    const o = BAND_ORIGINS[e.artist];
    if (!o) return;
    const k = o.country + ':' + o.x + ',' + o.y;
    if (!here.has(k)) prior.set(k, o);
  });

  if (!located.length && !prior.size) {
    card.hidden = true;
    mapDots = [];
    return;
  }
  card.hidden = false;

  const svgs = Object.keys(MAP_DEFS).map(country => {
    const def = MAP_DEFS[country];
    if (!def.path) return '';
    const greys = [...prior.values()].filter(o => o.country === country)
      .map(o => `<circle class="map-dot is-prior" cx="${o.x}" cy="${o.y}" r="3"></circle>`).join('');
    // Drawn after the grey so a live dot is never buried under a memory of itself.
    const reds = located.filter(x => x.origin.country === country)
      .map(x => `<circle class="map-dot" data-idx="${x.i}" cx="${x.origin.x}" cy="${x.origin.y}" r="4"></circle>`)
      .join('');
    return `<svg class="map-svg" data-country="${country}" viewBox="${def.viewBox}" hidden`
         + ` role="img" aria-label="Where this year's bands were from">`
         + `<path class="map-land" d="${def.path}"/>${greys}${reds}</svg>`;
  }).join('');

  document.getElementById('year-map').innerHTML = svgs;
  // A new year rebuilds the svgs, so the remembered country no longer refers to a live element.
  mapCountryShown = null;
  mapDots = located;
  if (located.length) setMapActive(located[0].i);
  else showMapFor([...prior.values()][0].country, '', '');
}

// Only one country on screen. Called on every highlight change, so the common case - same country,
// different band - must be cheap: it updates two lines of text and returns.
//
// A country CHANGE cross-fades. The two maps are different shapes, 631x400 against 330x400, which
// at sidebar width is 162px tall against 310px - so a fade alone would dissolve one map into
// another while the panel jumped 148px and shoved the caption up with it. The height is therefore
// transitioned at the same time, and both maps are stacked absolutely so neither reserves space.
let mapCountryShown = null;
let mapFadeToken = 0;

function mapHeightFor(svg, wrapWidth) {
  // From the viewBox, not from a measurement: the incoming map is invisible and may be display:none
  // at the moment we need its height, so there is nothing to measure yet.
  const vb = (svg.getAttribute('viewBox') || '').split(/\s+/).map(Number);
  if (vb.length !== 4 || !vb[2]) return 0;
  return wrapWidth * (vb[3] / vb[2]);
}

function showMapFor(country, band, city) {
  const b = document.getElementById('map-band');
  const c = document.getElementById('map-city');
  // Both lines always present, even empty, so the card does not change height as you scroll past an
  // album with no dot - a sidebar that jumps is worse than one that goes blank.
  if (b) b.textContent = band || '\u00a0';
  if (c) c.textContent = city || '\u00a0';

  if (country === mapCountryShown) return;

  const wrap = document.getElementById('year-map');
  if (!wrap) return;
  const svgs = [...wrap.querySelectorAll('.map-svg')];
  const next = svgs.find(s => s.dataset.country === country);
  if (!next) return;

  const show = () => {
    svgs.forEach(svg => {
      // setAttribute, NOT svg.hidden. `hidden` is defined on HTMLElement and an <svg> is an
      // SVGElement, so `svg.hidden = false` silently creates a plain JS property and leaves the
      // attribute in place - the element then reports hidden === false while [hidden] still
      // matches and display stays none. It looks like a CSS bug and is not one.
      if (svg === next) svg.removeAttribute('hidden');
      else svg.setAttribute('hidden', '');
    });
    wrap.style.height = mapHeightFor(next, wrap.clientWidth) + 'px';
  };

  const first = mapCountryShown === null;
  mapCountryShown = country;

  // First paint, or reduced motion: swap outright. Nothing has been seen yet in the first case, and
  // in the second the animation is the part being declined, not the map.
  if (first || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    show();
    wrap.classList.remove('is-fading');
    return;
  }

  // Fade THROUGH blank rather than cross-fading. Two maps dissolving into each other at different
  // sizes reads as a glitch; going out and back in reads as one panel changing its mind. The height
  // moves during the blank half, so the caption below never visibly jumps.
  const token = ++mapFadeToken;
  wrap.classList.add('is-fading');
  setTimeout(() => {
    if (token !== mapFadeToken) return;   // a faster scroll already asked for a different country
    show();
    // Force a style flush so the browser sees opacity 0 with the NEW map in place before it sees
    // opacity 1 - without a flush the two changes coalesce into one frame and there is nothing to
    // animate from. Deliberately not requestAnimationFrame: rAF does not fire in a backgrounded
    // tab, and if the un-fade never runs the map is left invisible with no way back until the next
    // country change. A forced reflow is synchronous and cannot be skipped.
    void wrap.offsetHeight;
    wrap.classList.remove('is-fading');
  }, 160);
}

function setMapActive(idx) {
  const hit = mapDots.find(m => m.i === idx);
  if (!hit) return;
  document.querySelectorAll('#year-map .map-dot').forEach(d => {
    const on = d.dataset.idx !== undefined && Number(d.dataset.idx) === idx;
    d.classList.toggle('is-active', on);
    // Move the active dot last so it paints over any dot sharing its coordinates - Los Angeles
    // carries three bands across the decade and London rather more, all on one pixel.
    if (on) d.parentNode.appendChild(d);
  });
  // The band name matters as much as the city: the year lists also hold acts with no dot at all, so
  // a bare city name leaves you working out which album it belongs to.
  showMapFor(hit.origin.country, hit.entry.artist, hit.origin.city);
}

// Which album is "at the top" - the last card whose top edge has passed the reading line. A fixed
// offset rather than an IntersectionObserver: the question is not "is this visible" but "which one
// is currently under the heading", and that is a comparison against one line.
function syncMapToScroll() {
  if (!mapDots.length) return;
  const cards = document.querySelectorAll('.year-list .year-card');
  if (!cards.length) return;
  const LINE = 120;
  let current = 0;
  cards.forEach((c, i) => {
    if (c.getBoundingClientRect().top <= LINE) current = i;
  });
  // The last cards can never reach the line - there is not enough page below them to scroll their
  // top edge that far - so without this the final album of every year would be unreachable.
  const atBottom = window.innerHeight + window.scrollY
                   >= document.documentElement.scrollHeight - 2;
  if (atBottom) current = cards.length - 1;

  // Hold the last located album rather than blanking, so scrolling through a run of acts with no
  // dot does not flicker the sidebar empty and back.
  let pick = mapDots[0].i;
  mapDots.forEach(m => { if (m.i <= current) pick = m.i; });
  setMapActive(pick);
}

let mapTick = false;
window.addEventListener('scroll', () => {
  if (mapTick) return;
  mapTick = true;
  requestAnimationFrame(() => { mapTick = false; syncMapToScroll(); });
}, { passive: true });

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

// The decade click handler that used to live here is gone. It toggled .is-active and .is-open by
// hand so that opening a decade cost no re-render; now that a decade is a link to a year, the
// navigation does that job — the new page derives openDecade from its own activeYear, so the row
// opens on arrival. Keeping the handler as well would have set those classes for the few
// milliseconds before the page unloaded, which is a no-op that reads as live code.
//
// What this trades away is browsing the nav without leaving the year you are reading. That was
// worth having when a decade did nothing else, but it is not what the pill means any more: it now
// answers "take me to the 1970s" rather than "show me which 1970s years exist".

// Arriving from a cross-link. The browser's own fragment handling cannot do this: the cards do
// not exist when the document is parsed, so by the time renderList creates the element with that
// id the browser has already looked for it, not found it, and given up.
//
// The card is centred rather than put at the top of the viewport because the anchor lands on a
// list, and a row flush against the top edge reads as the first row of the year. Centred, the
// rows above it are visible and its rank number is legible as a position within the year.
//
// The highlight is set on the element rather than left to :target so that it survives renderList
// replacing the innerHTML when the mini player opens and closes, and so it can be styled as a
// fading emphasis rather than a permanent state - :target would keep the card marked for as long
// as the fragment stayed in the address bar.
function focusLinkedAlbum() {
  const id = decodeURIComponent((window.location.hash || '').replace(/^#/, ''));
  if (!id) return;
  const card = document.getElementById(id);
  // A fragment naming an album that is not in this year, or not in the file at all, is ignored
  // rather than corrected: the year requested still renders, which is the more useful failure.
  if (!card) return;
  // Only ever one card marked. On a same-year jump the previous one is still marked, and two
  // highlighted rows says "these two" rather than "this one".
  document.querySelectorAll('.year-card.is-linked-to')
    .forEach(el => el.classList.remove('is-linked-to'));
  // Removing and re-adding a class in the same frame does not restart a CSS animation - the
  // browser never sees the element without it. Reading offsetWidth forces the reflow that makes
  // the removal take effect, so a second jump to the same card animates again instead of sitting
  // there already faded out.
  void card.offsetWidth;
  card.classList.add('is-linked-to');
  // The CSS drops the fade under prefers-reduced-motion; the scroll has to be asked separately,
  // since a smooth scroll the length of a year's list is the larger of the two movements.
  const still = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  card.scrollIntoView({ block: 'center', behavior: still ? 'auto' : 'smooth' });
}

// A link to an album in the year already on screen changes the fragment and nothing else - no
// navigation, no reload, so nothing above this line runs a second time. Without this the one
// same-year link in the data (1979 Anonym naming This Heat, also 1979) would jump with the
// browser's own fragment handling and arrive with no highlight and no centring, which looks like
// the link half-worked. Also covers the back button returning to a fragment.
window.addEventListener('hashchange', focusLinkedAlbum);

renderChrome();
renderYearNav();
renderList();
focusLinkedAlbum();
