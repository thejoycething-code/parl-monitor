# Chamber layer samples (10 October 2026)

Sample editions for parity layer 5 (debates, speeches and questions;
`src/chamber_store.py`, `tools/<cc>_chamber.py`). Each was rendered by the
real framework (`src/country_edition.py`, marked SAMPLE, never sent) from a
scratch store holding only this layer's tables, collected live on 10 October
2026, so they show no votes, bills or week ahead: the real editions carry
those as well. Windows: the Netherlands, France and Poland the week to 9
October; Switzerland the last week of the Herbstsession (to 2 October);
Austria 22 September to 9 October; Belgium 30 September to 9 October;
Portugal from 9 September and Brazil from 31 August (few questions a week).

Hand-checked against the sources, item by item. What is right, and what is
not yet:

- **Speeches are matched in their own words.** Every excerpt now shows the
  term that put the speech there (the excerpt is centred on it). No speech
  is on our ground for its debate's title alone, and no sitting is matched
  whole: the French bill on sexual and sexist violence (68 speeches) and the
  Swiss abortion initiative 25.455 (7) are there because of what each
  speaker said.
- **The chair is never stored**, nor the benches' interjections in Austria.
  Speakers are as printed; the party is the source's own (NL fractie, CH
  group and canton, AT club, BE group) or, for France, the group printed
  beside the name on first mention (the French weekly's roster fills the
  rest on the Mini). Poland's sample shows "deputy 332" because the scratch
  store held no pl_members; on the Mini the weekly's roster names them.
- **Switzerland**: 'IVG' cited as the disability-insurance law is masked
  (ten false abortion hits on the inclusion bill 26.029 before the fix);
  each speech is read with its own language's list.
- **Belgium**: a "Site under maintenance" page answered 200 for three
  sittings on 10 October; it is a gap and never a sitting read.
- **False friends in the taxonomies, for Chris** (the lists are generated
  files, not changed here; each wants a guard in its keyword-taxonomy doc):
  - taxonomy-fr `séparatisme` (area 8) matched "séparatisme territorial et social" in the
    debate on low-emission zones (5 speeches, France).
  - taxonomy-pt `fim de vida` (area 2) matched "Veículos em Fim de Vida"
    (end-of-life vehicles), a request to the environment minister (Portugal).
  - taxonomy-nl `transitie` (area 3, guarded with kinderen/jongeren) matched
    the debate on passend onderwijs (30 September), where the "transitie" is
    to inclusive schooling and the children are pupils (Netherlands).
  - All three are fixed at the source in the noise round of 10 October
    2026 (taxonomy-fr, -pt and -nl v0.2): `séparatisme` needs religious or
    laïcité company, `fim de vida` is vetoed by vehicles and waste, and
    `transitie` needs gender or medical company. The samples above are left
    as rendered.
  - Migration (area 11) is most of the Dutch, Austrian and Swiss matches; it
    is stored and, as everywhere, not shown.
- **Questions** are one entry each, with the asker, their group, the
  minister and whether an answer is recorded (Brazil's register does not
  say, so nothing is claimed). No answer text is ever shown.
