# Parliamentary Monitor: Portuguese (shared) keyword taxonomy

**Version 0.2 | 10 October 2026 | Owner: Christopher | Status: APPROVED AS DRAFTED (X4), NOT YET READ BY A NATIVE READER**

## Purpose

One Portuguese list for Brazil and Portugal (X2). Spelling variants and statutes that belong to one country are tagged `[only: br]` or `[only: pt]`; each collector loads the file with its own country code.

**This file is the master.** `config/taxonomy-pt.yaml` is generated from it:
edit here, then run `python3 tools/generate_taxonomy.py --lang pt`. The suite
fails if the two drift (`tests/test_taxonomy_sync.py`).

## How it was made

Merged on 10 October 2026 from the proposed lists in the scope documents of Brazil, Portugal (`docs/<country>-scope.md`), which Chris approved as drafted (X4) with the scope calls in `docs/country-decisions-2026-10-10.md`.
A term one country proposed as its own (a statute number, a national body, a national spelling) carries `[only: <code>]` and matches only for that country's collector; every other term is shared. Where countries proposed one term at different tiers, the shared copy takes the lower tier and the countries that asked for tier 1 get a tagged tier-1 copy, so no country is promoted past its own list. A term that one country guarded and another left bare is shared only in its guarded form; the bare copy is tagged for the countries that proposed it bare.
Accents fold for matching (X3), so accented and unaccented spellings are one term.

Scope calls applied while merging:

- Brazil X12: contraception already area 1 tier 2 (pílula do dia seguinte, contracepção de emergência); no change
- Brazil X11: Convenção de Belém do Pará kept in area 5 tier 2 (gender-violence convention)
- Brazil X13: no antisemitism terms in the Brazilian list
- Brazil BR2: misoginia moved from area 5 tier 2 to area 7 tier 2
- Brazil BR1: list approved as drafted
- Brazil Slash and bracket shorthand in the doc expanded into separate terms (e.g. regulação/regulamentação das redes into four terms, licença-paternidade in both spellings)
- Brazil Spelling variants Brazilian-only (gênero, contracepção, planejamento, celular, banheiro, vestiário, esporte, doador, etc.) marked country-only per the brief; terms that contain gênero are marked on the term where it is the distinguishing word
- Portugal X12: moved pílula do dia seguinte and contraceção de emergência from area 1 tier 1 to area 1 tier 2; contraceção (PT spelling) already tier 2
- Portugal X13: removed antissemitismo from area 8 tier 2
- Portugal X11: Convenção de Istambul kept in area 5 tier 2; no femicide term in the Portuguese list
- Portugal X2: shared taxonomy-pt, PT spelling variants and PT-only statutes tagged in only
- Portugal PT2 family policy (area 9), PT3 school choice (area 6), PT4 face covering (area 8), PT5 Church abuse (area 8): all kept as drafted
- Portugal Bracketed guards converted: dador* [with: órgãos, tecidos, transplant*] [without: dador de sangue]
- Brazil BR3 and BR4 (Chris approved the terms on 10 October 2026): gambling and betting (area 14) and drug decriminalisation (area 15) added as Brazil-only areas; every term in them carries [only: br], so Portugal's collector loads both areas empty and matches exactly what it matched before

Noise round (v0.2, 10 October 2026, approved by Chris).

- `"fim de vida"` (area 2, tier 2) is vetoed by vehicle and waste company (`veículo*`, `automóve*`, `resíduo*`, VFV). Measured on the Portuguese and Brazilian scoping and chamber-layer stores: one item lost, the request on the "Sistema Integrado de Gestão de Veículos em Fim de Vida" (XVII/2/R/11), noise; over the Assembleia's initiatives of the XV, XVI and XVII legislatures the one title with the phrase (the Rede Nacional de Cuidados Paliativos bill) still matches. Brazil unchanged.

## Issue areas

### 1. Abortion {#1_abortion}

