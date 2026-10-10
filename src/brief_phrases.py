"""The campaigner-facing sentences of the new countries' campaign briefs, per
language (src/country_briefs.py).

Only the CONTENT of a brief's cells is here. The cell labels stay the RF4
template's own (English: they are the sheet's fixed row labels), the header
values stay English (they are the Asana form's dropdowns, and the Campaign
Name is English by rulebook cell 1), and the Builder tab stays English (it is
the builder's notes to Chris). Facts quoted from the record (titles, stages,
tallies, party names) stay in the source's own words.

Written by Claude on 10 October 2026, without a native speaker's read (the
X4 precedent for term lists). Every language holds the same keys as English;
tests/test_country_briefs.py holds them together. No em dashes.
"""

from __future__ import annotations

EN = {
    "banner_nr": "NOT READY: awaiting sign-off.",
    "nr_dir": "CitizenGO's position on this bill has not been confirmed by a named person yet.",
    "nr_dir_none": "No position of CitizenGO's on this bill is on file yet.",
    "nr_reads": "Readings of its votes awaiting confirmation: {n}.",
    "nr_tail": "Do not launch, target or recommend anything from this draft until they are confirmed.",
    "banner_ready": "READY: CitizenGO's position on this bill and every reading of its votes have been "
                    "confirmed ({who}).",
    "generated": "Draft generated on {date} from the parliamentary record. The facts come from the "
                 "record; [CAMPAIGNER: ...] marks what a campaigner writes. No AI model wrote any of it.",
    "ph": "[CAMPAIGNER: {0}]",
    "ph_sponsor": "who brought it",
    "ph_stage": "the current stage",
    "ph_next": "the next key date (the record publishes none yet)",
    "ph_why": "why it matters: what changes in law or practice",
    "ph_history": "earlier CitizenGO campaigns on this issue, with signatures and links",
    "ph_routes": "the realistic routes to victory, in order",
    "ph_ask": "the ask, once CitizenGO's position on this bill is confirmed",
    "ph_story": "the storytelling line, once CitizenGO's position on this bill is confirmed",
    "ph_villain": "the villain",
    "ph_lead": "the lead sentence: if we <action>, <target> will <behaviour>, because <pressure point>",
    "ph_whip": "free vote or whipped, and by whom",
    "ph_members_seats": "our members in each constituency, from the postcode data",
    "ph_injustice": "5 to 10 injustices, each sourced: who is harmed, who is doing it, what they lose",
    "ph_arguments": "5 to 10 sourced arguments, then the opponents' top three claims with our answers",
    "ph_urgency": "why act now: the record publishes no date, and no deadline may be invented",
    "ph_bad": "the bad outcome: 60 to 120 words of concrete scenes, then two one-line alternates",
    "ph_good": "the good outcome: 60 to 120 words, then two one-line alternates",
    "ph_tim": "up to 10 related petitions from Bluebook (12 to 24 months ago, same list)",
    "ph_news": "a news report, in the list's language",
    "ph_evidence": "the study or report behind the strongest argument",
    "ph_minister": "if this is a government bill: the responsible minister, named and checked "
                   "against an official source",
    "ph_overlay": "overlay text for Canva, at most six words",
    "ph_rf1": "3 to 5 comparable campaigns from Bluebook, people and money against the list median",
    "ph_rf2": "3 to 5 allies and how this campaign helps them",
    "ph_rf3": "3 to 5 named opponents and how this campaign costs them, sourced",
    "ph_worth": "one sourced line on what the win is worth beyond this campaign",
    "ph_purpose": "no decision date in the record: confirm the purpose",
    "bg_what": "What: {title}.",
    "bg_who": "Who: {sponsor}. The decision lies with the {chamber}.",
    "bg_stage": "Where it stands: {stage} (last recorded event: {date}).",
    "bg_next": "What's next: {next}",
    "bg_next_agenda": "on the agenda of the {chamber} on {date}.",
    "bg_why": "Why it matters: {why}",
    "path_head": "Path to victory:",
    "path_wait": "the vote count awaits the sign-off of CitizenGO's readings; nobody is placed yet.",
    "fs_what": "What",
    "fs_who": "Who",
    "fs_stage": "Stage",
    "fs_next": "Next date",
    "fs_5ca": "5CA summary",
    "fs_history": "Our history",
    "fs_none": "none published",
    "type_opp": "Opportunity: the default; nothing on the record points to Obligatory or Survival.",
    "mp_pi": "a named deciding body and a key date in the record.",
    "launch": "{date} (the earliest: submission plus three working days; weekends counted, "
              "public holidays not checked)",
    "deliv_key": "{date} (two working days before {key})",
    "deliv_est": "{date} (estimate: launch plus 21 days; the record publishes no key date)",
    "method": "Method",
    "m1": "emails to the {members} during the campaign, one per signature",
    "m2": "on the delivery date, each member receives the number of signatures from their own "
          "constituency",
    "m3": "a photographed handover at the {chamber} and a PDF of the total for every member",
    "off_handover": "**Handover.** A photographed delivery of the signatures at the {chamber} on "
                    "{date}. Cost: €. Owner: Media Campaigner.",
    "off_letters": "**Constituency letters.** Supporters write to their own {members} in the week "
                   "before {date}. Cost: €. Owner: Media Campaigner.",
    "off_press": "**Press conference.** With allied experts on the day of the handover, in front of "
                 "the {chamber}. Cost: €€. Owner: Media Campaigner.",
    "off_ads": "**Geo-targeted ads.** In the constituencies of the undecided members, in the last "
               "two weeks before {date}. Cost: €€. Owner: Media Campaigner.",
    "off_vigil": "**Vigil.** Near the {chamber} on the eve of {date}, where it fits the list. "
                 "Cost: €. Owner: Media Campaigner.",
    "addr_all": "All members of the {chamber} ({members}).",
    "addr_split": "Option: split into separate petitions by 5CA segment: undecided (0/+/-): {p}; "
                  "allies (++): {a}; firm opponents (--): {o}, no petition.",
    "ask_against": "Vote against {bill} {when}.",
    "ask_for": "Vote for {bill} {when}.",
    "when_date": "on {date}",
    "when_next": "at its next vote",
    "seg": "Segment asks (if split): undecided: {ask}; allies: speak in the debate and use your "
           "constituents' numbers.",
    "lbl_arith": "Vote arithmetic",
    "lbl_votes": "Earlier votes",
    "lbl_whip": "Whip",
    "lbl_members": "Our members in their seats",
    "seats_line": "seats in the {chamber}: {parties}.",
    "fca_line": "{a} with us, {o} against, {p} undecided or with no record ({chamber}).",
    "ev_vote": "{date}: the {chamber} voted on '{q}' ({tally}).",
    "ev_stage": "{date}: {title}, stage '{stage}'.",
    "story": "Storytelling: villain = {villain}; princess = the {members} who have not yet decided; "
             "hero = the reader (a voter); helper = CitizenGO (carries the signatures to the "
             "{chamber}).",
    "u_launch": "**Launch ({stage}).** The {chamber} takes it up in {dur}.",
    "u_mid": "**Mid-campaign.** {dur} left before the {chamber} decides.",
    "u_final": "**Final week.** One week before the {chamber} decides.",
    "u_48": "**Final 48 hours.** Two days before the vote.",
    "dur_weeks": "{n} weeks",
    "dur_days": "{n} days",
    "funds_na": "N/A: AA emails carry the generic monthly-donation footer only.",
    "see_good": "See the good outcome.",
    "see_bad": "See the bad outcome. No backlash risk identified: expect 0.",
    "fca_na": "N/A: this parliament publishes no member votes, so there is no 5CA.",
    "fca_wait": "5CA awaiting sign-off. Readings of this bill's votes waiting for a named person: "
                "{n}. Nobody is placed and no target is set until they are confirmed.",
    "fca_novote": "No recorded vote on this bill yet.",
    "fca_done": "Five Column Analysis ({chamber}): {tally}. Targets (Y): {t}. The sheet is beside "
                "this file: {file}.",
}

ES = {
    "banner_nr": "NO LISTO: pendiente de validación.",
    "nr_dir": "La posición de CitizenGO sobre este proyecto aún no ha sido confirmada por una "
              "persona designada.",
    "nr_dir_none": "Aún no consta ninguna posición de CitizenGO sobre este proyecto.",
    "nr_reads": "Lecturas de sus votaciones pendientes de confirmación: {n}.",
    "nr_tail": "No lances, no señales objetivos ni recomiendes nada a partir de este borrador hasta "
               "que estén confirmadas.",
    "banner_ready": "LISTO: la posición de CitizenGO sobre este proyecto y todas las lecturas de sus "
                    "votaciones están confirmadas ({who}).",
    "generated": "Borrador generado el {date} a partir del registro parlamentario. Los hechos vienen "
                 "del registro; [CAMPAIGNER: ...] marca lo que escribe el campañista. Ningún modelo "
                 "de IA ha escrito nada de esto.",
    "ph": "[CAMPAIGNER: {0}]",
    "ph_sponsor": "quién lo presentó",
    "ph_stage": "la fase actual",
    "ph_next": "la próxima fecha clave (el registro aún no publica ninguna)",
    "ph_why": "por qué importa: qué cambia en la ley o en la práctica",
    "ph_history": "campañas anteriores de CitizenGO sobre este tema, con firmas y enlaces",
    "ph_routes": "las vías realistas hacia la victoria, en orden",
    "ph_ask": "la petición, cuando se confirme la posición de CitizenGO sobre este proyecto",
    "ph_story": "la línea narrativa, cuando se confirme la posición de CitizenGO sobre este proyecto",
    "ph_villain": "el villano",
    "ph_lead": "la frase principal: si <acción>, <destinatario> <conducta>, porque <punto de presión>",
    "ph_whip": "voto libre o disciplina de partido, y de quién",
    "ph_members_seats": "nuestros miembros en cada circunscripción, según los códigos postales",
    "ph_injustice": "de 5 a 10 injusticias con fuente: a quién perjudica, quién lo hace, qué pierden",
    "ph_arguments": "de 5 a 10 argumentos con fuente, y los tres principales argumentos contrarios "
                    "con nuestra respuesta",
    "ph_urgency": "por qué actuar ahora: el registro no publica ninguna fecha y no se puede inventar "
                  "un plazo",
    "ph_bad": "el mal resultado: de 60 a 120 palabras con escenas concretas, y dos alternativas de "
              "una línea",
    "ph_good": "el buen resultado: de 60 a 120 palabras, y dos alternativas de una línea",
    "ph_tim": "hasta 10 peticiones relacionadas de Bluebook (de hace 12 a 24 meses, misma lista)",
    "ph_news": "una noticia, en el idioma de la lista",
    "ph_evidence": "el estudio o informe que respalda el argumento más fuerte",
    "ph_minister": "si es un proyecto del Gobierno: el ministro responsable, con nombre y comprobado "
                   "en una fuente oficial",
    "ph_overlay": "texto para Canva, seis palabras como máximo",
    "ph_rf1": "de 3 a 5 campañas comparables de Bluebook, personas y dinero frente a la mediana de "
              "la lista",
    "ph_rf2": "de 3 a 5 aliados y cómo les ayuda esta campaña",
    "ph_rf3": "de 3 a 5 adversarios con nombre y qué les cuesta esta campaña, con fuente",
    "ph_worth": "una línea con fuente sobre lo que vale la victoria más allá de esta campaña",
    "ph_purpose": "no hay fecha de decisión en el registro: confirma el objetivo",
    "bg_what": "Qué: {title}.",
    "bg_who": "Quién: {sponsor}. Decide: {chamber}.",
    "bg_stage": "Situación: {stage} (último hecho registrado: {date}).",
    "bg_next": "Próximo paso: {next}",
    "bg_next_agenda": "en el orden del día ({chamber}) el {date}.",
    "bg_why": "Por qué importa: {why}",
    "path_head": "Camino a la victoria:",
    "path_wait": "el recuento de votos espera la validación de las lecturas de CitizenGO; aún no se "
                 "sitúa a nadie.",
    "fs_what": "Qué",
    "fs_who": "Quién",
    "fs_stage": "Fase",
    "fs_next": "Próxima fecha",
    "fs_5ca": "Resumen 5CA",
    "fs_history": "Nuestro historial",
    "fs_none": "ninguna publicada",
    "type_opp": "Opportunity: la opción por defecto; nada en el registro apunta a Obligatory ni a "
                "Survival.",
    "mp_pi": "un órgano de decisión identificado y una fecha clave en el registro.",
    "launch": "{date} (la más temprana: envío más tres días hábiles; se cuentan los fines de semana, "
              "no los festivos)",
    "deliv_key": "{date} (dos días hábiles antes del {key})",
    "deliv_est": "{date} (estimación: lanzamiento más 21 días; el registro no publica fecha clave)",
    "method": "Método",
    "m1": "correos a los {members} durante la campaña, uno por firma",
    "m2": "el día de la entrega, cada miembro recibe el número de firmas de su propia "
          "circunscripción",
    "m3": "una entrega fotografiada en la sede ({chamber}) y un PDF con el total para cada miembro",
    "off_handover": "**Entrega.** Entrega fotografiada de las firmas en la sede ({chamber}) el {date}. Coste: €. Responsable: Media Campaigner.",
    "off_letters": "**Cartas a los representantes.** Los firmantes escriben a sus propios {members} "
                   "la semana anterior al {date}. Coste: €. Responsable: Media Campaigner.",
    "off_press": "**Rueda de prensa.** Con expertos aliados el día de la entrega, frente a la sede ({chamber}). Coste: €€. Responsable: Media Campaigner.",
    "off_ads": "**Anuncios geolocalizados.** En las circunscripciones de los indecisos, en las dos "
               "últimas semanas antes del {date}. Coste: €€. Responsable: Media Campaigner.",
    "off_vigil": "**Vigilia.** Cerca de la sede ({chamber}) la víspera del {date}, si encaja con la lista. Coste: €. Responsable: Media Campaigner.",
    "addr_all": "Todos los miembros: {chamber} ({members}).",
    "addr_split": "Opción: dividir en peticiones separadas por segmento 5CA: indecisos (0/+/-): {p}; "
                  "aliados (++): {a}; adversarios firmes (--): {o}, sin petición.",
    "ask_against": "Votar en contra de {bill} {when}.",
    "ask_for": "Votar a favor de {bill} {when}.",
    "when_date": "el {date}",
    "when_next": "en su próxima votación",
    "seg": "Peticiones por segmento (si se divide): indecisos: {ask}; aliados: intervenir en el "
           "debate y usar las cifras de sus electores.",
    "lbl_arith": "Aritmética de votos",
    "lbl_votes": "Votaciones anteriores",
    "lbl_whip": "Disciplina de voto",
    "lbl_members": "Nuestros miembros en sus circunscripciones",
    "seats_line": "escaños ({chamber}): {parties}.",
    "fca_line": "{a} con nosotros, {o} en contra, {p} indecisos o sin registro ({chamber}).",
    "ev_vote": "{date}: votación ({chamber}) sobre '{q}' ({tally}).",
    "ev_stage": "{date}: {title}, fase '{stage}'.",
    "story": "Narrativa: villano = {villain}; princesa = los {members} que aún no han decidido; héroe = el lector (un votante); ayudante = CitizenGO (lleva las firmas a la sede: {chamber}).",
    "u_launch": "**Lanzamiento ({stage}).** {chamber}: se trata dentro de {dur}.",
    "u_mid": "**Mitad de campaña.** Quedan {dur} para la decisión ({chamber}).",
    "u_final": "**Última semana.** Una semana antes de la decisión ({chamber}).",
    "u_48": "**Últimas 48 horas.** Dos días antes de la votación.",
    "dur_weeks": "{n} semanas",
    "dur_days": "{n} días",
    "funds_na": "N/A: los correos AA solo llevan el pie genérico de donación mensual.",
    "see_good": "Ver el buen resultado.",
    "see_bad": "Ver el mal resultado. No se identifica riesgo de reacción adversa: se espera 0.",
    "fca_na": "N/A: este parlamento no publica votos individuales, así que no hay 5CA.",
    "fca_wait": "5CA pendiente de validación. Lecturas de las votaciones de este proyecto que esperan "
                "a una persona designada: {n}. No se sitúa a nadie ni se fija ningún objetivo hasta "
                "que se confirmen.",
    "fca_novote": "Aún no hay ninguna votación registrada sobre este proyecto.",
    "fca_done": "Análisis de cinco columnas ({chamber}): {tally}. Objetivos (Y): {t}. La hoja está "
                "junto a este archivo: {file}.",
}

