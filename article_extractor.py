import itertools
import os
import pathlib
import re
import unicodedata

import deepl
from newspaper import Article
import nltk
from loguru import logger
import click
import html
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread_formatting import set_column_width, set_row_height
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

scope = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]


def base26(num):
    if num == 0:
        return ''
    num, rem = divmod(num - 1, 26)
    return base26(num) + chr(rem + ord('A'))


def get_client():
    credentials = ServiceAccountCredentials.from_json_keyfile_name('secret.json', scope)
    gc = gspread.authorize(credentials)
    return gc


def fetch_n_create_template(url, from_language, output_dir):
    logger.info(f'Fetching {url}')
    article = Article(url, keep_article_html=True)
    article.download()

    if not article.html.strip():
        logger.error('Could not download article. Trying with real browser with selenium.')
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        options = Options()

        driver = webdriver.Chrome(options=options)
        driver.get(url)
        # wait for page to load
        driver.implicitly_wait(1)
        # if there is a captcha, we need to solve it
        if 'captcha' in article.html:
            logger.error('Captcha detected. Please solve it and press enter.')
            input()

        if driver.page_source.strip():
            logger.info('Successfully downloaded article with selenium. We were probably blocked by a firewall.')
            article.download(input_html=driver.page_source)

        driver.quit()

    article.parse()

    if not article.text:
        raise Exception('Could not parse article.')

    article.nlp()

    # examples of matches for the regex: ^(?=.*\d)(?=.*[a-z])(?=.*[A-Z])(?=.*[!@#$^&*()_-]).{8,18}$
    # 1. (?=.*\d) - at least one digit
    # 2. (?=.*[a-z]) - at least one lowercase letter
    # 3. (?=.*[A-Z]) - at least one uppercase letter
    # 4. (?=.*[!@#$^&*()_-]) - at least one special character
    # 5. .{8,18} - at least 8 characters and at most 18 characters

    output_dir = output_dir or (pathlib.Path.cwd() / article.title)
    output_dir.mkdir(parents=True, exist_ok=True)

    # normalize the text
    original_language_article_html = html.unescape(article.article_html)
    original_language_article_html = unicodedata.normalize('NFKD', original_language_article_html)
    template_html = original_language_article_html

    # everything between tags
    rgx = re.compile(r'(?<=>)[^<>]+(?=<)')
    localization_strings = list(filter(lambda x: len(x.strip()) > 1, re.findall(rgx, template_html)))

    # remove empty strings
    localization_strings_sanitized = [s.strip() for s in localization_strings]

    # sorting by length to avoid matching the wrong string in case of same prefix
    # e.g. 'Kubo' and 'Kubo Education'
    # 'Kubo Education'.replace('Kubo', '') -> ' Education'
    # and we won't match 'Kubo Education'
    localization_longest_to_shortest_idx = sorted(range(len(localization_strings_sanitized)),
                                                  key=lambda idx: len(localization_strings_sanitized[idx]),
                                                  reverse=True)

    meta_localization = {
        'title': article.title,
        'meta-description': article.meta_description,
        'meta-keywords': ','.join(article.meta_keywords),
    }

    if not meta_localization['meta-keywords']:
        article.nlp()
        meta_localization['meta-keywords'] = ','.join(article.keywords)

    # replace strings with jinja2 variables
    # {{ idx }} is the index of the string in the list
    for i in localization_longest_to_shortest_idx:
        s = localization_strings_sanitized[i]
        # check if there are multiple occurrences of the same string
        if template_html.count(s) == 1:
            template_html = template_html.replace(s, f'{{{{ s{i} }}}}')
        else:
            # only replace if the string is not inside a tag
            # e.g. <a href="https://www.kuboeducation.com">Kubo Education</a> should match 'Kubo Education'
            # but <a href="https://www.kuboeducation.com"> Kubo Education </a> should also match 'Kubo Education'

            rgx = re.compile(rf'(?<=>)[^<>]*{re.escape(localization_strings_sanitized[i])}[^<>]*(?=<)')
            n_matches = len(rgx.findall(template_html))
            if n_matches == 0:
                logger.error(f'Could not find {s} in the article. Exiting...')
                exit(1)
            else:
                # only replace the first occurrence
                template_html = rgx.sub(f'{{{{ s{i} }}}}', template_html, count=1)

    # extend base.html with the article content
    with open('base.html', 'r') as f:
        base_html = f.read()

    template_html = base_html.replace('{{ content }}', template_html)
    original_language_article_html = base_html.replace('{{ content }}', original_language_article_html)

    # save the html to a file
    with open(output_dir / 'template.html', 'w') as f:
        f.write(template_html)

    with open(output_dir / f'{from_language}.html', 'w') as f:
        f.write(original_language_article_html)

    return localization_strings_sanitized, meta_localization, article


