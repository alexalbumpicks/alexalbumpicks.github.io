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

// A bare query string keeps the visitor on this page whatever it is named or wherever it is
// mounted. The editor hard-codes its own filename here; the reader has no reason to.
function yearLink(year) {
  return `?year=${encodeURIComponent(year)}`;
}

// Years that are still being filled in, dimmed in the nav so the thin ones do not read as
// finished. Kept as a predicate rather than a list of years because the pre-1967 stretch is a
// contiguous range: adding 1958 to the data should not also require editing this file.
// Deliberately presentational - these years sort, render and play like any other.
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

const years = [...new Set(allAlbums().map(({ entry }) => entry.year))].sort((a, b) => b - a);
const params = new URLSearchParams(window.location.search);
const requestedYear = Number.parseInt(params.get('year'), 10);
// An unknown ?year= is honoured rather than corrected, so a shared link to a year that has
// since been emptied lands on the empty state instead of silently showing a different year.
const activeYear = Number.isFinite(requestedYear) ? requestedYear : (years[0] || new Date().getFullYear());

let activePlayerIndex = null;

function renderYearNav() {
  const navYears = years.includes(activeYear)
    ? years
    : [activeYear, ...years].sort((a, b) => b - a);
  document.getElementById('year-nav').innerHTML = navYears
    .map(year => {
      const cls = `year-pill${year === activeYear ? ' is-active' : ''}${isProvisional(year) ? ' is-provisional' : ''}`;
      // The title carries the reason in words. Dimming is only legible by comparison, so on
      // its own it says "different" without ever saying what is different about it.
      const why = isProvisional(year) ? ' title="Still being filled in"' : '';
      return `<a class="${cls}" href="${yearLink(year)}"${why}>${year}</a>`;
    })
    .join('');
}

function renderList() {
  const list = document.getElementById('year-list');
  const yearAlbums = sortedYearAlbums(activeYear);

  document.getElementById('year-title').textContent = `Best Albums of ${activeYear}`;
  // The year blurb stays hidden here for the same reason as on the editor: the list is the
  // argument, and a paragraph above the number one only competes with it.
  document.getElementById('year-dek').hidden = true;
  // Said in words on the year itself, not just implied by a dim pill in the nav - somebody who
  // arrives on a shared link to 1962 never sees the nav state that would have explained it.
  document.getElementById('ranking-note').textContent =
    'Albums are ordered by hand, best first. Years I have not gone through yet fall back to rating order.'
    + (isProvisional(activeYear) ? ' This year is still being filled in.' : '');

  if (!yearAlbums.length) {
    list.innerHTML = `
      <section class="year-empty">
        <h2>No albums for ${esc(activeYear)}</h2>
        <p>Nothing ranked for this year yet.</p>
      </section>
    `;
    return;
  }

  list.innerHTML = yearAlbums.map(({ entry }, i) => {
    const tags = (entry.tags || []).map(tag => `<span class="year-tag">${esc(tag)}</span>`).join('');
    const audio = entry.audio
      ? `<button class="year-action" type="button" data-listen="${i}" aria-expanded="${activePlayerIndex === i ? 'true' : 'false'}">${activePlayerIndex === i ? 'Hide player' : 'Listen'}</button>`
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

renderYearNav();
renderList();