PT = {
    "banner_nr": "NÃO PRONTO: aguarda validação.",
    "nr_dir": "A posição da CitizenGO sobre este projeto ainda não foi confirmada por uma pessoa "
              "designada.",
    "nr_dir_none": "Ainda não consta nenhuma posição da CitizenGO sobre este projeto.",
    "nr_reads": "Leituras das suas votações a aguardar confirmação: {n}.",
    "nr_tail": "Não lances, não definas alvos nem recomendes nada a partir deste rascunho até estarem "
               "confirmadas.",
    "banner_ready": "PRONTO: a posição da CitizenGO sobre este projeto e todas as leituras das suas "
                    "votações estão confirmadas ({who}).",
    "generated": "Rascunho gerado em {date} a partir do registo parlamentar. Os factos vêm do "
                 "registo; [CAMPAIGNER: ...] marca o que o campanhista escreve. Nenhum modelo de IA "
                 "escreveu nada disto.",
    "ph": "[CAMPAIGNER: {0}]",
    "ph_sponsor": "quem o apresentou",
    "ph_stage": "a fase atual",
    "ph_next": "a próxima data-chave (o registo ainda não publica nenhuma)",
    "ph_why": "porque importa: o que muda na lei ou na prática",
    "ph_history": "campanhas anteriores da CitizenGO sobre o tema, com assinaturas e ligações",
    "ph_routes": "os caminhos realistas para a vitória, por ordem",
    "ph_ask": "o pedido, quando a posição da CitizenGO sobre este projeto estiver confirmada",
    "ph_story": "a linha narrativa, quando a posição da CitizenGO sobre este projeto estiver "
                "confirmada",
    "ph_villain": "o vilão",
    "ph_lead": "a frase principal: se <ação>, <destinatário> <comportamento>, porque <ponto de "
               "pressão>",
    "ph_whip": "voto livre ou disciplina partidária, e de quem",
    "ph_members_seats": "os nossos membros em cada círculo eleitoral, pelos códigos postais",
    "ph_injustice": "5 a 10 injustiças com fonte: quem é prejudicado, quem o faz, o que perdem",
    "ph_arguments": "5 a 10 argumentos com fonte, e os três principais argumentos contrários com a "
                    "nossa resposta",
    "ph_urgency": "porquê agir agora: o registo não publica nenhuma data e nenhum prazo pode ser "
                  "inventado",
    "ph_bad": "o mau resultado: 60 a 120 palavras com cenas concretas, e duas alternativas de uma "
              "linha",
    "ph_good": "o bom resultado: 60 a 120 palavras, e duas alternativas de uma linha",
    "ph_tim": "até 10 petições relacionadas do Bluebook (de há 12 a 24 meses, mesma lista)",
    "ph_news": "uma notícia, na língua da lista",
    "ph_evidence": "o estudo ou relatório que sustenta o argumento mais forte",
    "ph_minister": "se for um projeto do Governo: o ministro responsável, com nome e verificado numa "
                   "fonte oficial",
    "ph_overlay": "texto para o Canva, no máximo seis palavras",
    "ph_rf1": "3 a 5 campanhas comparáveis do Bluebook, pessoas e dinheiro face à mediana da lista",
    "ph_rf2": "3 a 5 aliados e como esta campanha os ajuda",
    "ph_rf3": "3 a 5 adversários com nome e o que esta campanha lhes custa, com fonte",
    "ph_worth": "uma linha com fonte sobre o que a vitória vale para além desta campanha",
    "ph_purpose": "não há data de decisão no registo: confirma o objetivo",
    "bg_what": "O quê: {title}.",
    "bg_who": "Quem: {sponsor}. Decide: {chamber}.",
    "bg_stage": "Onde está: {stage} (último facto registado: {date}).",
    "bg_next": "Próximo passo: {next}",
    "bg_next_agenda": "na ordem do dia ({chamber}) em {date}.",
    "bg_why": "Porque importa: {why}",
    "path_head": "Caminho para a vitória:",
    "path_wait": "a contagem de votos aguarda a validação das leituras da CitizenGO; ainda ninguém "
                 "está posicionado.",
    "fs_what": "O quê",
    "fs_who": "Quem",
    "fs_stage": "Fase",
    "fs_next": "Próxima data",
    "fs_5ca": "Resumo 5CA",
    "fs_history": "O nosso historial",
    "fs_none": "nenhuma publicada",
    "type_opp": "Opportunity: a opção por defeito; nada no registo aponta para Obligatory ou "
                "Survival.",
    "mp_pi": "um órgão de decisão identificado e uma data-chave no registo.",
    "launch": "{date} (a mais cedo: envio mais três dias úteis; contam-se os fins de semana, não os "
              "feriados)",
    "deliv_key": "{date} (dois dias úteis antes de {key})",
    "deliv_est": "{date} (estimativa: lançamento mais 21 dias; o registo não publica data-chave)",
    "method": "Método",
    "m1": "emails aos {members} durante a campanha, um por assinatura",
    "m2": "no dia da entrega, cada membro recebe o número de assinaturas do seu próprio círculo",
    "m3": "uma entrega fotografada na sede ({chamber}) e um PDF com o total para cada membro",
    "off_handover": "**Entrega.** Entrega fotografada das assinaturas na sede ({chamber}) em {date}. Custo: €. Responsável: Media Campaigner.",
    "off_letters": "**Cartas aos eleitos.** Os signatários escrevem aos seus próprios {members} na "
                   "semana antes de {date}. Custo: €. Responsável: Media Campaigner.",
    "off_press": "**Conferência de imprensa.** Com especialistas aliados no dia da entrega, em frente à sede ({chamber}). Custo: €€. Responsável: Media Campaigner.",
    "off_ads": "**Anúncios geolocalizados.** Nos círculos dos indecisos, nas duas últimas semanas "
               "antes de {date}. Custo: €€. Responsável: Media Campaigner.",
    "off_vigil": "**Vigília.** Perto da sede ({chamber}) na véspera de {date}, se fizer sentido para a lista. Custo: €. Responsável: Media Campaigner.",
    "addr_all": "Todos os membros: {chamber} ({members}).",
    "addr_split": "Opção: dividir em petições separadas por segmento 5CA: indecisos (0/+/-): {p}; "
                  "aliados (++): {a}; adversários firmes (--): {o}, sem petição.",
    "ask_against": "Votar contra {bill} {when}.",
    "ask_for": "Votar a favor de {bill} {when}.",
    "when_date": "em {date}",
    "when_next": "na sua próxima votação",
    "seg": "Pedidos por segmento (se dividido): indecisos: {ask}; aliados: intervir no debate e "
           "usar os números dos seus eleitores.",
    "lbl_arith": "Aritmética dos votos",
    "lbl_votes": "Votações anteriores",
    "lbl_whip": "Disciplina de voto",
    "lbl_members": "Os nossos membros nos seus círculos",
    "seats_line": "lugares ({chamber}): {parties}.",
    "fca_line": "{a} connosco, {o} contra, {p} indecisos ou sem registo ({chamber}).",
    "ev_vote": "{date}: votação ({chamber}) sobre '{q}' ({tally}).",
    "ev_stage": "{date}: {title}, fase '{stage}'.",
    "story": "Narrativa: vilão = {villain}; princesa = os {members} que ainda não decidiram; herói = o leitor (um eleitor); ajudante = a CitizenGO (leva as assinaturas à sede: {chamber}).",
    "u_launch": "**Lançamento ({stage}).** {chamber}: trata do assunto dentro de {dur}.",
    "u_mid": "**Meio da campanha.** Faltam {dur} para a decisão ({chamber}).",
    "u_final": "**Última semana.** Uma semana antes da decisão ({chamber}).",
    "u_48": "**Últimas 48 horas.** Dois dias antes da votação.",
    "dur_weeks": "{n} semanas",
    "dur_days": "{n} dias",
    "funds_na": "N/A: os emails AA levam apenas o rodapé genérico de doação mensal.",
    "see_good": "Ver o bom resultado.",
    "see_bad": "Ver o mau resultado. Nenhum risco de reação adversa identificado: espera-se 0.",
    "fca_na": "N/A: este parlamento não publica votos individuais, por isso não há 5CA.",
    "fca_wait": "5CA a aguardar validação. Leituras das votações deste projeto à espera de uma "
                "pessoa designada: {n}. Ninguém é posicionado e nenhum alvo é definido até serem "
                "confirmadas.",
    "fca_novote": "Ainda não há nenhuma votação registada sobre este projeto.",
    "fca_done": "Análise de cinco colunas ({chamber}): {tally}. Alvos (Y): {t}. A folha está junto "
                "a este ficheiro: {file}.",
}

