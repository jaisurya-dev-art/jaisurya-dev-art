"""Builds the profile's cards (stats, languages, one per pinned project) as SVG, in a dark and a light
version, from the GitHub API. Public repositories only. Usage: python cards.py <user> <out-dir>
(needs GITHUB_TOKEN). Run daily by .github/workflows/profile.yml."""
import html, json, os, sys, urllib.request

USER, OUT = sys.argv[1], sys.argv[2]
PINS = ['Mayflower-glTF', 'ComfyUI-ModelRouter', 'ComfyUI-AssetSync', 'ComfyUI-MaterialSync']
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
THEMES = {
    'dark': dict(bg='#0d1117', border='#30363d', title='#7ba7c7', text='#c9d1d9', weak='#8b949e', bar='#21262d'),
    'light': dict(bg='#ffffff', border='#d0d7de', title='#3b6f96', text='#24292f', weak='#57606a', bar='#eaeef2'),
}

QUERY = '''query($login: String!) { user(login: $login) {
  followers { totalCount }
  pullRequests { totalCount }
  issues { totalCount }
  repositoriesContributedTo(first: 1, contributionTypes: [COMMIT, PULL_REQUEST, ISSUE]) { totalCount }
  contributionsCollection { totalCommitContributions restrictedContributionsCount }
  repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) { nodes {
    name description stargazerCount forkCount
    primaryLanguage { name color }
    languages(first: 10, orderBy: { field: SIZE, direction: DESC }) { edges { size node { name color } } }
  } }
} }'''


def api():
    req = urllib.request.Request('https://api.github.com/graphql', json.dumps({'query': QUERY, 'variables': {'login': USER}}).encode(),
                                 {'Authorization': f"bearer {os.environ['GITHUB_TOKEN']}", 'Content-Type': 'application/json'})
    data = json.load(urllib.request.urlopen(req))
    if 'errors' in data:
        raise SystemExit(data['errors'])
    return data['data']['user']


def esc(s):
    return html.escape(str(s), quote=True)


def card(w, h, t, body, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}">'
            f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="10" fill="{t["bg"]}" stroke="{t["border"]}"/>'
            f'<g font-family="{FONT}">{body}</g></svg>')


def wrap(text, width):
    lines, line = [], ''
    for word in (text or '').split():
        if len(line) + len(word) + 1 > width:
            lines.append(line)
            line = word
        else:
            line = f'{line} {word}'.strip()
    if line:
        lines.append(line)
    if len(lines) > 2:
        lines = lines[:2]
        lines[1] = lines[1][: width - 1].rstrip() + '…'
    return lines


def fmt(n):
    return f'{n / 1000:.1f}k' if n >= 1000 else str(n)


def stats_card(u, repos, t):
    c = u['contributionsCollection']
    rows = [
        ('Stars earned', sum(r['stargazerCount'] for r in repos)),
        ('Commits this year', c['totalCommitContributions'] + c['restrictedContributionsCount']),
        ('Pull requests', u['pullRequests']['totalCount']),
        ('Issues', u['issues']['totalCount']),
        ('Contributed to', u['repositoriesContributedTo']['totalCount']),
    ]
    body = f'<text x="25" y="38" fill="{t["title"]}" font-size="17" font-weight="600">GitHub</text>'
    for i, (label, value) in enumerate(rows):
        y = 74 + i * 25
        body += (f'<text x="25" y="{y}" fill="{t["weak"]}" font-size="14">{label}</text>'
                 f'<text x="300" y="{y}" fill="{t["text"]}" font-size="14" font-weight="600" text-anchor="end">{fmt(value)}</text>')
    big = sum(r['stargazerCount'] for r in repos)
    body += (f'<circle cx="400" cy="100" r="46" fill="none" stroke="{t["bar"]}" stroke-width="7"/>'
             f'<circle cx="400" cy="100" r="46" fill="none" stroke="{t["title"]}" stroke-width="7" stroke-linecap="round" '
             f'stroke-dasharray="{min(big / 500, 1) * 289:.1f} 289" transform="rotate(-90 400 100)"/>'
             f'<text x="400" y="104" fill="{t["text"]}" font-size="24" font-weight="700" text-anchor="middle">{fmt(big)}</text>'
             f'<text x="400" y="124" fill="{t["weak"]}" font-size="11" text-anchor="middle">stars</text>')
    return card(495, 195, t, body, 'GitHub stats')


def langs_card(repos, t):
    sizes, colors = {}, {}
    for r in repos:
        for e in r['languages']['edges']:
            n = e['node']['name']
            sizes[n] = sizes.get(n, 0) + e['size']
            colors[n] = e['node']['color'] or '#8b949e'
    top = sorted(sizes.items(), key=lambda kv: -kv[1])[:8]
    total = sum(v for _, v in top) or 1
    body = f'<text x="25" y="38" fill="{t["title"]}" font-size="17" font-weight="600">Languages</text>'
    body += f'<clipPath id="bar"><rect x="25" y="56" width="445" height="10" rx="5"/></clipPath><g clip-path="url(#bar)">'
    x = 25.0
    for name, size in top:
        w = 445 * size / total
        body += f'<rect x="{x:.2f}" y="56" width="{w + 0.5:.2f}" height="10" fill="{colors[name]}"/>'
        x += w
    body += '</g>'
    for i, (name, size) in enumerate(top):
        cx, cy = 25 + (i % 2) * 225, 96 + (i // 2) * 25
        body += (f'<circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{colors[name]}"/>'
                 f'<text x="{cx + 17}" y="{cy}" fill="{t["text"]}" font-size="13">{esc(name)}</text>'
                 f'<text x="{cx + 205}" y="{cy}" fill="{t["weak"]}" font-size="13" text-anchor="end">{100 * size / total:.1f}%</text>')
    return card(495, 195, t, body, 'Top languages')


def pin_card(r, t):
    body = f'<text x="25" y="38" fill="{t["title"]}" font-size="17" font-weight="600">{esc(r["name"])}</text>'
    for i, line in enumerate(wrap(r['description'], 58)):
        body += f'<text x="25" y="{68 + i * 21}" fill="{t["weak"]}" font-size="13.5">{esc(line)}</text>'
    lang = r['primaryLanguage']
    x = 25
    if lang:
        body += (f'<circle cx="{x + 6}" cy="{126}" r="6" fill="{lang["color"] or t["weak"]}"/>'
                 f'<text x="{x + 18}" y="131" fill="{t["text"]}" font-size="13">{esc(lang["name"])}</text>')
        x += 30 + 8 * len(lang['name'])
    body += (f'<text x="{x}" y="131" fill="{t["text"]}" font-size="13">★ {fmt(r["stargazerCount"])}</text>'
             f'<text x="{x + 52}" y="131" fill="{t["text"]}" font-size="13">⑂ {fmt(r["forkCount"])}</text>')
    return card(400, 150, t, body, r['name'])


def main():
    u = api()
    repos = u['repositories']['nodes']
    by_name = {r['name']: r for r in repos}
    os.makedirs(OUT, exist_ok=True)
    for theme, t in THEMES.items():
        write(f'stats-{theme}.svg', stats_card(u, repos, t))
        write(f'langs-{theme}.svg', langs_card(repos, t))
        for name in PINS:
            if name in by_name:
                write(f'pin-{name}-{theme}.svg', pin_card(by_name[name], t))


def write(name, svg):
    with open(os.path.join(OUT, name), 'w', encoding='utf-8') as f:
        f.write(svg)


main()
