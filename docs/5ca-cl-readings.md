# Chile 5CA: readings to sign

Drafted by `tools/country_5ca.py` (src/country5ca.py) from the store's watched and tier-1 votes, by rules, never by a model. **Nothing here places anyone until a named person confirms it.**

**How to sign.** Tick `[x]` on each reading you accept as drafted, then run `python3 tools/country_5ca.py --cc cl --sign-from-doc --by NAME` (it sets `status: confirmed` with `confirmed_by` and `confirmed_on` in `config/cl_stance.yaml`). To change a value, edit the stance file first. A reading that needs reading has no box: write `yea:`/`nay:` in the stance file, set `status: draft`, then confirm it.

Counts: 0 proposed, 0 procedural (evidence only), 5 need reading, 0 confirmed.

## Needs reading (no box: write the values first)

- `camara-90141` 2026-09-23 Boletín N° 18584-25 Indicación renovada de la diputada Schneider y los diputados Salinas, Pinilla y Araya, Jai [amendment]: An amendment, an article or one point ('Boletín N° 18584-25 Indicación renovada de la diputada Schneider y los diputados Salinas, Pinilla y Araya, Jaime, para a'): which side is ours depends on its text, which the store 
- `camara-89383` 2026-07-13 Boletín N° 18399-06 Artículo único del proyecto, en los términos propuestos por la Comisión de Gobierno Interi [other]: The kind of vote could not be read from its wording ('Boletín N° 18399-06 Artículo único del proyecto, en los términos propuestos por la Comisión de Gobierno Interior, Nacion'): read the question put, then write yea/nay.
- `camara-89307` 2026-07-07 Boletín N° 16743-04 Indicación renovada, de la diputada Emilia Schneider, que agrega el siguiente número 4 nue [amendment]: An amendment, an article or one point ('Boletín N° 16743-04 Indicación renovada, de la diputada Emilia Schneider, que agrega el siguiente número 4 nuevo al artí'): which side is ours depends on its text, which the store 
- `camara-88946` 2026-05-20 Boletín N° 18216-05 Renovación de una indicación de la diputada Ana María Gazmuri para agregar un artículo nue [amendment]: An amendment, an article or one point ('Boletín N° 18216-05 Renovación de una indicación de la diputada Ana María Gazmuri para agregar un artículo nuevo permane'): which side is ours depends on its text, which the store 
- `senado-16709-f5b00dd9443e` 2025-01-29 Proyecto de ley, iniciado en Moción de los Honorables Senadores señoras Núñez y Órdenes, y señores Castro Gonz [final]: A vote on the whole text or the motion itself, but no bill direction is on file for 16709-11: CitizenGO's position on 'Modifica la ley N° 20.418, que fija normas sobre información, orientación y prestaciones en materia d

## Bill directions on file (inputs to the drafts; they place nobody)

- `7736-11` against: Euthanasia, the matrix bill: 'asistencia médica con el objeto de acelerar la muerte' (draft)
- `9644-11` against: Euthanasia, merged into 7736-11 (draft)
- `11745-11` against: Euthanasia, merged into 7736-11 (draft)
- `11577-11` against: Euthanasia, merged into 7736-11; its title is a patients' rights amendment (draft)
- `17571-18` with: Protects minors from irreversible medical or legal interventions (gender transition) (draft)
- `17586-18` with: Protects minors from irreversible medical or legal interventions (gender transition) (draft)
- `17636-18` with: Bans practices, treatments or surgery against children's healthy development (gender transition) (draft)
- `17798-11` with: Bans surgical or hormonal sex-change interventions under 18 (draft)
- `17564-11` against: Interrupción voluntaria del embarazo: elective abortion within a time limit (draft)
- `17494-07` with: Constitutional protection of the life of the human being in gestation (draft)
- `17728-11` with: Removes the rape ground of the three-grounds law (Ley 21.030) (draft)
- `17930-04` with: Regulates the parents' preferential right and duty to educate their children (draft)
- `17967-07` with: Creates a constitutional action protecting freedom of conscience, religion and worship (draft)