- **Tier 1:** aborto*; abortamento*; abortiv*; nascituro*; "interrupção voluntária da gravidez"; "interrupção da gravidez"; "interrupção da gestação"; "interrupção de gravidez"; "interrupção de gestação"; "desde a concepção" [only: br]; "assistolia fetal"; mifepristona; misoprostol; Cytotec [only: br]; "ADPF 442" [only: br]; "bolsa estupro" [only: br]; anencefal*; "direitos sexuais e reprodutivos" [only: pt]; "interrupção voluntária de gravidez"; IVG [only: pt]; "Lei n.º 16/2007" [only: pt]; "Lei 16/2007" [only: pt]; "vida intrauterina" [only: pt]; "vida pré-natal"; "pílula abortiva"; "objeção de consciência"; "objecção de consciência" [only: pt]; objetor*; objector* [only: pt]
- **Tier 2:** "direitos reprodutivos"; "saúde reprodutiva"; "direitos sexuais e reprodutivos"; "vida intrauterina" [with: proteção, direito]; feto*; fetal; nidação; "pílula do dia seguinte"; "contracepção de emergência" [only: br]; "gestação decorrente de estupro"; "gravidez decorrente de estupro"; "Dia do Nascituro" [only: br]; "contraceção de emergência" [only: pt]; "saúde sexual e reprodutiva"; contraceção [only: pt]; "diagnóstico pré-natal"; "planeamento familiar" [only: pt]; grávida*; gestante*
- **Notes:** Brazil: Measured in the Câmara record; ADPF 442 is the STF case on decriminalisation to 12 weeks, 'bolsa estupro' the campaigners' name for the Estatuto do Nascituro payment. Portugal: Drafted and measured on the XVII dump; Lei 16/2007 is the 2007 referendum law, pre-1990 spellings kept for older texts.

### 2. Assisted dying and end of life {#2_assisted_dying}

- **Tier 1:** eutanásia*; "suicídio assistido"; "morte assistida"; "morte digna"; distanásia [only: br]; ortotanásia [only: br]; "morte medicamente assistida" [only: pt]; "Lei n.º 22/2023" [only: pt]; eutanásia; "suicídio medicamente assistido"; "antecipação da morte"
- **Tier 2:** distanásia; "cuidados paliativos"; "diretivas antecipadas de vontade"; "testamento vital"; "terminalidade da vida"; "prevenção do suicídio"; "fim de vida" [without: veículo*, automóve*, resíduo*, VFV]; "directivas antecipadas de vontade" [only: pt]; "obstinação terapêutica"
- **Notes:** Brazil: Draft list; ortotanásia is the Brazilian addition to the shared vocabulary. Portugal: 'Cuidados paliativos' is twelve of the XVII's twelve area-2 matches (palliative funding); drop it if it floods.

### 3. Gender medicine and children {#3_gender_medicine_children}

- **Tier 1:** "bloqueador* de puberdade"; "bloqueador* puberais"; "bloqueio puberal"; "bloqueio da puberdade"; "hormonização cruzada"; "terapia hormonal cruzada"; "redesignação sexual"; "redesignação de sexo"; "cirurgia* de transgenitalização" [only: br]; transgenitalização [only: br]; "disforia de gênero" [only: br, pt]; "incongruência de gênero" [only: br, pt]; "crianças trans"; "crianças transgênero" [only: br]; "adolescentes trans"; "processo transexualizador" [only: br]; "afirmação de gênero" [only: br, pt]; detransição; destransição; "bloqueadores da puberdade"; "bloqueadores hormonais" [only: pt]; "transição de género" [only: pt]; "cirurgia de redesignação"; "reatribuição de sexo"
- **Tier 2:** hormonização [with: criança*, adolescente*, menor*]; "transição de gênero" [with: criança*, adolescente*, menor*] [only: br]; "bloqueadores hormonais" [with: criança*, adolescente*, menor*]; "tratamentos hormonais" [with: menores, crianças, jovens, género] [only: pt]; "identidade de género" [with: menores, crianças, escolas, jovens] [only: pt]
- **Notes:** Brazil: Tier 2 terms guarded to criança/adolescente/menor; the 2025 CFM resolution on minors needs its number added once confirmed. Portugal: Tier 2 guarded to minors and schools.