IT = {
    "banner_nr": "NON PRONTO: in attesa di convalida.",
    "nr_dir": "La posizione di CitizenGO su questo provvedimento non è ancora stata confermata da "
              "una persona designata.",
    "nr_dir_none": "Non risulta ancora alcuna posizione di CitizenGO su questo provvedimento.",
    "nr_reads": "Letture delle sue votazioni in attesa di conferma: {n}.",
    "nr_tail": "Non lanciare, non indicare obiettivi e non raccomandare nulla sulla base di questa "
               "bozza finché non saranno confermate.",
    "banner_ready": "PRONTO: la posizione di CitizenGO su questo provvedimento e tutte le letture "
                    "delle sue votazioni sono confermate ({who}).",
    "generated": "Bozza generata il {date} dagli atti parlamentari. I fatti vengono dagli atti; "
                 "[CAMPAIGNER: ...] indica ciò che scrive il campaigner. Nessun modello di IA ne ha "
                 "scritto una parola.",
    "ph": "[CAMPAIGNER: {0}]",
    "ph_sponsor": "chi lo ha presentato",
    "ph_stage": "la fase attuale",
    "ph_next": "la prossima data chiave (gli atti non ne pubblicano ancora)",
    "ph_why": "perché conta: cosa cambia nella legge o nella prassi",
    "ph_history": "precedenti campagne di CitizenGO sul tema, con firme e link",
    "ph_routes": "le strade realistiche verso la vittoria, in ordine",
    "ph_ask": "la richiesta, una volta confermata la posizione di CitizenGO su questo provvedimento",
    "ph_story": "la linea narrativa, una volta confermata la posizione di CitizenGO su questo "
                "provvedimento",
    "ph_villain": "il cattivo",
    "ph_lead": "la frase principale: se <azione>, <destinatario> <comportamento>, perché <leva>",
    "ph_whip": "voto libero o disciplina di gruppo, e di chi",
    "ph_members_seats": "i nostri membri in ogni collegio, dai codici postali",
    "ph_injustice": "da 5 a 10 ingiustizie con fonte: chi è danneggiato, chi lo fa, cosa perde",
    "ph_arguments": "da 5 a 10 argomenti con fonte, poi i tre principali argomenti avversari con la "
                    "nostra risposta",
    "ph_urgency": "perché agire ora: gli atti non pubblicano alcuna data e nessuna scadenza può "
                  "essere inventata",
    "ph_bad": "l'esito negativo: da 60 a 120 parole di scene concrete, poi due alternative di una "
              "riga",
    "ph_good": "l'esito positivo: da 60 a 120 parole, poi due alternative di una riga",
    "ph_tim": "fino a 10 petizioni collegate da Bluebook (da 12 a 24 mesi fa, stessa lista)",
    "ph_news": "un articolo di cronaca, nella lingua della lista",
    "ph_evidence": "lo studio o il rapporto dietro l'argomento più forte",
    "ph_minister": "se è un disegno di legge del Governo: il ministro competente, con nome e "
                   "verificato su una fonte ufficiale",
    "ph_overlay": "testo per Canva, al massimo sei parole",
    "ph_rf1": "da 3 a 5 campagne comparabili da Bluebook, persone e denaro rispetto alla mediana "
              "della lista",
    "ph_rf2": "da 3 a 5 alleati e come questa campagna li aiuta",
    "ph_rf3": "da 3 a 5 avversari con nome e quanto costa loro questa campagna, con fonte",
    "ph_worth": "una riga con fonte su cosa vale la vittoria oltre questa campagna",
    "ph_purpose": "nessuna data di decisione negli atti: conferma lo scopo",
    "bg_what": "Cosa: {title}.",
    "bg_who": "Chi: {sponsor}. Decide: {chamber}.",
    "bg_stage": "A che punto è: {stage} (ultimo evento registrato: {date}).",
    "bg_next": "Prossimo passo: {next}",
    "bg_next_agenda": "all'ordine del giorno ({chamber}) il {date}.",
    "bg_why": "Perché conta: {why}",
    "path_head": "Strada verso la vittoria:",
    "path_wait": "il conteggio dei voti attende la convalida delle letture di CitizenGO; nessuno è "
                 "ancora collocato.",
    "fs_what": "Cosa",
    "fs_who": "Chi",
    "fs_stage": "Fase",
    "fs_next": "Prossima data",
    "fs_5ca": "Sintesi 5CA",
    "fs_history": "Il nostro storico",
    "fs_none": "nessuna pubblicata",
    "type_opp": "Opportunity: la scelta predefinita; nulla negli atti indica Obligatory o Survival.",
    "mp_pi": "un organo decisionale identificato e una data chiave negli atti.",
    "launch": "{date} (la più vicina: invio più tre giorni lavorativi; contati i fine settimana, non "
              "i festivi)",
    "deliv_key": "{date} (due giorni lavorativi prima del {key})",
    "deliv_est": "{date} (stima: lancio più 21 giorni; gli atti non pubblicano una data chiave)",
    "method": "Metodo",
    "m1": "email ai {members} durante la campagna, una per firma",
    "m2": "il giorno della consegna, ogni membro riceve il numero di firme del proprio collegio",
    "m3": "una consegna fotografata in sede ({chamber}) e un PDF con il totale per ogni membro",
    "off_handover": "**Consegna.** Consegna fotografata delle firme in sede ({chamber}) il {date}. Costo: €. Responsabile: Media Campaigner.",
    "off_letters": "**Lettere ai parlamentari.** I firmatari scrivono ai propri {members} nella "
                   "settimana prima del {date}. Costo: €. Responsabile: Media Campaigner.",
    "off_press": "**Conferenza stampa.** Con esperti alleati il giorno della consegna, davanti alla sede ({chamber}). Costo: €€. Responsabile: Media Campaigner.",
    "off_ads": "**Annunci geolocalizzati.** Nei collegi degli indecisi, nelle ultime due settimane "
               "prima del {date}. Costo: €€. Responsabile: Media Campaigner.",
    "off_vigil": "**Veglia.** Vicino alla sede ({chamber}) la vigilia del {date}, se adatta alla lista. Costo: €. Responsabile: Media Campaigner.",
    "addr_all": "Tutti i membri: {chamber} ({members}).",
    "addr_split": "Opzione: dividere in petizioni separate per segmento 5CA: indecisi (0/+/-): {p}; "
                  "alleati (++): {a}; avversari decisi (--): {o}, nessuna petizione.",
    "ask_against": "Votare contro {bill} {when}.",
    "ask_for": "Votare a favore di {bill} {when}.",
    "when_date": "il {date}",
    "when_next": "alla prossima votazione",
    "seg": "Richieste per segmento (se divisa): indecisi: {ask}; alleati: intervenire nel dibattito "
           "e usare i numeri dei propri elettori.",
    "lbl_arith": "Aritmetica dei voti",
    "lbl_votes": "Votazioni precedenti",
    "lbl_whip": "Disciplina di voto",
    "lbl_members": "I nostri membri nei loro collegi",
    "seats_line": "seggi ({chamber}): {parties}.",
    "fca_line": "{a} con noi, {o} contro, {p} indecisi o senza precedenti ({chamber}).",
    "ev_vote": "{date}: votazione ({chamber}) su '{q}' ({tally}).",
    "ev_stage": "{date}: {title}, fase '{stage}'.",
    "story": "Narrazione: cattivo = {villain}; principessa = i {members} ancora indecisi; eroe = il lettore (un elettore); aiutante = CitizenGO (porta le firme in sede: {chamber}).",
    "u_launch": "**Lancio ({stage}).** {chamber}: esame tra {dur}.",
    "u_mid": "**Metà campagna.** Mancano {dur} alla decisione ({chamber}).",
    "u_final": "**Ultima settimana.** Una settimana prima della decisione ({chamber}).",
    "u_48": "**Ultime 48 ore.** Due giorni prima del voto.",
    "dur_weeks": "{n} settimane",
    "dur_days": "{n} giorni",
    "funds_na": "N/A: le email AA riportano solo il piè di pagina generico per la donazione mensile.",
    "see_good": "Vedi l'esito positivo.",
    "see_bad": "Vedi l'esito negativo. Nessun rischio di contraccolpo individuato: atteso 0.",
    "fca_na": "N/A: questo parlamento non pubblica i voti dei singoli membri, quindi non c'è 5CA.",
    "fca_wait": "5CA in attesa di convalida. Letture delle votazioni di questo provvedimento in "
                "attesa di una persona designata: {n}. Nessuno è collocato e nessun obiettivo è "
                "fissato finché non saranno confermate.",
    "fca_novote": "Nessuna votazione registrata su questo provvedimento finora.",
    "fca_done": "Analisi a cinque colonne ({chamber}): {tally}. Obiettivi (Y): {t}. Il foglio è "
                "accanto a questo file: {file}.",
}

