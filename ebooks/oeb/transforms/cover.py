# Copyright 2010, Kovid Goyal <kovid@kovidgoyal.net>
# Copyright 2013 Hardcoded Software (http://www.hardcoded.net)
# 
# This software is licensed under the "GPL v3" License as described in the "LICENSE" file, 
# which should be included with this package. The terms are also available at 
# http://www.hardcoded.net/licenses/gplv3_license

import textwrap
from urllib.parse import unquote
import logging

from lxml import etree
from ...utils.mimetypes import guess_type

coding = list(zip(
[1000,900,500,400,100,90,50,40,10,9,5,4,1],
["M","CM","D","CD","C","XC","L","XL","X","IX","V","IV","I"]
))

def roman(num):
    if num <= 0 or num >= 4000 or int(num) != num:
        return str(num)
    result = []
    for d, r in coding:
        while num >= d:
            result.append(r)
            num -= d
    return ''.join(result)


def fmt_sidx(i, fmt='%.2f', use_roman=False):
    if i is None or i == '':
        i = 1
    try:
        i = float(i)
    except TypeError:
        return str(i)
    if int(i) == float(i):
        return roman(int(i)) if use_roman else '%d'%int(i)
    return fmt%i

class CoverManager(object):

    SVG_TEMPLATE = textwrap.dedent('''\
        <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
            <head>
                <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
                <meta name="calibre:cover" content="true" />
                <title>Cover</title>
                <style type="text/css" title="override_css">
                    @page {padding: 0pt; margin:0pt}
                    body { text-align: center; padding:0pt; margin: 0pt; }
                </style>
            </head>
            <body>
                <div>
                    <svg version="1.1" xmlns="http://www.w3.org/2000/svg"
                        xmlns:xlink="http://www.w3.org/1999/xlink"
                        width="100%%" height="100%%" viewBox="__viewbox__"
                        preserveAspectRatio="__ar__">
                        <image width="__width__" height="__height__" xlink:href="%s"/>
                    </svg>
                </div>
            </body>
        </html>
        ''')

    NONSVG_TEMPLATE = textwrap.dedent('''\
        <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
            <head>
                <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
                <meta name="calibre:cover" content="true" />
                <title>Cover</title>
                <style type="text/css" title="override_css">
                    @page {padding: 0pt; margin:0pt}
                    body { text-align: center; padding:0pt; margin: 0pt }
                    div { padding:0pt; margin: 0pt }
                    img { padding:0pt; margin: 0pt }
                </style>
            </head>
            <body>
                <div>
                    <img src="%s" alt="cover" __style__ />
                </div>
            </body>
        </html>
    ''')


    def __init__(self, no_default_cover=False, no_svg_cover=False,
            preserve_aspect_ratio=False, fixed_size=None):
        self.no_default_cover = no_default_cover
        self.no_svg_cover = no_svg_cover
        self.preserve_aspect_ratio = preserve_aspect_ratio

        ar = 'xMidYMid meet' if preserve_aspect_ratio else 'none'
        self.svg_template = self.SVG_TEMPLATE.replace('__ar__', ar)

        if fixed_size is None:
            style = 'style="height: 100%%"'
        else:
            width, height = fixed_size
            style = 'style="height: %s; width: %s"'%(width, height)
        self.non_svg_template = self.NONSVG_TEMPLATE.replace('__style__',
                style)

    def __call__(self, oeb):
        self.oeb = oeb
        self.insert_cover()

    def default_cover(self):
        '''
        Create a generic cover for books that dont have a cover
        '''
        if self.no_default_cover:
            return None
        m = self.oeb.metadata
        title = str(m.title[0])
        authors = [str(x) for x in m.creator if x.role == 'aut']
        series_string = None
        if m.series and m.series_index:
            series_string = 'Book %(sidx)s of %(series)s' % dict(
                    sidx=fmt_sidx(m.series_index[0], use_roman=True),
                    series=str(m.series[0]))

        # try:
        #     from calibre.ebooks import calibre_cover
        #     img_data = calibre_cover(title, authors_to_string(authors),
        #             series_string=series_string)
        #     id, href = self.oeb.manifest.generate('cover',
        #             'cover_image.jpg')
        #     item = self.oeb.manifest.add(id, href, guess_type('t.jpg')[0],
        #                 data=img_data)
        #     m.clear('cover')
        #     m.add('cover', item.id)
        # 
        #     return item.href
        # except:
        #     logging.exception('Failed to generate default cover')
        return None

    def inspect_cover(self, href):
        # from calibre.ebooks.oeb.base import urlnormalize
        # for x in self.oeb.manifest:
        #     if x.href == urlnormalize(href):
        #         try:
        #             raw = x.data
        #             return identify_data(raw)[:2]
        #         except:
        #             logging.exception('Failed to read image dimensions')
        return None, None

    def insert_cover(self):
        from ..base import urldefrag
        g, m = self.oeb.guide, self.oeb.manifest
        item = None
        if 'titlepage' not in g:
            if 'cover' in g:
                href = g['cover'].href
            else:
                href = self.default_cover()
            if href is None:
                return
            width, height = self.inspect_cover(href)
            if width is None or height is None:
                logging.warning('Failed to read cover dimensions')
                width, height = 600, 800
            #if self.preserve_aspect_ratio:
            #    width, height = 600, 800
            self.svg_template = self.svg_template.replace('__viewbox__',
                    '0 0 %d %d'%(width, height))
            self.svg_template = self.svg_template.replace('__width__',
                    str(width))
            self.svg_template = self.svg_template.replace('__height__',
                    str(height))

            if href is not None:
                templ = self.non_svg_template if self.no_svg_cover \
                        else self.svg_template
                tp = templ%unquote(href)
                id, href = m.generate('titlepage', 'titlepage.xhtml')
                item = m.add(id, href, guess_type('t.xhtml')[0],
                        data=etree.fromstring(tp))
        else:
            item = self.oeb.manifest.hrefs[
                    urldefrag(self.oeb.guide['titlepage'].href)[0]]
        if item is not None:
            self.oeb.spine.insert(0, item, True)
            if 'cover' not in self.oeb.guide.refs:
                self.oeb.guide.add('cover', 'Title Page', 'a')
            self.oeb.guide.refs['cover'].href = item.href
            if 'titlepage' in self.oeb.guide.refs:
                self.oeb.guide.refs['titlepage'].href = item.href


