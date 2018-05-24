# Copyright (C) 2018 East Asian Observatory
# All Rights Reserved.
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful,but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,51 Franklin
# Street, Fifth Floor, Boston, MA  02110-1301, USA

from __future__ import absolute_import, division, print_function, \
    unicode_literals


ads_responses = {
    'bibcode:(1965ApJ...142..419P)': '{"responseHeader":{"status":0,"QTime":4,"params":{"q":"bibcode:(1965ApJ...142..419P)","x-amzn-trace-id":"Root=1-5b060986-f529581e2e65f963d983ce1f","fl":"bibcode,title,author,pubdate","start":"0","rows":"10","wt":"json"}},"response":{"numFound":1,"start":0,"docs":[{"bibcode":"1965ApJ...142..419P","pubdate":"1965-07-00","author":["Penzias, A. A.","Wilson, R. W."],"title":["A Measurement of Excess Antenna Temperature at 4080 Mc/s."]}]}}',
}

# Abbreviated responses from arxiv.
arxiv_responses = {
    '1001.0001': '''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1001.0001v1</id>
    <updated>2009-12-30T21:39:20Z</updated>
    <published>2009-12-30T21:39:20Z</published>
    <title>On the structure of non-full-rank perfect codes</title>
    <author>
      <name>Denis Krotov</name>
    </author>
    <author>
      <name>Olof Heden</name>
    </author>
  </entry>
</feed>''',

    '1611.02297': '''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1611.02297v1</id>
    <updated>2016-11-07T21:05:46Z</updated>
    <published>2016-11-07T21:05:46Z</published>
    <title>Dynamical modeling validation ...</title>
    <author>
      <name>Damir ...</name>
    </author>
    <author>
      <name>J ...</name>
    </author>
    <author>
      <name>Peter ///</name>
    </author>
  </entry>
</feed>''',
}
