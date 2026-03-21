"""
Funcoes de scraping e extracao de conteudo de artigos Alura.
Usa BeautifulSoup para parsing HTML determinístico, sem IA.
"""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString
from unidecode import unidecode


def is_banner_or_promotional(element):
    """Verifica se elemento é banner/propaganda."""
    parent_a = element.find_parent('a') if element.name != 'a' else element
    if parent_a and parent_a.get('href'):
        href = parent_a.get('href', '')
        promo_patterns = [
            '/escola-', '/formacao-', '/planos-', '/curso-online',
            '/empresas', 'cursos.alura.com.br/loginForm',
            'utm_source=blog', 'utm_medium=banner', 'utm_campaign=',
            '/carreiras/', '/pos-tech'
        ]
        for pattern in promo_patterns:
            if pattern in href:
                return True

    if element.name == 'img':
        src = element.get('src', '').lower()
        alt = element.get('alt', '').lower()
        if any(x in src for x in ['matricula-escola', 'saiba-mais', 'banner']):
            return True
        if 'banner' in alt:
            return True

    return False


def is_site_chrome(element):
    """Verifica se elemento faz parte do chrome do site."""
    if element.find_parent(['nav', 'footer', 'aside']):
        return True

    parent_header = element.find_parent('header')
    if parent_header:
        if parent_header.find('a', href=lambda x: x and '/carreiras' in x):
            return True

    if element.find_parent(class_=lambda x: x and 'cosmos-author' in str(x)):
        return True

    if element.find_parent(class_=lambda x: x and 'social-media' in str(x)):
        return True
    if element.find_parent(class_=lambda x: x and 'cosmos-container-social' in str(x)):
        return True

    if element.name == 'p':
        text = element.get_text(strip=True).lower()
        if text == 'compartilhe':
            return True

    return False


def is_decorative_element(element):
    """Verifica se é elemento decorativo."""
    if element.name == 'img':
        src = element.get('src', '').lower()
        classes = element.get('class', [])

        if 'cosmos-image' in classes:
            return False

        if 'cdn-wcsm.alura.com.br' in src:
            return False

        decorative_patterns = [
            '/assets/img/header/', '/assets/img/home/', '/assets/img/caelum',
            '/assets/img/footer/', '/assets/img/ecossistema/',
            'arrow-', 'return-', 'icon', 'avatar',
            'gravatar.com/avatar', 'gnarususercontent.com.br'
        ]

        for pattern in decorative_patterns:
            if pattern in src:
                return True

        if '.svg' in src and '/assets/' in src:
            return True

        width = element.get('width')
        if width:
            try:
                if int(width) < 50:
                    return True
            except ValueError:
                pass

    return False


def get_text_preserving_spaces(element):
    """Extrai texto preservando espaços entre elementos inline."""
    texts = []
    for child in element.descendants:
        if isinstance(child, NavigableString):
            texts.append(str(child))
    result = ''.join(texts)
    result = re.sub(r'\s+', ' ', result)
    return result.strip()


def extract_text_with_formatting(element, base_url):
    """Extrai texto preservando formatação (links, bold, italic)."""
    segments = []

    for child in element.children:
        if isinstance(child, NavigableString):
            text = str(child)
            if text.strip():
                segments.append({"text": text})

        elif child.name == 'a':
            href = child.get('href', '')
            text = child.get_text()
            if text.strip():
                if href and not href.startswith('http') and not href.startswith('#'):
                    href = urljoin(base_url, href)
                segments.append({"text": text, "link": href if href else None})

        elif child.name in ['strong', 'b']:
            inner_a = child.find('a')
            inner_em = child.find(['em', 'i'])

            if inner_a:
                href = inner_a.get('href', '')
                if href and not href.startswith('http') and not href.startswith('#'):
                    href = urljoin(base_url, href)
                text = child.get_text()
                if text.strip():
                    segments.append({"text": text, "link": href, "bold": True})
            elif inner_em:
                for subchild in child.children:
                    if isinstance(subchild, NavigableString):
                        text = str(subchild)
                        if text.strip():
                            segments.append({"text": text, "bold": True})
                    elif subchild.name in ['em', 'i']:
                        em_a = subchild.find('a')
                        if em_a:
                            href = em_a.get('href', '')
                            if href and not href.startswith('http') and not href.startswith('#'):
                                href = urljoin(base_url, href)
                            segments.append({"text": subchild.get_text(), "link": href, "bold": True, "italic": True})
                        else:
                            segments.append({"text": subchild.get_text(), "bold": True, "italic": True})
                    elif subchild.name == 'a':
                        href = subchild.get('href', '')
                        if href and not href.startswith('http') and not href.startswith('#'):
                            href = urljoin(base_url, href)
                        segments.append({"text": subchild.get_text(), "link": href, "bold": True})
            else:
                text = child.get_text()
                if text.strip():
                    segments.append({"text": text, "bold": True})

        elif child.name in ['em', 'i']:
            inner_a = child.find('a')
            if inner_a:
                href = inner_a.get('href', '')
                if href and not href.startswith('http') and not href.startswith('#'):
                    href = urljoin(base_url, href)
                text = child.get_text()
                if text.strip():
                    segments.append({"text": text, "link": href, "italic": True})
            else:
                text = child.get_text()
                if text.strip():
                    segments.append({"text": text, "italic": True})

        elif child.name == 'code':
            text = child.get_text()
            if text.strip():
                segments.append({"text": f"`{text}`", "bold": True})

        elif child.name == 'p':
            inner_segments = extract_text_with_formatting(child, base_url)
            segments.extend(inner_segments)

        elif child.name in ['span', 'mark', 'u']:
            inner_segments = extract_text_with_formatting(child, base_url)
            segments.extend(inner_segments)

        elif child.name == 'br':
            segments.append({"text": "\n"})

        elif child.name in ['sup', 'sub']:
            text = child.get_text()
            if text.strip():
                segments.append({"text": text})

        else:
            text = child.get_text()
            if text.strip():
                segments.append({"text": text})

    return segments