FR = {
    "banner_nr": "PAS PRÊT : en attente de validation.",
    "nr_dir": "La position de CitizenGO sur ce texte n'a pas encore été confirmée par une personne "
              "désignée.",
    "nr_dir_none": "Aucune position de CitizenGO sur ce texte n'est encore enregistrée.",
    "nr_reads": "Lectures de ses scrutins en attente de confirmation : {n}.",
    "nr_tail": "Ne lancez rien, ne fixez aucune cible et ne recommandez rien à partir de ce brouillon "
               "tant qu'elles ne sont pas confirmées.",
    "banner_ready": "PRÊT : la position de CitizenGO sur ce texte et toutes les lectures de ses "
                    "scrutins sont confirmées ({who}).",
    "generated": "Brouillon généré le {date} à partir des données parlementaires. Les faits viennent "
                 "de ces données ; [CAMPAIGNER: ...] signale ce que rédige le chargé de campagne. "
                 "Aucun modèle d'IA n'en a écrit un mot.",
    "ph": "[CAMPAIGNER: {0}]",
    "ph_sponsor": "qui l'a déposé",
    "ph_stage": "l'étape actuelle",
    "ph_next": "la prochaine date clé (les données n'en publient pas encore)",
    "ph_why": "pourquoi c'est important : ce qui change dans la loi ou la pratique",
    "ph_history": "les campagnes précédentes de CitizenGO sur le sujet, avec signatures et liens",
    "ph_routes": "les voies réalistes vers la victoire, dans l'ordre",
    "ph_ask": "la demande, une fois confirmée la position de CitizenGO sur ce texte",
    "ph_story": "la ligne narrative, une fois confirmée la position de CitizenGO sur ce texte",
    "ph_villain": "le méchant",
    "ph_lead": "la phrase d'accroche : si <action>, <cible> <comportement>, parce que <levier>",
    "ph_whip": "vote libre ou consigne de groupe, et de qui",
    "ph_members_seats": "nos membres dans chaque circonscription, d'après les codes postaux",
    "ph_injustice": "5 à 10 injustices sourcées : qui est lésé, qui en est responsable, ce qu'ils "
                    "perdent",
    "ph_arguments": "5 à 10 arguments sourcés, puis les trois principaux arguments adverses avec "
                    "notre réponse",
    "ph_urgency": "pourquoi agir maintenant : les données ne publient aucune date, et aucune "
                  "échéance ne peut être inventée",
    "ph_bad": "le mauvais résultat : 60 à 120 mots de scènes concrètes, puis deux variantes d'une "
              "ligne",
    "ph_good": "le bon résultat : 60 à 120 mots, puis deux variantes d'une ligne",
    "ph_tim": "jusqu'à 10 pétitions liées dans Bluebook (il y a 12 à 24 mois, même liste)",
    "ph_news": "un article de presse, dans la langue de la liste",
    "ph_evidence": "l'étude ou le rapport derrière l'argument le plus fort",
    "ph_minister": "s'il s'agit d'un projet du Gouvernement : le ministre compétent, nommé et vérifié "
                   "auprès d'une source officielle",
    "ph_overlay": "texte pour Canva, six mots au plus",
    "ph_rf1": "3 à 5 campagnes comparables tirées de Bluebook, personnes et argent face à la "
              "médiane de la liste",
    "ph_rf2": "3 à 5 alliés et comment cette campagne les aide",
    "ph_rf3": "3 à 5 adversaires nommés et ce que cette campagne leur coûte, sourcé",
    "ph_worth": "une ligne sourcée sur ce que vaut la victoire au-delà de cette campagne",
    "ph_purpose": "aucune date de décision dans les données : confirmez l'objectif",
    "bg_what": "Quoi : {title}.",
    "bg_who": "Qui : {sponsor}. Décide : {chamber}.",
    "bg_stage": "Où en est-on : {stage} (dernier événement enregistré : {date}).",
    "bg_next": "Prochaine étape : {next}",
    "bg_next_agenda": "à l'ordre du jour ({chamber}) le {date}.",
    "bg_why": "Pourquoi c'est important : {why}",
    "path_head": "Chemin vers la victoire :",
    "path_wait": "le décompte des voix attend la validation des lectures de CitizenGO ; personne "
                 "n'est encore placé.",
    "fs_what": "Quoi",
    "fs_who": "Qui",
    "fs_stage": "Étape",
    "fs_next": "Prochaine date",
    "fs_5ca": "Synthèse 5CA",
    "fs_history": "Notre historique",
    "fs_none": "aucune publiée",
    "type_opp": "Opportunity : le choix par défaut ; rien dans les données n'indique Obligatory ou "
                "Survival.",
    "mp_pi": "un organe de décision identifié et une date clé dans les données.",
    "launch": "{date} (au plus tôt : dépôt plus trois jours ouvrés ; week-ends comptés, jours fériés "
              "non vérifiés)",
    "deliv_key": "{date} (deux jours ouvrés avant le {key})",
    "deliv_est": "{date} (estimation : lancement plus 21 jours ; aucune date clé publiée)",
    "method": "Méthode",
    "m1": "des courriels aux {members} pendant la campagne, un par signature",
    "m2": "le jour de la remise, chaque élu reçoit le nombre de signatures de sa propre "
          "circonscription",
    "m3": "une remise photographiée au siège ({chamber}) et un PDF du total pour chaque élu",
    "off_handover": "**Remise.** Remise photographiée des signatures au siège ({chamber}) le {date}. Coût : €. Responsable : Media Campaigner.",
    "off_letters": "**Lettres aux élus.** Les signataires écrivent à leurs propres {members} la "
                   "semaine précédant le {date}. Coût : €. Responsable : Media Campaigner.",
    "off_press": "**Conférence de presse.** Avec des experts alliés le jour de la remise, devant le siège ({chamber}). Coût : €€. Responsable : Media Campaigner.",
    "off_ads": "**Publicités géociblées.** Dans les circonscriptions des indécis, dans les deux "
               "dernières semaines avant le {date}. Coût : €€. Responsable : Media Campaigner.",
    "off_vigil": "**Veillée.** Près du siège ({chamber}) la veille du {date}, si cela convient à la liste. Coût : €. Responsable : Media Campaigner.",
    "addr_all": "Tous les membres : {chamber} ({members}).",
    "addr_split": "Option : diviser en pétitions distinctes par segment 5CA : indécis (0/+/-) : {p} ; "
                  "alliés (++) : {a} ; adversaires résolus (--) : {o}, pas de pétition.",
    "ask_against": "Voter contre {bill} {when}.",
    "ask_for": "Voter pour {bill} {when}.",
    "when_date": "le {date}",
    "when_next": "lors de son prochain scrutin",
    "seg": "Demandes par segment (si divisé) : indécis : {ask} ; alliés : intervenir dans le débat "
           "et citer les chiffres de leurs électeurs.",
    "lbl_arith": "Arithmétique des voix",
    "lbl_votes": "Scrutins précédents",
    "lbl_whip": "Consigne de vote",
    "lbl_members": "Nos membres dans leurs circonscriptions",
    "seats_line": "sièges ({chamber}) : {parties}.",
    "fca_line": "{a} avec nous, {o} contre, {p} indécis ou sans antécédent ({chamber}).",
    "ev_vote": "{date} : scrutin ({chamber}) sur « {q} » ({tally}).",
    "ev_stage": "{date} : {title}, étape « {stage} ».",
    "story": "Récit : méchant = {villain} ; princesse = les {members} encore indécis ; héros = le lecteur (un électeur) ; adjuvant = CitizenGO (porte les signatures au siège : {chamber}).",
    "u_launch": "**Lancement ({stage}).** {chamber} : examen dans {dur}.",
    "u_mid": "**Mi-campagne.** Il reste {dur} avant la décision ({chamber}).",
    "u_final": "**Dernière semaine.** Une semaine avant la décision ({chamber}).",
    "u_48": "**Dernières 48 heures.** Deux jours avant le vote.",
    "dur_weeks": "{n} semaines",
    "dur_days": "{n} jours",
    "funds_na": "N/A : les courriels AA ne portent que le pied de page générique du don mensuel.",
    "see_good": "Voir le bon résultat.",
    "see_bad": "Voir le mauvais résultat. Aucun risque de contrecoup identifié : attendu 0.",
    "fca_na": "N/A : ce parlement ne publie pas les votes individuels, il n'y a donc pas de 5CA.",
    "fca_wait": "5CA en attente de validation. Lectures des scrutins de ce texte en attente d'une "
                "personne désignée : {n}. Personne n'est placé et aucune cible n'est fixée tant "
                "qu'elles ne sont pas confirmées.",
    "fca_novote": "Aucun scrutin enregistré sur ce texte à ce jour.",
    "fca_done": "Analyse en cinq colonnes ({chamber}) : {tally}. Cibles (Y) : {t}. La feuille est à "
                "côté de ce fichier : {file}.",
}

DE = {
    "banner_nr": "NICHT FREIGEGEBEN: wartet auf Bestätigung.",
    "nr_dir": "Die Position von CitizenGO zu dieser Vorlage ist noch von keiner benannten Person "
              "bestätigt.",
    "nr_dir_none": "Zu dieser Vorlage ist noch keine Position von CitizenGO hinterlegt.",
    "nr_reads": "Lesarten ihrer Abstimmungen, die auf Bestätigung warten: {n}.",
    "nr_tail": "Aus diesem Entwurf nichts starten, keine Ziele festlegen und nichts empfehlen, bevor "
               "sie bestätigt sind.",
    "banner_ready": "FREIGEGEBEN: Die Position von CitizenGO zu dieser Vorlage und alle Lesarten ihrer "
                    "Abstimmungen sind bestätigt ({who}).",
    "generated": "Entwurf vom {date}, erstellt aus den Parlamentsdaten. Die Fakten stammen aus diesen "
                 "Daten; [CAMPAIGNER: ...] markiert, was die Kampagnenleitung schreibt. Kein KI-Modell "
                 "hat daran mitgeschrieben.",
    "ph": "[CAMPAIGNER: {0}]",
    "ph_sponsor": "wer sie eingebracht hat",
    "ph_stage": "der aktuelle Stand",
    "ph_next": "der nächste wichtige Termin (die Daten nennen noch keinen)",
    "ph_why": "warum es wichtig ist: was sich in Recht oder Praxis ändert",
    "ph_history": "frühere CitizenGO-Kampagnen zum Thema, mit Unterschriften und Links",
    "ph_routes": "die realistischen Wege zum Erfolg, in dieser Reihenfolge",
    "ph_ask": "die Forderung, sobald die Position von CitizenGO zu dieser Vorlage bestätigt ist",
    "ph_story": "die erzählerische Linie, sobald die Position von CitizenGO zu dieser Vorlage "
                "bestätigt ist",
    "ph_villain": "der Bösewicht",
    "ph_lead": "der Leitsatz: Wenn wir <Aktion>, wird <Adressat> <Verhalten>, weil <Druckpunkt>",
    "ph_whip": "freie Abstimmung oder Fraktionszwang, und von wem",
    "ph_members_seats": "unsere Mitglieder in jedem Wahlkreis, aus den Postleitzahlen",
    "ph_injustice": "5 bis 10 belegte Ungerechtigkeiten: wer geschädigt wird, wer es tut, was sie "
                    "verlieren",
    "ph_arguments": "5 bis 10 belegte Argumente, dann die drei wichtigsten Gegenargumente mit unserer "
                    "Antwort",
    "ph_urgency": "warum jetzt handeln: die Daten nennen keinen Termin, und keine Frist darf erfunden "
                  "werden",
    "ph_bad": "das schlechte Ergebnis: 60 bis 120 Wörter mit konkreten Szenen, dann zwei einzeilige "
              "Varianten",
    "ph_good": "das gute Ergebnis: 60 bis 120 Wörter, dann zwei einzeilige Varianten",
    "ph_tim": "bis zu 10 verwandte Petitionen aus Bluebook (vor 12 bis 24 Monaten, gleiche Liste)",
    "ph_news": "ein Nachrichtenbericht, in der Sprache der Liste",
    "ph_evidence": "die Studie oder der Bericht hinter dem stärksten Argument",
    "ph_minister": "falls Regierungsvorlage: die zuständige Ministerin oder der zuständige Minister, "
                   "namentlich und an einer amtlichen Quelle geprüft",
    "ph_overlay": "Text für Canva, höchstens sechs Wörter",
    "ph_rf1": "3 bis 5 vergleichbare Kampagnen aus Bluebook, Personen und Geld gegenüber dem Median "
              "der Liste",
    "ph_rf2": "3 bis 5 Verbündete und wie diese Kampagne ihnen hilft",
    "ph_rf3": "3 bis 5 namentlich genannte Gegner und was diese Kampagne sie kostet, belegt",
    "ph_worth": "eine belegte Zeile dazu, was der Sieg über diese Kampagne hinaus wert ist",
    "ph_purpose": "kein Entscheidungstermin in den Daten: Zweck bestätigen",
    "bg_what": "Was: {title}.",
    "bg_who": "Wer: {sponsor}. Es entscheidet: {chamber}.",
    "bg_stage": "Stand: {stage} (letztes erfasstes Ereignis: {date}).",
    "bg_next": "Als Nächstes: {next}",
    "bg_next_agenda": "auf der Tagesordnung ({chamber}) am {date}.",
    "bg_why": "Warum es wichtig ist: {why}",
    "path_head": "Weg zum Erfolg:",
    "path_wait": "die Stimmenrechnung wartet auf die Bestätigung der Lesarten von CitizenGO; noch "
                 "niemand ist eingeordnet.",
    "fs_what": "Was",
    "fs_who": "Wer",
    "fs_stage": "Stand",
    "fs_next": "Nächster Termin",
    "fs_5ca": "5CA-Übersicht",
    "fs_history": "Unsere Vorgeschichte",
    "fs_none": "keiner veröffentlicht",
    "type_opp": "Opportunity: die Voreinstellung; nichts in den Daten spricht für Obligatory oder "
                "Survival.",
    "mp_pi": "ein benanntes Entscheidungsgremium und ein wichtiger Termin in den Daten.",
    "launch": "{date} (frühestens: Einreichung plus drei Arbeitstage; Wochenenden gezählt, Feiertage "
              "nicht geprüft)",
    "deliv_key": "{date} (zwei Arbeitstage vor dem {key})",
    "deliv_est": "{date} (Schätzung: Start plus 21 Tage; die Daten nennen keinen Termin)",
    "method": "Methode",
    "m1": "E-Mails an die {members} während der Kampagne, eine pro Unterschrift",
    "m2": "am Übergabetag erhält jedes Mitglied die Zahl der Unterschriften aus dem eigenen Wahlkreis",
    "m3": "eine fotografierte Übergabe am Sitz ({chamber}) und ein PDF mit der Gesamtzahl für jedes Mitglied",
    "off_handover": "**Übergabe.** Fotografierte Übergabe der Unterschriften am Sitz ({chamber}) am {date}. Kosten: €. Zuständig: Media Campaigner.",
    "off_letters": "**Briefe an die Abgeordneten.** Unterstützer schreiben in der Woche vor dem "
                   "{date} an ihre eigenen {members}. Kosten: €. Zuständig: Media Campaigner.",
    "off_press": "**Pressekonferenz.** Mit verbündeten Fachleuten am Tag der Übergabe, vor dem Sitz ({chamber}). Kosten: €€. Zuständig: Media Campaigner.",
    "off_ads": "**Regional ausgespielte Anzeigen.** In den Wahlkreisen der Unentschlossenen, in den "
               "letzten zwei Wochen vor dem {date}. Kosten: €€. Zuständig: Media Campaigner.",
    "off_vigil": "**Mahnwache.** In der Nähe des Sitzes ({chamber}) am Vorabend des {date}, wo es zur Liste passt. Kosten: €. Zuständig: Media Campaigner.",
    "addr_all": "Alle Mitglieder: {chamber} ({members}).",
    "addr_split": "Option: getrennte Petitionen nach 5CA-Segment: Unentschlossene (0/+/-): {p}; "
                  "Verbündete (++): {a}; feste Gegner (--): {o}, keine Petition.",
    "ask_against": "Gegen {bill} stimmen, {when}.",
    "ask_for": "Für {bill} stimmen, {when}.",
    "when_date": "am {date}",
    "when_next": "bei der nächsten Abstimmung",
    "seg": "Forderungen nach Segment (falls getrennt): Unentschlossene: {ask}; Verbündete: in der "
           "Debatte sprechen und die Zahlen ihrer Wähler nennen.",
    "lbl_arith": "Stimmenrechnung",
    "lbl_votes": "Frühere Abstimmungen",
    "lbl_whip": "Fraktionsdisziplin",
    "lbl_members": "Unsere Mitglieder in ihren Wahlkreisen",
    "seats_line": "Sitze ({chamber}): {parties}.",
    "fca_line": "{a} mit uns, {o} dagegen, {p} unentschlossen oder ohne Erfassung ({chamber}).",
    "ev_vote": "{date}: Abstimmung ({chamber}) über '{q}' ({tally}).",
    "ev_stage": "{date}: {title}, Stand '{stage}'.",
    "story": "Erzählung: Bösewicht = {villain}; Prinzessin = die noch unentschlossenen {members}; Held = die Leserin oder der Leser (eine Wählerin, ein Wähler); Helfer = CitizenGO (bringt die Unterschriften an den Sitz: {chamber}).",
    "u_launch": "**Start ({stage}).** {chamber}: Beratung in {dur}.",
    "u_mid": "**Halbzeit.** Noch {dur} bis zur Entscheidung ({chamber}).",
    "u_final": "**Letzte Woche.** Eine Woche vor der Entscheidung ({chamber}).",
    "u_48": "**Letzte 48 Stunden.** Zwei Tage vor der Abstimmung.",
    "dur_weeks": "{n} Wochen",
    "dur_days": "{n} Tagen",
    "funds_na": "N/A: AA-E-Mails tragen nur die allgemeine Fußzeile für Monatsspenden.",
    "see_good": "Siehe das gute Ergebnis.",
    "see_bad": "Siehe das schlechte Ergebnis. Kein Risiko einer Gegenreaktion erkennbar: 0 erwartet.",
    "fca_na": "N/A: Dieses Parlament veröffentlicht keine Einzelstimmen, daher gibt es keine 5CA.",
    "fca_wait": "5CA wartet auf Bestätigung. Lesarten der Abstimmungen zu dieser Vorlage, die auf "
                "eine benannte Person warten: {n}. Niemand wird eingeordnet und kein Ziel gesetzt, "
                "bevor sie bestätigt sind.",
    "fca_novote": "Zu dieser Vorlage gibt es noch keine erfasste Abstimmung.",
    "fca_done": "Fünf-Spalten-Analyse ({chamber}): {tally}. Ziele (Y): {t}. Das Blatt liegt neben "
                "dieser Datei: {file}.",
}

