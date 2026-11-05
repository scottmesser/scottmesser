"""Render only the contribution counts already visible on Scott's public profile."""

import argparse
from datetime import date, datetime, timezone
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.request import Request, urlopen


class CalendarParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cells = {}
        self.tooltips = {}
        self.target = None
        self.heading = False
        self.heading_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'td' and 'data-date' in attrs:
            self.cells[attrs['id']] = attrs['data-date']
        if tag == 'tool-tip':
            self.target = attrs.get('for')
            if self.target:
                self.tooltips[self.target] = ''
        if tag == 'h2':
            self.heading = True

    def handle_data(self, value):
        if self.target:
            self.tooltips[self.target] += value
        if self.heading:
            self.heading_parts.append(value)

    def handle_endtag(self, tag):
        if tag == 'tool-tip':
            self.target = None
        if tag == 'h2':
            self.heading = False


def parse_calendar(html):
    parser = CalendarParser()
    parser.feed(html)
    heading = re.search(r'([\d,]+)\s+contributions?\s+in the last year', ' '.join(parser.heading_parts))
    if not heading or not 360 <= len(parser.cells) <= 380:
        raise ValueError('Public contribution calendar format changed; keeping the existing card.')
    days = []
    for cell_id, value in parser.cells.items():
        text = parser.tooltips.get(cell_id, '').strip()
        count = re.match(r'([\d,]+) contributions? on ', text)
        if text.startswith('No contributions on '):
            amount = 0
        elif count:
            amount = int(count.group(1).replace(',', ''))
        else:
            raise ValueError('Missing contribution count; keeping the existing card.')
        days.append((date.fromisoformat(value), amount))
    days.sort()
    if len({day for day, _ in days}) != len(days):
        raise ValueError('Duplicate calendar dates.')
    if any((b[0] - a[0]).days != 1 for a, b in zip(days, days[1:])):
        raise ValueError('Incomplete contribution calendar.')
    total = int(heading.group(1).replace(',', ''))
    if sum(count for _, count in days) != total:
        raise ValueError('Calendar total did not match its daily counts.')
    return days, total


def render(days, total):
    active = sum(count > 0 for _, count in days)
    streak = longest = 0
    for _, count in days:
        streak = streak + 1 if count else 0
        longest = max(longest, streak)
    peak = max(count for _, count in days)
    updated = datetime.now(timezone.utc).date().isoformat()
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="220" viewBox="0 0 1120 220" role="img" aria-labelledby="title desc"><title id="title">Scott Messer: field notes</title><desc id="desc">{active} active days, {longest} day longest streak, {peak} contributions on busiest day. From the public contribution calendar. Updated {updated}.</desc><rect width="1120" height="220" rx="14" fill="#0b202b"/><path d="M0 220L100 170 180 197 270 155 360 195 450 160 560 200 650 150 780 195 900 155 1020 190 1120 155V220Z" fill="#173c48"/><g font-family="Arial, Helvetica, sans-serif"><text x="36" y="35" fill="#8ce3c9" font-family="monospace" font-size="11" letter-spacing="2">FIELD NOTES / THE LAST YEAR</text>']
    for x, value, label in [(36, active, 'ACTIVE DAYS'), (405, longest, 'DAY LONGEST STREAK'), (775, peak, 'CONTRIBUTIONS / BUSIEST DAY')]:
        out.append(f'<text x="{x}" y="103" fill="#e7f5ed" font-size="48" font-weight="600" letter-spacing="-2">{value}</text><text x="{x}" y="132" fill="#91b4be" font-family="monospace" font-size="11" letter-spacing="1">{label}</text>')
    out.append(f'<text x="36" y="198" fill="#9ec2c7" font-family="monospace" font-size="10">{days[0][0]} — {days[-1][0]} · public + anonymized private counts</text><text x="1084" y="198" text-anchor="end" fill="#9ec2c7" font-family="monospace" font-size="10">UPDATED {updated} UTC</text></g></svg>')
    return '\n'.join(out) + '\n'


def main():
    args = argparse.ArgumentParser()
    args.add_argument('--input', type=Path, help='Saved public calendar HTML for offline verification.')
    args.add_argument('--output', type=Path, default=Path('github-activity.svg'))
    options = args.parse_args()
    if options.input:
        html = options.input.read_text()
    else:
        request = Request('https://github.com/users/scottmesser/contributions', headers={'User-Agent': 'scottmesser-profile-stats/1.0'})
        with urlopen(request, timeout=30) as response:
            html = response.read().decode('utf-8')
    days, total = parse_calendar(html)
    svg = render(days, total)
    temporary = options.output.with_suffix('.tmp')
    temporary.write_text(svg)
    temporary.replace(options.output)
    print(f'Updated public activity card: {total:,} contributions across {len(days)} calendar days.')


if __name__ == '__main__':
    main()
