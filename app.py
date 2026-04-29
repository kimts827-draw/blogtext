import re
from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup, Tag

app = Flask(__name__)

def extract_content(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
    }

    try:
        # 1. 네이버 블로그 iframe 처리
        if "blog.naver.com" in url:
            res = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            iframe = soup.find('iframe', id='mainFrame')
            if iframe and iframe.get('src'):
                url = "https://blog.naver.com" + iframe['src']

        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        if not soup:
            return "페이지를 읽을 수 없습니다."

        # 불필요한 요소 제거
        REMOVE_TAGS = ['script', 'style', 'nav', 'header', 'footer', 'aside', 'button', 'template', 'noscript']
        for s in soup.find_all(REMOVE_TAGS):
            s.extract()

        # --- [제목 추출] ---
        title = ""
        for sel in ['.se-title-text', '.se-documentTitle', '.title_h1']:
            title_node = soup.select_one(sel)
            if title_node:
                title = title_node.get_text(strip=True)
                break

        # --- [본문 영역 탐색] ---
        targets = ['.se-main-container', '.entry-content', '#article-view', '.contents_style']
        content_area = None
        for target in targets:
            content_area = soup.select_one(target)
            if content_area:
                break

        if not content_area:
            content_area = soup.body

        # --- [본문 추출 로직] ---
        output = []

        def walk_html(node, is_quote=False):
            if node is None:
                return

            if isinstance(node, str):
                text = node.strip()
                if text and not re.search(r'SE-TEXT|\{.*?\}', text):
                    output.append(text)
                return

            if isinstance(node, Tag):
                tag_name = node.name
                raw_classes = node.get('class', [])
                classes = raw_classes if isinstance(raw_classes, list) else [str(raw_classes)]

                if tag_name == 'a' or tag_name in ['figcaption', 'img', 'video', 'canvas']:
                    return
                if any(c in ['se-caption', 'se-image-caption', 'caption'] for c in classes):
                    return

                is_current_quote = (tag_name == 'blockquote' or any('quote' in str(c) for c in classes))

                if is_current_quote and not is_quote:
                    if output and not str(output[-1]).endswith('\n'):
                        output.append('\n')
                    output.append('\n**')
                    for child in node.children:
                        walk_html(child, is_quote=True)
                    output.append('**\n')
                    return

                if tag_name == 'br':
                    output.append('\n')
                elif tag_name in ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'li']:
                    if output and not str(output[-1]).endswith('\n'):
                        output.append('\n')
                    for child in node.children:
                        walk_html(child, is_quote)
                    if output and not str(output[-1]).endswith('\n'):
                        output.append('\n')
                elif tag_name == 'table':
                    output.append('\n')
                    for row in node.find_all('tr'):
                        cells = [cell.get_text(strip=True) for cell in row.find_all(['td', 'th'])]
                        output.append(' | '.join(cells) + '\n')
                else:
                    for child in node.children:
                        walk_html(child, is_quote)

        if content_area:
            walk_html(content_area)

        raw_text = "".join(output)
        cleaned_text = re.sub(r'SE-TEXT\s*\{.*?\}', '', raw_text, flags=re.DOTALL)
        cleaned_text = re.sub(r'[ \t]+', ' ', cleaned_text)
        cleaned_text = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_text)

        # --- [결과 조립] ---
        final_output = []
        if title:
            final_output.append(f"제목: {title}")
        if cleaned_text.strip():
            final_output.append(cleaned_text.strip())

        return "\n\n".join(final_output)

    except Exception as e:
        return f"오류 발생: {str(e)}"


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/extract', methods=['POST'])
def extract():
    url = request.json.get('url')
    if not url:
        return jsonify({'text': 'URL을 입력해주세요.'})
    result = extract_content(url)
    return jsonify({'text': result})


if __name__ == '__main__':
    app.run(debug=True, port=5000)