NL = {
    "banner_nr": "NIET KLAAR: wacht op bevestiging.",
    "nr_dir": "Het standpunt van CitizenGO over dit voorstel is nog niet bevestigd door een "
              "aangewezen persoon.",
    "nr_dir_none": "Er staat nog geen standpunt van CitizenGO over dit voorstel op papier.",
    "nr_reads": "Lezingen van de stemmingen die op bevestiging wachten: {n}.",
    "nr_tail": "Start niets, kies geen doelwitten en beveel niets aan op basis van dit concept "
               "voordat ze bevestigd zijn.",
    "banner_ready": "KLAAR: het standpunt van CitizenGO over dit voorstel en alle lezingen van de "
                    "stemmingen zijn bevestigd ({who}).",
    "generated": "Concept gemaakt op {date} uit de parlementaire gegevens. De feiten komen uit die "
                 "gegevens; [CAMPAIGNER: ...] markeert wat de campagnevoerder schrijft. Geen enkel "
                 "AI-model heeft hieraan meegeschreven.",
    "ph": "[CAMPAIGNER: {0}]",
    "ph_sponsor": "wie het indiende",
    "ph_stage": "de huidige fase",
    "ph_next": "de volgende sleuteldatum (de gegevens noemen er nog geen)",
    "ph_why": "waarom het ertoe doet: wat er verandert in wet of praktijk",
    "ph_history": "eerdere CitizenGO-campagnes over dit onderwerp, met handtekeningen en links",
    "ph_routes": "de realistische wegen naar de overwinning, op volgorde",
    "ph_ask": "de oproep, zodra het standpunt van CitizenGO over dit voorstel bevestigd is",
    "ph_story": "de verhaallijn, zodra het standpunt van CitizenGO over dit voorstel bevestigd is",
    "ph_villain": "de schurk",
    "ph_lead": "de openingszin: als wij <actie>, zal <doelwit> <gedrag>, omdat <drukmiddel>",
    "ph_whip": "vrije stemming of fractiediscipline, en van wie",
    "ph_members_seats": "onze leden per kieskring, uit de postcodegegevens",
    "ph_injustice": "5 tot 10 onderbouwde onrechtvaardigheden: wie gedupeerd wordt, wie het doet, "
                    "wat zij verliezen",
    "ph_arguments": "5 tot 10 onderbouwde argumenten, dan de drie sterkste tegenargumenten met ons "
                    "antwoord",
    "ph_urgency": "waarom nu: de gegevens noemen geen datum en er mag geen termijn verzonnen worden",
    "ph_bad": "de slechte afloop: 60 tot 120 woorden met concrete scènes, dan twee varianten van één "
              "regel",
    "ph_good": "de goede afloop: 60 tot 120 woorden, dan twee varianten van één regel",
    "ph_tim": "tot 10 verwante petities uit Bluebook (12 tot 24 maanden geleden, zelfde lijst)",
    "ph_news": "een nieuwsbericht, in de taal van de lijst",
    "ph_evidence": "het onderzoek of rapport achter het sterkste argument",
    "ph_minister": "bij een regeringsvoorstel: de verantwoordelijke minister, met naam en gecontroleerd "
                   "aan een officiële bron",
    "ph_overlay": "tekst voor Canva, hooguit zes woorden",
    "ph_rf1": "3 tot 5 vergelijkbare campagnes uit Bluebook, mensen en geld tegenover de mediaan van "
              "de lijst",
    "ph_rf2": "3 tot 5 bondgenoten en hoe deze campagne hen helpt",
    "ph_rf3": "3 tot 5 tegenstanders bij naam en wat deze campagne hen kost, onderbouwd",
    "ph_worth": "één onderbouwde regel over wat de overwinning waard is buiten deze campagne",
    "ph_purpose": "geen beslisdatum in de gegevens: bevestig het doel",
    "bg_what": "Wat: {title}.",
    "bg_who": "Wie: {sponsor}. Beslist: {chamber}.",
    "bg_stage": "Stand van zaken: {stage} (laatst geregistreerde gebeurtenis: {date}).",
    "bg_next": "Volgende stap: {next}",
    "bg_next_agenda": "op de agenda ({chamber}) op {date}.",
    "bg_why": "Waarom het ertoe doet: {why}",
    "path_head": "Weg naar de overwinning:",
    "path_wait": "de stemmentelling wacht op de bevestiging van de lezingen van CitizenGO; nog niemand "
                 "is ingedeeld.",
    "fs_what": "Wat",
    "fs_who": "Wie",
    "fs_stage": "Fase",
    "fs_next": "Volgende datum",
    "fs_5ca": "5CA-samenvatting",
    "fs_history": "Onze voorgeschiedenis",
    "fs_none": "geen gepubliceerd",
    "type_opp": "Opportunity: de standaard; niets in de gegevens wijst op Obligatory of Survival.",
    "mp_pi": "een benoemd beslisorgaan en een sleuteldatum in de gegevens.",
    "launch": "{date} (op zijn vroegst: indiening plus drie werkdagen; weekends geteld, feestdagen "
              "niet gecontroleerd)",
    "deliv_key": "{date} (twee werkdagen voor {key})",
    "deliv_est": "{date} (schatting: start plus 21 dagen; de gegevens noemen geen sleuteldatum)",
    "method": "Methode",
    "m1": "e-mails aan de {members} tijdens de campagne, één per handtekening",
    "m2": "op de overhandigingsdag krijgt elk lid het aantal handtekeningen uit de eigen regio",
    "m3": "een gefotografeerde overhandiging in het gebouw ({chamber}) en een pdf met het totaal voor elk lid",
    "off_handover": "**Overhandiging.** Gefotografeerde overhandiging van de handtekeningen in het gebouw ({chamber}) op {date}. Kosten: €. Eigenaar: Media Campaigner.",
    "off_letters": "**Brieven aan volksvertegenwoordigers.** Ondertekenaars schrijven in de week voor "
                   "{date} aan hun eigen {members}. Kosten: €. Eigenaar: Media Campaigner.",
    "off_press": "**Persconferentie.** Met bevriende deskundigen op de dag van de overhandiging, voor het gebouw ({chamber}). Kosten: €€. Eigenaar: Media Campaigner.",
    "off_ads": "**Regionaal gerichte advertenties.** In de regio's van de twijfelaars, in de laatste "
               "twee weken voor {date}. Kosten: €€. Eigenaar: Media Campaigner.",
    "off_vigil": "**Wake.** Bij het gebouw ({chamber}) op de avond voor {date}, waar het bij de lijst past. Kosten: €. Eigenaar: Media Campaigner.",
    "addr_all": "Alle leden: {chamber} ({members}).",
    "addr_split": "Optie: aparte petities per 5CA-segment: twijfelaars (0/+/-): {p}; bondgenoten "
                  "(++): {a}; vaste tegenstanders (--): {o}, geen petitie.",
    "ask_against": "Stem tegen {bill} {when}.",
    "ask_for": "Stem voor {bill} {when}.",
    "when_date": "op {date}",
    "when_next": "bij de volgende stemming",
    "seg": "Oproepen per segment (bij opsplitsing): twijfelaars: {ask}; bondgenoten: spreek in het "
           "debat en gebruik de cijfers van uw kiezers.",
    "lbl_arith": "Stemmenrekensom",
    "lbl_votes": "Eerdere stemmingen",
    "lbl_whip": "Fractiediscipline",
    "lbl_members": "Onze leden in hun regio",
    "seats_line": "zetels ({chamber}): {parties}.",
    "fca_line": "{a} met ons, {o} tegen, {p} twijfelend of zonder registratie ({chamber}).",
    "ev_vote": "{date}: stemming ({chamber}) over '{q}' ({tally}).",
    "ev_stage": "{date}: {title}, fase '{stage}'.",
    "story": "Verhaal: schurk = {villain}; prinses = de {members} die nog niet beslist hebben; held = de lezer (een kiezer); helper = CitizenGO (brengt de handtekeningen naar het gebouw: {chamber}).",
    "u_launch": "**Start ({stage}).** {chamber}: behandeling over {dur}.",
    "u_mid": "**Halverwege.** Nog {dur} tot het besluit ({chamber}).",
    "u_final": "**Laatste week.** Een week voor het besluit ({chamber}).",
    "u_48": "**Laatste 48 uur.** Twee dagen voor de stemming.",
    "dur_weeks": "{n} weken",
    "dur_days": "{n} dagen",
    "funds_na": "N/A: AA-e-mails dragen alleen de algemene voettekst voor maandelijkse giften.",
    "see_good": "Zie de goede afloop.",
    "see_bad": "Zie de slechte afloop. Geen risico op een averechts effect gevonden: verwacht 0.",
    "fca_na": "N/A: dit parlement publiceert geen individuele stemmen, dus er is geen 5CA.",
    "fca_wait": "5CA wacht op bevestiging. Lezingen van de stemmingen over dit voorstel die op een "
                "aangewezen persoon wachten: {n}. Niemand wordt ingedeeld en er wordt geen doelwit "
                "gekozen voordat ze bevestigd zijn.",
    "fca_novote": "Er is nog geen geregistreerde stemming over dit voorstel.",
    "fca_done": "Vijfkolommenanalyse ({chamber}): {tally}. Doelwitten (Y): {t}. Het blad staat naast "
                "dit bestand: {file}.",
}