### 4. Conversion practices {#4_conversion_practices}

- **Tier 1:** "terapia* de conversão"; "terapia* de reversão"; "cura gay" [only: br]; "reorientação sexual"; "reversão sexual"; "conversão sexual"; "práticas de conversão"; "terapias de conversão"; "terapia de conversão"; "Lei n.º 15/2024" [only: pt]
- **Tier 2:** "orientação sexual" [with: terapia, tratamento, psicólogo*, reversão]
- **Notes:** Brazil: Draft list; 'cura gay' is the Brazilian campaign label. Portugal: Lei 15/2024 is the Portuguese conversion-practices statute.

### 5. Sex-based rights and single-sex spaces {#5_sex_based_rights}

- **Tier 1:** "ideologia de gênero" [only: br, pt]; "identidade de gênero" [only: br, pt]; "linguagem neutra"; "linguagem não binária"; "pronome neutro"; "nome social" [only: br]; "sexo biológico"; transgênero* [only: br, pt]; transexua*; travesti* [only: br]; "mulher* trans"; "atleta* trans"; LGBT*; "não binári*"; homotransfobia; transfobia; LGBTfobia; homofobia; "autodeterminação da identidade de género" [only: pt]; "autodeterminação de género" [only: pt]; "expressão de género" [only: pt]; "características sexuais"; "Lei n.º 38/2018" [only: pt]; "Lei 38/2018" [only: pt]; "mudança de sexo"; "menção do sexo" [only: pt]; "mudança da menção do sexo" [only: pt]; "pessoas trans"; "linguagem inclusiva"
- **Tier 2:** banheiro* [with: sexo, gênero, trans, unissex, biológico] [only: br]; vestiário* [with: sexo, gênero, trans, biológico] [only: br]; "orientação sexual"; "diversidade sexual"; "igualdade de gênero" [only: br]; "perspectiva de gênero" [only: br]; "equidade de gênero" [only: br]; "questões de gênero" [only: br]; "esporte* feminino*" [with: sexo, trans, biológico, gênero] [only: br]; "Convenção de Belém do Pará" [only: br]; "Convenção de Istambul"; "igualdade de género" [with: "identidade de género", trans*, escola*] [only: pt]; "casas de banho" [only: pt]; balneários [only: pt]; "desporto feminino" [only: pt]
- **Notes:** Brazil: 'Ideologia de gênero' is the most used phrase on our side of the Brazilian debate; LGBT* is case-sensitive. Portugal: Lei 38/2018 is the self-determination law; igualdade de género guarded to identity, trans, school.

### 6. Parental rights and education {#6_parental_rights_education}

- **Tier 1:** "Escola sem Partido" [only: br]; "educação domiciliar" [only: br]; "ensino domiciliar" [only: br]; homeschooling; doutrinação; "educação sexual"; "direito* dos pais"; "direito das famílias na educação"; adultização [only: br]; "ECA Digital" [only: br]; "erotização infantil"; "erotização de crianças"; "sexualização infantil"; "sexualização de crianças"; "Cidadania e Desenvolvimento" [only: pt]; "Estratégia Nacional de Educação para a Cidadania" [only: pt]; "educação para a cidadania"; "Lei n.º 60/2009" [only: pt]; "educação para a saúde"; "ensino doméstico" [only: pt]; "ensino individual" [only: pt]; "liberdade de educação"; "liberdade de ensino"; "direito dos pais"; "direitos dos pais"; "neutralidade ideológica"
- **Tier 2:** "redes sociais" [with: criança*, adolescente*, menor*]; celular* [with: escola*, "sala de aula", ensino] [only: br]; smartphone* [with: escola*, "sala de aula"]; "Base Nacional Comum Curricular" [with: gênero, sexual, sexualidade] [only: br]; "Plano Nacional de Educação" [with: gênero, sexual, sexualidade] [only: br]; "poder familiar" [only: br]; "educação para a sexualidade"; "verificação de idade"; "ambiente digital" [with: criança*, adolescente*]; "responsabilidades parentais" [only: pt]; "ensino particular e cooperativo" [only: pt]; "contratos de associação" [only: pt]; telemóve* [with: escola, aluno, ensino] [only: pt]; "redes sociais" [with: menores, crianças, jovens, idade]; "controlo parental" [only: pt]; "manuais escolares" [only: pt]
- **Notes:** Brazil: 'Adultização' became a political term in August 2025 and carries 76 bills since; ECA Digital is Lei 15.211/2025. Portugal: Ten of the XVII's seventeen area-6 matches are private and cooperative school funding; school choice kept in by PT3.

