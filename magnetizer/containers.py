"""Python-Markdown extension for ::: fenced container blocks.

    ::: my-class
    Content, which may itself contain Markdown.
    :::

renders as:

    <div class="container my-class">
    <p>Content, which may itself contain Markdown.</p>
    </div>

The class name is optional; the rendered div always carries the default
`container` class, with any given class name appended. An opening fence
with no matching closing fence is left untouched as ordinary text.
"""

import re
import xml.etree.ElementTree as etree

from markdown.blockprocessors import BlockProcessor
from markdown.extensions import Extension

DEFAULT_CLASS = 'container'

_OPEN_RE = re.compile(r'^:::[ \t]*(?P<extra_class>\S[^\n]*)?[ \t]*(?:\n|$)')
_CLOSE_RE = re.compile(r'^:::[ \t]*$', re.MULTILINE)


class ContainerBlockProcessor(BlockProcessor):

    def test(self, parent, block):
        return bool(_OPEN_RE.match(block))

    def run(self, parent, blocks):
        m = _OPEN_RE.match(blocks[0])
        extra_class = (m.group('extra_class') or '').strip()
        remainder = blocks[0][m.end():]

        search_texts = [remainder] + blocks[1:]
        inner_parts = []
        end_index = None
        trailing = ''
        for index, text in enumerate(search_texts):
            close_match = _CLOSE_RE.search(text)
            if close_match:
                inner_parts.append(text[:close_match.start()].rstrip('\n'))
                trailing = text[close_match.end():]
                end_index = index
                break
            inner_parts.append(text)

        if end_index is None:
            return False

        del blocks[0:end_index + 1]

        classes = f'{DEFAULT_CLASS} {extra_class}' if extra_class else DEFAULT_CLASS
        div = etree.SubElement(parent, 'div')
        div.set('class', classes)
        self.parser.parseChunk(div, '\n\n'.join(inner_parts))

        if trailing.strip():
            blocks.insert(0, trailing)

        return True


class ContainerExtension(Extension):

    def extendMarkdown(self, md):
        md.parser.blockprocessors.register(ContainerBlockProcessor(md.parser), 'container_block', 105)


def makeExtension(**kwargs):
    return ContainerExtension(**kwargs)
