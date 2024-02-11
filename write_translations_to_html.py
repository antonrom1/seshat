import os
import jinja2
from loguru import logger
import click
import gspread
from oauth2client.service_account import ServiceAccountCredentials


@click.command()
@click.option('--url', '-u', type=str, prompt='Google Sheet URL')
@click.option('--dir', '-d', type=str, prompt='Directory to save files')
def main(url, dir):
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(searchpath=f'{dir}/'),
        autoescape=jinja2.select_autoescape(['html', 'xml'])
    )
    template = env.get_template('template.html')

    credentials = ServiceAccountCredentials.from_json_keyfile_name('secret.json', scope)
    gc = gspread.authorize(credentials)

    sheet = gc.open_by_url(url)
    worksheet = sheet.sheet1

    rows = worksheet.get_all_values()
    url = rows[0][1]
    langs = rows[1]
    strings = [row[0:] for row in rows[2:]]


    for lang_idx, lang in enumerate(langs):
        d = {
            f's{string_idx}': strings[string_idx][lang_idx]
            for string_idx, string in enumerate(strings)
        }
        output = template.render(**d)
        with open(os.path.join(dir, f'{lang}.html'), 'w') as f:
            f.write(output)
        logger.info(f'Wrote {os.path.join(dir, f"{lang}.html")}')


if __name__ == '__main__':
    main()
