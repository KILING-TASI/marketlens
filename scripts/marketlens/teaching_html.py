"""Render only saved teaching Markdown, without inferring new conclusions."""
from html import escape

def render(text):
    blocks=[];table=False
    for raw in text.splitlines():
        line=raw.strip()
        if line.startswith('|') and line.endswith('|'):
            cells=[x.strip() for x in line.strip('|').split('|')]
            if all(c and set(c)<=set('-: ') for c in cells):continue
            tag='td' if table else 'th'
            if not table:blocks.append('<div class="table"><table>');table=True
            blocks.append('<tr>'+''.join('<'+tag+'>'+escape(c.replace('**',''))+'</'+tag+'>' for c in cells)+'</tr>');continue
        if table:blocks.append('</table></div>');table=False
        if line.startswith('## '):blocks.append('<h2>'+escape(line[3:])+'</h2>')
        elif line.startswith('# '):blocks.append('<h2>'+escape(line[2:])+'</h2>')
        elif line:blocks.append('<p>'+escape(line.replace('**',''))+'</p>')
    if table:blocks.append('</table></div>')
    return ''.join(blocks)