### 7. Free speech, privacy and civil liberties {#7_free_speech_online_safety}

- **Name:** Free speech, privacy and civil liberties
- **Tier 1:** "liberdade de expressão"; "PL das Fake News" [only: br]; "Lei das Fake News" [only: br]; "regulação das redes"; "regulamentação das redes"; "regulação das plataformas"; "regulamentação das plataformas"; censura; "crime de opinião"; "delito de opinião"; desinformação [only: pt]; "discurso de ódio" [only: pt]; "incitamento ao ódio"; "crimes de ódio"; "verificação de idade"; pornografia; "Carta Portuguesa de Direitos Humanos na Era Digital" [only: pt]; "Regulamento dos Serviços Digitais"
- **Tier 2:** "Marco Civil da Internet" [only: br]; "fake news"; desinformação; "discurso de ódio"; "moderação de conteúdo"; "plataformas digitais" [with: conteúdo*, moderação, remoção, criança*, adolescente*, "redes sociais", desinformação]; "remoção de conteúdo"; "liberdade de imprensa"; "liberdade de manifestação"; "notícias fraudulentas"; misoginia; "conteúdos ilegais"
- **Notes:** Brazil: Marco Civil is tier 2 because every online-fraud bill amends it (112 hits); misoginia moved here by BR2. Portugal: Inteligência artificial and plataformas digitais dropped after measuring: forest fires, delivery riders, an AI model.

### 8. Freedom of religion or belief {#8_freedom_of_religion}

- **Tier 1:** "liberdade religiosa"; "liberdade de culto"; "liberdade de crença"; "liberdade de consciência e de crença"; "intolerância religiosa"; "perseguição religiosa" [only: br]; "perseguição a cristãos"; "cristãos perseguidos"; "objeção de consciência"; "ensino religioso"; "templos de qualquer culto"; "cultos religiosos"; laicidade [only: pt]; "Lei da Liberdade Religiosa" [only: pt]; "Lei n.º 16/2001" [only: pt]; Concordata [only: pt]; "Igreja Católica"; "confissões religiosas"; "comunidades religiosas"; "assistência religiosa"; "Educação Moral e Religiosa" [only: pt]; EMRC [only: pt]; "símbolos religiosos"; "ocultação do rosto"; burca*; burqa*; niqab*; "abusos sexuais na Igreja"; "liberdade de consciência"; "lugares de culto"
- **Tier 2:** "perseguição religiosa"; "imunidade tributária" [with: templo*, igreja*, religios*, culto]; capelania*; capelão; Bíblia; "estado laico"; laicidade; "organizações religiosas"; "entidades religiosas"; igreja* [with: fechamento, liberdade, proibição, perseguição]; "racismo religioso"; "religiões de matriz africana"; religios*; cristãos; islamofobia
- **Notes:** Brazil: Draft list. Portugal: Face-covering law (July 2026) in by PT4; Church abuse compensation in by PT5.

### 9. Marriage and family {#9_marriage_family}

