# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals
import argparse
import re

import requests


class NightCrawler(object):
    """
    Looks *recursively* for unwanted terms/links inside a domain's pages.

    Example calls:

    # Look for all pages in http://my.base.domain that contains >0 strings = 'promotion'
    python night_crawler.py --base-domain="http://my.base.domain" --terms promotion

    # Look for all pages in http://my.base.domain that contains >0 strings = 'promotion' (and print a lot of output)
    python night_crawler.py --base-domain="http://my.base.domain" --terms promotion --verbosity-level=2

    # Look for all pages in http://my.base.domain that contains >0 *links* to 'promotion.domain.com'
    python night_crawler.py --base-domain="http://my.base.domain" --terms promotion.domain.com --use-link-lookup

    # Look for all pages in http://my.base.domain that contains >1 strings = 'promotion'
    python night_crawler.py --base-domain="http://my.base.domain" --terms promotion:1

    # Look for all pages in http://my.base.domain that contains either (>1 strings = promotion) or (>0 strings = bonus)
    python night_crawler.py --base-domain="http://my.base.domain" --terms promotion:1 bonus
    """

    FILETYPES_TO_IGNORE = [
        '.pdf',
        '.svg',
        '.png',
        '.css',
        '.ico',
        '.js',
    ]
    STR_CONTEXT_SIZE = 30
    URLS_CHECKED = {}  # Datamodel: {url: # of occurrences of unwanted terms}

    def __init__(self, base_domain, unwanted_terms, use_link_lookup, verbose_level):
        self.base_domain = base_domain
        self.unwanted_terms = unwanted_terms
        self.use_link_lookup = use_link_lookup
        self.verbose_level = verbose_level

    def crawl(self):
        self.check_page(self.base_domain)

    def write(self, message, verbose_level=2):
        if verbose_level <= self.verbose_level:
            print(message)

    def is_useful_link(self, url):
        if not(self.base_domain in url) and not(url.startswith('/')):
            return False

        for filetype in self.FILETYPES_TO_IGNORE:
            if url.endswith(filetype):
                return False

        return True

    def check_page(self, url):
        if url.startswith('/'):
            url = self.base_domain + url

        if url in self.URLS_CHECKED:
            self.write('-' * 10, verbose_level=3)
            self.write('{} : Skip as it was already crawled'.format(url), verbose_level=3)
            return

        self.write('-' * 10)
        self.write('{} : Init'.format(url))
        try:
            content = requests.get(url).content.decode('utf-8')
        except Exception as e:
            self.write('{} : Error {}'.format(url, e), verbose_level=1)
            return

        # Check if any of bad terms appear in this page's content
        total_count = 0
        for unwanted_term, max_qty in self.unwanted_terms.items():
            if self.use_link_lookup:
                # Get occurences as a complete URL of the unwanted links
                occurrences = re.findall(r'''({}.*?)(?:'|"|#)'''.format(unwanted_term), content)
                count = len(occurrences)
                count_beyond_expected = max(count - max_qty, 0)
                total_count += count_beyond_expected
                if count_beyond_expected:
                    self.write('{} : Found {} total occurrences of "{}" as link'.format(url, count, unwanted_term), verbose_level=1)
                    for occurrence in occurrences:
                        self.write('    {} : Found link to "{}"'.format(url, occurrence), verbose_level=1)
            else:
                # Get occurences as a simple HTML output with some context so user can understand where the unwanted term is
                occurrences = [m.start() for m in re.finditer(unwanted_term, content)]
                count = len(occurrences)
                count_beyond_expected = max(count - max_qty, 0)
                total_count += count_beyond_expected
                if count_beyond_expected:
                    self.write('{} : Found {} total occurrences of "{}" as html'.format(url, count, unwanted_term), verbose_level=1)
                    for start_idx in occurrences:
                        substr = content[start_idx:start_idx + len(unwanted_term) + self.STR_CONTEXT_SIZE]
                        self.write('    {} : Found html "{}"'.format(url, repr(substr)), verbose_level=1)
        self.URLS_CHECKED[url] = total_count

        # Look up child pages to be crawled as well
        links = re.findall(r'href="(.*?)(?:"|#)', content) + re.findall(r"href='(.*?)(?:'|#)", content)
        links = [x.strip() for x in links]
        links = list(set(links))
        links = list(filter(self.is_useful_link, links))
        for link in links:
            self.check_page(link)

    def print_summary(self):
        total_pages = len(self.URLS_CHECKED)
        pages_clear = {url: qty for url, qty in self.URLS_CHECKED.items() if qty == 0}
        len_pages_clear = len(pages_clear)
        pages_with_terms = {url: qty for url, qty in self.URLS_CHECKED.items() if qty > 0}
        len_pages_with_terms = len(pages_with_terms)

        self.write('\n\nPAGES CLEAR', verbose_level=1)
        for url in pages_clear:
            self.write(url, verbose_level=1)

        self.write('\n\nPAGES WITH TERMS', verbose_level=1)
        for url, qty in pages_with_terms.items():
            self.write('{} : {}'.format(url, qty), verbose_level=1)

        self.write('\n\nTOTALS', verbose_level=1)
        self.write('Pages checked: {}'.format(total_pages), verbose_level=1)
        self.write('Pages cleared: {}'.format(len_pages_clear), verbose_level=1)
        self.write('Pages with terms: {}'.format(len_pages_with_terms), verbose_level=1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--base-domain', action='store', dest='base_domain', required=True,
        help='Base domain (one used to start crawling and to complete relative paths).',
    )
    parser.add_argument(
        '--terms', action='store', dest='unwanted_terms', required=True, nargs='+',
        help='Terms to lookup. You can set a occurrence threshold using the format "term:threshold".',
    )
    parser.add_argument(
        '--use-link-lookup', action='store_true', dest='use_link_lookup', required=False, default=False,
        help='Consider only link terms when looking for matches.',
    )
    parser.add_argument(
        '--verbosity-level', action='store', dest='verbose_level', required=False, default='1', type=int,
        help='Verbosity level (1 = min verbosity, 3 = max verbosity).',
    )
    args = parser.parse_args()

    unwanted_terms = {}
    for term_data in args.unwanted_terms:
        try:
            term, qty = term_data.split(':')
        except ValueError:
            term, qty = term_data, '0'
        qty = int(qty)
        unwanted_terms[term] = qty

    night_crawler = NightCrawler(args.base_domain, unwanted_terms, args.use_link_lookup, args.verbose_level)
    night_crawler.crawl()
    night_crawler.print_summary()