def write_to_google_spreadsheet(
        localization_strings_sanitized,
        meta_localization,
        article,
        from_language,
        to_languages,
        email,
        url,
):
    logger.info('Writing to Google Spreadsheet')
    # now create a sheet with the strings for translators
    filename = f'{article.title} - localization strings'
    article_title = article.title.replace(':', ' -')

    # remove special characters

    gc = get_client()
    # create a new sheet if it doesn't exist
    try:
        spreadsheet = gc.open(filename)
    except gspread.exceptions.SpreadsheetNotFound:
        spreadsheet = gc.create(filename)
        sheet = spreadsheet.sheet1

    else:
        click.confirm(
            f'The spreadsheet {filename} already exists. Do you want to overwrite it?',
            abort=True,
        )

        for worksheet in spreadsheet.worksheets()[1:]:
            logger.info(f'Deleting worksheet {worksheet.title}')
            spreadsheet.del_worksheet(worksheet)

        sheet = spreadsheet.sheet1
        sheet.clear()
        sheet.resize(1000, 100)
    sheet.update_title(f'{article_title}')

    # check what email address is used to access the sheet
    # ask user if he wants to add his email address permissions to the sheet
    email = email or click.prompt('Enter your gmail address to add permissions to the sheet')
    spreadsheet.share(email, perm_type='user', role='writer', notify=False)

    logger.info(f'Formatting the sheet')

    # add the strings to the sheet
    sheet.update('A1', from_language)
    # set_row_height(sheet, '', 100)
    set_column_width(sheet, f'A:{base26(len(to_languages) + 1)}', 300)
    set_row_height(sheet, '2:100', 300)
    sheet.format(f'A2:{base26(len(to_languages) + 1)}{len(localization_strings_sanitized) + 1}',
                 {'wrapStrategy': 'WRAP', 'verticalAlignment': 'MIDDLE'})

    sheet.freeze(rows=1, cols=1)

    logger.info(f'Adding the original strings to the sheet')
    sheet.update(f'A2:A{len(localization_strings_sanitized) + 1}', [[s] for s in localization_strings_sanitized])
    sheet.update(f'B1:{base26(len(to_languages) + 1)}1', [to_languages])

    # translate the strings with deepl api
    logger.info(f'Translating the strings with deepl api')
    translator = deepl.Translator(os.environ['DEEPL_API_KEY'])
    translation_results = [[None] * len(to_languages) for _ in range(len(localization_strings_sanitized))]

    for i, j in tqdm(itertools.product(range(len(localization_strings_sanitized)), range(len(to_languages))),
                     total=len(localization_strings_sanitized) * len(to_languages), desc='Translating'):
        s = localization_strings_sanitized[i]
        t = to_languages[j]
        translation_results[i][j] = translator.translate_text(s, source_lang=from_language, target_lang=t).text

    logger.info(f'Adding the translations to the sheet')
    # add the translations to the sheet
    sheet.update(f'B2:{base26(len(to_languages) + 1)}{len(localization_strings_sanitized) + 1}', translation_results)

    sheet.insert_row([f'{article_title} localization strings', url], index=1)

    # add the meta localization strings to second sheet
    logger.info(f'Adding the meta localization strings to the sheet...')
    sheet = spreadsheet.add_worksheet(title='Meta localization', rows=1000, cols=100)
    sheet.update('A1', 'Meta localization strings')
    set_column_width(sheet, f'A:{base26(len(to_languages) + 1)}', 400)
    set_row_height(sheet, f'2:{len(meta_localization) + 1}', 300)
    sheet.freeze(rows=1, cols=1)
    sheet.format(f'A:{base26(len(to_languages) + 2)}', {'wrapStrategy': 'WRAP', 'verticalAlignment': 'MIDDLE'})
    sheet.update('B1:B', 'English')

    sheet.update(f'A2:B{len(meta_localization) + 1}', list(meta_localization.items()))

    translation_results = [[""] * len(to_languages) for _ in range(len(meta_localization))]
    for i, s in enumerate(meta_localization.values()):
        for j, lang in enumerate(to_languages):
            if not s:
                continue
            try:
                translation_results[i][j] = translator.translate_text(s, source_lang=from_language,
                                                                      target_lang=lang).text
            except ValueError:
                logger.error(f'Error translating {s} to {lang}')

    sheet.update(f'C2:{base26(len(to_languages) + 2)}{len(meta_localization) + 1}', translation_results)

    print('Done. You can access the sheet here:')
    print(spreadsheet.url)


@click.command()
@click.option('--url', '-u', type=str, prompt='Enter the url of the article')
@click.option('--to-languages', '-tr', type=list, help='Languages to translate to', default=['FR', 'NL'])
@click.option('--from-language', '-f', type=str, help='Enter the language of the article', default='EN')
@click.option('--output-dir', '-o', type=str, default=None)
@click.option('--email', '-e', type=str, default=None)
def main(url, to_languages, from_language, output_dir, email):
    localization_strings_sanitized, meta_localization, article = fetch_n_create_template(url, from_language, output_dir)
    write_to_google_spreadsheet(
        localization_strings_sanitized,
        meta_localization,
        article,
        from_language,
        to_languages,
        email,
        url,
    )
    logger.info('Done')


if __name__ == '__main__':
    import sys

    sys.setrecursionlimit(100000)
    main()