- **Tier 1:** "casamento homoafetivo" [only: br]; "união homoafetiva" [only: br]; "uniões homoafetivas" [only: br]; "casamento entre pessoas do mesmo sexo"; "casamento civil entre pessoas do mesmo sexo"; "Estatuto da Família" [only: br]; "entidade familiar"; "união poliafetiva" [only: br]; poliamor; "casamento infantil"; "casamento de menores"; "adoção homoafetiva" [only: br]; "adoção por casais do mesmo sexo"; coadoção [only: pt]; "casamento civil"; "união de facto" [only: pt]; "uniões de facto" [only: pt]; divórcio
- **Tier 2:** "união estável" [with: homoafetiv*, "mesmo sexo", poliafetiv*] [only: br]; licença-paternidade [only: br]; "licença paternidade" [only: br]; licença-maternidade [only: br]; "licença maternidade" [only: br]; "planejamento familiar" [only: br]; "família natural"; multiparentalidade; "parentalidade socioafetiva"; natalidade; parentalidade; "apoio à família"; "famílias numerosas"; "licença parental"; "conciliação da vida familiar"; "quociente familiar" [only: pt]
- **Notes:** Brazil: Draft list. Portugal: Tier 2 is family policy, 20 of the XVII's 21 area-9 matches; kept in by PT2.

### 10. Surrogacy and embryology {#10_surrogacy_embryology}

- **Tier 1:** "barriga de aluguel" [only: br]; "barriga solidária"; "gestação de substituição"; "útero de substituição"; "cessão temporária de útero"; "maternidade de substituição"; "reprodução assistida" [only: br]; "reprodução humana assistida" [only: br]; "células-tronco embrionárias" [only: br]; "clonagem humana"; "embriões humanos"; "embriões excedentários"; embrião [only: pt]; embriões [only: pt]; "doação de gâmetas"; "barrigas de aluguer" [only: pt]; "barriga de aluguer" [only: pt]; "procriação medicamente assistida"; PMA [only: pt]; "Lei n.º 32/2006" [only: pt]; CNPMA [only: pt]; "inseminação post mortem"; gâmetas; "dação de gâmetas" [only: pt]
- **Tier 2:** "fertilização in vitro"; "inseminação artificial"; embrião; embriões; "edição genética"; "Lei de Biossegurança" [only: br]; infertilidade; fertilidade; "células estaminais" [only: pt]; clonagem
- **Notes:** Brazil: Draft list. Portugal: Gestação de substituição is the Portuguese legal term.

### 11. Migration {#11_migration}

- **Tier 1:** imigração; imigrante*; migrante*; refugiad*; "Lei de Migração" [only: br]; deportação; asilo [only: pt]; imigrantes; estrangeiros; "Lei de Estrangeiros" [only: pt]; "lei da nacionalidade" [only: pt]; AIMA [only: pt]; "manifestação de interesse" [only: pt]; "reagrupamento familiar" [only: pt]
- **Tier 2:** asilo; apátrida*; "acolhida humanitária"; "visto humanitário"; nacionalidade; migrantes; refugiados
- **Notes:** Brazil: Collated, never campaigned. Portugal: 42 of the XVII's 126 matches are migration; hidden on every surface.

### 12. Prostitution, trafficking and sexual exploitation {#12_prostitution}

- **Name:** Prostitution, trafficking and sexual exploitation
- **Tier 1:** prostituição; "tráfico de pessoas"; "tráfico humano"; "exploração sexual"; pornografia*; pornográfic*; "casa de prostituição"; "profissionais do sexo"; "trabalho sexual"; "Lei Gabriela Leite" [only: br]; "abuso sexual de crianças" [only: pt]; lenocínio [only: pt]; "tráfico de seres humanos"; "pornografia infantil"; "abuso sexual de menores"; "abusos sexuais de menores"
- **Tier 2:** "abuso sexual infantil"; "abuso sexual de crianças"; "conteúdo sexual"; "turismo sexual"; nudez; deepfake*; "imagens íntimas"; "mutilação genital feminina"; "casamento infantil"; "casamentos forçados"
- **Notes:** Brazil: Draft list; includes pornography and deepfake terms. Portugal: Draft list.

### 13. Organ donation and transplant ethics {#13_organ_donation}