PL = {
    "banner_nr": "NIEGOTOWE: czeka na zatwierdzenie.",
    "nr_dir": "Stanowisko CitizenGO wobec tego projektu nie zostało jeszcze potwierdzone przez "
              "wskazaną osobę.",
    "nr_dir_none": "Nie ma jeszcze zapisanego stanowiska CitizenGO wobec tego projektu.",
    "nr_reads": "Odczyty jego głosowań czekające na potwierdzenie: {n}.",
    "nr_tail": "Nie uruchamiaj kampanii, nie wskazuj celów i niczego nie rekomenduj na podstawie tego "
               "szkicu, dopóki nie zostaną potwierdzone.",
    "banner_ready": "GOTOWE: stanowisko CitizenGO wobec tego projektu i wszystkie odczyty jego "
                    "głosowań są potwierdzone ({who}).",
    "generated": "Szkic wygenerowany {date} z danych parlamentarnych. Fakty pochodzą z tych danych; "
                 "[CAMPAIGNER: ...] oznacza to, co pisze kampanier. Żaden model AI nie napisał tu ani "
                 "słowa.",
    "ph": "[CAMPAIGNER: {0}]",
    "ph_sponsor": "kto go wniósł",
    "ph_stage": "obecny etap",
    "ph_next": "następna kluczowa data (dane jeszcze jej nie podają)",
    "ph_why": "dlaczego to ważne: co zmienia się w prawie lub w praktyce",
    "ph_history": "wcześniejsze kampanie CitizenGO w tej sprawie, z podpisami i linkami",
    "ph_routes": "realne drogi do zwycięstwa, po kolei",
    "ph_ask": "apel, gdy stanowisko CitizenGO wobec tego projektu zostanie potwierdzone",
    "ph_story": "linia narracyjna, gdy stanowisko CitizenGO wobec tego projektu zostanie potwierdzone",
    "ph_villain": "czarny charakter",
    "ph_lead": "zdanie przewodnie: jeśli <działanie>, <adresat> <zachowanie>, ponieważ <punkt nacisku>",
    "ph_whip": "głosowanie swobodne czy dyscyplina klubowa, i czyja",
    "ph_members_seats": "nasi członkowie w każdym okręgu, według kodów pocztowych",
    "ph_injustice": "od 5 do 10 niesprawiedliwości ze źródłami: kto jest krzywdzony, kto to robi, co "
                    "tracą",
    "ph_arguments": "od 5 do 10 argumentów ze źródłami, potem trzy główne argumenty przeciwników z "
                    "naszą odpowiedzią",
    "ph_urgency": "dlaczego teraz: dane nie podają żadnej daty, a terminu nie wolno wymyślać",
    "ph_bad": "zły scenariusz: od 60 do 120 słów konkretnych scen, potem dwie jednozdaniowe wersje",
    "ph_good": "dobry scenariusz: od 60 do 120 słów, potem dwie jednozdaniowe wersje",
    "ph_tim": "do 10 powiązanych petycji z Bluebook (sprzed 12 do 24 miesięcy, ta sama lista)",
    "ph_news": "artykuł prasowy, w języku listy",
    "ph_evidence": "badanie lub raport stojący za najmocniejszym argumentem",
    "ph_minister": "jeśli to projekt rządowy: właściwy minister, z nazwiska, sprawdzony w oficjalnym "
                   "źródle",
    "ph_overlay": "tekst do Canvy, najwyżej sześć słów",
    "ph_rf1": "od 3 do 5 porównywalnych kampanii z Bluebook, ludzie i pieniądze wobec mediany listy",
    "ph_rf2": "od 3 do 5 sojuszników i jak ta kampania im pomaga",
    "ph_rf3": "od 3 do 5 przeciwników z nazwy i ile ich ta kampania kosztuje, ze źródłami",
    "ph_worth": "jedno zdanie ze źródłem o tym, ile zwycięstwo jest warte poza tą kampanią",
    "ph_purpose": "brak daty decyzji w danych: potwierdź cel",
    "bg_what": "Co: {title}.",
    "bg_who": "Kto: {sponsor}. Decyzja należy do: {chamber}.",
    "bg_stage": "Na jakim etapie: {stage} (ostatnie zarejestrowane zdarzenie: {date}).",
    "bg_next": "Co dalej: {next}",
    "bg_next_agenda": "w porządku obrad ({chamber}) {date}.",
    "bg_why": "Dlaczego to ważne: {why}",
    "path_head": "Droga do zwycięstwa:",
    "path_wait": "rachunek głosów czeka na zatwierdzenie odczytów CitizenGO; nikt nie jest jeszcze "
                 "przypisany.",
    "fs_what": "Co",
    "fs_who": "Kto",
    "fs_stage": "Etap",
    "fs_next": "Następna data",
    "fs_5ca": "Podsumowanie 5CA",
    "fs_history": "Nasza historia",
    "fs_none": "brak",
    "type_opp": "Opportunity: domyślnie; nic w danych nie wskazuje na Obligatory ani Survival.",
    "mp_pi": "wskazany organ decyzyjny i kluczowa data w danych.",
    "launch": "{date} (najwcześniej: zgłoszenie plus trzy dni robocze; liczone weekendy, święta nie "
              "sprawdzone)",
    "deliv_key": "{date} (dwa dni robocze przed {key})",
    "deliv_est": "{date} (szacunek: start plus 21 dni; dane nie podają kluczowej daty)",
    "method": "Metoda",
    "m1": "e-maile do posłów ({members}) w trakcie kampanii, jeden na każdy podpis",
    "m2": "w dniu przekazania każdy członek otrzymuje liczbę podpisów ze swojego okręgu",
    "m3": "sfotografowane przekazanie podpisów ({chamber}) i PDF z sumą dla każdego członka",
    "off_handover": "**Przekazanie.** Sfotografowane przekazanie podpisów ({chamber}) {date}. "
                    "Koszt: €. Odpowiada: Media Campaigner.",
    "off_letters": "**Listy do parlamentarzystów.** Sygnatariusze piszą do swoich ({members}) w "
                   "tygodniu przed {date}. Koszt: €. Odpowiada: Media Campaigner.",
    "off_press": "**Konferencja prasowa.** Z zaprzyjaźnionymi ekspertami w dniu przekazania, przed "
                 "budynkiem ({chamber}). Koszt: €€. Odpowiada: Media Campaigner.",
    "off_ads": "**Reklamy kierowane geograficznie.** W okręgach niezdecydowanych, w ostatnich dwóch "
               "tygodniach przed {date}. Koszt: €€. Odpowiada: Media Campaigner.",
    "off_vigil": "**Czuwanie modlitewne.** W pobliżu budynku ({chamber}) w przeddzień {date}, jeśli "
                 "pasuje do listy. Koszt: €. Odpowiada: Media Campaigner.",
    "addr_all": "Wszyscy członkowie: {chamber} ({members}).",
    "addr_split": "Opcja: osobne petycje według segmentu 5CA: niezdecydowani (0/+/-): {p}; sojusznicy "
                  "(++): {a}; zdecydowani przeciwnicy (--): {o}, bez petycji.",
    "ask_against": "Głosować przeciw: {bill}, {when}.",
    "ask_for": "Głosować za: {bill}, {when}.",
    "when_date": "{date}",
    "when_next": "w najbliższym głosowaniu",
    "seg": "Apele według segmentu (przy podziale): niezdecydowani: {ask}; sojusznicy: zabrać głos w "
           "debacie i użyć liczb od swoich wyborców.",
    "lbl_arith": "Arytmetyka głosów",
    "lbl_votes": "Wcześniejsze głosowania",
    "lbl_whip": "Dyscyplina klubowa",
    "lbl_members": "Nasi członkowie w okręgach",
    "seats_line": "mandaty ({chamber}): {parties}.",
    "fca_line": "{a} z nami, {o} przeciw, {p} niezdecydowanych lub bez zapisu ({chamber}).",
    "ev_vote": "{date}: głosowanie ({chamber}) nad '{q}' ({tally}).",
    "ev_stage": "{date}: {title}, etap '{stage}'.",
    "story": "Narracja: czarny charakter = {villain}; księżniczka = niezdecydowani ({members}); "
             "bohater = czytelnik (wyborca); pomocnik = CitizenGO (zanosi podpisy: {chamber}).",
    "u_launch": "**Start ({stage}).** {chamber} zajmie się tym za {dur}.",
    "u_mid": "**Połowa kampanii.** Zostało {dur} do decyzji ({chamber}).",
    "u_final": "**Ostatni tydzień.** Tydzień przed decyzją ({chamber}).",
    "u_48": "**Ostatnie 48 godzin.** Dwa dni przed głosowaniem.",
    "dur_weeks": "{n} tyg.",
    "dur_days": "{n} dni",
    "funds_na": "N/A: e-maile AA mają tylko ogólną stopkę z prośbą o comiesięczną darowiznę.",
    "see_good": "Zob. dobry scenariusz.",
    "see_bad": "Zob. zły scenariusz. Nie stwierdzono ryzyka efektu odwrotnego: oczekiwane 0.",
    "fca_na": "N/A: ten parlament nie publikuje głosów poszczególnych członków, więc nie ma 5CA.",
    "fca_wait": "5CA czeka na zatwierdzenie. Odczyty głosowań nad tym projektem czekające na wskazaną "
                "osobę: {n}. Nikt nie jest przypisany i żaden cel nie jest wskazany, dopóki nie "
                "zostaną potwierdzone.",
    "fca_novote": "Nad tym projektem nie odbyło się jeszcze żadne zarejestrowane głosowanie.",
    "fca_done": "Analiza pięciu kolumn ({chamber}): {tally}. Cele (Y): {t}. Arkusz leży obok tego "
                "pliku: {file}.",
}