def process_list_items(ul_or_ol, base_url, ordered=False):
    """Processa itens de lista, incluindo listas aninhadas."""
    items = []

    for li in ul_or_ol.find_all('li', recursive=False):
        item = {}
        sublist = li.find(['ul', 'ol'], recursive=False)

        if sublist:
            sublist_copy = sublist.extract()
            segments = extract_text_with_formatting(li, base_url)
            li.append(sublist_copy)

            if segments:
                has_formatting = any(
                    seg.get('link') or seg.get('bold') or seg.get('italic')
                    for seg in segments
                )

                if has_formatting:
                    item['segments'] = segments
                elif len(segments) == 1:
                    item['text'] = segments[0].get('text', '').strip()
                else:
                    item['text'] = ''.join(seg.get('text', '') for seg in segments).strip()

            sub_ordered = sublist_copy.name == 'ol'
            sub_items = process_list_items(sublist_copy, base_url, sub_ordered)
            if sub_items:
                item['sublist'] = {
                    'ordered': sub_ordered,
                    'items': sub_items
                }
        else:
            segments = extract_text_with_formatting(li, base_url)
            if segments:
                has_formatting = any(
                    seg.get('link') or seg.get('bold') or seg.get('italic')
                    for seg in segments
                )

                if has_formatting:
                    item['segments'] = segments
                elif len(segments) == 1:
                    item['text'] = segments[0].get('text', '').strip()
                else:
                    item['text'] = ''.join(seg.get('text', '') for seg in segments).strip()

        if item:
            items.append(item)

    return items


def extract_table(table_tag):
    """Extrai dados de tabela HTML."""
    headers = []
    rows = []

    thead = table_tag.find('thead')
    if thead:
        header_row = thead.find('tr')
        if header_row:
            headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]

    if not headers:
        first_row = table_tag.find('tr')
        if first_row:
            ths = first_row.find_all('th')
            if ths:
                headers = [th.get_text(strip=True) for th in ths]

    tbody = table_tag.find('tbody') or table_tag
    for tr in tbody.find_all('tr'):
        if tr.find('th') and not rows and headers:
            continue

        cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
        if cells and any(c for c in cells):
            rows.append(cells)

    return headers, rows


