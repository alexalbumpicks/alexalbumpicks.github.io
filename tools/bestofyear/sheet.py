"""Parse Album Masterlist Lite.xlsx (sheet 'Album Scores') with stdlib only."""
import zipfile, xml.etree.ElementTree as ET, re

XLSX = '/Users/alexziyujiang/Documents/GitHub/indie_rock_timeline/Album Masterlist Lite.xlsx'
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
RNS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def rows():
    z = zipfile.ZipFile(XLSX)
    shared = []
    if 'xl/sharedStrings.xml' in z.namelist():
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')):
            shared.append(''.join(t.text or '' for t in si.iter(NS + 't')))

    wb = ET.fromstring(z.read('xl/workbook.xml'))
    rels = {r.get('Id'): r.get('Target') for r in
            ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    target = None
    for sh in wb.iter(NS + 'sheet'):
        if sh.get('name') == 'Album Scores':
            target = rels[sh.get(RNS + 'id')]
    path = 'xl/' + target.lstrip('/').replace('xl/', '', 1)

    out = []
    for row in ET.fromstring(z.read(path)).iter(NS + 'row'):
        cells = {}
        for c in row.iter(NS + 'c'):
            col = re.match(r'[A-Z]+', c.get('r')).group()
            v = c.find(NS + 'v')
            if c.get('t') == 'inlineStr':
                is_ = c.find(NS + 'is')
                val = ''.join(t.text or '' for t in is_.iter(NS + 't')) if is_ is not None else ''
            elif v is None:
                val = ''
            elif c.get('t') == 's':
                val = shared[int(v.text)]
            else:
                val = v.text
            cells[col] = (val or '').strip()
        out.append(cells)
    return out


def records():
    r = rows()
    hdr = {v: k for k, v in r[0].items() if v}
    recs = []
    for row in r[1:]:
        d = {name: row.get(col, '') for name, col in hdr.items()}
        if d.get('Albums'):
            recs.append(d)
    return recs, list(hdr)


# ---------------------------------------------------------------- corrections
# The spreadsheet has typos, truncations, inconsistent casing, and in one case a
# song title where the album should be. Search APIs need the real names, and these
# are what get written into data.js.
ARTIST_FIX = {
    'Okkrevil River': 'Okkervil River',
    'Jazz Liberatroz': 'Jazz Liberatorz',
    'Queens of the stone age': 'Queens of the Stone Age',
}

TITLE_FIX = {
    # 'Yr.' and the exclamation mark are both part of the real title, and both are how the
    # entry is already spelled on the site - spell it out and the row stops matching itself.
    'Lift your skinny fists ...':          'Lift Yr. Skinny Fists Like Antennas to Heaven!',
    'Rate R':                              'Rated R',
    'Up the Wolves':                       'The Sunset Tree',      # a song on it, not the album
    'Summer of Abaddon':                   'Summer in Abaddon',
    'Piracy Funds Terrorism Mixtape':      'Piracy Funds Terrorism',
    'Speakerboxxx/Love Below':             'Speakerboxxx/The Love Below',
    'Song in A minor':                     'Songs in A Minor',
    'Deathconciousness':                   'Deathconsciousness',
    'And the refinement of their decline': 'And Their Refinement of the Decline',
    'Birth Movie Soundtrack':              'Birth',

    # --- 2010s ---
    # Excel read "4:44" as a time and stored it as a fraction of a day
    # (0.19722... * 24h = 4h44m). The album is Jay-Z's 4:44.
    '0.19722222222222222':                 '4:44',
    'From Row Seat to Earth':              'Front Row Seat to Earth',
    'Hurry up, we are dreaming':           'Hurry Up, We’re Dreaming',
    'when we fall asleep where do we go':  'WHEN WE ALL FALL ASLEEP, WHERE DO WE GO?',
    'A I A II: Alien Observer':            'A I A : Alien Observer',
    'Strange Cacti EP':                    'Strange Cacti',
    'Boygenius EP':                        'boygenius',
    'Born To Die/Paradise':                'Born to Die - The Paradise Edition',
    'Uncut Gems Soundtrack':               'Uncut Gems (Original Motion Picture Soundtrack)',
    'Phantom Thread Movie Soundtrack':     'Phantom Thread (Original Motion Picture Soundtrack)',
    # Apple files Britell's score as "...Score", not "...Soundtrack" - the soundtrack
    # title finds nothing at all.
    'If Beale Street Could Talk':          'If Beale Street Could Talk (Original Motion Picture Score)',
    '1000 Gecs':                           '1000 gecs',
    'Hasta La Raiz':                       'Hasta la Raíz',

    # --- 2020s ---
    # Only genuine wrong-word errors belong here. Casing and diacritics don't:
    # build2020s.title_for takes Apple's spelling whenever it names the same record,
    # so 'Seed of a seed' and 'ORQUIDEAS' correct themselves.
    'The Waves':                    'In Waves',
    'Mashmashana':                  'Mahashmashana',
    'Heatland':                     'Heartmind',
    'Like a Hammer':                'With a Hammer',
    'Ramona Park Break My Heart':   'RAMONA PARK BROKE MY HEART',
    'Chloe and the 20th Century':   'Chloë and the Next 20th Century',
    # Excel read "11:11" as a time, as it did 4:44 in 2017. 0.46597... * 24h = 11h11m.
    '0.46597222222222223':          '11:11',
    'Tortured Poets Department':    'THE TORTURED POETS DEPARTMENT',
    # Apple abbreviates the numeral: 'Women In Music Pt. III'. Spelling it out matches
    # nothing, and 'pt.' is a demoted word, so the sheet's wording has to give way.
    'Women in Music, Part III':     'Women in Music Pt. III',
    'Sin Miedo':                    'Sin Miedo (del Amor y Otros Demonios) ∞',
    # Not a standalone album - LANA is the deluxe reissue of SOS, which is how Apple
    # carries it and the only place the songs exist.
    'LANA':                         'SOS Deluxe: LANA',
    'Challengers Movie Soundtrack': 'Challengers (Original Score)',
    # Contraction vs. the expanded form Apple files it under. Not a casing difference, so
    # title_for can't correct it on its own - nothing matches to take the spelling from.
    "I'm not there anymore":        'I Am Not There Anymore',
    # Apple spells both halves differently: 'Hallelujah' with a j, 'Hell Yeah' as two words.
    'Halleluyah Hellyeah':          'Hallelujah Hell Yeah',
    'Killers of the flower moon soundtrack':
        'Killers of the Flower Moon (Soundtrack from the Apple Original Film)',

    # --- pre-2000 (1969, 1993, 1994, 1997, 1998) ---
    # Dropped articles. Neither can self-correct: title_for can only take Apple's spelling
    # once something has matched, and a missing leading 'The' stops the match happening.
    'Lonesome Crowded West':        'The Lonesome Crowded West',
    'Chicago Transit Authority':    'The Chicago Transit Authority',
    # Sheet gives the short name. Apple carries only the full one, and 'Arthur' is too
    # short to clear the score threshold on a prefix match alone.
    'Arthur':                       'Arthur or the Decline and Fall of the British Empire',
    # Two words wrong and two missing: the record is 'In an Expression of the Inexpressible'.
    'Expression of the inexpressable': 'In an Expression of the Inexpressible',
    # Apple uses the ampersand for the album as well as the band.
    'Crosby, Stills and Nash':      'Crosby, Stills & Nash',
    # Apple spells this one out, the opposite way round from Crosby, Stills & Nash above.
    'Bubble & Scrape':              'Bubble and Scrape',
    # Those two no longer have to be here to *resolve* - score2020s._amp folds '&' and 'and'
    # together now, which is what was really wrong. They stay because they are also what
    # matches the sheet row to the entry already written into bestof-data.js: drop them and
    # build stops recognising its own import and appends a duplicate.
    # 'Extra Painful' is the 2014 expanded reissue. The 1993 record is Painful, and that's
    # the one the entry is filed under.
    'Extra Painful':                'Painful',
    # Apple carries this one twice: 'Gay?' (the 1996 record) and 'Gay (Ep)' (a later reissue
    # with the question mark dropped and EP mis-cased). The sheet's trailing 'EP' scored
    # against the reissue, so the walk took the wrong one and the bowdlerised title with it.
    # Drop the suffix as 'Strange Cacti EP' and 'Boygenius EP' already do; the release is
    # pinned in resolve2020s.APPLE_ID so the match no longer decides which of the two wins.
    'Gay? EP':                      'Gay?',

    # --- the rest of pre-2000 (1954-1999) ---
    # Apple files it under Aimee Mann with its full subtitle. 'Movie Soundtrack' is the
    # sheet's own shorthand and matches nothing, same as the 2010s soundtrack rows above.
    'Magnolia Movie Soundtrack':    'Magnolia (Music from the Motion Picture)',
    # Apple carries the short form of the ninety-word title, not the sheet's opening clause.
    'When the Pawn hits he thinks like a king...': 'When the Pawn...',
    # Plain misspellings and transpositions.
    '20 Funk Jazz Greats':          '20 Jazz Funk Greats',
    'Trans-Europ-Express':          'Trans-Europe Express',
    'Music from the Big Pink':      'Music from Big Pink',
    "St. Peppers' Lonely Hearts Club Band": "Sgt. Pepper's Lonely Hearts Club Band",
    'Pleasures of the Harbour':     'Pleasures of the Harbor',
    'The Times They Are Changing':  "The Times They Are A-Changin'",
    'Parralellograms':              'Parallelograms',
    'Just Another Diamon Day':      'Just Another Diamond Day',
    # Both from the batch Alex added after the sheet had already been imported once, and both
    # a single letter out, so neither matched anything on Apple at all.
    'Boys for Peele':               'Boys for Pele',
    'La Mia Via Violenta':          'La Mia Vita Violenta',
    # Not a misspelling: the row carries the moniker in the album column and the album nowhere.
    # 'Kazu' is what Kazu Makino releases under (ARTIST_FIX handles the 'Kazuo' half), and her
    # only record under it is Adult Baby - which is the 2019 the row is filed at.
    'KAZU':                         'Adult Baby',
    # Warp spell the number out. Not a typo on the sheet's part - just the other way of writing
    # it - but the scorer compares tokens, so '7' and 'Seven' never agree and the catalogue
    # lookup came back empty even though a plain search finds the record first hit.
    'R Plus 7':                     'R Plus Seven',
    # 'Kaleidoscopic' for 'Kaleidoscope' - an extra syllable rather than a stray letter, so the
    # scorer reads it as a different word and the lookup found nothing at all.
    'Kaleidoscopic Dream':          'Kaleidoscope Dream',
    # Same shape as 'R Plus 7' above, one numeral system further out: Madonna styles the sequel
    # 'CONFESSIONS II' and the sheet writes the digit. Neither spelling is wrong, but '2' and
    # 'II' share no tokens, so the catalogue walk over her 165 releases scored every one of them
    # at zero and the row came back with no art and no preview. Search cannot rescue it either -
    # every phrasing of the query returns 'Confessions on a Dance Floor' instead.
    'Confessions 2':                'CONFESSIONS II',

    # --- rows that were already on the site under a different spelling ---
    # None of these are unresolved: every one of them is on bestof-data.js already, put there
    # by an earlier pass or by hand. They are here purely so the sheet row still *recognises*
    # its own entry. Without the mapping the identity check misses, the row reads as new, and
    # the next build appends a second copy - which is exactly how the six duplicates merged at
    # schema v18 (The Replacements, Wipers, Descendents et al) came to exist in the first place.
    'Merriweather Post Pavillion':  'Merriweather Post Pavilion',
    'Dragging a Dead Deer Up the Hill': 'Dragging a Dead Deer Up a Hill',
    'Apologies to Queen Mary':      'Apologies to the Queen Mary',
    'Our Endlessly Numbered Days':  'Our Endless Numbered Days',
    'Who will cut our hair when we are gone?': "Who Will Cut Our Hair When We're Gone?",
    'Lo que va a escandilar es el día': '..Lo Que Va a Encandilar Es El Día',
    'The Disintegration Tapes':     'The Disintegration Loops',
    'The Glow, Part 2':             'The Glow, Pt. 2',
    # Same three-way '&'/'and'/'+' fold as Crosby, Stills & Nash above. G.amp settles it for
    # *resolving*, but the written entry carries Apple's spelling, so the sheet row needs the
    # mapping to find it again.
    # The row that got away: without this the sheet's bare title matched nothing, the row read as
    # new, and the build appended a second copy of a record already on the site - which is exactly
    # what this block exists to stop, and it had already happened by the time anyone looked. The
    # duplicate is retired at schema v48.
    #
    # Unlike every other mapping here, this one does not make the row import cleanly - it makes it
    # *fail loudly*. The sheet files the album at 1978, its ECM release; the site has it at 1976,
    # when it was recorded. So the row now finds its entry and then trips the year-mismatch branch
    # in build2020s, which reports and skips. That is the wanted behaviour: a year disagreement is
    # Alex's call, not the importer's, and the alternative to a printed warning is silently moving
    # the album out of the "Origins" era or silently duplicating it again. Deliberately not in
    # YEAR_FIX, which is only for years the release date proves wrong - 1978 is not wrong.
    'Music for 18 Musicians':       'Reich: Music for 18 Musicians',
    # Same shape, caught while fixing the above, and still unexploded: the site carries the short
    # title and nothing has re-run this year set since, so the row has not had the chance to append
    # its second copy yet. Both halves agree on 1964, so unlike Reich this one will simply match
    # and backfill.
    'Presenting the Fabulous Ronettes featuring Veronica':
        'Presenting the Fabulous Ronettes',
    'Slanted and Enchanted':        'Slanted & Enchanted',
    'Beers, Steers and Queers':     'Beers, Steers + Queers',
    'Architecture And Morality':    'Architecture & Morality',

    # One sheet row, two records released together. There is no combined release to
    # point at, so the entry is titled for the pair and resolved against the first -
    # see APPLE_ID in resolve2020s.py.
    'Piedras 1&2':                  'Piedras 1 & 2',
    'songs/instrumentals':          'songs / instrumentals',
    'KicK i-v':                     'KiCk i-v',
    'Eusexua/Eusexua Afterglow':    'EUSEXUA / EUSEXUA Afterglow',
}

ARTIST_FIX.update({
    'Daniel Lopatim': 'Daniel Lopatin',
    'Beyonce':        'Beyoncé',
    'Rosalia':        'ROSALÍA',
    'Ninos del cerro': 'Niños del Cerro',
    'Sharon van Etten': 'Sharon Van Etten',
    'Hayley Heynderickx': 'Haley Heynderickx',   # one y - nothing matches with two
    '100 Gecs':       '100 gecs',
    'Boygenius':      'boygenius',
})

# --- 2020s ---
# Artist casing is *not* self-correcting the way titles are - whatever is here is what
# gets written - so lower-case and diacritic spellings have to be spelled out.
ARTIST_FIX.update({
    'Charli xcx':          'Charli XCX',
    'Nilufer Yanya':       'Nilüfer Yanya',
    'Touche Amore':        'Touché Amoré',
    'Mickinley Dixon':     'McKinley Dixon',
    'Slowthai':            'slowthai',
    'Alt-J':               'alt-J',
    'Pedro and the Lion':  'Pedro the Lion',
    # Collaborations the sheet writes with a slash or comma. '&' is what Apple uses and
    # what reads correctly on the card.
    'Sam Prekop/John McEntire': 'Sam Prekop & John McEntire',
    'Panda Bear/Sonic Boom':    'Panda Bear & Sonic Boom',
    'billy woods, Kenny Segal':  'billy woods & Kenny Segal',
    'JPEGMAFIA, Danny Brown':    'JPEGMAFIA & Danny Brown',
    # Apple writes the band with an ampersand and a capital T.
    'Elvis Costello and the Imposters': 'Elvis Costello & The Imposters',
    # Sheet typo - the Miami band is Seafoam Walls. XVI is theirs.
    'Seafoam Wells':       'Seafoam Walls',
})

# --- pre-2000 ---
ARTIST_FIX.update({
    'Bjork':                    'Björk',
    'Outkast':                  'OutKast',
    'Crosby, Stills and Nash':  'Crosby, Stills & Nash',
    'Smashing Pumpkins':        'The Smashing Pumpkins',
})

# --- the rest of pre-2000 ---
ARTIST_FIX.update({
    'Descendants':          'Descendents',
    'Scritti Politi':       'Scritti Politti',
    'The Millenium':        'The Millennium',
    'Brook T & The MGs':    "Booker T. & The M.G.'s",
    'Orchestral Manoeuvres In The Dark': 'Orchestral Manoeuvres in the Dark',
    # Bands the sheet writes out as 'and'. resolve2020s._aname now folds that against
    # Apple's ampersand so these resolve either way, but the written credit still comes
    # from this table, and Apple's is the standard spelling.
    'Simon and Garfunkel':          'Simon & Garfunkel',
    'Nick Cave and the Bad Seeds':  'Nick Cave & The Bad Seeds',
    'Richard and Linda Thompson':   'Richard & Linda Thompson',
    'Siouxsie and the Banshees':    'Siouxsie & The Banshees',
    # Singular 'Interest', and the site already spells it that way - see the block of
    # already-on-the-site mappings in TITLE_FIX for why that matters.
    'Newfound interests in Connecticut': 'Newfound Interest in Connecticut',
    # The Blonde Redhead singer records under the bare moniker 'Kazu', which is also what the
    # sheet put in the *album* column - see TITLE_FIX. 'Kazuo' is a different name entirely.
    'Kazuo Makino':                 'Kazu',
})

# A few rows have the album and the act in the wrong columns, or name the artist in
# both. Those can't be repaired by the single-column tables above, so they're keyed
# on the (Act, Albums) pair exactly as the sheet spells it.
PAIR_FIX = {
    # Artist and album swapped: Candy Claws is the band.
    ('Ceres and Calypso in Deep Time', 'Candy Claws'):
        ('Ceres & Calypso in the Deep Time', 'Candy Claws'),
    # Blake Mills has no self-titled record; his 2010 debut is Break Mirrors.
    ('Blake Mills', 'Blake Mills'): ('Break Mirrors', 'Blake Mills'),
    # Swapped again: Sparks is the band, Kimono My House the 1974 album.
    ('Kimono My House', 'Sparks'): ('Kimono My House', 'Sparks'),
    # Swapped *and* misremembered: the band is the Cleaners from Venus, not 'from the
    # Mars', and Midnight Cleaners is the record.
    ('Midnight Cleaners', 'Cleaners from the Mars'):
        ('Midnight Cleaners', 'The Cleaners from Venus'),
}


# Rows filed under the wrong year. Only outright errors go here, confirmed against the
# release date (tools/bestofyear/yearcheck.py) - not records simply heard a year late.
# Animal Collective put out nothing in 2011; Centipede Hz is September 2012.
YEAR_FIX = {
    ('Animal Collective', 'Centipede Hz'): 2012,
    # Virgin is 2025-06-27. Filed under 2024 in the sheet, but the import stops at 2024,
    # so correcting the year is also what keeps it out - which is right: it belongs to a
    # year Alex says he didn't log properly.
    ('Lorde', 'Virgin'): 2025,
}


def fixed(rec):
    """(title, artist) with sheet errors corrected."""
    pair = PAIR_FIX.get((rec['Act'], rec['Albums']))
    if pair:
        return pair
    return (TITLE_FIX.get(rec['Albums'], rec['Albums']),
            ARTIST_FIX.get(rec['Act'], rec['Act']))


def sheet_year(rec):
    """The year as typed in the sheet. Cache keys are built from this, so a year
    correction doesn't orphan an already-resolved record."""
    return int(float(rec['Year']))


def fixed_year(rec):
    """The year the album actually belongs to."""
    return YEAR_FIX.get((rec['Act'], rec['Albums']), sheet_year(rec))