HR = {
    "banner_nr": "NIJE SPREMNO: čeka potvrdu.",
    "nr_dir": "Stav CitizenGO-a o ovom prijedlogu još nije potvrdila imenovana osoba.",
    "nr_dir_none": "Stav CitizenGO-a o ovom prijedlogu još nije zabilježen.",
    "nr_reads": "Tumačenja njegovih glasovanja koja čekaju potvrdu: {n}.",
    "nr_tail": "Ne pokrećite kampanju, ne određujte ciljeve i ništa ne preporučujte na temelju ovog "
               "nacrta dok ne budu potvrđena.",
    "banner_ready": "SPREMNO: stav CitizenGO-a o ovom prijedlogu i sva tumačenja njegovih glasovanja "
                    "su potvrđeni ({who}).",
    "generated": "Nacrt izrađen {date} iz parlamentarnih podataka. Činjenice dolaze iz tih podataka; "
                 "[CAMPAIGNER: ...] označava ono što piše voditelj kampanje. Nijedan AI model nije "
                 "napisao ništa od ovoga.",
    "ph": "[CAMPAIGNER: {0}]",
    "ph_sponsor": "tko ga je podnio",
    "ph_stage": "trenutna faza",
    "ph_next": "sljedeći ključni datum (podaci ga još ne navode)",
    "ph_why": "zašto je važno: što se mijenja u zakonu ili praksi",
    "ph_history": "ranije kampanje CitizenGO-a o ovoj temi, s potpisima i poveznicama",
    "ph_routes": "realni putovi do pobjede, redom",
    "ph_ask": "zahtjev, kad stav CitizenGO-a o ovom prijedlogu bude potvrđen",
    "ph_story": "narativna linija, kad stav CitizenGO-a o ovom prijedlogu bude potvrđen",
    "ph_villain": "negativac",
    "ph_lead": "uvodna rečenica: ako <radnja>, <adresat> će <ponašanje>, jer <točka pritiska>",
    "ph_whip": "slobodno glasovanje ili stranačka stega, i čija",
    "ph_members_seats": "naši članovi u svakoj izbornoj jedinici, prema poštanskim brojevima",
    "ph_injustice": "5 do 10 nepravdi s izvorima: tko je oštećen, tko to čini, što gube",
    "ph_arguments": "5 do 10 argumenata s izvorima, zatim tri glavne tvrdnje protivnika s našim "
                    "odgovorom",
    "ph_urgency": "zašto sada: podaci ne navode datum i rok se ne smije izmisliti",
    "ph_bad": "loš ishod: 60 do 120 riječi konkretnih prizora, zatim dvije varijante od jednog retka",
    "ph_good": "dobar ishod: 60 do 120 riječi, zatim dvije varijante od jednog retka",
    "ph_tim": "do 10 povezanih peticija iz Bluebooka (prije 12 do 24 mjeseca, ista lista)",
    "ph_news": "novinski članak, na jeziku liste",
    "ph_evidence": "studija ili izvješće iza najjačeg argumenta",
    "ph_minister": "ako je vladin prijedlog: nadležni ministar, imenom i provjeren u službenom izvoru",
    "ph_overlay": "tekst za Canvu, najviše šest riječi",
    "ph_rf1": "3 do 5 usporedivih kampanja iz Bluebooka, ljudi i novac prema medijanu liste",
    "ph_rf2": "3 do 5 saveznika i kako im ova kampanja pomaže",
    "ph_rf3": "3 do 5 imenovanih protivnika i što ih ova kampanja stoji, s izvorima",
    "ph_worth": "jedan redak s izvorom o tome koliko pobjeda vrijedi izvan ove kampanje",
    "ph_purpose": "u podacima nema datuma odluke: potvrdite svrhu",
    "bg_what": "Što: {title}.",
    "bg_who": "Tko: {sponsor}. Odluka je na: {chamber}.",
    "bg_stage": "Gdje je: {stage} (posljednji zabilježeni događaj: {date}).",
    "bg_next": "Sljedeći korak: {next}",
    "bg_next_agenda": "na dnevnom redu ({chamber}) {date}.",
    "bg_why": "Zašto je važno: {why}",
    "path_head": "Put do pobjede:",
    "path_wait": "zbroj glasova čeka potvrdu tumačenja CitizenGO-a; još nitko nije svrstan.",
    "fs_what": "Što",
    "fs_who": "Tko",
    "fs_stage": "Faza",
    "fs_next": "Sljedeći datum",
    "fs_5ca": "Sažetak 5CA",
    "fs_history": "Naša povijest",
    "fs_none": "nije objavljen",
    "type_opp": "Opportunity: zadana vrijednost; ništa u podacima ne upućuje na Obligatory ili "
                "Survival.",
    "mp_pi": "imenovano tijelo odlučivanja i ključni datum u podacima.",
    "launch": "{date} (najranije: podnošenje plus tri radna dana; vikendi uračunati, praznici nisu "
              "provjereni)",
    "deliv_key": "{date} (dva radna dana prije {key})",
    "deliv_est": "{date} (procjena: početak plus 21 dan; podaci ne navode ključni datum)",
    "method": "Način",
    "m1": "e-poruke zastupnicima ({members}) tijekom kampanje, jedna po potpisu",
    "m2": "na dan predaje svaki član dobiva broj potpisa iz svoje izborne jedinice",
    "m3": "fotografirana predaja ({chamber}) i PDF s ukupnim brojem za svakog člana",
    "off_handover": "**Predaja.** Fotografirana predaja potpisa ({chamber}) {date}. Trošak: €. "
                    "Nositelj: Media Campaigner.",
    "off_letters": "**Pisma zastupnicima.** Potpisnici pišu svojim zastupnicima ({members}) u tjednu "
                   "prije {date}. Trošak: €. Nositelj: Media Campaigner.",
    "off_press": "**Konferencija za medije.** S prijateljskim stručnjacima na dan predaje, ispred "
                 "zgrade ({chamber}). Trošak: €€. Nositelj: Media Campaigner.",
    "off_ads": "**Geografski ciljani oglasi.** U izbornim jedinicama neodlučnih, u posljednja dva "
               "tjedna prije {date}. Trošak: €€. Nositelj: Media Campaigner.",
    "off_vigil": "**Molitveno bdjenje.** U blizini zgrade ({chamber}) uoči {date}, ako odgovara "
                 "listi. Trošak: €. Nositelj: Media Campaigner.",
    "addr_all": "Svi članovi: {chamber} ({members}).",
    "addr_split": "Opcija: zasebne peticije po segmentu 5CA: neodlučni (0/+/-): {p}; saveznici (++): "
                  "{a}; čvrsti protivnici (--): {o}, bez peticije.",
    "ask_against": "Glasati protiv: {bill}, {when}.",
    "ask_for": "Glasati za: {bill}, {when}.",
    "when_date": "{date}",
    "when_next": "na sljedećem glasovanju",
    "seg": "Zahtjevi po segmentu (ako se dijeli): neodlučni: {ask}; saveznici: govoriti u raspravi i "
           "koristiti brojke svojih birača.",
    "lbl_arith": "Aritmetika glasova",
    "lbl_votes": "Ranija glasovanja",
    "lbl_whip": "Stranačka stega",
    "lbl_members": "Naši članovi u izbornim jedinicama",
    "seats_line": "mjesta ({chamber}): {parties}.",
    "fca_line": "{a} s nama, {o} protiv, {p} neodlučnih ili bez zapisa ({chamber}).",
    "ev_vote": "{date}: glasovanje ({chamber}) o '{q}' ({tally}).",
    "ev_stage": "{date}: {title}, faza '{stage}'.",
    "story": "Priča: negativac = {villain}; princeza = neodlučni zastupnici ({members}); junak = "
             "čitatelj (birač); pomagač = CitizenGO (nosi potpise: {chamber}).",
    "u_launch": "**Početak ({stage}).** {chamber} o tome raspravlja za {dur}.",
    "u_mid": "**Sredina kampanje.** Ostaje {dur} do odluke ({chamber}).",
    "u_final": "**Posljednji tjedan.** Tjedan dana prije odluke ({chamber}).",
    "u_48": "**Posljednjih 48 sati.** Dva dana prije glasovanja.",
    "dur_weeks": "{n} tj.",
    "dur_days": "{n} dana",
    "funds_na": "N/A: AA e-poruke nose samo opće podnožje za mjesečnu donaciju.",
    "see_good": "Vidi dobar ishod.",
    "see_bad": "Vidi loš ishod. Nije utvrđen rizik od suprotnog učinka: očekuje se 0.",
    "fca_na": "N/A: ovaj parlament ne objavljuje pojedinačne glasove, pa nema 5CA.",
    "fca_wait": "5CA čeka potvrdu. Tumačenja glasovanja o ovom prijedlogu koja čekaju imenovanu osobu: "
                "{n}. Nitko nije svrstan i nijedan cilj nije određen dok ne budu potvrđena.",
    "fca_novote": "O ovom prijedlogu još nema zabilježenog glasovanja.",
    "fca_done": "Analiza pet stupaca ({chamber}): {tally}. Ciljevi (Y): {t}. Tablica je uz ovu "
                "datoteku: {file}.",
}

SK = {
    "banner_nr": "NIE JE PRIPRAVENÉ: čaká na potvrdenie.",
    "nr_dir": "Stanovisko CitizenGO k tomuto návrhu zatiaľ nepotvrdila určená osoba.",
    "nr_dir_none": "K tomuto návrhu zatiaľ nie je zaznamenané žiadne stanovisko CitizenGO.",
    "nr_reads": "Výklady jeho hlasovaní čakajúce na potvrdenie: {n}.",
    "nr_tail": "Nespúšťajte kampaň, neurčujte ciele a nič neodporúčajte na základe tohto návrhu, "
               "kým nebudú potvrdené.",
    "banner_ready": "PRIPRAVENÉ: stanovisko CitizenGO k tomuto návrhu a všetky výklady jeho hlasovaní "
                    "sú potvrdené ({who}).",
    "generated": "Návrh vytvorený {date} z parlamentných údajov. Fakty pochádzajú z týchto údajov; "
                 "[CAMPAIGNER: ...] označuje to, čo píše kampaňový pracovník. Žiadny model AI tu "
                 "nenapísal ani slovo.",
    "ph": "[CAMPAIGNER: {0}]",
    "ph_sponsor": "kto ho predložil",
    "ph_stage": "aktuálna fáza",
    "ph_next": "ďalší kľúčový dátum (údaje zatiaľ žiadny neuvádzajú)",
    "ph_why": "prečo je to dôležité: čo sa mení v zákone alebo v praxi",
    "ph_history": "predchádzajúce kampane CitizenGO k téme, s podpismi a odkazmi",
    "ph_routes": "reálne cesty k víťazstvu, v poradí",
    "ph_ask": "výzva, keď bude stanovisko CitizenGO k tomuto návrhu potvrdené",
    "ph_story": "príbehová línia, keď bude stanovisko CitizenGO k tomuto návrhu potvrdené",
    "ph_villain": "záporák",
    "ph_lead": "úvodná veta: ak <akcia>, <adresát> <správanie>, pretože <bod tlaku>",
    "ph_whip": "voľné hlasovanie alebo klubová disciplína, a čia",
    "ph_members_seats": "naši členovia v jednotlivých regiónoch, podľa PSČ",
    "ph_injustice": "5 až 10 nespravodlivostí so zdrojmi: kto je poškodený, kto to robí, čo strácajú",
    "ph_arguments": "5 až 10 argumentov so zdrojmi, potom tri hlavné tvrdenia odporcov s našou "
                    "odpoveďou",
    "ph_urgency": "prečo teraz: údaje neuvádzajú žiadny dátum a lehotu nemožno vymyslieť",
    "ph_bad": "zlý výsledok: 60 až 120 slov konkrétnych scén, potom dve jednoriadkové varianty",
    "ph_good": "dobrý výsledok: 60 až 120 slov, potom dve jednoriadkové varianty",
    "ph_tim": "do 10 súvisiacich petícií z Bluebooku (spred 12 až 24 mesiacov, rovnaký zoznam)",
    "ph_news": "spravodajský článok, v jazyku zoznamu",
    "ph_evidence": "štúdia alebo správa za najsilnejším argumentom",
    "ph_minister": "ak ide o vládny návrh: zodpovedný minister, menom a overený v úradnom zdroji",
    "ph_overlay": "text pre Canvu, najviac šesť slov",
    "ph_rf1": "3 až 5 porovnateľných kampaní z Bluebooku, ľudia a peniaze oproti mediánu zoznamu",
    "ph_rf2": "3 až 5 spojencov a ako im táto kampaň pomáha",
    "ph_rf3": "3 až 5 menovaných odporcov a čo ich táto kampaň stojí, so zdrojmi",
    "ph_worth": "jeden riadok so zdrojom o tom, akú hodnotu má víťazstvo nad rámec tejto kampane",
    "ph_purpose": "v údajoch nie je dátum rozhodnutia: potvrďte účel",
    "bg_what": "Čo: {title}.",
    "bg_who": "Kto: {sponsor}. Rozhoduje: {chamber}.",
    "bg_stage": "Kde je: {stage} (posledná zaznamenaná udalosť: {date}).",
    "bg_next": "Čo ďalej: {next}",
    "bg_next_agenda": "v programe schôdze ({chamber}) {date}.",
    "bg_why": "Prečo je to dôležité: {why}",
    "path_head": "Cesta k víťazstvu:",
    "path_wait": "počty hlasov čakajú na potvrdenie výkladov CitizenGO; zatiaľ nikto nie je zaradený.",
    "fs_what": "Čo",
    "fs_who": "Kto",
    "fs_stage": "Fáza",
    "fs_next": "Ďalší dátum",
    "fs_5ca": "Súhrn 5CA",
    "fs_history": "Naša história",
    "fs_none": "neuvedený",
    "type_opp": "Opportunity: predvolené; nič v údajoch nesvedčí o Obligatory ani Survival.",
    "mp_pi": "určený rozhodovací orgán a kľúčový dátum v údajoch.",
    "launch": "{date} (najskôr: podanie plus tri pracovné dni; víkendy započítané, sviatky "
              "neoverené)",
    "deliv_key": "{date} (dva pracovné dni pred {key})",
    "deliv_est": "{date} (odhad: spustenie plus 21 dní; údaje neuvádzajú kľúčový dátum)",
    "method": "Spôsob",
    "m1": "e-maily poslancom ({members}) počas kampane, jeden za každý podpis",
    "m2": "v deň odovzdania dostane každý poslanec počet podpisov zo svojho regiónu",
    "m3": "fotografované odovzdanie ({chamber}) a PDF s celkovým počtom pre každého poslanca",
    "off_handover": "**Odovzdanie.** Fotografované odovzdanie podpisov ({chamber}) {date}. "
                    "Náklady: €. Zodpovedá: Media Campaigner.",
    "off_letters": "**Listy poslancom.** Signatári píšu svojim poslancom ({members}) v týždni pred "
                   "{date}. Náklady: €. Zodpovedá: Media Campaigner.",
    "off_press": "**Tlačová konferencia.** So spriatelenými odborníkmi v deň odovzdania, pred budovou "
                 "({chamber}). Náklady: €€. Zodpovedá: Media Campaigner.",
    "off_ads": "**Geograficky cielené reklamy.** V regiónoch nerozhodnutých, v posledných dvoch "
               "týždňoch pred {date}. Náklady: €€. Zodpovedá: Media Campaigner.",
    "off_vigil": "**Modlitebné bdenie.** Pri budove ({chamber}) v predvečer {date}, ak sa hodí k "
                 "zoznamu. Náklady: €. Zodpovedá: Media Campaigner.",
    "addr_all": "Všetci členovia: {chamber} ({members}).",
    "addr_split": "Možnosť: samostatné petície podľa segmentu 5CA: nerozhodnutí (0/+/-): {p}; "
                  "spojenci (++): {a}; pevní odporcovia (--): {o}, bez petície.",
    "ask_against": "Hlasovať proti: {bill}, {when}.",
    "ask_for": "Hlasovať za: {bill}, {when}.",
    "when_date": "{date}",
    "when_next": "pri najbližšom hlasovaní",
    "seg": "Výzvy podľa segmentu (pri rozdelení): nerozhodnutí: {ask}; spojenci: vystúpiť v rozprave "
           "a použiť čísla od svojich voličov.",
    "lbl_arith": "Aritmetika hlasov",
    "lbl_votes": "Predchádzajúce hlasovania",
    "lbl_whip": "Klubová disciplína",
    "lbl_members": "Naši členovia v regiónoch",
    "seats_line": "kreslá ({chamber}): {parties}.",
    "fca_line": "{a} s nami, {o} proti, {p} nerozhodnutých alebo bez záznamu ({chamber}).",
    "ev_vote": "{date}: hlasovanie ({chamber}) o '{q}' ({tally}).",
    "ev_stage": "{date}: {title}, fáza '{stage}'.",
    "story": "Príbeh: záporák = {villain}; princezná = nerozhodnutí poslanci ({members}); hrdina = "
             "čitateľ (volič); pomocník = CitizenGO (prináša podpisy: {chamber}).",
    "u_launch": "**Spustenie ({stage}).** {chamber} sa tým bude zaoberať o {dur}.",
    "u_mid": "**Polovica kampane.** Zostáva {dur} do rozhodnutia ({chamber}).",
    "u_final": "**Posledný týždeň.** Týždeň pred rozhodnutím ({chamber}).",
    "u_48": "**Posledných 48 hodín.** Dva dni pred hlasovaním.",
    "dur_weeks": "{n} týž.",
    "dur_days": "{n} dní",
    "funds_na": "N/A: e-maily AA nesú len všeobecnú pätičku pre mesačný dar.",
    "see_good": "Pozri dobrý výsledok.",
    "see_bad": "Pozri zlý výsledok. Riziko opačného účinku nezistené: očakáva sa 0.",
    "fca_na": "N/A: tento parlament nezverejňuje hlasovanie jednotlivých poslancov, preto 5CA nie je.",
    "fca_wait": "5CA čaká na potvrdenie. Výklady hlasovaní o tomto návrhu, ktoré čakajú na určenú "
                "osobu: {n}. Nikto nie je zaradený a žiadny cieľ nie je určený, kým nebudú potvrdené.",
    "fca_novote": "O tomto návrhu sa zatiaľ nehlasovalo.",
    "fca_done": "Analýza piatich stĺpcov ({chamber}): {tally}. Ciele (Y): {t}. Hárok je vedľa tohto "
                "súboru: {file}.",
}