def extract_article_content(html: str, base_url: str) -> dict:
    """
    Extrai conteúdo estruturado de artigo Alura usando BeautifulSoup.
    100% determinístico, sem IA.
    """
    soup = BeautifulSoup(html, 'html.parser')

    for tag in soup.find_all(['script', 'style', 'noscript', 'svg', 'iframe']):
        tag.decompose()

    metadata = {
        'title': None,
        'author': None,
        'publishDate': None
    }
    content = []
    processed_elements = set()

    h1 = soup.find('h1')
    if h1:
        metadata['title'] = h1.get_text(strip=True)
        processed_elements.add(id(h1))

    date_pattern = re.compile(r'\d{2}/\d{2}/\d{4}')
    page_text = soup.get_text()
    date_match = date_pattern.search(page_text)
    if date_match:
        metadata['publishDate'] = date_match.group()

    author_candidates = []
    for img in soup.find_all('img'):
        src = img.get('src', '')
        alt = img.get('alt', '')
        if 'gravatar.com' in src or 'gnarususercontent.com.br' in src:
            if alt and len(alt) > 2 and not any(x in alt.lower() for x in ['logo', 'banner', 'alura']):
                author_candidates.append(alt)

    if author_candidates:
        metadata['author'] = author_candidates[0]

    main_content = soup.find('body') or soup
    stop_processing = False

    list_item_texts = set()
    for li in main_content.find_all('li'):
        li_text = li.get_text(strip=True)
        if li_text and len(li_text) > 10:
            list_item_texts.add(li_text)

    for element in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'p', 'ul', 'ol',
                                           'blockquote', 'pre', 'table', 'img', 'figure']):
        elem_id = id(element)
        if elem_id in processed_elements:
            continue
        processed_elements.add(elem_id)

        if is_site_chrome(element):
            continue
        if is_banner_or_promotional(element):
            continue
        if is_decorative_element(element):
            continue

        if element.name in ['h2', 'h3']:
            text = element.get_text(strip=True).lower()
            if any(x in text for x in ['leia também', 'artigos relacionados', 'veja outros artigos']):
                stop_processing = True

        if stop_processing:
            continue

        if element.name == 'h1':
            continue

        if element.name in ['h2', 'h3', 'h4', 'h5']:
            text = get_text_preserving_spaces(element)
            if text and len(text) > 1:
                if element.find_parent(class_=lambda x: x and 'toc' in x.lower() if x else False):
                    continue
                level = int(element.name[1])
                content.append({
                    'type': 'heading',
                    'level': level,
                    'text': text
                })

        elif element.name == 'p':
            text = element.get_text(strip=True)
            if not text:
                continue
            if text in list_item_texts:
                continue

            segments = extract_text_with_formatting(element, base_url)
            if segments:
                has_formatting = any(
                    seg.get('link') or seg.get('bold') or seg.get('italic')
                    for seg in segments
                )

                if not has_formatting and len(segments) == 1:
                    content.append({
                        'type': 'paragraph',
                        'text': segments[0].get('text', '').strip()
                    })
                else:
                    content.append({
                        'type': 'paragraph',
                        'segments': segments
                    })

        elif element.name in ['ul', 'ol']:
            if element.find_parent(['ul', 'ol']):
                continue

            ordered = element.name == 'ol'
            items = process_list_items(element, base_url, ordered)

            if items:
                content.append({
                    'type': 'list',
                    'ordered': ordered,
                    'items': items
                })

        elif element.name == 'blockquote':
            segments = extract_text_with_formatting(element, base_url)
            cite_tag = element.find('cite')
            cite = cite_tag.get_text(strip=True) if cite_tag else None

            if segments:
                blockquote_item = {'type': 'blockquote', 'segments': segments}
                if cite:
                    blockquote_item['cite'] = cite
                content.append(blockquote_item)

        elif element.name == 'pre':
            code_tag = element.find('code')
            if code_tag:
                code_content = code_tag.get_text()
                classes = code_tag.get('class', [])
                language = None
                for cls in classes:
                    if isinstance(cls, str):
                        if cls.startswith('language-'):
                            language = cls.replace('language-', '')
                            break
                        elif cls in ['python', 'javascript', 'java', 'sql', 'bash',
                                    'html', 'css', 'json', 'typescript', 'jsx', 'ruby',
                                    'go', 'rust', 'php', 'csharp', 'kotlin', 'swift']:
                            language = cls
                            break

                content.append({
                    'type': 'code',
                    'language': language,
                    'content': code_content
                })
            else:
                content.append({
                    'type': 'code',
                    'content': element.get_text()
                })

        elif element.name == 'table':
            headers, rows = extract_table(element)
            if headers or rows:
                content.append({
                    'type': 'table',
                    'headers': headers,
                    'rows': rows
                })

        elif element.name == 'img':
            src = element.get('src', '')
            if not src:
                continue
            if is_banner_or_promotional(element):
                continue
            if is_decorative_element(element):
                continue

            if not src.startswith('http'):
                src = urljoin(base_url, src)

            alt = element.get('alt', '')
            width = element.get('width')
            height = element.get('height')

            img_item = {
                'type': 'image',
                'url': src,
                'alt': alt
            }

            if width:
                try:
                    img_item['width'] = int(width)
                except:
                    pass
            if height:
                try:
                    img_item['height'] = int(height)
                except:
                    pass

            content.append(img_item)

        elif element.name == 'figure':
            img = element.find('img')
            if img:
                src = img.get('src', '')
                if not src:
                    continue

                if not src.startswith('http'):
                    src = urljoin(base_url, src)

                figcaption = element.find('figcaption')
                alt = figcaption.get_text(strip=True) if figcaption else img.get('alt', '')

                content.append({
                    'type': 'image',
                    'url': src,
                    'alt': alt
                })
                processed_elements.add(id(img))

    content = [item for item in content if item]

    stats = {}
    for item in content:
        item_type = item.get('type', 'unknown')
        stats[item_type] = stats.get(item_type, 0) + 1

    filename = metadata.get('title', 'documento') or 'documento'
    filename = unidecode(filename)
    filename = re.sub(r'[^a-zA-Z0-9\s-]', '', filename)
    filename = re.sub(r'\s+', '-', filename).strip('-')
    filename = filename[:80]
    filename = f"{filename}.docx"

    return {
        'metadata': metadata,
        'content': content,
        'filename': filename,
        'base_url': base_url,
        'stats': stats
    }
