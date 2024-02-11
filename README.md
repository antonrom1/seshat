# seshat

nooby.tech automated tool for extracting web article content, translating via DeepL API, and republishing as
multilingual HTML

## Installation

First start by creating a virtual environment and installing the required packages:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Then, you will need to create a `.env` file with the following content:

```bash
cp .env.example .env
```

You will need to create a DeepL API key by signing up at [DeepL API](https://www.deepl.com/pro#developer). With the
DeepL API Free plan, you can translate up to 500,000 characters per month for free.
Now that the you have an API key, fill in the `DEEPL_API_KEY` with your DeepL API key.

Next step is to [create a Google Cloud project](https://developers.google.com/workspace/guides/create-project)
and enable the [Google Sheets API](https://console.cloud.google.com/flows/enableapi?apiid=sheets.googleapis.com). 
After enabling the API, you will need to [create a service account](https://console.cloud.google.com/iam-admin/serviceaccounts/create).
Create an API key and download it as a JSON file.
Rename the JSON file to `secret.json` and move it to the root of the project.

## Usage

The process consists of three steps: 

### 1. Translate the content
First, you will need to extract the content from the source website

```bash
python article_extractor.py --url https://news.vex.com/2024/01/26/first-drive-forward-friday-2024/ --email your_google_account@gmail.com
```

The `--url` flag is the URL of the article you want to extract. 
The `--email` flag is the email that will be given read/write access to the Google Sheet with the localization strings.

This step will try to fetch the article content.
It will use the newspaper3k library to extract the article content, its name and description.
The content will be saved in a Google Sheet.
The link to the Google Sheet will be printed in the terminal to stdout.

### 2. Manual translation review and template html editing
The second step is to review the translation and make any necessary changes in the Google Sheet.

At this point,
you can also edit the template HTML file
(e.g. `./First\ Drive\ Forward\ Friday\ of\ 2024/template.html`) to remove any unnecessary tags/content.
The template variables are marked with `{{ sn }}`.
If you want to remove any text from the template,
you can remove the corresponding `{{ sn }}` tag from the HTML template file.

### 3. Render the template HTML
After the translation is reviewed, you can run 
```bash
python write_translations_to_html.py --url google_sheet_url --dir ...
```

Now you have a clean HTML file with the translated content that you can publish on your website.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details


## Next Steps

This project is just a POC. The next steps are:
- [ ] Replace newspaper3k with a more robust library like Scrapy. Newspaper3k is no longer maintained and has some
  issues with some websites and articles.
- [ ] Replace using Google Sheets 