HU = {
    "banner_nr": "NEM KÉSZ: jóváhagyásra vár.",
    "nr_dir": "A CitizenGO álláspontját erről a javaslatról még nem erősítette meg kijelölt személy.",
    "nr_dir_none": "Erről a javaslatról még nincs rögzítve a CitizenGO álláspontja.",
    "nr_reads": "A szavazásainak megerősítésre váró értelmezései: {n}.",
    "nr_tail": "Ebből a tervezetből ne indíts kampányt, ne jelölj ki célpontot és ne ajánlj semmit, "
               "amíg ezek nincsenek megerősítve.",
    "banner_ready": "KÉSZ: a CitizenGO álláspontja erről a javaslatról és szavazásainak minden "
                    "értelmezése megerősítve ({who}).",
    "generated": "A tervezet {date}-án készült a parlamenti adatokból. A tények ezekből az adatokból "
                 "származnak; a [CAMPAIGNER: ...] jelzi, mit ír a kampányfelelős. Ebből semmit sem "
                 "írt MI-modell.",
    "ph": "[CAMPAIGNER: {0}]",
    "ph_sponsor": "ki nyújtotta be",
    "ph_stage": "a jelenlegi szakasz",
    "ph_next": "a következő fontos dátum (az adatok még nem közölnek ilyet)",
    "ph_why": "miért fontos: mi változik a jogban vagy a gyakorlatban",
    "ph_history": "a CitizenGO korábbi kampányai a témában, aláírásokkal és linkekkel",
    "ph_routes": "a győzelemhez vezető reális utak, sorrendben",
    "ph_ask": "a kérés, amint a CitizenGO álláspontja erről a javaslatról megerősítést nyer",
    "ph_story": "a történetvezetés, amint a CitizenGO álláspontja erről a javaslatról megerősítést nyer",
    "ph_villain": "a gonosz",
    "ph_lead": "a vezérmondat: ha <cselekvés>, <címzett> <viselkedés>, mert <nyomásgyakorlási pont>",
    "ph_whip": "szabad szavazás vagy frakciófegyelem, és kié",
    "ph_members_seats": "tagjaink választókerületenként, az irányítószámok alapján",
    "ph_injustice": "5-10 forrással alátámasztott igazságtalanság: kit ér kár, ki okozza, mit "
                    "veszítenek",
    "ph_arguments": "5-10 forrással alátámasztott érv, majd az ellenfelek három fő állítása a "
                    "válaszunkkal",
    "ph_urgency": "miért most: az adatok nem közölnek dátumot, határidőt kitalálni nem szabad",
    "ph_bad": "a rossz kimenet: 60-120 szó konkrét jelenetekkel, majd két egysoros változat",
    "ph_good": "a jó kimenet: 60-120 szó, majd két egysoros változat",
    "ph_tim": "legfeljebb 10 kapcsolódó petíció a Bluebookból (12-24 hónapja, ugyanaz a lista)",
    "ph_news": "egy hírcikk, a lista nyelvén",
    "ph_evidence": "a legerősebb érv mögötti tanulmány vagy jelentés",
    "ph_minister": "ha kormányjavaslat: a felelős miniszter, névvel, hivatalos forrásból ellenőrizve",
    "ph_overlay": "felirat a Canvához, legfeljebb hat szó",
    "ph_rf1": "3-5 összehasonlítható kampány a Bluebookból, emberek és pénz a lista mediánjához "
              "képest",
    "ph_rf2": "3-5 szövetséges, és hogyan segíti őket ez a kampány",
    "ph_rf3": "3-5 megnevezett ellenfél, és mibe kerül nekik ez a kampány, forrással",
    "ph_worth": "egy forrással alátámasztott sor arról, mit ér a győzelem e kampányon túl",
    "ph_purpose": "az adatokban nincs döntési dátum: erősítsd meg a célt",
    "bg_what": "Mi: {title}.",
    "bg_who": "Ki: {sponsor}. A döntés: {chamber}.",
    "bg_stage": "Hol tart: {stage} (utolsó rögzített esemény: {date}).",
    "bg_next": "Következő lépés: {next}",
    "bg_next_agenda": "napirenden ({chamber}) {date}.",
    "bg_why": "Miért fontos: {why}",
    "path_head": "Út a győzelemhez:",
    "path_wait": "a szavazatszámítás a CitizenGO értelmezéseinek jóváhagyására vár; még senki sincs "
                 "besorolva.",
    "fs_what": "Mi",
    "fs_who": "Ki",
    "fs_stage": "Szakasz",
    "fs_next": "Következő dátum",
    "fs_5ca": "5CA összefoglaló",
    "fs_history": "Előzményeink",
    "fs_none": "nincs közzétéve",
    "type_opp": "Opportunity: az alapértelmezés; az adatokban semmi sem utal Obligatory vagy Survival "
                "típusra.",
    "mp_pi": "megnevezett döntéshozó testület és fontos dátum az adatokban.",
    "launch": "{date} (legkorábban: beadás plusz három munkanap; hétvégék beszámítva, ünnepnapok "
              "nincsenek ellenőrizve)",
    "deliv_key": "{date} (két munkanappal {key} előtt)",
    "deliv_est": "{date} (becslés: indulás plusz 21 nap; az adatok nem közölnek fontos dátumot)",
    "method": "Módszer",
    "m1": "e-mailek a képviselőknek ({members}) a kampány alatt, aláírásonként egy",
    "m2": "az átadás napján minden képviselő megkapja a saját választókerületéből érkezett aláírások "
          "számát",
    "m3": "fényképes átadás ({chamber}) és egy PDF az összesítéssel minden képviselőnek",
    "off_handover": "**Átadás.** Az aláírások fényképes átadása ({chamber}) {date}. Költség: €. "
                    "Felelős: Media Campaigner.",
    "off_letters": "**Levelek a képviselőknek.** Az aláírók a {date} előtti héten saját "
                   "képviselőiknek ({members}) írnak. Költség: €. Felelős: Media Campaigner.",
    "off_press": "**Sajtótájékoztató.** Szövetséges szakértőkkel az átadás napján, az épület előtt "
                 "({chamber}). Költség: €€. Felelős: Media Campaigner.",
    "off_ads": "**Földrajzilag célzott hirdetések.** A bizonytalanok választókerületeiben, a {date} "
               "előtti utolsó két hétben. Költség: €€. Felelős: Media Campaigner.",
    "off_vigil": "**Imavirrasztás.** Az épület közelében ({chamber}) {date} előestéjén, ha illik a "
                 "listához. Költség: €. Felelős: Media Campaigner.",
    "addr_all": "Minden tag: {chamber} ({members}).",
    "addr_split": "Lehetőség: külön petíciók 5CA-szegmensenként: bizonytalanok (0/+/-): {p}; "
                  "szövetségesek (++): {a}; határozott ellenfelek (--): {o}, petíció nélkül.",
    "ask_against": "Szavazzanak ellene: {bill}, {when}.",
    "ask_for": "Szavazzanak mellette: {bill}, {when}.",
    "when_date": "{date}",
    "when_next": "a következő szavazáson",
    "seg": "Kérések szegmensenként (ha szétválasztjuk): bizonytalanok: {ask}; szövetségesek: "
           "szólaljanak fel a vitában, és használják választóik számait.",
    "lbl_arith": "Szavazati számtan",
    "lbl_votes": "Korábbi szavazások",
    "lbl_whip": "Frakciófegyelem",
    "lbl_members": "Tagjaink a választókerületekben",
    "seats_line": "mandátumok ({chamber}): {parties}.",
    "fca_line": "{a} velünk, {o} ellenünk, {p} bizonytalan vagy adat nélkül ({chamber}).",
    "ev_vote": "{date}: szavazás ({chamber}) erről: '{q}' ({tally}).",
    "ev_stage": "{date}: {title}, szakasz: '{stage}'.",
    "story": "Történet: gonosz = {villain}; királylány = a még bizonytalan képviselők ({members}); "
             "hős = az olvasó (egy választó); segítő = a CitizenGO (elviszi az aláírásokat: "
             "{chamber}).",
    "u_launch": "**Indulás ({stage}).** {chamber}: {dur} múlva tárgyalja.",
    "u_mid": "**A kampány közepe.** {dur} van hátra a döntésig ({chamber}).",
    "u_final": "**Utolsó hét.** Egy héttel a döntés előtt ({chamber}).",
    "u_48": "**Utolsó 48 óra.** Két nappal a szavazás előtt.",
    "dur_weeks": "{n} hét",
    "dur_days": "{n} nap",
    "funds_na": "N/A: az AA e-mailek csak az általános havi adományozási láblécet tartalmazzák.",
    "see_good": "Lásd a jó kimenetet.",
    "see_bad": "Lásd a rossz kimenetet. Visszahatás kockázata nem azonosítható: várható érték 0.",
    "fca_na": "N/A: ez a parlament nem közli az egyes képviselők szavazatait, így nincs 5CA.",
    "fca_wait": "Az 5CA jóváhagyásra vár. A javaslat szavazásainak kijelölt személyre váró "
                "értelmezései: {n}. Amíg nincsenek megerősítve, senki sincs besorolva és nincs "
                "célpont kijelölve.",
    "fca_novote": "Erről a javaslatról még nincs rögzített szavazás.",
    "fca_done": "Ötoszlopos elemzés ({chamber}): {tally}. Célpontok (Y): {t}. A táblázat e fájl "
                "mellett van: {file}.",
}

LANGUAGES = {"en": EN, "es": ES, "pt": PT, "it": IT, "fr": FR, "de": DE, "nl": NL, "pl": PL,
             "hr": HR, "sk": SK, "hu": HU}


def phrases(lang, swiss=False):
    """The phrase table for a language code, English for an unknown one.
    `swiss` writes "ss" for "ß" (rulebook cell 16: Swiss German)."""
    table = dict(LANGUAGES.get(lang) or EN)
    if swiss:
        table = {k: v.replace("ß", "ss") for k, v in table.items()}
    return table
