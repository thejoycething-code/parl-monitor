"""Rough area-term scan over data/raw/ve-probe/news.json (scope probe only; noisy, hand-check hits)."""
import json, re, collections, sys
items = json.load(open('data/raw/ve-probe/news.json'))
AREAS = {
 'life': r'\baborto|\babortiv|interrupci[oó]n (voluntaria )?del embarazo|despenaliz|no nacid|derecho a la vida|\bembri[oó]n',
 'euthanasia': r'eutanasia|muerte digna|suicidio asistido|cuidados paliativos',
 'family_marriage': r'matrimonio igualitario|matrimonio entre personas del mismo sexo|uni[oó]n(es)? civil|uni[oó]n(es)? estable|concubinato|protecci[oó]n (de|a) la familia|patria potestad|adopci[oó]n|tutela|divorcio',
 'gender': r'identidad de g[eé]nero|ideolog[ií]a de g[eé]nero|\btrans(g[eé]nero|exual)|LGBT|LGTB|sexo diverso|sexodivers|orientaci[oó]n sexual|perspectiva de g[eé]nero|cambio de sexo',
 'education_parental': r'educaci[oó]n sexual|educaci[oó]n integral de la sexualidad|\bESI\b|curr[ií]culo|pensum|padres y representantes|libertad de educaci[oó]n|ley org[aá]nica de educaci[oó]n',
 'religion': r'libertad religiosa|libertad de religi[oó]n|libertad de culto|\bcultos\b|iglesia|evang[eé]lic|cat[oó]lic|religios',
 'speech': r'ley contra el odio|discurso de odio|incitaci[oó]n al odio|libertad de expresi[oó]n|censura|redes sociales|fake news|noticias falsas',
 'children': r'ni[ñn]as, ni[ñn]os y adolescentes|LOPNNA|protecci[oó]n de ni[ñn]',
 'surrogacy_bio': r'gestaci[oó]n subrogada|vientres? de alquiler|reproducci[oó]n asistida|fecundaci[oó]n in vitro',
 'drugs_porn': r'pornograf|prostituci[oó]n|trata de personas|legalizaci[oó]n de (la )?(marihuana|cannabis|drogas)',
}
VOTE = r'unanimidad|por mayor[ií]a|votos a favor|votos en contra|abstenci[oó]n|votaci[oó]n nominal|votaron'
TALLY = r'\b\d{2,3}\s+votos\b|\bcon (el voto|los votos) (de|en contra)'
hits = collections.Counter(); ex = collections.defaultdict(list)
vote = tally = sanc = 0
for i in items:
    body = i['text']
    # strip site chrome: keep text after the title occurrence
    
    i['body'] = body
    if re.search(VOTE, body, re.I): vote += 1
    if re.search(TALLY, body, re.I): tally += 1
    if re.search(r'sancion', i['title'], re.I): sanc += 1
    for a, rx in AREAS.items():
        if re.search(rx, i['title'] + ' ' + body[:4000], re.I):
            hits[a] += 1; ex[a].append((i['date'], i['title']))
print('items', len(items), 'range', items[-1]['date'], items[0]['date'])
print('vote language', vote, 'numeric tally', tally, 'sanciona in title', sanc)
any_hit = sum(1 for i in items if any(re.search(rx, i['title']+' '+i['body'][:4000], re.I) for rx in AREAS.values()))
print('any area', any_hit)
for a, n in hits.most_common():
    print(f'\n{a}: {n}')
    for d, t in ex[a][:int(sys.argv[1]) if len(sys.argv)>1 else 6]: print('  ', d, t)