- **Name:** Organ donation and transplant ethics
- **Tier 1:** "doação de órgãos"; "doação presumida"; "doador presumido"; "consentimento presumido"; "tráfico de órgãos"; transplante* [only: pt]; "dádiva de órgãos"; "colheita de órgãos"; "morte cerebral"; RENNDA [only: pt]; dador* [with: órgãos, tecidos, transplant*] [without: "dador de sangue"] [only: pt]
- **Tier 2:** transplante*; "morte encefálica" [only: br]; "doador* de órgãos" [only: br]
- **Notes:** Brazil: Draft list. Portugal: Unguarded 'dador' matched six blood-donor bills and nothing else, hence the guard.

### 14. Gambling and betting {#14_gambling}

- **Name:** Gambling and betting
- **Tier 1:** "jogos de azar" [only: br]; "apostas esportivas" [only: br]; "apostas de quota fixa" [only: br]; bets [only: br]; "Lei das Bets" [only: br]; "Lei 14.790" [only: br]; cassino* [only: br]; "jogo do bicho" [only: br]; "marco regulatório dos jogos" [only: br]; "PL 2234/2022" [only: br]; "PL 442/1991" [only: br]
- **Tier 2:** bingo* [with: legaliz*, autoriz*, explora*] [only: br]; apostas [with: online, esportiv*, digital] [only: br]; "jogo online" [only: br]; ludopatia [only: br]; "jogo patológico" [only: br]; "vício em apostas" [only: br]; "publicidade de apostas" [only: br]
- **Notes:** Brazil: BR3, approved 10 October 2026. Lei 14.790/2023 legalised fixed-odds sports betting; PL 2234/2022 (Senate) and PL 442/1991 (Câmara) are one casino, bingo and jogo do bicho legalisation bill, the Câmara's record 15460 presented in 1991 and renumbered on reaching the Senate (both numbers checked on the Câmara and Senado open data, 9 October 2026). Measured on the Câmara's 2024 bills (5,516 PL, PEC, PLP, PDL, MPV, PRC): 80 match, 78 of them on no other area, mostly bills amending Lei 14.790 or barring Bolsa Família money from betting; in the 2026 scoping store (156 bills, 211 votes) none. Statutes are cited as "Lei nº 14.790", which the bare "Lei 14.790" phrase misses (1 hit); the bills are caught by "apostas de quota fixa" (51) instead.

### 15. Drug decriminalisation {#15_drug_decriminalisation}

- **Tier 1:** "descriminalização das drogas" [only: br]; "descriminalização do porte" [only: br]; "porte de drogas" [only: br]; "porte de maconha" [only: br]; "legalização da maconha" [only: br]; "RE 635659" [only: br]; "PEC 45/2023" [only: br]; "PEC das Drogas" [only: br]; "cultivo de cannabis" [only: br]; "Lei de Drogas" [only: br]; "Lei 11.343" [only: br]
- **Tier 2:** cannabis [only: br]; maconha [only: br]; canabidiol [only: br]; "cannabis medicinal" [only: br]; "PL 399/2015" [only: br]; "drogas ilícitas" [only: br]; "dependência química" [only: br]; "comunidades terapêuticas" [only: br]
- **Notes:** Brazil: BR4, approved 10 October 2026. RE 635659 is the STF case decriminalising small-quantity cannabis possession (2024; not checked, the STF portal refused the request); PEC 45/2023 is Congress's amendment criminalising possession of any amount; PL 399/2015 is the medical-cannabis bill (its ementa: medicines from Cannabis sativa); comunidades terapêuticas (mostly church-run rehab) are tier 2 because their funding is a recurring fight. Numbers checked on the Câmara and Senado open data and Lei 11.343/2006 on the Senado's legislation service, 9 October 2026. Measured on the Câmara's 2024 bills: 27 match, 26 on no other area (Lei 11.343 amendments, cannabis, motions to annul the CNAS and CONANDA resolutions on comunidades terapêuticas); in the 2026 scoping store 2 bills and 2 votes, both on dependência química.

## Global exclusions

The bare words that must never be promoted to a term on their own (advisory prose, not a filter input).

- **Terms:** vida; família; gênero; criança; mulher; saúde; educação; escola; religião; direitos

## Maintenance

Corrections from a native reader come in here, then `python3 tools/generate_taxonomy.py --lang pt`. A new term needs a measurement, written in the area's Notes.
